"""
Messaging Ports (Interfaces)

These interfaces define contracts that infrastructure adapters must implement.
Use cases depend on these abstractions, not on concrete implementations.
"""

from .whatsapp_gateway import IWhatsAppGateway
from .message_repository import IMessageRepository
from .message_event_publisher import IMessageEventPublisher

__all__ = [
    "IWhatsAppGateway",
    "IMessageRepository",
    "IMessageEventPublisher",
]
