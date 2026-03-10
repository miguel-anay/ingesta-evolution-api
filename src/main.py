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
    search_router,
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

    # --- Fase 7.2: Startup tasks ---

    # 1. Run Alembic migrations
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        if settings.database_url:
            db_url = settings.database_url
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as e:
        logger.warning(f"Alembic migrations skipped: {e}")

    # 2. Verify PostgreSQL connection
    from .infrastructure.http.dependencies import get_database_manager
    db_manager = get_database_manager()
    if db_manager:
        try:
            from sqlalchemy import text
            async with db_manager.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection verified")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")

    # 3. Create S3 bucket if not exists (MinIO in dev)
    if settings.storage_backend == "s3":
        from .infrastructure.http.dependencies import get_image_storage
        storage = get_image_storage()
        try:
            await storage.ensure_storage_directory()
            logger.info(f"S3 bucket '{settings.s3_bucket_name}' ready")
        except Exception as e:
            logger.warning(f"S3 bucket setup skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    if db_manager:
        await db_manager.close()
        logger.info("Database connections closed")


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
    app.include_router(search_router, prefix="/api/v1")

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
