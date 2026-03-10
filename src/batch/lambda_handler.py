"""
AWS Lambda Handler for Batch Processing

Triggered by EventBridge (cron schedule) or manual invocation.
Processes all pending images: Textract OCR + Titan embeddings.

Lambda Config:
- Runtime: Python 3.11
- Timeout: 900 seconds (15 min)
- Memory: 512 MB (only API calls, no local ML inference)
- Environment variables: DATABASE_URL, S3_BUCKET_NAME, etc.
"""

import asyncio
import json
import logging

from .process_pending import process_pending


logger = logging.getLogger(__name__)


def handler(event, context):
    """AWS Lambda entry point.

    Args:
        event: EventBridge event or manual trigger payload.
        context: Lambda context (request_id, remaining_time, etc.)

    Returns:
        dict with processing summary.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info(f"Lambda invoked. Event: {json.dumps(event, default=str)}")

    remaining_ms = context.get_remaining_time_in_millis() if context else 900_000
    logger.info(f"Remaining time: {remaining_ms}ms")

    summary = asyncio.run(process_pending())

    response = {
        "statusCode": 200,
        "body": summary,
    }
    logger.info(f"Lambda finished: {summary}")
    return response
