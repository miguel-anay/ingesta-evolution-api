"""
Text Embedding Worker

Consumes from text.embedding queue.
Reads OCR text from PostgreSQL, generates CLIP text embedding, saves to PostgreSQL.
When both embeddings are ready, marks processing as completed.
"""

import asyncio
import logging
from typing import Any

from .base_worker import BaseWorker
from ..config.settings import get_settings
from ..infrastructure.persistence.database import DatabaseManager
from ..infrastructure.persistence.repositories.postgres_metadata_repository import PostgresMetadataRepository
from ..infrastructure.vectorization.clip_adapter import ClipVectorizerAdapter


logger = logging.getLogger(__name__)


class TextEmbeddingWorker(BaseWorker):
    """Worker that generates CLIP text embeddings from OCR text."""

    def __init__(
        self,
        rabbitmq_url: str,
        repository: PostgresMetadataRepository,
        vectorizer: ClipVectorizerAdapter,
    ) -> None:
        super().__init__(rabbitmq_url, queue_name="text.embedding")
        self._repo = repository
        self._vectorizer = vectorizer

    async def process_message(self, payload: dict[str, Any]) -> None:
        metadata_id = payload["metadata_id"]

        logger.info(f"Text embedding worker processing metadata_id={metadata_id}")

        # Get OCR text from PostgreSQL
        model = await self._repo.get_by_id(metadata_id)
        if not model or not model.texto_ocr:
            logger.warning(f"No OCR text found for metadata_id={metadata_id}, skipping")
            return

        # Generate text embedding with CLIP
        text_embedding = await self._vectorizer.embed_text(model.texto_ocr)

        # Save to PostgreSQL
        await self._repo.update_text_embedding(metadata_id, text_embedding.to_list())

        # Check if both embeddings are done → mark completed
        await self._check_completion(metadata_id)

        logger.info(f"Text embedding saved for metadata_id={metadata_id}")

    async def _check_completion(self, metadata_id: int) -> None:
        """Check if all processing is done and update status."""
        model = await self._repo.get_by_id(metadata_id)
        if model and model.image_embedding is not None and model.text_embedding is not None:
            await self._repo.update_processing_status(metadata_id, "completed")
            logger.info(f"Processing completed for metadata_id={metadata_id}")


def main() -> None:
    """Entry point for running the text embedding worker standalone."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    settings = get_settings()

    db_manager = DatabaseManager(settings.database_url)
    repository = PostgresMetadataRepository(db_manager)
    vectorizer = ClipVectorizerAdapter(
        model_name=settings.clip_model_name,
        cache_dir=settings.clip_model_cache_dir,
    )

    worker = TextEmbeddingWorker(
        rabbitmq_url=settings.rabbitmq_url,
        repository=repository,
        vectorizer=vectorizer,
    )

    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
