"""
In-Memory Message Repository

Implementation of IMessageRepository for development and testing.
NOT for production use - data is lost on restart.
"""

from typing import Dict, List, Optional
from uuid import UUID
import asyncio

from ....application.messaging.ports.message_repository import IMessageRepository
from ....domain.messaging.entities import Message, MessageStatus
from ....domain.messaging.value_objects import PhoneNumber


class InMemoryMessageRepository(IMessageRepository):
    """
    In-memory implementation of IMessageRepository.

    Stores messages in a dictionary. Useful for:
    - Development without database setup
    - Unit testing
    - Quick prototyping

    NOT SUITABLE FOR PRODUCTION - no persistence.
    """

    def __init__(self):
        """Initialize empty message storage."""
        self._messages: Dict[UUID, Message] = {}
        self._by_external_id: Dict[str, UUID] = {}
        self._lock = asyncio.Lock()

    async def save(self, message: Message) -> None:
        """Save a message to memory."""
        async with self._lock:
            self._messages[message.id] = message
            if message.external_id:
                self._by_external_id[message.external_id] = message.id

    async def find_by_id(self, message_id: UUID) -> Optional[Message]:
        """Find message by internal ID."""
        return self._messages.get(message_id)

    async def find_by_external_id(self, external_id: str) -> Optional[Message]:
        """Find message by external WhatsApp ID."""
        internal_id = self._by_external_id.get(external_id)
        if internal_id:
            return self._messages.get(internal_id)
        return None

    async def find_by_recipient(
        self,
        recipient: PhoneNumber,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        """Find messages sent to a recipient."""
        messages = [
            m for m in self._messages.values()
            if m.recipient.full_number == recipient.full_number
        ]
        # Sort by created_at descending
        messages.sort(key=lambda m: m.created_at, reverse=True)
        return messages[offset:offset + limit]

    async def find_by_status(
        self,
        status: MessageStatus,
        limit: int = 100,
    ) -> List[Message]:
        """Find messages by status."""
        messages = [
            m for m in self._messages.values()
            if m.status == status
        ]
        messages.sort(key=lambda m: m.created_at, reverse=True)
        return messages[:limit]

    async def update_status(
        self,
        message_id: UUID,
        status: MessageStatus,
    ) -> None:
        """Update message status."""
        message = self._messages.get(message_id)
        if message:
            if status == MessageStatus.DELIVERED:
                message.mark_as_delivered()
            elif status == MessageStatus.READ:
                message.mark_as_read()
            elif status == MessageStatus.FAILED:
                message.mark_as_failed()

    async def delete(self, message_id: UUID) -> None:
        """Delete a message."""
        async with self._lock:
            message = self._messages.pop(message_id, None)
            if message and message.external_id:
                self._by_external_id.pop(message.external_id, None)

    # Utility methods for testing

    async def clear(self) -> None:
        """Clear all messages. For testing only."""
        async with self._lock:
            self._messages.clear()
            self._by_external_id.clear()

    async def count(self) -> int:
        """Get total message count."""
        return len(self._messages)
