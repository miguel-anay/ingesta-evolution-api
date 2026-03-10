"""
Auto OCR Adapter

Infrastructure adapter that implements IOcrPort with automatic fallback:
Tesseract first, then AWS Textract if the result is empty or too short.
"""

import logging

from ...application.ingestion.ports.ocr_port import IOcrPort
from ...domain.ingestion.value_objects import OcrText


logger = logging.getLogger(__name__)


class AutoOcrAdapter(IOcrPort):
    """
    Auto-fallback OCR adapter.

    Runs Tesseract first (free, local). If the result is empty or shorter
    than min_length, falls back to AWS Textract (cloud, paid).
    """

    def __init__(
        self,
        tesseract_adapter: IOcrPort,
        textract_adapter: IOcrPort,
        min_length: int = 10,
    ) -> None:
        self._tesseract = tesseract_adapter
        self._textract = textract_adapter
        self._min_length = min_length
        logger.info(
            f"Initialized Auto OCR adapter (min_length={min_length})"
        )

    async def extract_text(self, image_data: bytes) -> OcrText:
        """Extract text trying Tesseract first, falling back to Textract."""
        ocr_text = await self._tesseract.extract_text(image_data)

        if not ocr_text.is_empty and len(ocr_text.value.strip()) >= self._min_length:
            logger.debug("Tesseract produced sufficient text, skipping Textract")
            return ocr_text

        logger.info(
            f"Tesseract result too short ({len(ocr_text.value.strip())} chars), "
            f"falling back to Textract"
        )
        try:
            return await self._textract.extract_text(image_data)
        except Exception as e:
            logger.warning(f"Textract fallback failed: {e}; returning Tesseract result")
            return ocr_text
