"""
FastAPI Dependencies

Dependency injection configuration for FastAPI routes.
This is the COMPOSITION ROOT where we wire everything together.

IMPORTANT: This is the ONLY place where concrete implementations
are instantiated and injected into use cases.
"""

import logging
from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends

from ...application.messaging.use_cases import (
    SendTextMessageUseCase,
    SendMediaMessageUseCase,
    GetMessageStatusUseCase,
    HandleMessageWebhookUseCase,
)
from ...application.instances.use_cases import (
    CreateInstanceUseCase,
    ConnectInstanceUseCase,
    GetInstanceStatusUseCase,
    ListInstancesUseCase,
    DeleteInstanceUseCase,
)
from ...application.ingestion.use_cases import (
    IngestImagesUseCase,
    IngestChatImagesUseCase,
    IngestStatusImagesUseCase,
)
from ..integrations.evolution_api import (
    EvolutionApiClient,
    EvolutionApiWhatsAppAdapter,
    EvolutionApiInstanceAdapter,
    EvolutionApiImageSourceAdapter,
)
from ..persistence.repositories import (
    InMemoryMessageRepository,
    InMemoryInstanceRepository,
    CsvMetadataRepository,
)
from ..storage import FileSystemImageStorageAdapter
from ..messaging.rabbitmq import InMemoryEventPublisher
from ...config.settings import get_settings, Settings


logger = logging.getLogger(__name__)


# --- Singleton instances ---
# These are created once and reused across requests


@lru_cache()
def get_evolution_api_client() -> EvolutionApiClient:
    """Get Evolution API client singleton."""
    settings = get_settings()
    return EvolutionApiClient(
        base_url=settings.evolution_api_url,
        api_key=settings.evolution_api_key,
        timeout=settings.evolution_api_timeout,
    )


@lru_cache()
def get_message_repository() -> InMemoryMessageRepository:
    """Get message repository singleton."""
    return InMemoryMessageRepository()


@lru_cache()
def get_event_publisher() -> InMemoryEventPublisher:
    """Get event publisher singleton (for messaging use cases)."""
    return InMemoryEventPublisher()


@lru_cache()
def get_instance_repository() -> InMemoryInstanceRepository:
    """Get instance repository singleton."""
    return InMemoryInstanceRepository()


# --- New infrastructure singletons ---


@lru_cache()
def get_database_manager():
    """Get database manager singleton."""
    settings = get_settings()
    if not settings.database_url:
        return None
    from ..persistence.database import DatabaseManager
    return DatabaseManager(settings.database_url)


@lru_cache()
def get_vectorizer_adapter():
    """Get Titan vectorizer adapter singleton (loaded once)."""
    settings = get_settings()
    if not settings.embeddings_enabled:
        return None
    try:
        from ..vectorization.titan_adapter import TitanVectorizerAdapter
        return TitanVectorizerAdapter(
            region=settings.bedrock_region,
            model_id=settings.titan_model_id,
        )
    except Exception as e:
        logger.warning(f"Titan vectorizer not available: {e}")
        return None


@lru_cache()
def get_ocr_adapter():
    """Get AWS Textract OCR adapter singleton."""
    settings = get_settings()
    if not settings.ocr_enabled:
        return None
    try:
        from ..ocr.textract_adapter import TextractOcrAdapter
        return TextractOcrAdapter(region=settings.textract_region)
    except Exception as e:
        logger.warning(f"Textract OCR not available: {e}")
        return None


# --- Adapters ---


def get_whatsapp_adapter(
    client: Annotated[EvolutionApiClient, Depends(get_evolution_api_client)],
) -> EvolutionApiWhatsAppAdapter:
    """Get WhatsApp adapter."""
    return EvolutionApiWhatsAppAdapter(client)


def get_instance_adapter(
    client: Annotated[EvolutionApiClient, Depends(get_evolution_api_client)],
) -> EvolutionApiInstanceAdapter:
    """Get instance adapter."""
    return EvolutionApiInstanceAdapter(client)


# --- Messaging Use Cases ---


def get_send_text_use_case(
    whatsapp_adapter: Annotated[EvolutionApiWhatsAppAdapter, Depends(get_whatsapp_adapter)],
    message_repository: Annotated[InMemoryMessageRepository, Depends(get_message_repository)],
    event_publisher: Annotated[InMemoryEventPublisher, Depends(get_event_publisher)],
) -> SendTextMessageUseCase:
    """Get SendTextMessageUseCase with injected dependencies."""
    return SendTextMessageUseCase(
        whatsapp_gateway=whatsapp_adapter,
        message_repository=message_repository,
        event_publisher=event_publisher,
    )


def get_send_media_use_case(
    whatsapp_adapter: Annotated[EvolutionApiWhatsAppAdapter, Depends(get_whatsapp_adapter)],
    message_repository: Annotated[InMemoryMessageRepository, Depends(get_message_repository)],
    event_publisher: Annotated[InMemoryEventPublisher, Depends(get_event_publisher)],
) -> SendMediaMessageUseCase:
    """Get SendMediaMessageUseCase with injected dependencies."""
    return SendMediaMessageUseCase(
        whatsapp_gateway=whatsapp_adapter,
        message_repository=message_repository,
        event_publisher=event_publisher,
    )


def get_message_status_use_case(
    message_repository: Annotated[InMemoryMessageRepository, Depends(get_message_repository)],
) -> GetMessageStatusUseCase:
    """Get GetMessageStatusUseCase with injected dependencies."""
    return GetMessageStatusUseCase(
        message_repository=message_repository,
    )


