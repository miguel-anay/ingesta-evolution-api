"""
CLIP Image Embedding Worker

Consumes from image.processing.clip queue.
Downloads image from S3, generates CLIP embedding, saves to PostgreSQL.
"""

import asyncio
import logging
import sys
from typing import Any

from .base_worker import BaseWorker
from ..config.settings import get_settings
from ..infrastructure.persistence.database import DatabaseManager
from ..infrastructure.persistence.repositories.postgres_metadata_repository import PostgresMetadataRepository
from ..infrastructure.storage.s3_image_storage import S3ImageStorageAdapter
from ..infrastructure.vectorization.clip_adapter import ClipVectorizerAdapter


logger = logging.getLogger(__name__)


class ClipWorker(BaseWorker):
    """Worker that generates CLIP image embeddings."""

    def __init__(
        self,
        rabbitmq_url: str,
        s3_storage: S3ImageStorageAdapter,
        repository: PostgresMetadataRepository,
        vectorizer: ClipVectorizerAdapter,
    ) -> None:
        super().__init__(rabbitmq_url, queue_name="image.processing.clip")
        self._s3 = s3_storage
        self._repo = repository
        self._vectorizer = vectorizer

    async def process_message(self, payload: dict[str, Any]) -> None:
        metadata_id = payload["metadata_id"]
        s3_key = payload["s3_key"]

        logger.info(f"CLIP worker processing metadata_id={metadata_id}")

        # Download image from S3
        image_data = await self._s3.download_image(s3_key)

        # Generate CLIP embedding
        embedding = await self._vectorizer.embed_image(image_data)

        # Save to PostgreSQL
        await self._repo.update_image_embedding(metadata_id, embedding.to_list())

        # Check if both embeddings are done → mark completed
        await self._check_completion(metadata_id)

        logger.info(f"CLIP embedding saved for metadata_id={metadata_id}")

    async def _check_completion(self, metadata_id: int) -> None:
        """Check if all processing is done and update status."""
        model = await self._repo.get_by_id(metadata_id)
        if model and model.image_embedding is not None and model.text_embedding is not None:
            await self._repo.update_processing_status(metadata_id, "completed")
            logger.info(f"Processing completed for metadata_id={metadata_id}")


def main() -> None:
    """Entry point for running the CLIP worker standalone."""
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
    vectorizer = ClipVectorizerAdapter(
        model_name=settings.clip_model_name,
        cache_dir=settings.clip_model_cache_dir,
    )

    worker = ClipWorker(
        rabbitmq_url=settings.rabbitmq_url,
        s3_storage=s3_storage,
        repository=repository,
        vectorizer=vectorizer,
    )

    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
