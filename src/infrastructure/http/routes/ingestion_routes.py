"""
Image Ingestion HTTP Routes

FastAPI routes for triggering image ingestion from Evolution API.
This is the INBOUND adapter (presentation layer).

Per PROJECT_SPECS.md, ingestion requires:
- numero_celular: User phone number to ingest images from
- instancia: Evolution API instance identifier

Both parameters are REQUIRED. The service returns an error if any is missing.
"""

import logging
from typing import Annotated, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ....application.ingestion.use_cases import (
    IngestImagesUseCase,
    IngestChatImagesUseCase,
    IngestStatusImagesUseCase,
)
from ....application.ingestion.dto import (
    IngestImagesRequest,
    IngestImagesResponse,
    IngestionStatusResponse,
    ImageMetadataDTO,
)
from ....domain.ingestion.value_objects import SourceType
from ....domain.ingestion.exceptions import MissingRequiredParameterError
from ..dependencies import (
    get_ingest_images_use_case,
    get_ingest_chat_images_use_case,
    get_ingest_status_images_use_case,
    get_metadata_repository,
    get_image_storage,
    get_image_source,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["Image Ingestion"])


# --- Request/Response Schemas ---


class IngestRequestSchema(BaseModel):
    """
    Schema for ingestion request body.

    Per PROJECT_SPECS.md, both numero_celular and instancia are REQUIRED.
    The ingestion process will NOT start if any parameter is missing.
    """

    numero_celular: str = Field(
        ...,
        description="User phone number to ingest images from (required)",
        min_length=10,
        max_length=15,
        examples=["51999999999"],
    )
    instancia: str = Field(
        ...,
        description="Evolution API instance identifier (required)",
        min_length=1,
        max_length=100,
        examples=["instance_01"],
    )
    source_type: Optional[str] = Field(
        None,
        description="Type of source: 'chat', 'estado', or null for both",
        examples=["chat", "estado"],
    )
    limit: Optional[int] = Field(
        None,
        description="Maximum number of images to process (null for unlimited)",
        ge=1,
        le=10000,
    )


class IngestResponseSchema(BaseModel):
    """
    Schema for ingestion response.

    Contains summary and details of the ingestion operation.
    Note: downloaded_images contains the new metadata structure with
    numero_celular and instancia fields.
    """

    success: bool
    message: str
    total_processed: int
    new_images_downloaded: int
    duplicates_skipped: int
    errors_count: int
    errors: List[str] = []
    downloaded_images: List[ImageMetadataDTO] = []
    execution_time_seconds: float
    timestamp: str


class IngestionStatusSchema(BaseModel):
    """Schema for ingestion status response."""

    is_healthy: bool
    total_images_ingested: int
    storage_directory: str
    metadata_file: str
    last_sequential_id: int
    available_instances: List[str]
    message: str = ""


class MetadataListSchema(BaseModel):
    """Schema for metadata list response."""

    total: int
    items: List[ImageMetadataDTO]


# --- Route Handlers ---