def get_webhook_handler_use_case(
    message_repository: Annotated[InMemoryMessageRepository, Depends(get_message_repository)],
    event_publisher: Annotated[InMemoryEventPublisher, Depends(get_event_publisher)],
) -> HandleMessageWebhookUseCase:
    """Get HandleMessageWebhookUseCase with injected dependencies."""
    return HandleMessageWebhookUseCase(
        message_repository=message_repository,
        event_publisher=event_publisher,
    )


# --- Instance Use Cases ---


def get_create_instance_use_case(
    instance_adapter: Annotated[EvolutionApiInstanceAdapter, Depends(get_instance_adapter)],
    instance_repository: Annotated[InMemoryInstanceRepository, Depends(get_instance_repository)],
) -> CreateInstanceUseCase:
    """Get CreateInstanceUseCase with injected dependencies."""
    return CreateInstanceUseCase(
        instance_gateway=instance_adapter,
        instance_repository=instance_repository,
    )


def get_connect_instance_use_case(
    instance_adapter: Annotated[EvolutionApiInstanceAdapter, Depends(get_instance_adapter)],
    instance_repository: Annotated[InMemoryInstanceRepository, Depends(get_instance_repository)],
) -> ConnectInstanceUseCase:
    """Get ConnectInstanceUseCase with injected dependencies."""
    return ConnectInstanceUseCase(
        instance_gateway=instance_adapter,
        instance_repository=instance_repository,
    )


def get_instance_status_use_case(
    instance_adapter: Annotated[EvolutionApiInstanceAdapter, Depends(get_instance_adapter)],
    instance_repository: Annotated[InMemoryInstanceRepository, Depends(get_instance_repository)],
) -> GetInstanceStatusUseCase:
    """Get GetInstanceStatusUseCase with injected dependencies."""
    return GetInstanceStatusUseCase(
        instance_gateway=instance_adapter,
        instance_repository=instance_repository,
    )


def get_list_instances_use_case(
    instance_adapter: Annotated[EvolutionApiInstanceAdapter, Depends(get_instance_adapter)],
    instance_repository: Annotated[InMemoryInstanceRepository, Depends(get_instance_repository)],
) -> ListInstancesUseCase:
    """Get ListInstancesUseCase with injected dependencies."""
    return ListInstancesUseCase(
        instance_gateway=instance_adapter,
        instance_repository=instance_repository,
    )


def get_delete_instance_use_case(
    instance_adapter: Annotated[EvolutionApiInstanceAdapter, Depends(get_instance_adapter)],
    instance_repository: Annotated[InMemoryInstanceRepository, Depends(get_instance_repository)],
) -> DeleteInstanceUseCase:
    """Get DeleteInstanceUseCase with injected dependencies."""
    return DeleteInstanceUseCase(
        instance_gateway=instance_adapter,
        instance_repository=instance_repository,
    )


# --- Image Ingestion Singletons ---


@lru_cache()
def get_image_storage():
    """Get image storage adapter singleton (S3 or filesystem based on config)."""
    settings = get_settings()
    if settings.storage_backend == "s3":
        from ..storage.s3_image_storage import S3ImageStorageAdapter
        return S3ImageStorageAdapter(
            bucket_name=settings.s3_bucket_name,
            prefix=settings.s3_prefix,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
    return FileSystemImageStorageAdapter(
        base_directory=settings.ingestion_images_directory,
    )


@lru_cache()
def get_metadata_repository():
    """Get metadata repository singleton (Postgres or CSV based on config)."""
    settings = get_settings()
    db_manager = get_database_manager()
    if db_manager:
        from ..persistence.repositories.postgres_metadata_repository import PostgresMetadataRepository
        return PostgresMetadataRepository(db_manager)
    return CsvMetadataRepository(
        csv_file_path=settings.ingestion_metadata_file,
        images_base_directory=settings.ingestion_images_directory,
    )


def get_image_source(
    client: Annotated[EvolutionApiClient, Depends(get_evolution_api_client)],
) -> EvolutionApiImageSourceAdapter:
    """Get Evolution API image source adapter."""
    settings = get_settings()
    return EvolutionApiImageSourceAdapter(
        client=client,
        evolution_db_url=settings.evolution_database_url,
    )


# --- Image Ingestion Use Cases ---


def get_ingest_images_use_case(
    image_source: Annotated[EvolutionApiImageSourceAdapter, Depends(get_image_source)],
) -> IngestImagesUseCase:
    """Get IngestImagesUseCase with injected dependencies."""
    return IngestImagesUseCase(
        image_source=image_source,
        image_storage=get_image_storage(),
        metadata_repository=get_metadata_repository(),
    )


def get_ingest_chat_images_use_case(
    image_source: Annotated[EvolutionApiImageSourceAdapter, Depends(get_image_source)],
) -> IngestChatImagesUseCase:
    """Get IngestChatImagesUseCase with injected dependencies."""
    return IngestChatImagesUseCase(
        image_source=image_source,
        image_storage=get_image_storage(),
        metadata_repository=get_metadata_repository(),
    )


def get_ingest_status_images_use_case(
    image_source: Annotated[EvolutionApiImageSourceAdapter, Depends(get_image_source)],
) -> IngestStatusImagesUseCase:
    """Get IngestStatusImagesUseCase with injected dependencies."""
    return IngestStatusImagesUseCase(
        image_source=image_source,
        image_storage=get_image_storage(),
        metadata_repository=get_metadata_repository(),
    )
