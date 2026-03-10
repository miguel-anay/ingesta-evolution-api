"""
Batch Processor for Pending Images (Lambda version)

Calls the FastAPI microservice API instead of connecting directly to the database.

Flow:
1. GET /api/v1/batch/pending → get pending images
2. For each image:
   a. Download from S3
   b. Run OCR via AWS Textract
   c. Generate Titan image embedding (1024 dims)
   d. Generate Titan text embedding (if OCR text is non-empty)
   e. PATCH /api/v1/batch/{id}/complete → save results via API

Usage:
    python -m src.batch.process_pending

Designed to run as:
- AWS Lambda function triggered by EventBridge (cron)
"""

import asyncio
import logging
import os
import time

import httpx

from ..infrastructure.storage.s3_image_storage import S3ImageStorageAdapter
from ..infrastructure.vectorization.titan_adapter import TitanVectorizerAdapter
from ..infrastructure.ocr.textract_adapter import TextractOcrAdapter


logger = logging.getLogger(__name__)


API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:3000")


async def process_pending() -> dict:
    """Process all pending images: Textract OCR + Titan embeddings.

    Communicates with the FastAPI microservice via HTTP API
    instead of connecting directly to the database.

    Returns a summary dict suitable for Lambda response.
    """
    start_time = time.time()

    # Build infrastructure (S3, Textract, Titan — direct AWS API calls)
    s3 = S3ImageStorageAdapter(
        bucket_name=os.environ.get("S3_BUCKET_NAME", "whatsapp-images-prod"),
        prefix=os.environ.get("S3_PREFIX", "images/"),
        region=os.environ.get("S3_REGION", "us-east-1"),
    )

    ocr_adapter = None
    if os.environ.get("OCR_ENABLED", "true").lower() == "true":
        ocr_adapter = TextractOcrAdapter(
            region=os.environ.get("TEXTRACT_REGION", "us-east-1"),
        )

    titan_adapter = None
    if os.environ.get("EMBEDDINGS_ENABLED", "true").lower() == "true":
        titan_adapter = TitanVectorizerAdapter(
            region=os.environ.get("BEDROCK_REGION", "us-east-1"),
            model_id=os.environ.get("TITAN_MODEL_ID", "amazon.titan-embed-image-v1"),
        )

    # Fetch pending records from API
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        response = await client.get("/api/v1/batch/pending")
        response.raise_for_status()
        pending = response.json()

    total = len(pending)
    logger.info(f"Found {total} pending images to process")

    if total == 0:
        logger.info("Nothing to process. Exiting.")
        return {"total": 0, "completed": 0, "failed": 0, "elapsed_seconds": 0}

    completed = 0
    failed = 0

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0) as client:
        for record in pending:
            record_id = record["id"]
            s3_key = record["s3_key"]

            try:
                # Download image from S3
                logger.info(f"[{record_id}] Downloading from S3: {s3_key}")
                image_data = await s3.download_image(s3_key)

                result_payload = {"processing_status": "completed"}

                # OCR via Textract
                ocr_text = ""
                if ocr_adapter:
                    try:
                        ocr_result = await ocr_adapter.extract_text(image_data)
                        ocr_text = str(ocr_result)
                        result_payload["texto_ocr"] = ocr_text
                        logger.info(f"[{record_id}] Textract OCR done, text_length={len(ocr_text)}")
                    except Exception as e:
                        logger.warning(f"[{record_id}] Textract OCR failed (non-fatal): {e}")

                # Titan image embedding
                if titan_adapter:
                    try:
                        image_embedding = await titan_adapter.embed_image(image_data)
                        result_payload["image_embedding"] = image_embedding.to_list()
                        logger.info(f"[{record_id}] Titan image embedding generated (1024 dims)")
                    except Exception as e:
                        logger.warning(f"[{record_id}] Titan image embedding failed (non-fatal): {e}")

                    # Titan text embedding (only if OCR text is non-empty)
                    if ocr_text.strip():
                        try:
                            text_embedding = await titan_adapter.embed_text(ocr_text)
                            result_payload["text_embedding"] = text_embedding.to_list()
                            logger.info(f"[{record_id}] Titan text embedding generated (1024 dims)")
                        except Exception as e:
                            logger.warning(f"[{record_id}] Titan text embedding failed (non-fatal): {e}")

                # Send results to API
                resp = await client.patch(
                    f"/api/v1/batch/{record_id}/complete",
                    json=result_payload,
                )
                resp.raise_for_status()

                completed += 1
                logger.info(f"[{record_id}] Completed ({completed}/{total})")

            except Exception as e:
                failed += 1
                logger.error(f"[{record_id}] Failed: {e}", exc_info=True)
                try:
                    await client.patch(
                        f"/api/v1/batch/{record_id}/complete",
                        json={"processing_status": "failed"},
                    )
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
