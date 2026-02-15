from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

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
    mcp_server = create_mcp_server()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_backend = await create_database_backend(settings)
        schema_cache = SchemaCache(ttl_seconds=settings.schema_cache_ttl_seconds)
        chat_model = create_chat_model(settings)
        query_store = InMemoryQueryStore()

        graph = compile_pipeline(
            db_backend=db_backend,
            schema_cache=schema_cache,
            chat_model=chat_model,
            checkpointer=MemorySaver(),
        )

        orchestrator = PipelineOrchestrator(graph=graph, query_store=query_store)

        app.state.settings = settings
        app.state.db_backend = db_backend
        app.state.schema_cache = schema_cache
        app.state.chat_model = chat_model
        app.state.query_store = query_store
        app.state.orchestrator = orchestrator
        mcp_server.state = app.state  # type: ignore[attr-defined]

        yield

        await db_backend.close()

    mcp_http_app = mcp_server.http_app(path="/")

    @asynccontextmanager
    async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(lifespan(app))
            await stack.enter_async_context(mcp_http_app.lifespan(mcp_http_app))
            yield

    app = FastAPI(
        title="Text-to-SQL Pipeline",
        version="0.1.0",
        description="Multi-provider text-to-SQL with LangGraph orchestration and human-in-the-loop approval",
        lifespan=combined_lifespan,
    )
    app.include_router(api_router, prefix="/api")
    app.mount("/mcp", mcp_http_app)

    return app


app = create_app()
