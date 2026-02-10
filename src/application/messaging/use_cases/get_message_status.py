"""
Get Message Status Use Case

Application service for retrieving message status.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID
import logging

from ....domain.messaging.entities import Message
from ....domain.messaging.exceptions import MessageNotFoundError
from ..ports.message_repository import IMessageRepository


logger = logging.getLogger(__name__)


@dataclass
class GetMessageStatusRequest:
    """Input DTO for getting message status."""

    message_id: Optional[str] = None
    external_id: Optional[str] = None


@dataclass
class GetMessageStatusResponse:
    """Output DTO for message status."""

    message_id: str
    external_id: Optional[str]
    status: str
    recipient: str
    created_at: str
    sent_at: Optional[str]
    delivered_at: Optional[str]
    read_at: Optional[str]


class GetMessageStatusUseCase:
    """
    Use case for retrieving message status.

    Can query by internal ID or external WhatsApp ID.
    """

    def __init__(self, message_repository: IMessageRepository):
        self._message_repository = message_repository

    async def execute(self, request: GetMessageStatusRequest) -> GetMessageStatusResponse:
        """
        Execute the get message status use case.

        Args:
            request: Contains either message_id or external_id

        Returns:
            Response with message status details

        Raises:
            MessageNotFoundError: If message cannot be found
            ValueError: If neither message_id nor external_id provided
        """
        if not request.message_id and not request.external_id:
            raise ValueError("Either message_id or external_id must be provided")

        message: Optional[Message] = None

        if request.message_id:
            logger.info(f"Looking up message by ID: {request.message_id}")
            message = await self._message_repository.find_by_id(
                UUID(request.message_id)
            )
        elif request.external_id:
            logger.info(f"Looking up message by external ID: {request.external_id}")
            message = await self._message_repository.find_by_external_id(
                request.external_id
            )

        if not message:
            identifier = request.message_id or request.external_id
            raise MessageNotFoundError(message_id=identifier)

        return GetMessageStatusResponse(
            message_id=str(message.id),
            external_id=message.external_id,
            status=message.status.value,
            recipient=message.recipient.full_number,
            created_at=message.created_at.isoformat(),
            sent_at=message.sent_at.isoformat() if message.sent_at else None,
            delivered_at=message.delivered_at.isoformat() if message.delivered_at else None,
            read_at=message.read_at.isoformat() if message.read_at else None,
        )
