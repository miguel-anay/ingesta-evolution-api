"""
Image Storage Port

Defines the interface for storing images to persistent storage.
This is a DRIVEN port (outbound) - the application drives the adapter.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ....domain.ingestion.value_objects import ImagePath, SequentialId, ImageHash


class IImageStoragePort(ABC):
    """
    Port for storing images to persistent storage.

    Implementations might include:
    - FileSystem adapter (local disk storage)
    - S3 adapter (cloud storage)
    - Mock adapter (for unit tests)

    Responsibilities:
    - Store images with sequential filenames
    - Normalize images to JPEG format
    - Calculate image hashes
    - Ensure storage directory exists
    """

    @abstractmethod
    async def store_image(
        self,
        image_data: bytes,
        sequential_id: SequentialId,
    ) -> ImagePath:
        """
        Store an image with the given sequential ID.

        The implementation MUST:
        1. Convert image to JPEG format
        2. Save with filename: {sequential_id}.jpg
        3. Return the path where image was stored

        Args:
            image_data: Raw image bytes (any supported format)
            sequential_id: The sequential ID to use for filename

        Returns:
            ImagePath pointing to the stored file

        Raises:
            StorageError: If unable to store image
            InvalidImageError: If image data is corrupted
        """
        pass

    @abstractmethod
    async def calculate_hash(self, image_data: bytes) -> ImageHash:
        """
        Calculate SHA-256 hash of image data.

        Used for deduplication - same content produces same hash.

        Args:
            image_data: Raw image bytes

        Returns:
            ImageHash containing the SHA-256 hash

        Raises:
            InvalidImageError: If image data is invalid
        """
        pass

    @abstractmethod
    async def image_exists(self, path: ImagePath) -> bool:
        """
        Check if an image already exists at the given path.

        Args:
            path: The path to check

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def ensure_storage_directory(self) -> None:
        """
        Ensure the storage directory exists.

        Creates the directory if it doesn't exist.

        Raises:
            StorageError: If unable to create directory
        """
        pass

    @abstractmethod
    def get_base_directory(self) -> str:
        """
        Get the base directory for image storage.

        Returns:
            Absolute path to the storage directory
        """
        pass

    @abstractmethod
    async def delete_image(self, path: ImagePath) -> bool:
        """
        Delete an image at the given path.

        Used for cleanup in case of errors.

        Args:
            path: The path to the image to delete

        Returns:
            True if deleted, False if didn't exist
        """
        pass
