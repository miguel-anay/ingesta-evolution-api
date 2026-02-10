"""
Messaging Domain Entities

Core business entities for the messaging capability.
These are pure domain objects with NO infrastructure dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from .value_objects import PhoneNumber, MessageContent, MediaAttachment


class MessageStatus(Enum):
    """Message delivery status - reflects WhatsApp message states."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageType(Enum):
    """Types of messages supported by the system."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"


@dataclass
class Message:
    """
    Core domain entity representing a WhatsApp message.

    This entity encapsulates all business rules related to messages.
    It has NO knowledge of how it's persisted or transmitted.
    """

    recipient: PhoneNumber
    content: MessageContent
    message_type: MessageType
    id: UUID = field(default_factory=uuid4)
    status: MessageStatus = MessageStatus.PENDING
    sender: Optional[PhoneNumber] = None
    media: Optional[MediaAttachment] = None
    reply_to_message_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    external_id: Optional[str] = None  # ID from WhatsApp/Evolution API

    def mark_as_sent(self, external_id: str) -> None:
        """Mark message as successfully sent."""
        self.status = MessageStatus.SENT
        self.sent_at = datetime.utcnow()
        self.external_id = external_id

    def mark_as_delivered(self) -> None:
        """Mark message as delivered to recipient's device."""
        if self.status == MessageStatus.FAILED:
            raise ValueError("Cannot mark failed message as delivered")
        self.status = MessageStatus.DELIVERED
        self.delivered_at = datetime.utcnow()

    def mark_as_read(self) -> None:
        """Mark message as read by recipient."""
        if self.status == MessageStatus.FAILED:
            raise ValueError("Cannot mark failed message as read")
        self.status = MessageStatus.READ
        self.read_at = datetime.utcnow()

    def mark_as_failed(self, reason: Optional[str] = None) -> None:
        """Mark message as failed to send."""
        self.status = MessageStatus.FAILED
        # Could store failure reason in metadata if needed

    @property
    def is_media_message(self) -> bool:
        """Check if this message contains media."""
        return self.message_type in (
            MessageType.IMAGE,
            MessageType.AUDIO,
            MessageType.VIDEO,
            MessageType.DOCUMENT,
            MessageType.STICKER,
        )

    @property
    def is_delivered(self) -> bool:
        """Check if message was delivered."""
        return self.status in (MessageStatus.DELIVERED, MessageStatus.READ)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Message):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
