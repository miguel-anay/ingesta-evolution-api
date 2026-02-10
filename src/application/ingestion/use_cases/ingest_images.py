"""
Ingest Images Use Case

Main use case that orchestrates image ingestion from all sources.
This use case delegates to specialized use cases for chat and status.

Per PROJECT_SPECS.md, the ingestion REQUIRES:
- numero_celular: User phone number to filter images from
- instancia: Evolution API instance identifier

The service operates per user and per instance, ensuring controlled
and deterministic ingestion.
"""

import logging
import time
from typing import Optional

from ....domain.ingestion.entities import IngestionResult
from ....domain.ingestion.value_objects import SourceType, PhoneNumber, Instance
from ....domain.ingestion.exceptions import IngestionError, MissingRequiredParameterError
from ..ports import IImageSourcePort, IImageStoragePort, IMetadataRepositoryPort
from ..dto import (
    IngestImagesRequest,
    IngestImagesResponse,
    metadata_to_dto,
)


logger = logging.getLogger(__name__)


class IngestImagesUseCase:
    """
    Use case for ingesting images from Evolution API.

    This is the main entry point for image ingestion.
    It coordinates the ingestion process:
    1. Fetches images from source (chat or status)
    2. Checks for duplicates (by message ID and hash)
    3. Stores new images with sequential naming
    4. Records metadata in CSV

    IDEMPOTENCY: Running this multiple times is safe.
    Already-processed images are skipped.
    """

    def __init__(
        self,
        image_source: IImageSourcePort,
        image_storage: IImageStoragePort,
        metadata_repository: IMetadataRepositoryPort,
    ) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            image_source: Port for fetching images from external sources
            image_storage: Port for storing images to disk
            metadata_repository: Port for persisting metadata
        """
        self._image_source = image_source
        self._image_storage = image_storage
        self._metadata_repository = metadata_repository

    async def execute(
        self,
        request: IngestImagesRequest,
    ) -> IngestImagesResponse:
        """
        Execute the image ingestion process.

        Args:
            request: Parameters for the ingestion (numero_celular and instancia are REQUIRED)

        Returns:
            Response containing results of the ingestion

        Raises:
            MissingRequiredParameterError: If numero_celular or instancia is missing
        """
        start_time = time.time()

        # Validate required parameters (already done in DTO, but double-check)
        if not request.numero_celular or not request.numero_celular.strip():
            raise MissingRequiredParameterError("numero_celular")
        if not request.instancia or not request.instancia.strip():
            raise MissingRequiredParameterError("instancia")

        logger.info(
            "Starting image ingestion",
            extra={
                "instance": request.instancia,
                "phone_number": request.numero_celular,
                "source_type": request.source_type.value if request.source_type else "all",
                "limit": request.limit,
            },
        )

        try:
            # Validate and create domain value objects
            phone_number = PhoneNumber(request.numero_celular)
            instance = Instance(request.instancia)

            # Ensure storage directories exist
            await self._image_storage.ensure_storage_directory()
            await self._metadata_repository.ensure_storage_exists()

            # Determine which sources to ingest
            result = IngestionResult()

            if request.source_type is None or request.source_type == SourceType.CHAT:
                chat_result = await self._ingest_from_source(
                    instance_name=request.instancia,
                    phone_number=request.numero_celular,
                    instance=instance,
                    source_type=SourceType.CHAT,
                    limit=request.limit,
                )
                result = result.merge(chat_result)

            if request.source_type is None or request.source_type == SourceType.STATUS:
                status_result = await self._ingest_from_source(
                    instance_name=request.instancia,
                    phone_number=request.numero_celular,
                    instance=instance,
                    source_type=SourceType.STATUS,
                    limit=request.limit,
                )
                result = result.merge(status_result)

            execution_time = time.time() - start_time

            logger.info(
                "Image ingestion completed",
                extra={
                    "instance": request.instancia,
                    "phone_number": request.numero_celular,
                    "total_processed": result.total_processed,
                    "new_images": result.new_images_downloaded,
                    "duplicates": result.duplicates_skipped,
                    "errors": len(result.errors),
                    "execution_time": f"{execution_time:.2f}s",
                },
            )

            return IngestImagesResponse(
                success=not result.has_errors,
                total_processed=result.total_processed,
                new_images_downloaded=result.new_images_downloaded,
                duplicates_skipped=result.duplicates_skipped,
                errors_count=len(result.errors),
                errors=result.errors,
                downloaded_images=[
                    metadata_to_dto(m) for m in result.downloaded_images
                ],
                execution_time_seconds=round(execution_time, 2),
            )

        except MissingRequiredParameterError:
            raise

        except IngestionError as e:
            execution_time = time.time() - start_time
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            return IngestImagesResponse(
                success=False,
                total_processed=0,
                new_images_downloaded=0,
                duplicates_skipped=0,
                errors_count=1,
                errors=[str(e)],
                execution_time_seconds=round(execution_time, 2),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.exception(f"Unexpected error during ingestion: {e}")
            return IngestImagesResponse(
                success=False,
                total_processed=0,
                new_images_downloaded=0,
                duplicates_skipped=0,
                errors_count=1,
                errors=[f"Unexpected error: {str(e)}"],
                execution_time_seconds=round(execution_time, 2),
            )

    async def _ingest_from_source(
        self,
        instance_name: str,
        phone_number: str,
        instance: Instance,
        source_type: SourceType,
        limit: Optional[int],
    ) -> IngestionResult:
        """
        Ingest images from a specific source type for a specific phone number.

        Args:
            instance_name: WhatsApp instance to fetch from
            phone_number: Phone number to filter images by
            instance: Instance value object for metadata
            source_type: Type of source (chat or status)
            limit: Maximum images to process

        Returns:
            IngestionResult with details of what was processed
        """
        from ....domain.ingestion.entities import ImageMetadata, RawImageData
        from ....domain.ingestion.value_objects import ImagePath
        from datetime import datetime

        result = IngestionResult()

        # Select appropriate fetch method - now with phone number filter
        if source_type == SourceType.CHAT:
            image_iterator = self._image_source.fetch_chat_images(
                instance_name=instance_name,
                phone_number=phone_number,
                limit=limit,
            )
        else:
            image_iterator = self._image_source.fetch_status_images(
                instance_name=instance_name,
                phone_number=phone_number,
                limit=limit,
            )

        async for raw_image in image_iterator:
            try:
                # Check if message already processed (idempotency)
                if await self._metadata_repository.exists_by_message_id(
                    raw_image.message_id
                ):
                    logger.debug(
                        f"Skipping already processed message: {raw_image.message_id}"
                    )
                    result.add_duplicate()
                    continue

                # Calculate hash for deduplication
                image_hash = await self._image_storage.calculate_hash(
                    raw_image.image_bytes
                )

                # Check if image content already exists
                if await self._metadata_repository.exists_by_hash(image_hash):
                    logger.debug(
                        f"Skipping duplicate image content: {image_hash}"
                    )
                    result.add_duplicate()
                    continue

                # Get next sequential ID
                sequential_id = await self._metadata_repository.get_next_sequential_id()

                # Store the image
                image_path = await self._image_storage.store_image(
                    image_data=raw_image.image_bytes,
                    sequential_id=sequential_id,
                )

                # Create and save metadata with instancia field
                metadata = ImageMetadata(
                    id_secuencial=sequential_id,
                    id_mensaje=raw_image.message_id,
                    tipo_origen=source_type,
                    fecha_descarga=datetime.utcnow(),
                    numero_celular=raw_image.phone_number,
                    nombre_usuario=raw_image.user_name,
                    instancia=instance,
                    ruta_archivo=image_path,
                    hash_imagen=image_hash,
                )

                await self._metadata_repository.save(metadata)
                result.add_success(metadata)

                logger.info(
                    f"Downloaded image {sequential_id}",
                    extra={
                        "sequential_id": sequential_id.value,
                        "message_id": str(raw_image.message_id),
                        "source": source_type.value,
                        "instance": str(instance),
                        "phone_number": str(raw_image.phone_number),
                        "path": str(image_path),
                    },
                )

            except Exception as e:
                error_msg = f"Failed to process image {raw_image.message_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                result.add_error(error_msg)

        return result
