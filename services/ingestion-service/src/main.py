from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import structlog

from src.config.settings import settings
from src.api.routes.health import router as health_router
from src.api.routes.ingest import router as ingest_router
from src.api.routes.metadata import router as metadata_router
from src.db.session import init_db, close_db
from src.config.rabbitmq import close as close_rabbitmq
from src.events.consumer import setup_consumers

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan event handler."""
    # Startup
    await init_db()
    await setup_consumers()

    yield

    # Shutdown
    await close_db()
    await close_rabbitmq()


# Create FastAPI app
app = FastAPI(
    title="Poliwise Ingestion Service",
    description="Document extraction, chunking, and embedding service",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGIN",
            "http://localhost:3000,http://localhost:3001",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Internal-API-Key"],
)

# Register routes
app.include_router(health_router)
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(metadata_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ingestion-service",
        "version": "0.1.0",
        "status": "running",
    }
