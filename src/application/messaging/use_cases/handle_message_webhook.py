"""
Handle Message Webhook Use Case

Application service for processing incoming webhook events from Evolution API.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum
import logging

from ....domain.messaging.entities import MessageStatus
from ..ports.message_repository import IMessageRepository
from ..ports.message_event_publisher import IMessageEventPublisher


logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Types of webhook events from Evolution API."""

    MESSAGES_UPSERT = "messages.upsert"
    MESSAGES_UPDATE = "messages.update"
    MESSAGE_ACK = "message.ack"
    CONNECTION_UPDATE = "connection.update"
    QRCODE_UPDATED = "qrcode.updated"


@dataclass
class HandleWebhookRequest:
    """Input DTO for webhook handling."""

    event_type: str
    instance_name: str
    data: Dict[str, Any]


@dataclass
class HandleWebhookResponse:
    """Output DTO for webhook handling result."""

    processed: bool
    event_type: str
    message: str


class HandleMessageWebhookUseCase:
    """
    Use case for handling incoming webhook events.

    Processes different types of events from Evolution API:
    - Message received (messages.upsert)
    - Message status updates (messages.update, message.ack)
    """

    # Mapping of WhatsApp ACK values to our MessageStatus
    ACK_STATUS_MAP = {
        0: MessageStatus.PENDING,   # Error
        1: MessageStatus.SENT,      # Pending
        2: MessageStatus.SENT,      # Server ACK
        3: MessageStatus.DELIVERED, # Delivered
        4: MessageStatus.READ,      # Read
        5: MessageStatus.READ,      # Played (for audio)
    }

    def __init__(
        self,
        message_repository: IMessageRepository,
        event_publisher: IMessageEventPublisher,
    ):
        self._message_repository = message_repository
        self._event_publisher = event_publisher

    async def execute(self, request: HandleWebhookRequest) -> HandleWebhookResponse:
        """
        Execute webhook handling based on event type.

        Args:
            request: Webhook event data

        Returns:
            Response indicating if event was processed
        """
        logger.info(
            f"Processing webhook event: {request.event_type} "
            f"for instance: {request.instance_name}"
        )

        try:
            event_type = request.event_type.lower()

            if event_type == WebhookEventType.MESSAGES_UPSERT.value:
                await self._handle_message_received(request)
                return HandleWebhookResponse(
                    processed=True,
                    event_type=request.event_type,
                    message="Message received and processed",
                )

            elif event_type in (
                WebhookEventType.MESSAGES_UPDATE.value,
                WebhookEventType.MESSAGE_ACK.value,
            ):
                await self._handle_message_status_update(request)
                return HandleWebhookResponse(
                    processed=True,
                    event_type=request.event_type,
                    message="Message status updated",
                )

            else:
                logger.debug(f"Ignoring unhandled event type: {request.event_type}")
                return HandleWebhookResponse(
                    processed=False,
                    event_type=request.event_type,
                    message=f"Event type not handled: {request.event_type}",
                )

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return HandleWebhookResponse(
                processed=False,
                event_type=request.event_type,
                message=f"Error processing webhook: {str(e)}",
            )

    async def _handle_message_received(self, request: HandleWebhookRequest) -> None:
        """Handle incoming message event."""
        # Publish event for downstream processing
        await self._event_publisher.publish_message_received(
            instance_name=request.instance_name,
            message_data=request.data,
        )
        logger.info(f"Published message received event for instance {request.instance_name}")

    async def _handle_message_status_update(self, request: HandleWebhookRequest) -> None:
        """Handle message status update event."""
        data = request.data

        # Extract message ID and status from webhook data
        message_id = data.get("key", {}).get("id")
        ack = data.get("update", {}).get("status") or data.get("ack")

        if not message_id:
            logger.warning("No message ID in status update webhook")
            return

        # Find message by external ID
        message = await self._message_repository.find_by_external_id(message_id)
        if not message:
            logger.debug(f"Message not found for external ID: {message_id}")
            return

        # Map ACK value to status
        new_status = self.ACK_STATUS_MAP.get(ack)
        if not new_status:
            logger.warning(f"Unknown ACK value: {ack}")
            return

        # Update message status
        old_status = message.status

        if new_status == MessageStatus.DELIVERED:
            message.mark_as_delivered()
            await self._event_publisher.publish_message_delivered(message)
        elif new_status == MessageStatus.READ:
            message.mark_as_read()
            await self._event_publisher.publish_message_read(message)

        # Persist updated message
        await self._message_repository.save(message)

        logger.info(
            f"Message {message_id} status updated: {old_status.value} -> {new_status.value}"
        )
