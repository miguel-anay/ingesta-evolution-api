"""
RabbitMQ Ingestion Event Publisher

Publishes image processing events for async workers (OCR, CLIP).
"""

import json
import logging
from typing import Optional

import aio_pika

from ....application.ingestion.ports.event_publisher_port import IIngestionEventPort


logger = logging.getLogger(__name__)


class RabbitMqIngestionPublisher(IIngestionEventPort):
    """
    RabbitMQ publisher for ingestion processing events.

    Publishes to two queues simultaneously:
    - image.processing.clip (for CLIP image embedding worker)
    - image.processing.ocr (for Tesseract OCR worker)
    """

    def __init__(self, rabbitmq_url: str) -> None:
        self._url = rabbitmq_url
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if not self._connection or self._connection.is_closed:
            logger.info(f"Connecting ingestion publisher to RabbitMQ")
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()

            # Declare queues (durable)
            await self._channel.declare_queue("image.processing.clip", durable=True)
            await self._channel.declare_queue("image.processing.ocr", durable=True)
            await self._channel.declare_queue("text.embedding", durable=True)
            logger.info("Ingestion publisher connected, queues declared")

    async def close(self) -> None:
        """Close RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("Ingestion publisher disconnected")

    async def publish_image_ready(self, metadata_id: int, s3_key: str) -> None:
        """
        Publish image ready event to CLIP and OCR worker queues.

        Both workers process the same image independently.
        """
        await self.connect()

        payload = json.dumps({"metadata_id": metadata_id, "s3_key": s3_key}).encode()
        message = aio_pika.Message(
            body=payload,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        # Publish to both CLIP and OCR queues
        await self._channel.default_exchange.publish(
            message, routing_key="image.processing.clip"
        )
        await self._channel.default_exchange.publish(
            message, routing_key="image.processing.ocr"
        )

        logger.debug(f"Published image ready event: metadata_id={metadata_id}, s3_key={s3_key}")
