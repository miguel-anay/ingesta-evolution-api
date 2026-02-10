"""
Application Settings

Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    Environment variable names are uppercase versions of the field names.
    """

    # Application
    app_name: str = "WhatsApp Integration Microservice"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 3000

    # Evolution API
    evolution_api_url: str = "http://localhost:8080"
    evolution_api_key: str = "SUMlung9541"
    evolution_api_timeout: float = 30.0

    # Database (for future use)
    database_url: Optional[str] = None

    # Redis (for future use)
    redis_url: str = "redis://localhost:6379"
    redis_prefix: str = "whatsapp_ms"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "evolution_exchange"

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # CORS
    cors_origins: str = "*"  # Comma-separated list of origins

    # Webhook
    webhook_base_url: Optional[str] = None  # Base URL for registering webhooks

    # Image Ingestion Settings (US-ING-001)
    ingestion_data_directory: str = "/data"
    ingestion_images_subdirectory: str = "images"
    ingestion_metadata_subdirectory: str = "metadata"
    ingestion_metadata_filename: str = "images.csv"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def ingestion_images_directory(self) -> str:
        """Get full path to images storage directory."""
        return os.path.join(
            self.ingestion_data_directory,
            self.ingestion_images_subdirectory,
        )

    @property
    def ingestion_metadata_file(self) -> str:
        """Get full path to metadata CSV file."""
        return os.path.join(
            self.ingestion_data_directory,
            self.ingestion_metadata_subdirectory,
            self.ingestion_metadata_filename,
        )

    @property
    def cors_origins_list(self) -> list:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() in ("development", "dev", "local")

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ("production", "prod")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
