"""
Send Media Message Use Case

Application service for sending media messages (images, videos, documents) via WhatsApp.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ....domain.messaging.entities import Message, MessageType, MessageStatus
from ....domain.messaging.value_objects import PhoneNumber, MessageContent, MediaAttachment
from ....domain.messaging.exceptions import MessageDeliveryError
from ..ports.whatsapp_gateway import IWhatsAppGateway
from ..ports.message_repository import IMessageRepository
from ..ports.message_event_publisher import IMessageEventPublisher


logger = logging.getLogger(__name__)


@dataclass
class SendMediaMessageRequest:
    """Input DTO for sending a media message."""

    instance_name: str
    recipient_number: str
    media_url: str
    mime_type: str
    message_type: str  # "image", "audio", "video", "document"
    caption: Optional[str] = None
    filename: Optional[str] = None
    country_code: str = "52"
    reply_to_message_id: Optional[str] = None


@dataclass
class SendMediaMessageResponse:
    """Output DTO for send media message result."""

    message_id: str
    external_id: str
    status: str
    recipient: str
    media_type: str


class SendMediaMessageUseCase:
    """
    Use case for sending media messages via WhatsApp.

    Supports sending images, audio, video, and document files.
    """

    MESSAGE_TYPE_MAP = {
        "image": MessageType.IMAGE,
        "audio": MessageType.AUDIO,
        "video": MessageType.VIDEO,
        "document": MessageType.DOCUMENT,
        "sticker": MessageType.STICKER,
    }

    def __init__(
        self,
        whatsapp_gateway: IWhatsAppGateway,
        message_repository: IMessageRepository,
        event_publisher: IMessageEventPublisher,
    ):
        self._whatsapp_gateway = whatsapp_gateway
        self._message_repository = message_repository
        self._event_publisher = event_publisher

    async def execute(self, request: SendMediaMessageRequest) -> SendMediaMessageResponse:
        """
        Execute the send media message use case.

        Args:
            request: Input data for sending the media message

        Returns:
            Response with message details and status
        """
        logger.info(
            f"Sending {request.message_type} message to {request.recipient_number} "
            f"via instance {request.instance_name}"
        )

        # Validate and map message type
        message_type = self.MESSAGE_TYPE_MAP.get(request.message_type.lower())
        if not message_type:
            raise ValueError(f"Unsupported message type: {request.message_type}")

        # Create domain value objects
        recipient = PhoneNumber(
            number=request.recipient_number,
            country_code=request.country_code,
        )

        media = MediaAttachment(
            url=request.media_url,
            mime_type=request.mime_type,
            filename=request.filename,
            caption=request.caption,
        )

        # Create placeholder content for media messages
        content = MessageContent(
            text=request.caption if request.caption else f"[{request.message_type}]"
        )

        # Create message entity
        message = Message(
            recipient=recipient,
            content=content,
            message_type=message_type,
            media=media,
            reply_to_message_id=request.reply_to_message_id,
        )

        try:
            # Send via WhatsApp gateway
            external_id = await self._whatsapp_gateway.send_media_message(
                instance_name=request.instance_name,
                recipient=recipient,
                media=media,
                message_type=message_type,
                reply_to=request.reply_to_message_id,
            )

            message.mark_as_sent(external_id)
            await self._message_repository.save(message)
            await self._event_publisher.publish_message_sent(message)

            logger.info(f"Media message sent successfully. ID: {message.id}")

            return SendMediaMessageResponse(
                message_id=str(message.id),
                external_id=external_id,
                status=message.status.value,
                recipient=recipient.full_number,
                media_type=request.message_type,
            )

        except Exception as e:
            logger.error(f"Failed to send media message: {e}")
            message.mark_as_failed(str(e))
            await self._message_repository.save(message)
            await self._event_publisher.publish_message_failed(message, str(e))
            raise MessageDeliveryError(
                message_id=str(message.id),
                reason=str(e),
            )
