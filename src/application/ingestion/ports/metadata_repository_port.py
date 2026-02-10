"""
Metadata Repository Port

Defines the interface for persisting image metadata.
This is a DRIVEN port (outbound) - the application drives the adapter.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from ....domain.ingestion.entities import ImageMetadata
from ....domain.ingestion.value_objects import (
    SequentialId,
    MessageId,
    ImageHash,
)


class IMetadataRepositoryPort(ABC):
    """
    Port for managing image metadata persistence.

    Implementations might include:
    - CSV adapter (file-based storage)
    - PostgreSQL adapter (database storage)
    - Mock adapter (for unit tests)

    The CSV is the SINGLE SOURCE OF TRUTH for:
    - Which images have been ingested
    - What the next sequential ID should be
    - Deduplication state (message IDs and hashes)
    """

    @abstractmethod
    async def save(self, metadata: ImageMetadata) -> None:
        """
        Save a new metadata record.

        The implementation MUST:
        1. Append to existing records (never overwrite)
        2. Ensure atomic write operation
        3. Handle concurrent access safely

        Args:
            metadata: The metadata to save

        Raises:
            MetadataError: If unable to save
            DuplicateImageError: If image already exists
        """
        pass

    @abstractmethod
    async def exists_by_message_id(self, message_id: MessageId) -> bool:
        """
        Check if a record with the given message ID exists.

        Used for idempotency - don't process same message twice.

        Args:
            message_id: The message ID to check

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def exists_by_hash(self, image_hash: ImageHash) -> bool:
        """
        Check if a record with the given image hash exists.

        Used for deduplication - don't store same image twice.

        Args:
            image_hash: The hash to check

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_next_sequential_id(self) -> SequentialId:
        """
        Get the next available sequential ID.

        Returns:
            The next ID to use (highest existing + 1, or 1 if empty)

        Raises:
            MetadataError: If unable to determine next ID
        """
        pass

    @abstractmethod
    async def get_all(self) -> List[ImageMetadata]:
        """
        Retrieve all metadata records.

        Returns:
            List of all metadata, ordered by sequential ID

        Raises:
            MetadataError: If unable to read metadata
        """
        pass

    @abstractmethod
    async def get_by_sequential_id(
        self, sequential_id: SequentialId
    ) -> Optional[ImageMetadata]:
        """
        Retrieve metadata by sequential ID.

        Args:
            sequential_id: The ID to look up

        Returns:
            The metadata if found, None otherwise

        Raises:
            MetadataError: If unable to read metadata
        """
        pass

    @abstractmethod
    async def get_by_message_id(
        self, message_id: MessageId
    ) -> Optional[ImageMetadata]:
        """
        Retrieve metadata by message ID.

        Args:
            message_id: The message ID to look up

        Returns:
            The metadata if found, None otherwise

        Raises:
            MetadataError: If unable to read metadata
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Get the total count of metadata records.

        Returns:
            Number of records in the repository
        """
        pass

    @abstractmethod
    async def ensure_storage_exists(self) -> None:
        """
        Ensure the metadata storage exists and is initialized.

        For CSV: creates file with headers if not exists.
        For DB: ensures table exists.

        Raises:
            MetadataError: If unable to initialize storage
        """
        pass
