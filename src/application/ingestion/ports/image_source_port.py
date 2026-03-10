"""
Image Source Port

Defines the interface for fetching images from external sources.
This is a DRIVEN port (outbound) - the application drives the adapter.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, AsyncIterator, Optional

from ....domain.ingestion.entities import RawImageData
from ....domain.ingestion.value_objects import SourceType


class IImageSourcePort(ABC):
    """
    Port for fetching images from external sources.

    Implementations might include:
    - Evolution API adapter (chat messages, user status)
    - File system adapter (local files for testing)
    - Mock adapter (for unit tests)

    The application layer uses this interface without knowing
    the concrete implementation details.

    FILTERING: All fetch operations now require a phone_number parameter
    to filter images from a specific user only (per PROJECT_SPECS.md).
    """

    @abstractmethod
    async def fetch_chat_images(
        self,
        instance_name: str,
        phone_number: str,
        limit: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> AsyncIterator[RawImageData]:
        """
        Fetch images from chat messages for a specific phone number.

        Args:
            instance_name: The WhatsApp instance to fetch from
            phone_number: The phone number to filter messages by (required)
            limit: Maximum number of images to fetch (None for all)
            fecha_desde: Only fetch messages after this datetime
            fecha_hasta: Only fetch messages before this datetime

        Yields:
            RawImageData objects for each image found from the specified number

        Raises:
            ImageSourceError: If unable to fetch images
        """
        pass

    @abstractmethod
    async def fetch_status_images(
        self,
        instance_name: str,
        phone_number: str,
        limit: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> AsyncIterator[RawImageData]:
        """
        Fetch images from user status (stories) for a specific phone number.

        Args:
            instance_name: The WhatsApp instance to fetch from
            phone_number: The phone number to filter status by (required)
            limit: Maximum number of images to fetch (None for all)
            fecha_desde: Only fetch messages after this datetime
            fecha_hasta: Only fetch messages before this datetime

        Yields:
            RawImageData objects for each status image found from the specified number

        Raises:
            ImageSourceError: If unable to fetch status images
        """
        pass

    @abstractmethod
    async def download_media(
        self,
        instance_name: str,
        message_id: str,
    ) -> bytes:
        """
        Download the actual media content for a specific message.

        Args:
            instance_name: The WhatsApp instance
            message_id: The message ID containing the media

        Returns:
            Raw bytes of the media file

        Raises:
            ImageSourceError: If unable to download media
        """
        pass

    @abstractmethod
    async def get_available_instances(self) -> List[str]:
        """
        Get list of available WhatsApp instances.

        Returns:
            List of instance names that are connected

        Raises:
            ImageSourceError: If unable to fetch instances
        """
        pass
