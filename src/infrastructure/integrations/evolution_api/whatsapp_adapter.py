"""
Evolution API WhatsApp Adapter

Implements IWhatsAppGateway port using Evolution API.
This adapter translates domain concepts to Evolution API calls.
"""

from typing import Optional
import logging

from ....application.messaging.ports.whatsapp_gateway import IWhatsAppGateway
from ....domain.messaging.entities import MessageType
from ....domain.messaging.value_objects import PhoneNumber, MessageContent, MediaAttachment
from ....domain.messaging.exceptions import MessageDeliveryError
from ....domain.instances.exceptions import InstanceNotConnectedError
from .client import EvolutionApiClient
from .exceptions import EvolutionApiError


logger = logging.getLogger(__name__)


class EvolutionApiWhatsAppAdapter(IWhatsAppGateway):
    """
    Adapter implementing IWhatsAppGateway using Evolution API.

    This adapter:
    - Translates domain objects to Evolution API format
    - Handles API responses and errors
    - Maps external IDs back to domain

    IMPORTANT: This is the ONLY place where Evolution API is called
    for message operations. Application layer uses IWhatsAppGateway port.
    """

    # Map MessageType to Evolution API media type
    MEDIA_TYPE_MAP = {
        MessageType.IMAGE: "image",
        MessageType.AUDIO: "audio",
        MessageType.VIDEO: "video",
        MessageType.DOCUMENT: "document",
        MessageType.STICKER: "sticker",
    }

    def __init__(self, client: EvolutionApiClient):
        """
        Initialize adapter with Evolution API client.

        Args:
            client: Configured Evolution API HTTP client
        """
        self._client = client

    async def send_text_message(
        self,
        instance_name: str,
        recipient: PhoneNumber,
        content: MessageContent,
        reply_to: Optional[str] = None,
    ) -> str:
        """Send text message via Evolution API."""
        logger.info(f"Sending text to {recipient.full_number} via {instance_name}")

        options = {}
        if reply_to:
            options["quoted"] = {"key": {"id": reply_to}}

        try:
            response = await self._client.send_text(
                instance_name=instance_name,
                number=recipient.full_number,
                text=str(content),
                options=options if options else None,
            )

            # Extract message ID from response
            message_id = self._extract_message_id(response)
            logger.info(f"Message sent successfully. ID: {message_id}")
            return message_id

        except EvolutionApiError as e:
            logger.error(f"Failed to send message: {e}")
            if e.status_code == 404 or "not connected" in str(e).lower():
                raise InstanceNotConnectedError(instance_name)
            raise MessageDeliveryError(
                message_id="unknown",
                reason=str(e),
            )

    async def send_media_message(
        self,
        instance_name: str,
        recipient: PhoneNumber,
        media: MediaAttachment,
        message_type: MessageType,
        reply_to: Optional[str] = None,
    ) -> str:
        """Send media message via Evolution API."""
        logger.info(
            f"Sending {message_type.value} to {recipient.full_number} "
            f"via {instance_name}"
        )

        media_type = self.MEDIA_TYPE_MAP.get(message_type)
        if not media_type:
            raise ValueError(f"Unsupported media type: {message_type}")

        try:
            response = await self._client.send_media(
                instance_name=instance_name,
                number=recipient.full_number,
                media_type=media_type,
                media_url=media.url,
                caption=media.caption,
                filename=media.filename,
            )

            message_id = self._extract_message_id(response)
            logger.info(f"Media message sent successfully. ID: {message_id}")
            return message_id

        except EvolutionApiError as e:
            logger.error(f"Failed to send media message: {e}")
            if e.status_code == 404 or "not connected" in str(e).lower():
                raise InstanceNotConnectedError(instance_name)
            raise MessageDeliveryError(
                message_id="unknown",
                reason=str(e),
            )

    async def send_location(
        self,
        instance_name: str,
        recipient: PhoneNumber,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> str:
        """Send location message via Evolution API."""
        logger.info(f"Sending location to {recipient.full_number} via {instance_name}")

        try:
            endpoint = f"/message/sendLocation/{instance_name}"
            payload = {
                "number": recipient.full_number,
                "latitude": latitude,
                "longitude": longitude,
                "name": name or "",
                "address": address or "",
            }

            response = await self._client.post(endpoint, payload)
            message_id = self._extract_message_id(response)
            return message_id

        except EvolutionApiError as e:
            logger.error(f"Failed to send location: {e}")
            raise MessageDeliveryError(
                message_id="unknown",
                reason=str(e),
            )

    async def check_number_exists(
        self,
        instance_name: str,
        phone_number: PhoneNumber,
    ) -> bool:
        """Check if phone number has WhatsApp."""
        try:
            response = await self._client.check_is_whatsapp(
                instance_name=instance_name,
                numbers=[phone_number.full_number],
            )

            # Response format: [{"exists": true, "jid": "...@s.whatsapp.net"}]
            if isinstance(response, list) and len(response) > 0:
                return response[0].get("exists", False)
            return False

        except EvolutionApiError as e:
            logger.error(f"Failed to check number: {e}")
            return False

    async def mark_message_as_read(
        self,
        instance_name: str,
        message_id: str,
    ) -> None:
        """Mark message as read in WhatsApp."""
        try:
            endpoint = f"/chat/markMessageAsRead/{instance_name}"
            await self._client.post(endpoint, {"readMessages": [{"id": message_id}]})
        except EvolutionApiError as e:
            logger.warning(f"Failed to mark message as read: {e}")

    def _extract_message_id(self, response: dict) -> str:
        """Extract message ID from Evolution API response."""
        # Response format varies, try common patterns
        if isinstance(response, dict):
            # Try key.id pattern
            if "key" in response and "id" in response["key"]:
                return response["key"]["id"]
            # Try direct id
            if "id" in response:
                return response["id"]
            # Try messageId
            if "messageId" in response:
                return response["messageId"]

        logger.warning(f"Could not extract message ID from response: {response}")
        return str(response.get("key", {}).get("id", "unknown"))
