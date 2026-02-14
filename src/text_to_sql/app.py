from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from text_to_sql.api.router import api_router
from text_to_sql.config import get_settings
from text_to_sql.db.factory import create_database_backend
from text_to_sql.llm.router import create_chat_model
from text_to_sql.logging import setup_logging
from text_to_sql.mcp.tools import create_mcp_server
from text_to_sql.pipeline.graph import compile_pipeline
from text_to_sql.pipeline.orchestrator import PipelineOrchestrator
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.store.memory import InMemoryQueryStore


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    # Create MCP server
    mcp_server = create_mcp_server()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup: initialize shared resources
        db_backend = await create_database_backend(settings)
        schema_cache = SchemaCache(ttl_seconds=settings.schema_cache_ttl_seconds)
        chat_model = create_chat_model(settings)
        query_store = InMemoryQueryStore()

        # Build LangGraph pipeline with MemorySaver for interrupt/resume
        checkpointer = MemorySaver()
        graph = compile_pipeline(
            db_backend=db_backend,
            schema_cache=schema_cache,
            chat_model=chat_model,
            checkpointer=checkpointer,
        )

        orchestrator = PipelineOrchestrator(
            graph=graph,
            query_store=query_store,
        )

        # Attach to app.state for REST endpoint dependency injection
        app.state.settings = settings
        app.state.db_backend = db_backend
        app.state.schema_cache = schema_cache
        app.state.chat_model = chat_model
        app.state.query_store = query_store
        app.state.orchestrator = orchestrator

        # Inject into MCP server state for tool access
        mcp_server.state = app.state  # type: ignore[attr-defined]

        yield

        # Shutdown: cleanup
        await db_backend.close()

    app = FastAPI(
        title="Text-to-SQL Pipeline",
        version="0.1.0",
        description="Multi-provider text-to-SQL with LangGraph orchestration and human-in-the-loop approval",
        lifespan=lifespan,
    )

    # Mount REST API
    app.include_router(api_router, prefix="/api")

    # Mount MCP server as ASGI sub-app
    mcp_app = mcp_server.sse_app()
    app.mount("/mcp", mcp_app)

    return app


app = create_app()
