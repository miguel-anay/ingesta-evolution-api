"""
Connect Instance Use Case

Application service for connecting/authenticating WhatsApp instances.
"""

from dataclasses import dataclass
import logging

from ....domain.instances.value_objects import InstanceName
from ....domain.instances.exceptions import InstanceNotFoundError
from ..ports.instance_gateway import IInstanceGateway
from ..ports.instance_repository import IInstanceRepository


logger = logging.getLogger(__name__)


@dataclass
class ConnectInstanceRequest:
    """Input DTO for connecting an instance."""

    name: str


@dataclass
class ConnectInstanceResponse:
    """Output DTO for instance connection result."""

    instance_name: str
    qr_code: str  # Base64 encoded QR image
    qr_code_raw: str  # Raw QR code string
    expires_in_seconds: int
    message: str


class ConnectInstanceUseCase:
    """
    Use case for initiating WhatsApp connection.

    Returns a QR code that must be scanned with WhatsApp mobile app.
    The QR code expires after ~60 seconds.
    """

    def __init__(
        self,
        instance_gateway: IInstanceGateway,
        instance_repository: IInstanceRepository,
    ):
        self._gateway = instance_gateway
        self._repository = instance_repository

    async def execute(self, request: ConnectInstanceRequest) -> ConnectInstanceResponse:
        """
        Execute the connect instance use case.

        Args:
            request: Contains instance name to connect

        Returns:
            Response with QR code for authentication

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        logger.info(f"Initiating connection for instance: {request.name}")

        instance_name = InstanceName(value=request.name)

        # Verify instance exists locally
        instance = await self._repository.find_by_name(instance_name)
        if not instance:
            raise InstanceNotFoundError(request.name)

        # Get QR code from Evolution API
        qr_code = await self._gateway.connect_instance(instance_name)

        # Update instance with QR code
        instance.update_qr_code(qr_code)
        instance.connect()
        await self._repository.save(instance)

        logger.info(f"QR code generated for instance: {request.name}")

        return ConnectInstanceResponse(
            instance_name=str(instance_name),
            qr_code=qr_code.base64_image,
            qr_code_raw=qr_code.code,
            expires_in_seconds=qr_code.seconds_until_expiry,
            message="Scan QR code with WhatsApp to connect",
        )
