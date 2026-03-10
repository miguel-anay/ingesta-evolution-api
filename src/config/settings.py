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

    # Database
    database_url: str = "postgresql://postgres:postgres@postgres:5432/whatsapp_ingestion"

    # Evolution API Database (for LID resolution)
    evolution_database_url: str = "postgresql://postgres:postgres@postgres:5432/evolution"

    # Redis (for future use)
    redis_url: str = "redis://localhost:6379"
    redis_prefix: str = "whatsapp_ms"

    # S3 / MinIO
    s3_bucket_name: str = "whatsapp-images"
    s3_prefix: str = "images/"
    s3_region: str = "us-east-1"
    s3_endpoint_url: Optional[str] = None
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    storage_backend: str = "s3"  # "s3" or "filesystem"

    # AWS Bedrock / Titan Embeddings
    bedrock_region: str = "us-east-1"
    titan_model_id: str = "amazon.titan-embed-image-v1"
    embeddings_enabled: bool = True

    # AWS Textract OCR
    ocr_enabled: bool = True
    textract_region: str = "us-east-1"

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
