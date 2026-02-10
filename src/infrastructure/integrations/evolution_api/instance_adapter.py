"""
Evolution API Instance Adapter

Implements IInstanceGateway port using Evolution API.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from ....application.instances.ports.instance_gateway import IInstanceGateway
from ....domain.instances.value_objects import InstanceName, QRCode
from ....domain.instances.exceptions import (
    InstanceNotFoundError,
    InstanceAlreadyExistsError,
    InstanceConnectionError,
)
from .client import EvolutionApiClient
from .exceptions import EvolutionApiError, EvolutionApiNotFoundError


logger = logging.getLogger(__name__)


class EvolutionApiInstanceAdapter(IInstanceGateway):
    """
    Adapter implementing IInstanceGateway using Evolution API.

    Handles all instance management operations:
    - Creating/deleting instances
    - Connection management
    - QR code generation
    - Status retrieval
    """

    def __init__(self, client: EvolutionApiClient):
        """
        Initialize adapter with Evolution API client.

        Args:
            client: Configured Evolution API HTTP client
        """
        self._client = client

    async def create_instance(
        self,
        name: InstanceName,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new WhatsApp instance via Evolution API."""
        logger.info(f"Creating instance: {name}")

        try:
            response = await self._client.create_instance(
                instance_name=str(name),
                webhook_url=webhook_url,
            )

            logger.info(f"Instance created: {response}")
            return response

        except EvolutionApiError as e:
            if "already exists" in str(e).lower():
                raise InstanceAlreadyExistsError(str(name))
            raise

    async def connect_instance(self, name: InstanceName) -> QRCode:
        """Get QR code for instance authentication."""
        logger.info(f"Connecting instance: {name}")

        try:
            response = await self._client.connect_instance(str(name))

            # Extract QR code data from response
            qr_code_data = response.get("qrcode", response.get("code", ""))
            base64_image = response.get("base64", "")

            # If base64 not in response, try to get it from pairingCode
            if not base64_image and "pairingCode" in response:
                # Some versions return different format
                base64_image = response.get("pairingCode", "")

            qr_code = QRCode(
                code=qr_code_data,
                base64_image=base64_image or qr_code_data,
                created_at=datetime.utcnow(),
            )

            logger.info(f"QR code generated for instance: {name}")
            return qr_code

        except EvolutionApiNotFoundError:
            raise InstanceNotFoundError(str(name))
        except EvolutionApiError as e:
            raise InstanceConnectionError(str(name), str(e))

    async def disconnect_instance(self, name: InstanceName) -> None:
        """Disconnect/logout an instance."""
        logger.info(f"Disconnecting instance: {name}")

        try:
            await self._client.logout_instance(str(name))
            logger.info(f"Instance disconnected: {name}")
        except EvolutionApiNotFoundError:
            raise InstanceNotFoundError(str(name))

    async def delete_instance(self, name: InstanceName) -> None:
        """Delete an instance."""
        logger.info(f"Deleting instance: {name}")

        try:
            await self._client.delete_instance(str(name))
            logger.info(f"Instance deleted: {name}")
        except EvolutionApiNotFoundError:
            raise InstanceNotFoundError(str(name))

    async def get_instance_status(self, name: InstanceName) -> Dict[str, Any]:
        """Get current status of an instance."""
        logger.info(f"Getting status for instance: {name}")

        try:
            response = await self._client.get_instance_status(str(name))
            return response
        except EvolutionApiNotFoundError:
            raise InstanceNotFoundError(str(name))

    async def list_instances(self) -> List[Dict[str, Any]]:
        """List all instances."""
        logger.info("Listing all instances")

        response = await self._client.list_instances()

        # Response can be a list or dict with instances key
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("instances", response.get("data", []))
        return []

    async def restart_instance(self, name: InstanceName) -> None:
        """Restart an instance."""
        logger.info(f"Restarting instance: {name}")

        try:
            endpoint = f"/instance/restart/{name}"
            await self._client.put(endpoint)
            logger.info(f"Instance restarted: {name}")
        except EvolutionApiNotFoundError:
            raise InstanceNotFoundError(str(name))

    async def set_webhook(
        self,
        name: InstanceName,
        webhook_url: str,
        events: Optional[List[str]] = None,
    ) -> None:
        """Configure webhook for an instance."""
        logger.info(f"Setting webhook for instance: {name}")

        default_events = [
            "MESSAGES_UPSERT",
            "MESSAGES_UPDATE",
            "CONNECTION_UPDATE",
            "QRCODE_UPDATED",
            "MESSAGES_DELETE",
        ]

        try:
            endpoint = f"/webhook/set/{name}"
            payload = {
                "webhook": {
                    "enabled": True,
                    "url": webhook_url,
                    "events": events or default_events,
                }
            }
            await self._client.post(endpoint, payload)
            logger.info(f"Webhook configured for instance: {name}")
        except EvolutionApiNotFoundError:
            raise InstanceNotFoundError(str(name))
