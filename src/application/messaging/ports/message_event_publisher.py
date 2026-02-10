"""
Message Event Publisher Port

Interface for publishing message-related events.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from ....domain.messaging.entities import Message


class IMessageEventPublisher(ABC):
    """
    Port (interface) for publishing message events.

    This abstraction allows publishing events to message brokers
    without knowing the implementation details.

    IMPLEMENTATIONS:
    - RabbitMQMessageEventPublisher: For production
    - InMemoryEventPublisher: For testing
    """

    @abstractmethod
    async def publish_message_sent(self, message: Message) -> None:
        """
        Publish event when a message is sent.

        Args:
            message: The sent message
        """
        pass

    @abstractmethod
    async def publish_message_delivered(self, message: Message) -> None:
        """
        Publish event when a message is delivered.

        Args:
            message: The delivered message
        """
        pass

    @abstractmethod
    async def publish_message_read(self, message: Message) -> None:
        """
        Publish event when a message is read.

        Args:
            message: The read message
        """
        pass

    @abstractmethod
    async def publish_message_failed(
        self,
        message: Message,
        reason: str,
    ) -> None:
        """
        Publish event when a message fails to send.

        Args:
            message: The failed message
            reason: Reason for failure
        """
        pass

    @abstractmethod
    async def publish_message_received(
        self,
        instance_name: str,
        message_data: Dict[str, Any],
    ) -> None:
        """
        Publish event when a message is received.

        Args:
            instance_name: Name of the instance that received the message
            message_data: Raw message data from webhook
        """
        pass
