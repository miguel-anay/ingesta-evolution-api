"""
FastAPI Dependencies

Dependency injection configuration for FastAPI routes.
This is the COMPOSITION ROOT where we wire everything together.

IMPORTANT: This is the ONLY place where concrete implementations
are instantiated and injected into use cases.
"""

from functools import lru_cache
from typing import Annotated

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
    # TODO: Replace with PostgresMessageRepository for production
    return InMemoryMessageRepository()


@lru_cache()
def get_instance_repository() -> InMemoryInstanceRepository:
    """Get instance repository singleton."""
    # TODO: Replace with PostgresInstanceRepository for production
    return InMemoryInstanceRepository()


@lru_cache()
def get_event_publisher() -> InMemoryEventPublisher:
    """Get event publisher singleton."""
    # TODO: Replace with RabbitMQEventPublisher for production
    return InMemoryEventPublisher()


# --- Adapters ---
# Created from singleton dependencies


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
def get_image_storage() -> FileSystemImageStorageAdapter:
    """Get image storage adapter singleton."""
    settings = get_settings()
    return FileSystemImageStorageAdapter(
        base_directory=settings.ingestion_images_directory,
    )


@lru_cache()
def get_metadata_repository() -> CsvMetadataRepository:
    """Get CSV metadata repository singleton."""
    settings = get_settings()
    return CsvMetadataRepository(
        csv_file_path=settings.ingestion_metadata_file,
        images_base_directory=settings.ingestion_images_directory,
    )


def get_image_source(
    client: Annotated[EvolutionApiClient, Depends(get_evolution_api_client)],
) -> EvolutionApiImageSourceAdapter:
    """Get Evolution API image source adapter."""
    return EvolutionApiImageSourceAdapter(client)


# --- Image Ingestion Use Cases ---


def get_ingest_images_use_case(
    image_source: Annotated[EvolutionApiImageSourceAdapter, Depends(get_image_source)],
    image_storage: Annotated[FileSystemImageStorageAdapter, Depends(get_image_storage)],
    metadata_repository: Annotated[CsvMetadataRepository, Depends(get_metadata_repository)],
) -> IngestImagesUseCase:
    """Get IngestImagesUseCase with injected dependencies."""
    return IngestImagesUseCase(
        image_source=image_source,
        image_storage=image_storage,
        metadata_repository=metadata_repository,
    )


def get_ingest_chat_images_use_case(
    image_source: Annotated[EvolutionApiImageSourceAdapter, Depends(get_image_source)],
    image_storage: Annotated[FileSystemImageStorageAdapter, Depends(get_image_storage)],
    metadata_repository: Annotated[CsvMetadataRepository, Depends(get_metadata_repository)],
) -> IngestChatImagesUseCase:
    """Get IngestChatImagesUseCase with injected dependencies."""
    return IngestChatImagesUseCase(
        image_source=image_source,
        image_storage=image_storage,
        metadata_repository=metadata_repository,
    )


def get_ingest_status_images_use_case(
    image_source: Annotated[EvolutionApiImageSourceAdapter, Depends(get_image_source)],
    image_storage: Annotated[FileSystemImageStorageAdapter, Depends(get_image_storage)],
    metadata_repository: Annotated[CsvMetadataRepository, Depends(get_metadata_repository)],
) -> IngestStatusImagesUseCase:
    """Get IngestStatusImagesUseCase with injected dependencies."""
    return IngestStatusImagesUseCase(
        image_source=image_source,
        image_storage=image_storage,
        metadata_repository=metadata_repository,
    )
