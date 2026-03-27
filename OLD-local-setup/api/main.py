"""
FastAPI application entrypoint.

- Lifespan handler initialises DB pool, Redis, Qdrant, and embedding model.
- Mounts versioned routers (v1, v2) and middleware.
- Registers exception handlers for the custom exception hierarchy.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from api import __version__
from api.config import get_settings
from api.database import close_db, init_db
from api.dependencies import (
    close_qdrant,
    close_redis,
    init_embedding_service,
    init_qdrant,
    init_redis,
)
from api.exceptions import AppException, RateLimitError
# Azure enhancements (optional - install from azure-deployment/)
# from api.services.xml_validator import validate_mulesoft_xml
# from api.telemetry import init_telemetry
from api.websocket.events import close_publisher_redis
from api.websocket.manager import connection_manager

logger = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan: startup and shutdown hooks.

    Startup:
      1. Initialise async DB engine and create tables (dev convenience).
      2. Connect Redis pool.
      3. Connect Qdrant client.
      4. Load sentence-transformers embedding model (if RAG enabled).

    Shutdown:
      1. Close Qdrant.
      2. Close Redis.
      3. Dispose DB engine.
    """
    settings = get_settings()

    logger.info(
        "startup.begin",
        environment=settings.environment.value,
        version=__version__,
    )

    # -- Startup -------------------------------------------------
    # init_telemetry(settings)  # Azure enhancement - enable after integration
    # logger.info("startup.telemetry_ready")

    await init_db()
    logger.info("startup.db_ready")

    await init_redis(settings)
    logger.info("startup.redis_ready")

    await init_qdrant(settings)
    logger.info("startup.qdrant_ready")

    if settings.rag.enabled:
        init_embedding_service(settings)
        logger.info(
            "startup.embedding_model_loaded",
            model=settings.rag.embedding_model,
        )

    # Start WebSocket heartbeat loop
    connection_manager.start_heartbeat()
    logger.info("startup.websocket_heartbeat_started")

    logger.info("startup.complete")

    yield

    # -- Shutdown ------------------------------------------------
    logger.info("shutdown.begin")
    await connection_manager.shutdown()
    await close_publisher_redis()
    await close_qdrant()
    await close_redis()
    await close_db()
    logger.info("shutdown.complete")


