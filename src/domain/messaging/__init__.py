"""
Messaging Domain

Business entities and rules for WhatsApp messaging.
"""

from .entities import Message, MessageStatus, MessageType
from .value_objects import PhoneNumber, MessageContent, MediaAttachment
from .exceptions import (
    MessagingDomainError,
    InvalidPhoneNumberError,
    InvalidMessageContentError,
    MessageNotFoundError,
)

__all__ = [
    "Message",
    "MessageStatus",
    "MessageType",
    "PhoneNumber",
    "MessageContent",
    "MediaAttachment",
    "MessagingDomainError",
    "InvalidPhoneNumberError",
    "InvalidMessageContentError",
    "MessageNotFoundError",
]
