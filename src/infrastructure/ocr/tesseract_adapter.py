"""
Tesseract OCR Adapter

Infrastructure adapter that implements IOcrPort
for extracting text from images using Tesseract.
"""

import asyncio
import logging
from io import BytesIO

import pytesseract
from PIL import Image

from ...application.ingestion.ports.ocr_port import IOcrPort
from ...domain.ingestion.value_objects import OcrText
from ...domain.ingestion.exceptions import OcrError


logger = logging.getLogger(__name__)


class TesseractOcrAdapter(IOcrPort):
    """
    Tesseract OCR adapter for text extraction.

    Uses pytesseract (Tesseract wrapper) with configurable language support.
    Runs OCR in executor to avoid blocking the async event loop.
    """

    def __init__(self, language: str = "spa+eng") -> None:
        self._language = language
        logger.info(f"Initialized Tesseract OCR adapter (language={language})")

    async def extract_text(self, image_data: bytes) -> OcrText:
        """Extract text from image bytes using Tesseract OCR."""
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, self._do_ocr, image_data
            )
            return OcrText(value=text.strip())
        except OcrError:
            raise
        except Exception as e:
            raise OcrError(reason=f"Tesseract OCR failed: {str(e)}")

    def _do_ocr(self, image_data: bytes) -> str:
        """Synchronous OCR extraction."""
        try:
            image = Image.open(BytesIO(image_data))
            if image.mode != "RGB":
                image = image.convert("RGB")
            return pytesseract.image_to_string(image, lang=self._language)
        except Exception as e:
            raise OcrError(reason=f"Failed to process image: {str(e)}")