@router.post(
    "/ingest",
    response_model=IngestResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Ingest images from Evolution API",
    description="""
    Trigger image ingestion from the specified WhatsApp instance for a specific phone number.

    **REQUIRED PARAMETERS** (per PROJECT_SPECS.md):
    - `numero_celular`: User phone number to filter images from
    - `instancia`: Evolution API instance identifier

    The ingestion process will NOT start if any parameter is missing.

    This endpoint:
    - Downloads images from chat messages and/or user status FOR THE SPECIFIED PHONE NUMBER ONLY
    - Stores images locally with sequential filenames (1.jpg, 2.jpg, etc.)
    - Records metadata in CSV file (including numero_celular and instancia)
    - Is fully idempotent - safe to call multiple times

    **Idempotency**: Images that have already been processed (by message ID or
    content hash) will be skipped automatically.
    """,
)
async def ingest_images(
    request: IngestRequestSchema,
    use_case: Annotated[IngestImagesUseCase, Depends(get_ingest_images_use_case)],
) -> IngestResponseSchema:
    """
    Ingest images from Evolution API for a specific phone number.

    Downloads and stores images from chat messages and/or user status
    filtered by the provided phone number.
    """
    logger.info(
        f"Ingestion request received",
        extra={
            "instance": request.instancia,
            "phone_number": request.numero_celular,
            "source_type": request.source_type,
            "limit": request.limit,
        },
    )

    try:
        # Parse source type
        source_type = None
        if request.source_type:
            try:
                source_type = SourceType.from_string(request.source_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid source_type: {request.source_type}. Must be 'chat' or 'estado'.",
                )

        # Build domain request with required parameters
        domain_request = IngestImagesRequest(
            numero_celular=request.numero_celular,
            instancia=request.instancia,
            source_type=source_type,
            limit=request.limit,
        )

        # Execute use case
        response = await use_case.execute(domain_request)

        return IngestResponseSchema(
            success=response.success,
            message=response.message,
            total_processed=response.total_processed,
            new_images_downloaded=response.new_images_downloaded,
            duplicates_skipped=response.duplicates_skipped,
            errors_count=response.errors_count,
            errors=response.errors,
            downloaded_images=response.downloaded_images,
            execution_time_seconds=response.execution_time_seconds,
            timestamp=response.timestamp,
        )

    except HTTPException:
        raise
    except MissingRequiredParameterError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.post(
    "/ingest/chat",
    response_model=IngestResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Ingest images from chat messages only",
    description="""
    Convenience endpoint that ingests only chat message images for a specific phone number.

    **REQUIRED PARAMETERS**:
    - `numero_celular`: User phone number to filter images from
    - `instancia`: WhatsApp instance name
    """,
)
async def ingest_chat_images(
    numero_celular: str = Query(
        ...,
        description="User phone number to filter images from (required)",
        min_length=10,
    ),
    instancia: str = Query(
        ...,
        description="WhatsApp instance name (required)",
        min_length=1,
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum images to process",
        ge=1,
    ),
    use_case: IngestChatImagesUseCase = Depends(get_ingest_chat_images_use_case),
) -> IngestResponseSchema:
    """Ingest images from chat messages only for a specific phone number."""
    logger.info(
        f"Chat ingestion request: instance={instancia}, "
        f"phone={numero_celular}, limit={limit}"
    )

    try:
        response = await use_case.execute(
            numero_celular=numero_celular,
            instancia=instancia,
            limit=limit,
        )

        return IngestResponseSchema(
            success=response.success,
            message=response.message,
            total_processed=response.total_processed,
            new_images_downloaded=response.new_images_downloaded,
            duplicates_skipped=response.duplicates_skipped,
            errors_count=response.errors_count,
            errors=response.errors,
            downloaded_images=response.downloaded_images,
            execution_time_seconds=response.execution_time_seconds,
            timestamp=response.timestamp,
        )

    except MissingRequiredParameterError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Chat ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/ingest/status",
    response_model=IngestResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Ingest images from user status only",
    description="""
    Convenience endpoint that ingests only status (stories) images for a specific phone number.

    **REQUIRED PARAMETERS**:
    - `numero_celular`: User phone number to filter status from
    - `instancia`: WhatsApp instance name
    """,
)
async def ingest_status_images(
    numero_celular: str = Query(
        ...,
        description="User phone number to filter status from (required)",
        min_length=10,
    ),
    instancia: str = Query(
        ...,
        description="WhatsApp instance name (required)",
        min_length=1,
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum images to process",
        ge=1,
    ),
    use_case: IngestStatusImagesUseCase = Depends(get_ingest_status_images_use_case),
) -> IngestResponseSchema:
    """Ingest images from user status only for a specific phone number."""
    logger.info(
        f"Status ingestion request: instance={instancia}, "
        f"phone={numero_celular}, limit={limit}"
    )

    try:
        response = await use_case.execute(
            numero_celular=numero_celular,
            instancia=instancia,
            limit=limit,
        )

        return IngestResponseSchema(
            success=response.success,
            message=response.message,
            total_processed=response.total_processed,
            new_images_downloaded=response.new_images_downloaded,
            duplicates_skipped=response.duplicates_skipped,
            errors_count=response.errors_count,
            errors=response.errors,
            downloaded_images=response.downloaded_images,
            execution_time_seconds=response.execution_time_seconds,
            timestamp=response.timestamp,
        )

    except MissingRequiredParameterError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Status ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/status",
    response_model=IngestionStatusSchema,
    status_code=status.HTTP_200_OK,
    summary="Get ingestion system status",
    description="Check the health and state of the ingestion system.",
)
async def get_ingestion_status(
    metadata_repository=Depends(get_metadata_repository),
    image_storage=Depends(get_image_storage),
    image_source=Depends(get_image_source),
) -> IngestionStatusSchema:
    """Get the current status of the ingestion system."""
    try:
        # Get counts and state
        count = await metadata_repository.count()
        next_id = await metadata_repository.get_next_sequential_id()
        instances = await image_source.get_available_instances()

        return IngestionStatusSchema(
            is_healthy=True,
            total_images_ingested=count,
            storage_directory=image_storage.get_base_directory(),
            metadata_file=metadata_repository._csv_path,
            last_sequential_id=next_id.value - 1 if next_id.value > 1 else 0,
            available_instances=instances,
            message="Ingestion system is operational",
        )

    except Exception as e:
        logger.exception(f"Failed to get status: {e}")
        return IngestionStatusSchema(
            is_healthy=False,
            total_images_ingested=0,
            storage_directory="unknown",
            metadata_file="unknown",
            last_sequential_id=0,
            available_instances=[],
            message=f"Error: {str(e)}",
        )


@router.get(
    "/metadata",
    response_model=MetadataListSchema,
    status_code=status.HTTP_200_OK,
    summary="Get all image metadata",
    description="Retrieve metadata for all ingested images.",
)
async def get_all_metadata(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    metadata_repository=Depends(get_metadata_repository),
) -> MetadataListSchema:
    """Get all image metadata with pagination."""
    try:
        from ....application.ingestion.dto import metadata_to_dto

        all_metadata = await metadata_repository.get_all()
        total = len(all_metadata)

        # Apply pagination
        paginated = all_metadata[offset : offset + limit]

        return MetadataListSchema(
            total=total,
            items=[metadata_to_dto(m) for m in paginated],
        )

    except Exception as e:
        logger.exception(f"Failed to get metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metadata/{sequential_id}",
    response_model=ImageMetadataDTO,
    status_code=status.HTTP_200_OK,
    summary="Get metadata by sequential ID",
    description="Retrieve metadata for a specific image by its sequential ID.",
)
async def get_metadata_by_id(
    sequential_id: int,
    metadata_repository=Depends(get_metadata_repository),
) -> ImageMetadataDTO:
    """Get metadata for a specific image."""
    try:
        from ....domain.ingestion.value_objects import SequentialId
        from ....application.ingestion.dto import metadata_to_dto

        seq_id = SequentialId(sequential_id)
        metadata = await metadata_repository.get_by_sequential_id(seq_id)

        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image with sequential ID {sequential_id} not found",
            )

        return metadata_to_dto(metadata)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Failed to get metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# Export router
ingestion_router = router
