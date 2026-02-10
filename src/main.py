"""
Application Entry Point

FastAPI application setup and configuration.
This is the composition root where all pieces come together.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.settings import get_settings
from .config.logging_config import setup_logging
from .infrastructure.http.routes import (
    messaging_router,
    instance_router,
    health_router,
    ingestion_router,
)
from .infrastructure.http.webhooks import webhook_router
from .infrastructure.http.middleware import (
    LoggingMiddleware,
    setup_exception_handlers,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Manages startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    setup_logging(settings)

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Evolution API URL: {settings.evolution_api_url}")

    yield

    # Shutdown
    logger.info("Shutting down application...")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        WhatsApp Integration Microservice

        A clean architecture microservice for WhatsApp messaging via Evolution API.

        ## Features

        - Send text and media messages via WhatsApp
        - Manage WhatsApp instances (create, connect, disconnect)
        - Receive webhooks for message status updates
        - **Image Ingestion**: Download and store images from chats and user status
        - Clean hexagonal architecture

        ## Image Ingestion (US-ING-001)

        The service provides idempotent image ingestion from Evolution API:
        - Downloads images from chat messages and user status (stories)
        - Stores images with sequential filenames (1.jpg, 2.jpg, etc.)
        - Records metadata in CSV file for tracking
        - Deduplicates by message ID and image hash

        ## Architecture

        - **Domain Layer**: Business entities and rules
        - **Application Layer**: Use cases and port definitions
        - **Infrastructure Layer**: Adapters, HTTP, integrations
        """,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(LoggingMiddleware)

    # Setup exception handlers
    setup_exception_handlers(app)

    # Register routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(instance_router, prefix="/api/v1")
    app.include_router(messaging_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")
    app.include_router(ingestion_router, prefix="/api/v1")

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
