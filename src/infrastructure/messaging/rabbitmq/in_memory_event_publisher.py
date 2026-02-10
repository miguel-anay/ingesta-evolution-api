"""
In-Memory Event Publisher

Simple event publisher for development and testing.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

from ....application.messaging.ports.message_event_publisher import IMessageEventPublisher
from ....domain.messaging.entities import Message


logger = logging.getLogger(__name__)


@dataclass
class PublishedEvent:
    """Record of a published event."""

    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class InMemoryEventPublisher(IMessageEventPublisher):
    """
    In-memory implementation of IMessageEventPublisher.

    Stores events in memory for inspection during testing.
    Logs events for development visibility.
    """

    def __init__(self):
        """Initialize event storage."""
        self._events: List[PublishedEvent] = []

    async def publish_message_sent(self, message: Message) -> None:
        """Publish message sent event."""
        event = PublishedEvent(
            event_type="message.sent",
            data={
                "message_id": str(message.id),
                "external_id": message.external_id,
                "recipient": message.recipient.full_number,
                "status": message.status.value,
            },
        )
        self._events.append(event)
        logger.info(f"Event published: {event.event_type} - {event.data}")

    async def publish_message_delivered(self, message: Message) -> None:
        """Publish message delivered event."""
        event = PublishedEvent(
            event_type="message.delivered",
            data={
                "message_id": str(message.id),
                "external_id": message.external_id,
                "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
            },
        )
        self._events.append(event)
        logger.info(f"Event published: {event.event_type} - {event.data}")

    async def publish_message_read(self, message: Message) -> None:
        """Publish message read event."""
        event = PublishedEvent(
            event_type="message.read",
            data={
                "message_id": str(message.id),
                "external_id": message.external_id,
                "read_at": message.read_at.isoformat() if message.read_at else None,
            },
        )
        self._events.append(event)
        logger.info(f"Event published: {event.event_type} - {event.data}")

    async def publish_message_failed(
        self,
        message: Message,
        reason: str,
    ) -> None:
        """Publish message failed event."""
        event = PublishedEvent(
            event_type="message.failed",
            data={
                "message_id": str(message.id),
                "recipient": message.recipient.full_number,
                "reason": reason,
            },
        )
        self._events.append(event)
        logger.warning(f"Event published: {event.event_type} - {event.data}")

    async def publish_message_received(
        self,
        instance_name: str,
        message_data: Dict[str, Any],
    ) -> None:
        """Publish message received event."""
        event = PublishedEvent(
            event_type="message.received",
            data={
                "instance_name": instance_name,
                "message_data": message_data,
            },
        )
        self._events.append(event)
        logger.info(f"Event published: {event.event_type} for instance {instance_name}")

    # Utility methods for testing

    def get_events(self, event_type: str = None) -> List[PublishedEvent]:
        """Get published events, optionally filtered by type."""
        if event_type:
            return [e for e in self._events if e.event_type == event_type]
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    def count(self) -> int:
        """Get total event count."""
        return len(self._events)
