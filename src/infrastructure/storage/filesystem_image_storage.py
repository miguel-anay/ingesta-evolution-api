"""
FileSystem Image Storage Adapter

Infrastructure adapter that implements IImageStoragePort
for storing images to the local filesystem.
"""

import asyncio
import hashlib
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

from ...application.ingestion.ports import IImageStoragePort
from ...domain.ingestion.value_objects import ImagePath, SequentialId, ImageHash
from ...domain.ingestion.exceptions import StorageError, InvalidImageError


logger = logging.getLogger(__name__)


class FileSystemImageStorageAdapter(IImageStoragePort):
    """
    Adapter for storing images to the local filesystem.

    Implements IImageStoragePort to provide:
    - Image storage with sequential filenames
    - Automatic conversion to JPEG format
    - SHA-256 hash calculation for deduplication
    - Directory management

    All images are normalized to JPEG format regardless
    of their original format (PNG, WebP, GIF, etc.).
    """

    # JPEG quality setting (1-100)
    JPEG_QUALITY = 85

    # Maximum image dimensions (resize if larger)
    MAX_DIMENSION = 4096

    def __init__(self, base_directory: str) -> None:
        """
        Initialize the storage adapter.

        Args:
            base_directory: Absolute path to the image storage directory
        """
        self._base_directory = os.path.abspath(base_directory)
        logger.info(f"Initialized image storage at: {self._base_directory}")

    async def store_image(
        self,
        image_data: bytes,
        sequential_id: SequentialId,
    ) -> ImagePath:
        """
        Store an image with the given sequential ID.

        Converts the image to JPEG format and saves it
        with filename: {sequential_id}.jpg

        Args:
            image_data: Raw image bytes (any supported format)
            sequential_id: The sequential ID to use for filename

        Returns:
            ImagePath pointing to the stored file

        Raises:
            StorageError: If unable to store image
            InvalidImageError: If image data is corrupted
        """
        filename = f"{sequential_id.value}.jpg"
        full_path = os.path.join(self._base_directory, filename)

        logger.debug(f"Storing image {sequential_id} to {full_path}")

        try:
            # Convert to JPEG in a thread pool (PIL is blocking)
            jpeg_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._convert_to_jpeg,
                image_data,
            )

            # Write to file
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._write_file,
                full_path,
                jpeg_data,
            )

            logger.info(f"Stored image {sequential_id} ({len(jpeg_data)} bytes)")

            return ImagePath(
                base_directory=self._base_directory,
                filename=filename,
            )

        except InvalidImageError:
            raise
        except OSError as e:
            raise StorageError(
                operation="write",
                path=full_path,
                reason=str(e),
            )
        except Exception as e:
            raise StorageError(
                operation="store",
                path=full_path,
                reason=f"Unexpected error: {str(e)}",
            )

    async def calculate_hash(self, image_data: bytes) -> ImageHash:
        """
        Calculate SHA-256 hash of image data.

        Args:
            image_data: Raw image bytes

        Returns:
            ImageHash containing the SHA-256 hash

        Raises:
            InvalidImageError: If image data is invalid
        """
        if not image_data:
            raise InvalidImageError(
                reason="Empty image data",
                message_id=None,
            )

        try:
            # Calculate hash in thread pool
            hash_value = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: hashlib.sha256(image_data).hexdigest(),
            )

            return ImageHash(hash_value)

        except Exception as e:
            raise InvalidImageError(
                reason=f"Failed to calculate hash: {str(e)}",
                message_id=None,
            )

    async def image_exists(self, path: ImagePath) -> bool:
        """
        Check if an image already exists at the given path.

        Args:
            path: The path to check

        Returns:
            True if file exists, False otherwise
        """
        full_path = path.full_path

        return await asyncio.get_event_loop().run_in_executor(
            None,
            os.path.exists,
            full_path,
        )

    async def ensure_storage_directory(self) -> None:
        """
        Ensure the storage directory exists.

        Creates the directory and any parent directories if needed.

        Raises:
            StorageError: If unable to create directory
        """
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: os.makedirs(self._base_directory, exist_ok=True),
            )
            logger.debug(f"Ensured storage directory: {self._base_directory}")

        except OSError as e:
            raise StorageError(
                operation="create_directory",
                path=self._base_directory,
                reason=str(e),
            )

    def get_base_directory(self) -> str:
        """
        Get the base directory for image storage.

        Returns:
            Absolute path to the storage directory
        """
        return self._base_directory

    async def delete_image(self, path: ImagePath) -> bool:
        """
        Delete an image at the given path.

        Args:
            path: The path to the image to delete

        Returns:
            True if deleted, False if didn't exist
        """
        full_path = path.full_path

        try:
            if not await self.image_exists(path):
                return False

            await asyncio.get_event_loop().run_in_executor(
                None,
                os.remove,
                full_path,
            )
            logger.info(f"Deleted image: {full_path}")
            return True

        except OSError as e:
            logger.warning(f"Failed to delete {full_path}: {e}")
            return False

    # Private helper methods

    def _convert_to_jpeg(self, image_data: bytes) -> bytes:
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
            # Open image with PIL
            image = Image.open(BytesIO(image_data))

            # Convert to RGB mode if necessary (removes alpha channel)
            if image.mode in ("RGBA", "LA", "P"):
                # Create white background for transparency
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
            if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                ratio = min(
                    self.MAX_DIMENSION / width,
                    self.MAX_DIMENSION / height,
                )
                new_size = (int(width * ratio), int(height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"Resized image from {width}x{height} to {new_size}")

            # Save as JPEG
            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=self.JPEG_QUALITY,
                optimize=True,
            )

            return output.getvalue()

        except Exception as e:
            raise InvalidImageError(
                reason=f"Failed to convert image to JPEG: {str(e)}",
                message_id=None,
            )

    def _write_file(self, path: str, data: bytes) -> None:
        """
        Write data to file atomically.

        Uses write-and-rename pattern for atomicity.

        Args:
            path: Target file path
            data: Data to write
        """
        # Write to temporary file first
        temp_path = f"{path}.tmp"

        try:
            with open(temp_path, "wb") as f:
                f.write(data)

            # Atomic rename
            os.replace(temp_path, path)

        finally:
            # Clean up temp file if rename failed
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
