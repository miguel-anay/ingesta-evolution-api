"""
Send Text Message Use Case

Application service for sending text messages via WhatsApp.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ....domain.messaging.entities import Message, MessageType, MessageStatus
from ....domain.messaging.value_objects import PhoneNumber, MessageContent
from ....domain.messaging.exceptions import MessageDeliveryError
from ..ports.whatsapp_gateway import IWhatsAppGateway
from ..ports.message_repository import IMessageRepository
from ..ports.message_event_publisher import IMessageEventPublisher


logger = logging.getLogger(__name__)


@dataclass
class SendTextMessageRequest:
    """Input DTO for sending a text message."""

    instance_name: str
    recipient_number: str
    text: str
    country_code: str = "52"
    reply_to_message_id: Optional[str] = None


@dataclass
class SendTextMessageResponse:
    """Output DTO for send text message result."""

    message_id: str
    external_id: str
    status: str
    recipient: str


class SendTextMessageUseCase:
    """
    Use case for sending text messages via WhatsApp.

    This class orchestrates the domain logic for sending messages:
    1. Validates input and creates domain objects
    2. Sends message via WhatsApp gateway
    3. Persists message to repository
    4. Publishes message sent event

    Dependencies are injected via constructor (Dependency Inversion).
    """

    def __init__(
        self,
        whatsapp_gateway: IWhatsAppGateway,
        message_repository: IMessageRepository,
        event_publisher: IMessageEventPublisher,
    ):
        """
        Initialize use case with required ports.

        Args:
            whatsapp_gateway: Port for sending WhatsApp messages
            message_repository: Port for message persistence
            event_publisher: Port for publishing events
        """
        self._whatsapp_gateway = whatsapp_gateway
        self._message_repository = message_repository
        self._event_publisher = event_publisher

    async def execute(self, request: SendTextMessageRequest) -> SendTextMessageResponse:
        """
        Execute the send text message use case.

        Args:
            request: Input data for sending the message

        Returns:
            Response with message details and status

        Raises:
            InvalidPhoneNumberError: If recipient number is invalid
            InvalidMessageContentError: If message content is invalid
            MessageDeliveryError: If message cannot be sent
        """
        logger.info(
            f"Sending text message to {request.recipient_number} "
            f"via instance {request.instance_name}"
        )

        # Create domain value objects (validation happens here)
        recipient = PhoneNumber(
            number=request.recipient_number,
            country_code=request.country_code,
        )
        content = MessageContent(text=request.text)

        # Create message entity
        message = Message(
            recipient=recipient,
            content=content,
            message_type=MessageType.TEXT,
            reply_to_message_id=request.reply_to_message_id,
        )

        try:
            # Send via WhatsApp gateway
            external_id = await self._whatsapp_gateway.send_text_message(
                instance_name=request.instance_name,
                recipient=recipient,
                content=content,
                reply_to=request.reply_to_message_id,
            )

            # Update message with external ID and status
            message.mark_as_sent(external_id)

            # Persist message
            await self._message_repository.save(message)

            # Publish event
            await self._event_publisher.publish_message_sent(message)

            logger.info(
                f"Message sent successfully. ID: {message.id}, "
                f"External ID: {external_id}"
            )

            return SendTextMessageResponse(
                message_id=str(message.id),
                external_id=external_id,
                status=message.status.value,
                recipient=recipient.full_number,
            )

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            message.mark_as_failed(str(e))

            # Still persist failed message for tracking
            await self._message_repository.save(message)

            # Publish failure event
            await self._event_publisher.publish_message_failed(message, str(e))

            raise MessageDeliveryError(
                message_id=str(message.id),
                reason=str(e),
            )
