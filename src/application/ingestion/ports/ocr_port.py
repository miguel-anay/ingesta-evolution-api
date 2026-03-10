"""
OCR Port

Defines the interface for extracting text from images via OCR.
This is a DRIVEN port (outbound).
"""

from abc import ABC, abstractmethod

from ....domain.ingestion.value_objects import OcrText


class IOcrPort(ABC):
    """
    Port for OCR text extraction from images.

    Implementations might include:
    - Tesseract adapter (local, free)
    - AWS Textract adapter (cloud, paid)
    """

    @abstractmethod
    async def extract_text(self, image_data: bytes) -> OcrText:
        """
        Extract text from image bytes using OCR.

        Args:
            image_data: Raw image bytes (JPEG/PNG)

        Returns:
            OcrText with extracted text content

        Raises:
            OcrError: If OCR processing fails
        """
        pass
