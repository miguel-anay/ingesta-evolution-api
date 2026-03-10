"""
Batch Processor for Pending Images

Processes all pending images using AWS Textract (OCR) + Titan (embeddings).

For each pending image:
1. Download from S3
2. Run OCR via AWS Textract
3. Generate Titan image embedding (1024 dims)
4. Generate Titan text embedding (if OCR text is non-empty)
5. Mark as completed

Usage:
    python -m src.batch.process_pending

Designed to run as:
- Local: docker-compose run --rm batch-processor
- AWS:   Lambda function triggered by EventBridge (cron)
"""

import asyncio
import logging
import sys
import time

from ..config.settings import get_settings
from ..infrastructure.persistence.database import DatabaseManager
from ..infrastructure.persistence.repositories.postgres_metadata_repository import PostgresMetadataRepository
from ..infrastructure.storage.s3_image_storage import S3ImageStorageAdapter
from ..infrastructure.vectorization.titan_adapter import TitanVectorizerAdapter
from ..infrastructure.ocr.textract_adapter import TextractOcrAdapter


logger = logging.getLogger(__name__)


async def process_pending() -> dict:
    """Process all pending images: Textract OCR + Titan embeddings.

    Returns a summary dict suitable for Lambda response.
    """
    settings = get_settings()
    start_time = time.time()

    # Build infrastructure
    db_manager = DatabaseManager(settings.database_url)
    repo = PostgresMetadataRepository(db_manager)
    s3 = S3ImageStorageAdapter(
        bucket_name=settings.s3_bucket_name,
        prefix=settings.s3_prefix,
        region=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
    )

    ocr_adapter = None
    if settings.ocr_enabled:
        ocr_adapter = TextractOcrAdapter(region=settings.textract_region)

    titan_adapter = None
    if settings.embeddings_enabled:
        titan_adapter = TitanVectorizerAdapter(
            region=settings.bedrock_region,
            model_id=settings.titan_model_id,
        )

    # Fetch pending records
    pending = await repo.get_pending()
    total = len(pending)
    logger.info(f"Found {total} pending images to process")

    if total == 0:
        logger.info("Nothing to process. Exiting.")
        return {"total": 0, "completed": 0, "failed": 0, "elapsed_seconds": 0}

    completed = 0
    failed = 0

    for record in pending:
        record_id = record.id
        s3_key = record.s3_key

        try:
            # Mark as processing
            await repo.update_processing_status(record_id, "processing")

            # Download image from S3
            logger.info(f"[{record_id}] Downloading from S3: {s3_key}")
            image_data = await s3.download_image(s3_key)

            # OCR via Textract
            ocr_text = ""
            if ocr_adapter:
                try:
                    ocr_result = await ocr_adapter.extract_text(image_data)
                    ocr_text = str(ocr_result)
                    await repo.update_ocr_text(record_id, ocr_text)
                    logger.info(f"[{record_id}] Textract OCR done, text_length={len(ocr_text)}")
                except Exception as e:
                    logger.warning(f"[{record_id}] Textract OCR failed (non-fatal): {e}")

            # Titan image embedding
            if titan_adapter:
                try:
                    image_embedding = await titan_adapter.embed_image(image_data)
                    await repo.update_image_embedding(record_id, image_embedding.to_list())
                    logger.info(f"[{record_id}] Titan image embedding saved (1024 dims)")
                except Exception as e:
                    logger.warning(f"[{record_id}] Titan image embedding failed (non-fatal): {e}")

                # Titan text embedding (only if OCR text is non-empty)
                if ocr_text.strip():
                    try:
                        text_embedding = await titan_adapter.embed_text(ocr_text)
                        await repo.update_text_embedding(record_id, text_embedding.to_list())
                        logger.info(f"[{record_id}] Titan text embedding saved (1024 dims)")
                    except Exception as e:
                        logger.warning(f"[{record_id}] Titan text embedding failed (non-fatal): {e}")

            # Mark completed
            await repo.update_processing_status(record_id, "completed")
            completed += 1
            logger.info(f"[{record_id}] Completed ({completed}/{total})")

        except Exception as e:
            failed += 1
            logger.error(f"[{record_id}] Failed: {e}", exc_info=True)
            try:
                await repo.update_processing_status(record_id, "failed")
            except Exception:
                logger.error(f"[{record_id}] Could not update status to failed")

    elapsed = time.time() - start_time
    summary = {
        "total": total,
        "completed": completed,
        "failed": failed,
        "elapsed_seconds": round(elapsed, 1),
    }
    logger.info(
        f"Batch processing finished: {completed} completed, {failed} failed, "
        f"{total} total, elapsed={elapsed:.1f}s"
    )
    return summary


def main() -> None:
    """Entry point for batch processor (CLI / Docker)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting batch processor (Textract + Titan)")
    asyncio.run(process_pending())
    logger.info("Batch processor finished")


if __name__ == "__main__":
    main()
