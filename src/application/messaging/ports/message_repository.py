"""
Message Repository Port

Interface for message persistence operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ....domain.messaging.entities import Message, MessageStatus
from ....domain.messaging.value_objects import PhoneNumber


class IMessageRepository(ABC):
    """
    Port (interface) for message persistence.

    This abstraction allows the application layer to store/retrieve messages
    without knowing the storage implementation details.

    IMPLEMENTATIONS:
    - InMemoryMessageRepository: For development/testing
    - PostgresMessageRepository: For production
    - RedisMessageRepository: For caching
    """

    @abstractmethod
    async def save(self, message: Message) -> None:
        """
        Save a message.

        Args:
            message: Message entity to save
        """
        pass

    @abstractmethod
    async def find_by_id(self, message_id: UUID) -> Optional[Message]:
        """
        Find a message by its internal ID.

        Args:
            message_id: UUID of the message

        Returns:
            Message if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_external_id(self, external_id: str) -> Optional[Message]:
        """
        Find a message by its external WhatsApp ID.

        Args:
            external_id: External ID from WhatsApp

        Returns:
            Message if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_recipient(
        self,
        recipient: PhoneNumber,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        """
        Find messages sent to a specific recipient.

        Args:
            recipient: Phone number of the recipient
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of messages
        """
        pass

    @abstractmethod
    async def find_by_status(
        self,
        status: MessageStatus,
        limit: int = 100,
    ) -> List[Message]:
        """
        Find messages by their status.

        Args:
            status: Message status to filter by
            limit: Maximum number of messages to return

        Returns:
            List of messages with the given status
        """
        pass

    @abstractmethod
    async def update_status(
        self,
        message_id: UUID,
        status: MessageStatus,
    ) -> None:
        """
        Update the status of a message.

        Args:
            message_id: UUID of the message
            status: New status
        """
        pass

    @abstractmethod
    async def delete(self, message_id: UUID) -> None:
        """
        Delete a message.

        Args:
            message_id: UUID of the message to delete
        """
        pass
