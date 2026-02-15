from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from text_to_sql.api.rate_limit import RateLimiter
from text_to_sql.api.router import api_router
from text_to_sql.cache.query_cache import QueryCache
from text_to_sql.config import get_settings
from text_to_sql.db.factory import create_database_backend
from text_to_sql.llm.router import create_chat_model
from text_to_sql.logging import setup_logging
from text_to_sql.mcp.tools import create_mcp_server
from text_to_sql.observability.metrics import PipelineMetrics
from text_to_sql.pipeline.graph import compile_pipeline
from text_to_sql.pipeline.orchestrator import PipelineOrchestrator
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.store.factory import create_stores


def _configure_langsmith(settings) -> None:
    """Enable LangSmith tracing if API key is configured."""
    key = settings.langsmith_api_key.get_secret_value()
    if key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    _configure_langsmith(settings)
    mcp_server = create_mcp_server()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_backend = await create_database_backend(settings)
        schema_cache = SchemaCache(ttl_seconds=settings.schema_cache_ttl_seconds)
        chat_model = create_chat_model(settings)

        # Create stores (in-memory or SQLite based on config)
        stores = await create_stores(
            settings.storage_type, settings.storage_sqlite_path
        )
        query_store = stores["query_store"]
        session_store = stores["session_store"]

        # Create checkpointer — SQLite for persistent storage, MemorySaver for in-memory
        if settings.storage_type == "sqlite":
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            checkpointer = AsyncSqliteSaver.from_conn_string(settings.storage_sqlite_path)
            await checkpointer.setup()
        else:
            checkpointer = MemorySaver()

        # Create query cache if enabled
        query_cache = (
            QueryCache(ttl_seconds=settings.cache_ttl_seconds)
            if settings.cache_enabled
            else None
        )

        # Pipeline metrics
        metrics = PipelineMetrics()

        # Rate limiter
        rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_requests_per_minute,
            window_seconds=60,
        )

        graph = compile_pipeline(
            db_backend=db_backend,
            schema_cache=schema_cache,
            chat_model=chat_model,
            checkpointer=checkpointer,
            include_tables=settings.schema_include_tables or None,
            exclude_tables=settings.schema_exclude_tables or None,
            context_max_tokens=settings.context_max_tokens,
            context_schema_budget_pct=settings.context_schema_budget_pct,
            context_history_max_messages=settings.context_history_max_messages,
            schema_selection_mode=settings.schema_selection_mode,
            schema_max_selected_tables=settings.schema_max_selected_tables,
            max_correction_attempts=settings.max_correction_attempts,
            llm_retry_attempts=settings.llm_retry_attempts,
            llm_retry_min_wait=settings.llm_retry_min_wait_seconds,
            llm_retry_max_wait=settings.llm_retry_max_wait_seconds,
            db_query_timeout_seconds=settings.db_query_timeout_seconds,
            analytical_max_plan_steps=settings.analytical_max_plan_steps,
            analytical_max_synthesis_attempts=settings.analytical_max_synthesis_attempts,
        )

        orchestrator = PipelineOrchestrator(
            graph=graph,
            query_store=query_store,
            session_store=session_store,
            query_cache=query_cache,
            database_type=db_backend.backend_type,
        )

        app.state.settings = settings
        app.state.db_backend = db_backend
        app.state.schema_cache = schema_cache
        app.state.chat_model = chat_model
        app.state.query_store = query_store
        app.state.session_store = session_store
        app.state.orchestrator = orchestrator
        app.state.metrics = metrics
        app.state.rate_limiter = rate_limiter
        mcp_server.state = app.state  # type: ignore[attr-defined]

        yield

        await db_backend.close()
        if stores.get("cleanup"):
            await stores["cleanup"]()

    mcp_http_app = mcp_server.http_app(path="/")

    @asynccontextmanager
    async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(lifespan(app))
            await stack.enter_async_context(mcp_http_app.lifespan(mcp_http_app))
            yield

    app = FastAPI(
        title="Text-to-SQL Pipeline",
        version="0.3.0",
        description="Enterprise-grade text-to-SQL with LangGraph orchestration, multi-turn conversations, SSE streaming, self-correction, caching, and observability",
        lifespan=combined_lifespan,
    )
    app.include_router(api_router, prefix="/api")
    app.mount("/mcp", mcp_http_app)

    return app


app = create_app()
