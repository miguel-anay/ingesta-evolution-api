"""
Messaging Routes

FastAPI routes for messaging operations.
These routes are thin controllers that delegate to use cases.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ....application.messaging.use_cases import (
    SendTextMessageUseCase,
    SendTextMessageRequest,
    SendMediaMessageUseCase,
    SendMediaMessageRequest,
    GetMessageStatusUseCase,
    GetMessageStatusRequest,
)
from ....domain.messaging.exceptions import (
    InvalidPhoneNumberError,
    InvalidMessageContentError,
    MessageNotFoundError,
    MessageDeliveryError,
)
from ....domain.instances.exceptions import InstanceNotConnectedError
from ..dependencies import get_send_text_use_case, get_send_media_use_case, get_message_status_use_case


router = APIRouter(prefix="/messages", tags=["Messaging"])


# Request/Response DTOs for API

class SendTextMessageDTO(BaseModel):
    """Request body for sending text message."""

    instance_name: str = Field(..., description="Name of the WhatsApp instance")
    recipient: str = Field(..., description="Recipient phone number")
    text: str = Field(..., min_length=1, max_length=4096, description="Message text")
    country_code: str = Field(default="52", description="Country code (default: Mexico)")
    reply_to: Optional[str] = Field(default=None, description="Message ID to reply to")

    model_config = {
        "json_schema_extra": {
            "example": {
                "instance_name": "my-instance",
                "recipient": "5551234567",
                "text": "Hello from the API!",
                "country_code": "52",
            }
        }
    }


class SendMediaMessageDTO(BaseModel):
    """Request body for sending media message."""

    instance_name: str = Field(..., description="Name of the WhatsApp instance")
    recipient: str = Field(..., description="Recipient phone number")
    media_url: str = Field(..., description="URL of the media file")
    mime_type: str = Field(..., description="MIME type of the media")
    media_type: str = Field(..., description="Type: image, audio, video, document")
    caption: Optional[str] = Field(default=None, description="Optional caption")
    filename: Optional[str] = Field(default=None, description="Filename for documents")
    country_code: str = Field(default="52", description="Country code")
    reply_to: Optional[str] = Field(default=None, description="Message ID to reply to")

    model_config = {
        "json_schema_extra": {
            "example": {
                "instance_name": "my-instance",
                "recipient": "5551234567",
                "media_url": "https://example.com/image.jpg",
                "mime_type": "image/jpeg",
                "media_type": "image",
                "caption": "Check this out!",
            }
        }
    }


class MessageResponseDTO(BaseModel):
    """Response for message operations."""

    message_id: str
    external_id: str
    status: str
    recipient: str


class MessageStatusResponseDTO(BaseModel):
    """Response for message status query."""

    message_id: str
    external_id: Optional[str]
    status: str
    recipient: str
    created_at: str
    sent_at: Optional[str]
    delivered_at: Optional[str]
    read_at: Optional[str]


class ErrorResponseDTO(BaseModel):
    """Error response format."""

    error: str
    code: str
    detail: Optional[str] = None


@router.post(
    "/text",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponseDTO, "description": "Invalid request"},
        404: {"model": ErrorResponseDTO, "description": "Instance not found or not connected"},
        500: {"model": ErrorResponseDTO, "description": "Server error"},
    },
    summary="Send text message",
    description="Send a text message via WhatsApp",
)
async def send_text_message(
    body: SendTextMessageDTO,
    use_case: SendTextMessageUseCase = Depends(get_send_text_use_case),
) -> MessageResponseDTO:
    """
    Send a text message to a WhatsApp number.

    The instance must be connected before sending messages.
    """
    try:
        request = SendTextMessageRequest(
            instance_name=body.instance_name,
            recipient_number=body.recipient,
            text=body.text,
            country_code=body.country_code,
            reply_to_message_id=body.reply_to,
        )

        result = await use_case.execute(request)

        return MessageResponseDTO(
            message_id=result.message_id,
            external_id=result.external_id,
            status=result.status,
            recipient=result.recipient,
        )

    except InvalidPhoneNumberError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "code": e.code},
        )
    except InvalidMessageContentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "code": e.code},
        )
    except InstanceNotConnectedError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "code": e.code},
        )
    except MessageDeliveryError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "code": e.code},
        )


@router.post(
    "/media",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Send media message",
    description="Send a media message (image, audio, video, document)",
)
async def send_media_message(
    body: SendMediaMessageDTO,
    use_case: SendMediaMessageUseCase = Depends(get_send_media_use_case),
) -> MessageResponseDTO:
    """
    Send a media message to a WhatsApp number.

    Supported types: image, audio, video, document.
    """
    try:
        request = SendMediaMessageRequest(
            instance_name=body.instance_name,
            recipient_number=body.recipient,
            media_url=body.media_url,
            mime_type=body.mime_type,
            message_type=body.media_type,
            caption=body.caption,
            filename=body.filename,
            country_code=body.country_code,
            reply_to_message_id=body.reply_to,
        )

        result = await use_case.execute(request)

        return MessageResponseDTO(
            message_id=result.message_id,
            external_id=result.external_id,
            status=result.status,
            recipient=result.recipient,
        )

    except (InvalidPhoneNumberError, InvalidMessageContentError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "INVALID_REQUEST"},
        )
    except InstanceNotConnectedError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "code": e.code},
        )


@router.get(
    "/{message_id}/status",
    response_model=MessageStatusResponseDTO,
    summary="Get message status",
    description="Get the current status of a message",
)
async def get_message_status(
    message_id: str,
    use_case: GetMessageStatusUseCase = Depends(get_message_status_use_case),
) -> MessageStatusResponseDTO:
    """
    Get the status of a sent message.

    Returns delivery status (pending, sent, delivered, read, failed).
    """
    try:
        request = GetMessageStatusRequest(message_id=message_id)
        result = await use_case.execute(request)

        return MessageStatusResponseDTO(
            message_id=result.message_id,
            external_id=result.external_id,
            status=result.status,
            recipient=result.recipient,
            created_at=result.created_at,
            sent_at=result.sent_at,
            delivered_at=result.delivered_at,
            read_at=result.read_at,
        )

    except MessageNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "code": e.code},
        )
