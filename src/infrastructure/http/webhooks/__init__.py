"""
Webhook Handlers

Endpoints for receiving webhooks from Evolution API.
"""

from .evolution_webhook import router as webhook_router

__all__ = ["webhook_router"]