# ── Application Factory ──────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="MuleSoft-to-SpringBoot Migration API",
        description=(
            "Agentic AI platform that converts MuleSoft integration "
            "applications into Spring Boot microservices using LLMs, "
            "RAG-augmented knowledge, and multi-agent orchestration."
        ),
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else "/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "health",
                "description": "Health-check and readiness probes.",
            },
            {
                "name": "migrations",
                "description": "Upload MuleSoft projects and trigger migration.",
            },
            {
                "name": "projects",
                "description": "CRUD operations on migration projects.",
            },
            {
                "name": "agents",
                "description": "Agent orchestration and status.",
            },
            {
                "name": "rag",
                "description": "RAG knowledge-base management.",
            },
            {
                "name": "websocket",
                "description": "Real-time progress streaming.",
            },
            {
                "name": "auth",
                "description": "Authentication and user management.",
            },
        ],
    )

    # ── Middleware (order matters: first added = outermost) ─────
    #
    # Starlette processes middleware in reverse-add order for requests,
    # so add outermost first:
    #   Request flow:  SecurityHeaders → CORS → GZip → TrustedHost
    #                  → ErrorHandler → CorrelationId → RateLimit
    #                  → RequestLogging → handler

    from api.middleware import (
        CorrelationIdMiddleware,
        ErrorHandlerMiddleware,
        RateLimitMiddleware,
        RequestLoggingMiddleware,
    )

    # SecurityHeadersMiddleware - enable after azure-deployment integration
    # from api.middleware import SecurityHeadersMiddleware
    # app.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.security.trusted_hosts_list,
    )

    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception Handlers ─────────────────────────────────────

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        headers = {}
        if isinstance(exc, RateLimitError) and exc.context.get("retry_after_seconds"):
            headers["Retry-After"] = str(exc.context["retry_after_seconds"])
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "detail": "An unexpected internal error occurred.",
            },
        )

    # ── Prometheus metrics (optional) ──────────────────────────
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/health", "/readiness", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except ImportError:
        logger.warning("prometheus_instrumentator_not_available")

    # ── Health / Readiness ─────────────────────────────────────

    @app.get("/health", tags=["health"], summary="Liveness probe")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/readiness", tags=["health"], summary="Readiness probe")
    async def readiness():
        """Deep health check: verify DB, Redis, and Qdrant."""
        checks: dict[str, str] = {}
        overall = True

        # DB
        try:
            from sqlalchemy import text as sa_text

            from api.database import _get_engine

            engine = _get_engine()
            async with engine.connect() as conn:
                await conn.execute(sa_text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"
            overall = False

        # Redis
        try:
            from api.dependencies import _redis_pool

            if _redis_pool is not None:
                await _redis_pool.ping()
                checks["redis"] = "ok"
            else:
                checks["redis"] = "not initialized"
                overall = False
        except Exception as e:
            checks["redis"] = f"error: {e}"
            overall = False

        # Qdrant
        try:
            from api.dependencies import _qdrant_client

            if _qdrant_client is not None:
                info = await _qdrant_client.get_collections()
                checks["qdrant"] = "ok"
            else:
                checks["qdrant"] = "not initialized"
                overall = False
        except Exception as e:
            checks["qdrant"] = f"error: {e}"
            overall = False

        status_code = 200 if overall else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if overall else "degraded",
                "version": __version__,
                "checks": checks,
            },
        )

    # ── Mount versioned API routers ────────────────────────────
    _mount_routers(app)

    # ── Mount WebSocket routers ───────────────────────────────
    try:
        from api.websocket.migration_ws import router as migration_ws_router
        from api.websocket.build_ws import router as build_ws_router

        app.include_router(migration_ws_router, tags=["websocket"])
        app.include_router(build_ws_router, tags=["websocket"])
        logger.info("router.websocket_mounted")
    except Exception as exc:
        logger.warning("router.websocket_mount_error", error=str(exc))

    return app


def _mount_routers(app: FastAPI) -> None:
    """
    Dynamically import and mount route modules.

    Each router module is expected to expose an ``router`` attribute
    (an ``APIRouter`` instance).  Missing modules are logged as
    warnings and skipped so the app can boot partially.
    """
    router_specs = [
        # ── V1 (legacy backward-compatible) ────────────────────
        ("api.routers.v1.migrate", "/api/v1", ["migrations"]),
        ("api.routers.v1.migrations", "/api/v1", ["migrations"]),
        ("api.routers.v1.projects", "/api/v1", ["projects"]),
        ("api.routers.v1.agents", "/api/v1", ["agents"]),
        ("api.routers.v1.rag", "/api/v1", ["rag"]),
        ("api.routers.v1.auth", "/api/v1", ["auth"]),
        # ── V2 (current async API) ────────────────────────────
        ("api.routers.v2.migrations", "/api/v2", ["migrations"]),
        ("api.routers.v2.builds", "/api/v2", ["migrations"]),
        ("api.routers.v2.rag", "/api/v2", ["rag"]),
        ("api.routers.v2.github", "/api/v2", ["migrations"]),
        ("api.routers.v2.projects", "/api/v2", ["projects"]),
    ]

    for module_path, prefix, tags in router_specs:
        try:
            import importlib

            mod = importlib.import_module(module_path)
            router = getattr(mod, "router", None)
            if router is not None:
                app.include_router(router, prefix=prefix, tags=tags)
                logger.info("router.mounted", module=module_path, prefix=prefix)
            else:
                logger.debug("router.skipped_no_attr", module=module_path)
        except (ImportError, ModuleNotFoundError):
            logger.debug("router.not_found", module=module_path)
        except Exception as exc:
            logger.warning("router.mount_error", module=module_path, error=str(exc))


# ── Module-level app instance (for uvicorn / gunicorn) ────────────

app = create_app()
