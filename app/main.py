"""Main FastAPI application entry point."""

from pathlib import Path

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api.v1 import dashboards, monitors, metrics
from app.db.database import init_db, close_db

# Import adapters to register them with AdapterFactory
from app.adapters import (  # noqa: F401
    datadog,
    prometheus,
    grafana,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("Starting Metrics Explorer Service", env=settings.app_env)
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Metrics Explorer Service")
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title="Metrics Explorer Service",
    description=(
        "A unified REST API for exploring dashboards, monitors, and metrics "
        "from multiple providers (Datadog, Prometheus, Grafana) using "
        "OpenTelemetry semantic conventions."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
        },
    )


# Include API routers
app.include_router(
    dashboards.router,
    prefix="/api/v1/dashboards",
    tags=["dashboards"],
)
app.include_router(
    monitors.router,
    prefix="/api/v1/monitors",
    tags=["monitors"],
)
app.include_router(
    metrics.router,
    prefix="/api/v1/metrics",
    tags=["metrics"],
)
# Organization management router (for setting up providers)
from app.api.v1 import organizations
app.include_router(
    organizations.router,
    prefix="/api/v1/organizations",
    tags=["organizations"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/")
async def root():
    """Root redirects to API tester UI in development."""
    if settings.is_development:
        return RedirectResponse(url="/ui/")
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "description": "Metrics Explorer Service - Unified metrics exploration API",
        "docs": "/docs" if settings.is_development else None,
    }


# Serve frontend at /ui/ (React build in frontend/dist, or static frontend folder)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_frontend_path = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dist.exists():
    app.mount("/ui", StaticFiles(directory=str(_frontend_dist), html=True), name="ui")
elif _frontend_path.exists():
    app.mount("/ui", StaticFiles(directory=str(_frontend_path), html=True), name="ui")
