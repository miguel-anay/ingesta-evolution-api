"""
Create Instance Use Case

Application service for creating new WhatsApp instances.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ....domain.instances.entities import Instance
from ....domain.instances.value_objects import InstanceName
from ....domain.instances.exceptions import InstanceAlreadyExistsError
from ..ports.instance_gateway import IInstanceGateway
from ..ports.instance_repository import IInstanceRepository


logger = logging.getLogger(__name__)


@dataclass
class CreateInstanceRequest:
    """Input DTO for creating an instance."""

    name: str
    webhook_url: Optional[str] = None


@dataclass
class CreateInstanceResponse:
    """Output DTO for instance creation result."""

    instance_id: str
    name: str
    status: str
    message: str


class CreateInstanceUseCase:
    """
    Use case for creating a new WhatsApp instance.

    Flow:
    1. Validate instance name
    2. Check if instance already exists
    3. Create instance via gateway (Evolution API)
    4. Persist instance locally
    """

    def __init__(
        self,
        instance_gateway: IInstanceGateway,
        instance_repository: IInstanceRepository,
    ):
        self._gateway = instance_gateway
        self._repository = instance_repository

    async def execute(self, request: CreateInstanceRequest) -> CreateInstanceResponse:
        """
        Execute the create instance use case.

        Args:
            request: Instance creation parameters

        Returns:
            Response with created instance details

        Raises:
            InvalidInstanceNameError: If name is invalid
            InstanceAlreadyExistsError: If name is taken
        """
        logger.info(f"Creating new instance: {request.name}")

        # Create and validate instance name
        instance_name = InstanceName(value=request.name)

        # Check if instance already exists locally
        if await self._repository.exists_by_name(instance_name):
            raise InstanceAlreadyExistsError(request.name)

        # Create instance via Evolution API
        api_response = await self._gateway.create_instance(
            name=instance_name,
            webhook_url=request.webhook_url,
        )

        # Create domain entity
        instance = Instance(
            name=instance_name,
            webhook_url=request.webhook_url,
        )

        # Persist locally
        await self._repository.save(instance)

        logger.info(f"Instance created successfully: {instance.id}")

        return CreateInstanceResponse(
            instance_id=str(instance.id),
            name=str(instance_name),
            status=instance.status.value,
            message="Instance created successfully. Use connect to get QR code.",
        )
