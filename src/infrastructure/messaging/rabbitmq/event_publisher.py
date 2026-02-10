"""
RabbitMQ Event Publisher

Production event publisher using RabbitMQ.
"""

from typing import Dict, Any, Optional
import json
import logging

from ....application.messaging.ports.message_event_publisher import IMessageEventPublisher
from ....domain.messaging.entities import Message

# Note: aio-pika is optional dependency for RabbitMQ
try:
    import aio_pika
    HAS_AIOPIKA = True
except ImportError:
    HAS_AIOPIKA = False


logger = logging.getLogger(__name__)


class RabbitMQEventPublisher(IMessageEventPublisher):
    """
    RabbitMQ implementation of IMessageEventPublisher.

    Publishes events to RabbitMQ exchange for consumption by other services.
    Uses the same exchange configured in Evolution API (evolution_exchange).
    """

    def __init__(
        self,
        rabbitmq_url: str,
        exchange_name: str = "evolution_exchange",
    ):
        """
        Initialize RabbitMQ publisher.

        Args:
            rabbitmq_url: AMQP URL (e.g., amqp://guest:guest@localhost:5672/)
            exchange_name: Name of the exchange to publish to
        """
        if not HAS_AIOPIKA:
            raise ImportError(
                "aio-pika is required for RabbitMQ. Install with: pip install aio-pika"
            )

        self._url = rabbitmq_url
        self._exchange_name = exchange_name
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if not self._connection or self._connection.is_closed:
            logger.info(f"Connecting to RabbitMQ: {self._url}")
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            logger.info("Connected to RabbitMQ")

    async def close(self) -> None:
        """Close RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("Disconnected from RabbitMQ")

    async def _publish(self, routing_key: str, data: Dict[str, Any]) -> None:
        """Publish message to exchange."""
        await self.connect()

        message = aio_pika.Message(
            body=json.dumps(data).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self._exchange.publish(message, routing_key=routing_key)
        logger.debug(f"Published to {routing_key}: {data}")

    async def publish_message_sent(self, message: Message) -> None:
        """Publish message sent event to RabbitMQ."""
        await self._publish(
            routing_key="message.sent",
            data={
                "event": "message.sent",
                "message_id": str(message.id),
                "external_id": message.external_id,
                "recipient": message.recipient.full_number,
                "status": message.status.value,
                "sent_at": message.sent_at.isoformat() if message.sent_at else None,
            },
        )

    async def publish_message_delivered(self, message: Message) -> None:
        """Publish message delivered event to RabbitMQ."""
        await self._publish(
            routing_key="message.delivered",
            data={
                "event": "message.delivered",
                "message_id": str(message.id),
                "external_id": message.external_id,
                "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
            },
        )

    async def publish_message_read(self, message: Message) -> None:
        """Publish message read event to RabbitMQ."""
        await self._publish(
            routing_key="message.read",
            data={
                "event": "message.read",
                "message_id": str(message.id),
                "external_id": message.external_id,
                "read_at": message.read_at.isoformat() if message.read_at else None,
            },
        )

    async def publish_message_failed(
        self,
        message: Message,
        reason: str,
    ) -> None:
        """Publish message failed event to RabbitMQ."""
        await self._publish(
            routing_key="message.failed",
            data={
                "event": "message.failed",
                "message_id": str(message.id),
                "recipient": message.recipient.full_number,
                "reason": reason,
            },
        )

    async def publish_message_received(
        self,
        instance_name: str,
        message_data: Dict[str, Any],
    ) -> None:
        """Publish message received event to RabbitMQ."""
        await self._publish(
            routing_key="message.received",
            data={
                "event": "message.received",
                "instance_name": instance_name,
                "data": message_data,
            },
        )
