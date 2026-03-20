"""
HirePilot — FastAPI Application Factory

This is the main entry point for the backend server.
Run with: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    setup_logging()
    logger.info("HirePilot starting up", env=settings.app_env)
    yield
    logger.info("HirePilot shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered job search automation platform",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS Middleware ──────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API Routes ───────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # ── Health Check ─────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "service": settings.app_name}

    # ── Global Exception Handlers ───────────────────────────────
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        origin = request.headers.get("origin")
        headers = {}
        if origin and origin in settings.cors_origins:
            headers["access-control-allow-origin"] = origin
            headers["access-control-allow-credentials"] = "true"
            headers["vary"] = "Origin"
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
            headers=headers,
        )

    return app


# Create the app instance
app = create_app()
