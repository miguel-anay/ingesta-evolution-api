"""
Evolution API Webhook Handler

Receives and processes webhook events from Evolution API.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel
import logging

from ....application.messaging.use_cases import (
    HandleMessageWebhookUseCase,
    HandleWebhookRequest,
)
from ..dependencies import get_webhook_handler_use_case


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookResponseDTO(BaseModel):
    """Response for webhook processing."""

    received: bool
    event_type: str
    processed: bool
    message: str


@router.post(
    "/evolution",
    response_model=WebhookResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Evolution API webhook",
    description="Receive webhook events from Evolution API",
)
async def evolution_webhook(
    request: Request,
    use_case: HandleMessageWebhookUseCase = Depends(get_webhook_handler_use_case),
) -> WebhookResponseDTO:
    """
    Handle incoming webhook from Evolution API.

    Processes events like:
    - messages.upsert: New message received
    - messages.update: Message status changed
    - connection.update: Instance connection changed
    - qrcode.updated: New QR code available
    """
    try:
        # Parse webhook body
        body = await request.json()

        # Extract event information
        event_type = body.get("event", "unknown")
        instance_name = body.get("instance", body.get("instanceName", "unknown"))
        data = body.get("data", body)

        logger.info(f"Webhook received: {event_type} from {instance_name}")
        logger.debug(f"Webhook data: {body}")

        # Process through use case
        webhook_request = HandleWebhookRequest(
            event_type=event_type,
            instance_name=instance_name,
            data=data,
        )

        result = await use_case.execute(webhook_request)

        return WebhookResponseDTO(
            received=True,
            event_type=event_type,
            processed=result.processed,
            message=result.message,
        )

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        # Always return 200 to Evolution API to prevent retries
        return WebhookResponseDTO(
            received=True,
            event_type="unknown",
            processed=False,
            message=f"Error processing webhook: {str(e)}",
        )


@router.post(
    "/evolution/{instance_name}",
    response_model=WebhookResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Instance-specific webhook",
    description="Webhook endpoint with instance name in URL",
)
async def instance_webhook(
    instance_name: str,
    request: Request,
    use_case: HandleMessageWebhookUseCase = Depends(get_webhook_handler_use_case),
) -> WebhookResponseDTO:
    """
    Handle webhook for a specific instance.

    Alternative endpoint format with instance name in URL path.
    """
    try:
        body = await request.json()
        event_type = body.get("event", "unknown")
        data = body.get("data", body)

        logger.info(f"Instance webhook received: {event_type} for {instance_name}")

        webhook_request = HandleWebhookRequest(
            event_type=event_type,
            instance_name=instance_name,
            data=data,
        )

        result = await use_case.execute(webhook_request)

        return WebhookResponseDTO(
            received=True,
            event_type=event_type,
            processed=result.processed,
            message=result.message,
        )

    except Exception as e:
        logger.error(f"Instance webhook error: {e}")
        return WebhookResponseDTO(
            received=True,
            event_type="unknown",
            processed=False,
            message=f"Error: {str(e)}",
        )
