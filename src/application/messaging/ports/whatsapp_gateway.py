"""
WhatsApp Gateway Port

Interface defining operations for WhatsApp message sending/receiving.
Infrastructure layer provides concrete implementations (e.g., Evolution API adapter).
"""

from abc import ABC, abstractmethod
from typing import Optional

from ....domain.messaging.entities import Message, MessageType
from ....domain.messaging.value_objects import PhoneNumber, MessageContent, MediaAttachment


class IWhatsAppGateway(ABC):
    """
    Port (interface) for WhatsApp messaging operations.

    This abstraction allows the application layer to send messages
    without knowing the details of the underlying WhatsApp API.

    IMPLEMENTATIONS:
    - EvolutionApiWhatsAppAdapter: Uses Evolution API
    - MockWhatsAppAdapter: For testing
    """

    @abstractmethod
    async def send_text_message(
        self,
        instance_name: str,
        recipient: PhoneNumber,
        content: MessageContent,
        reply_to: Optional[str] = None,
    ) -> str:
        """
        Send a text message via WhatsApp.

        Args:
            instance_name: Name of the WhatsApp instance to use
            recipient: Phone number of the recipient
            content: Message content
            reply_to: Optional message ID to reply to

        Returns:
            External message ID from WhatsApp

        Raises:
            MessageDeliveryError: If message cannot be sent
            InstanceNotConnectedError: If instance is not connected
        """
        pass

    @abstractmethod
    async def send_media_message(
        self,
        instance_name: str,
        recipient: PhoneNumber,
        media: MediaAttachment,
        message_type: MessageType,
        reply_to: Optional[str] = None,
    ) -> str:
        """
        Send a media message (image, audio, video, document).

        Args:
            instance_name: Name of the WhatsApp instance to use
            recipient: Phone number of the recipient
            media: Media attachment with URL and metadata
            message_type: Type of media being sent
            reply_to: Optional message ID to reply to

        Returns:
            External message ID from WhatsApp

        Raises:
            MessageDeliveryError: If message cannot be sent
            InstanceNotConnectedError: If instance is not connected
        """
        pass

    @abstractmethod
    async def send_location(
        self,
        instance_name: str,
        recipient: PhoneNumber,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> str:
        """
        Send a location message.

        Args:
            instance_name: Name of the WhatsApp instance to use
            recipient: Phone number of the recipient
            latitude: Location latitude
            longitude: Location longitude
            name: Optional location name
            address: Optional address text

        Returns:
            External message ID from WhatsApp
        """
        pass

    @abstractmethod
    async def check_number_exists(
        self,
        instance_name: str,
        phone_number: PhoneNumber,
    ) -> bool:
        """
        Check if a phone number has WhatsApp.

        Args:
            instance_name: Name of the WhatsApp instance to use
            phone_number: Phone number to check

        Returns:
            True if number has WhatsApp, False otherwise
        """
        pass

    @abstractmethod
    async def mark_message_as_read(
        self,
        instance_name: str,
        message_id: str,
    ) -> None:
        """
        Mark a received message as read.

        Args:
            instance_name: Name of the WhatsApp instance
            message_id: ID of the message to mark as read
        """
        pass
