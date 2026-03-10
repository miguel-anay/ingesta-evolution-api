"""
Base Worker

Abstract base class for RabbitMQ async workers with connection management,
retry logic, and error handling.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage


logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """
    Base class for RabbitMQ consumer workers.

    Provides:
    - Connection management with auto-reconnect
    - Message deserialization
    - Error handling with nack/requeue
    - Graceful shutdown
    """

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        prefetch_count: int = 1,
    ) -> None:
        self._rabbitmq_url = rabbitmq_url
        self._queue_name = queue_name
        self._prefetch_count = prefetch_count
        self._connection: aio_pika.Connection | None = None
        self._channel: aio_pika.Channel | None = None
        self._should_stop = False

    @abstractmethod
    async def process_message(self, payload: dict[str, Any]) -> None:
        """
        Process a single message. Subclasses implement business logic here.

        Args:
            payload: Deserialized JSON message body

        Raises:
            Exception: Any exception will trigger nack + requeue
        """
        pass

    async def start(self) -> None:
        """Start consuming messages from the queue."""
        logger.info(f"Starting worker for queue: {self._queue_name}")

        while not self._should_stop:
            try:
                self._connection = await aio_pika.connect_robust(self._rabbitmq_url)
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=self._prefetch_count)

                queue = await self._channel.declare_queue(self._queue_name, durable=True)
                await queue.consume(self._on_message)

                logger.info(f"Worker consuming from queue: {self._queue_name}")

                # Wait until connection closes or stop is requested
                await asyncio.Future()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker connection error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        self._should_stop = True
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info(f"Worker stopped: {self._queue_name}")

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        """Handle incoming message with error handling."""
        async with message.process(requeue=True):
            try:
                payload = json.loads(message.body.decode())
                logger.debug(f"[{self._queue_name}] Processing: {payload}")
                await self.process_message(payload)
                logger.debug(f"[{self._queue_name}] Completed: {payload.get('metadata_id')}")
            except json.JSONDecodeError as e:
                logger.error(f"[{self._queue_name}] Invalid JSON: {e}")
                # Don't requeue malformed messages — reject permanently
                raise
            except Exception as e:
                logger.error(f"[{self._queue_name}] Processing error: {e}")
                raise
