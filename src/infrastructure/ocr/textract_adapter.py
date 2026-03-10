"""
AWS Textract OCR Adapter

Infrastructure adapter that implements IOcrPort
for extracting text from images using AWS Textract.
"""

import asyncio
import logging
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ...application.ingestion.ports.ocr_port import IOcrPort
from ...domain.ingestion.value_objects import OcrText
from ...domain.ingestion.exceptions import OcrError


logger = logging.getLogger(__name__)


class TextractOcrAdapter(IOcrPort):
    """
    AWS Textract OCR adapter for text extraction.

    Uses boto3 Textract client to detect text in images.
    Runs in executor to avoid blocking the async event loop.
    """

    def __init__(
        self,
        region: str = "us-east-1",
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ) -> None:
        kwargs: dict = {"region_name": region, "service_name": "textract"}
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key

        self._client = boto3.client(**kwargs)
        logger.info(f"Initialized AWS Textract OCR adapter (region={region})")

    async def extract_text(self, image_data: bytes) -> OcrText:
        """Extract text from image bytes using AWS Textract."""
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, self._do_textract, image_data
            )
            return OcrText(value=text.strip())
        except OcrError:
            raise
        except Exception as e:
            raise OcrError(reason=f"AWS Textract failed: {str(e)}")

    def _do_textract(self, image_data: bytes) -> str:
        """Synchronous Textract call."""
        try:
            response = self._client.detect_document_text(
                Document={"Bytes": image_data}
            )
            lines = [
                block["Text"]
                for block in response.get("Blocks", [])
                if block["BlockType"] == "LINE"
            ]
            return "\n".join(lines)
        except (BotoCoreError, ClientError) as e:
            raise OcrError(reason=f"Textract API error: {str(e)}")
