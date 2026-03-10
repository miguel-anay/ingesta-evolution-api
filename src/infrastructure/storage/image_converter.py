"""
Image Converter

Shared utility for converting images to JPEG format.
Extracted from FileSystemImageStorageAdapter for reuse by S3 adapter.
"""

import logging
from io import BytesIO

from PIL import Image

from ...domain.ingestion.exceptions import InvalidImageError


logger = logging.getLogger(__name__)

# JPEG quality setting (1-100)
JPEG_QUALITY = 85

# Maximum image dimensions (resize if larger)
MAX_DIMENSION = 4096


def convert_to_jpeg(image_data: bytes) -> bytes:
    """
    Convert image data to JPEG format.

    Handles conversion from PNG, WebP, GIF, BMP, etc.
    Also resizes images if they exceed maximum dimensions.

    Args:
        image_data: Raw image bytes

    Returns:
        JPEG encoded bytes

    Raises:
        InvalidImageError: If image cannot be processed
    """
    try:
        image = Image.open(BytesIO(image_data))

        # Convert to RGB mode if necessary (removes alpha channel)
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(
                image,
                mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None,
            )
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if too large
        width, height = image.size
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
            new_size = (int(width * ratio), int(height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.debug(f"Resized image from {width}x{height} to {new_size}")

        # Save as JPEG
        output = BytesIO()
        image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return output.getvalue()

    except Exception as e:
        raise InvalidImageError(
            reason=f"Failed to convert image to JPEG: {str(e)}",
            message_id=None,
        )
