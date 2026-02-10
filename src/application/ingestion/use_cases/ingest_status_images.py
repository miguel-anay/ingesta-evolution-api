"""
Ingest Status Images Use Case

Specialized use case for ingesting images from user status (stories) only.

Per PROJECT_SPECS.md, the ingestion REQUIRES:
- numero_celular: User phone number to filter images from
- instancia: Evolution API instance identifier
"""

import logging
from typing import Optional

from ....domain.ingestion.value_objects import SourceType
from ..ports import IImageSourcePort, IImageStoragePort, IMetadataRepositoryPort
from ..dto import IngestImagesRequest, IngestImagesResponse
from .ingest_images import IngestImagesUseCase


logger = logging.getLogger(__name__)


class IngestStatusImagesUseCase:
    """
    Use case for ingesting images specifically from user status (stories).

    This is a convenience wrapper around IngestImagesUseCase
    that pre-configures it to only process status images.

    REQUIRED PARAMETERS:
    - numero_celular: User phone number to ingest images from
    - instancia: Evolution API instance identifier
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
        self._ingest_use_case = IngestImagesUseCase(
            image_source=image_source,
            image_storage=image_storage,
            metadata_repository=metadata_repository,
        )

    async def execute(
        self,
        numero_celular: str,
        instancia: str,
        limit: Optional[int] = None,
    ) -> IngestImagesResponse:
        """
        Execute status image ingestion for a specific phone number.

        Args:
            numero_celular: Phone number to filter status from (required)
            instancia: WhatsApp instance to fetch from (required)
            limit: Maximum number of images to process

        Returns:
            Response containing results of the ingestion
        """
        logger.info(
            f"Starting status image ingestion for instance: {instancia}, "
            f"phone: {numero_celular}"
        )

        request = IngestImagesRequest(
            numero_celular=numero_celular,
            instancia=instancia,
            source_type=SourceType.STATUS,
            limit=limit,
        )

        return await self._ingest_use_case.execute(request)
