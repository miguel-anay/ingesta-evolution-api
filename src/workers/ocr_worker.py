"""
OCR Worker

Consumes from image.processing.ocr queue.
Downloads image from S3, runs Tesseract OCR, saves text to PostgreSQL,
then publishes to text.embedding queue for the next step.
"""

import asyncio
import json
import logging
from typing import Any

import aio_pika

from .base_worker import BaseWorker
from ..config.settings import get_settings
from ..application.ingestion.ports.ocr_port import IOcrPort
from ..infrastructure.persistence.database import DatabaseManager
from ..infrastructure.persistence.repositories.postgres_metadata_repository import PostgresMetadataRepository
from ..infrastructure.storage.s3_image_storage import S3ImageStorageAdapter


logger = logging.getLogger(__name__)


class OcrWorker(BaseWorker):
    """Worker that performs OCR text extraction and publishes for text embedding."""

    def __init__(
        self,
        rabbitmq_url: str,
        s3_storage: S3ImageStorageAdapter,
        repository: PostgresMetadataRepository,
        ocr_adapter: IOcrPort,
    ) -> None:
        super().__init__(rabbitmq_url, queue_name="image.processing.ocr")
        self._s3 = s3_storage
        self._repo = repository
        self._ocr = ocr_adapter
        self._rabbitmq_url = rabbitmq_url

    async def process_message(self, payload: dict[str, Any]) -> None:
        metadata_id = payload["metadata_id"]
        s3_key = payload["s3_key"]

        logger.info(f"OCR worker processing metadata_id={metadata_id}")

        # Download image from S3
        image_data = await self._s3.download_image(s3_key)

        # Run OCR
        ocr_text = await self._ocr.extract_text(image_data)

        # Save to PostgreSQL
        await self._repo.update_ocr_text(metadata_id, str(ocr_text))

        # Publish to text embedding queue
        if not ocr_text.is_empty:
            await self._publish_text_embedding(metadata_id)

        logger.info(f"OCR completed for metadata_id={metadata_id}, text_length={len(str(ocr_text))}")

    async def _publish_text_embedding(self, metadata_id: int) -> None:
        """Publish message to text.embedding queue for the text embedding worker."""
        connection = await aio_pika.connect_robust(self._rabbitmq_url)
        try:
            channel = await connection.channel()
            message = aio_pika.Message(
                body=json.dumps({"metadata_id": metadata_id}).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(message, routing_key="text.embedding")
            logger.debug(f"Published text embedding request for metadata_id={metadata_id}")
        finally:
            await connection.close()


def _build_ocr_adapter(settings) -> IOcrPort:
    """Build the appropriate OCR adapter based on settings."""
    backend = settings.ocr_backend.lower()

    if backend == "textract":
        from ..infrastructure.ocr.textract_adapter import TextractOcrAdapter
        return TextractOcrAdapter(
            region=settings.textract_region,
            access_key_id=settings.textract_access_key_id,
            secret_access_key=settings.textract_secret_access_key,
        )

    if backend == "auto":
        from ..infrastructure.ocr.tesseract_adapter import TesseractOcrAdapter
        from ..infrastructure.ocr.textract_adapter import TextractOcrAdapter
        from ..infrastructure.ocr.auto_ocr_adapter import AutoOcrAdapter
        tesseract = TesseractOcrAdapter(language=settings.ocr_language)
        textract = TextractOcrAdapter(
            region=settings.textract_region,
            access_key_id=settings.textract_access_key_id,
            secret_access_key=settings.textract_secret_access_key,
        )
        return AutoOcrAdapter(
            tesseract_adapter=tesseract,
            textract_adapter=textract,
        )

    # Default: tesseract
    from ..infrastructure.ocr.tesseract_adapter import TesseractOcrAdapter
    return TesseractOcrAdapter(language=settings.ocr_language)


def main() -> None:
    """Entry point for running the OCR worker standalone."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    settings = get_settings()

    db_manager = DatabaseManager(settings.database_url)
    repository = PostgresMetadataRepository(db_manager)
    s3_storage = S3ImageStorageAdapter(
        bucket_name=settings.s3_bucket_name,
        prefix=settings.s3_prefix,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
    )
    ocr_adapter = _build_ocr_adapter(settings)

    worker = OcrWorker(
        rabbitmq_url=settings.rabbitmq_url,
        s3_storage=s3_storage,
        repository=repository,
        ocr_adapter=ocr_adapter,
    )

    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
