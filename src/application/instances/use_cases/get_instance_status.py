"""
Get Instance Status Use Case

Application service for retrieving instance status.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ....domain.instances.value_objects import InstanceName
from ....domain.instances.exceptions import InstanceNotFoundError
from ..ports.instance_gateway import IInstanceGateway
from ..ports.instance_repository import IInstanceRepository


logger = logging.getLogger(__name__)


@dataclass
class GetInstanceStatusRequest:
    """Input DTO for getting instance status."""

    name: str


@dataclass
class GetInstanceStatusResponse:
    """Output DTO for instance status."""

    instance_name: str
    status: str
    connection_state: str
    phone_number: Optional[str]
    profile_name: Optional[str]
    is_connected: bool
    is_ready_to_send: bool


class GetInstanceStatusUseCase:
    """
    Use case for retrieving instance status.

    Combines local state with live status from Evolution API.
    """

    def __init__(
        self,
        instance_gateway: IInstanceGateway,
        instance_repository: IInstanceRepository,
    ):
        self._gateway = instance_gateway
        self._repository = instance_repository

    async def execute(self, request: GetInstanceStatusRequest) -> GetInstanceStatusResponse:
        """
        Execute the get instance status use case.

        Args:
            request: Contains instance name

        Returns:
            Response with current instance status

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        logger.info(f"Getting status for instance: {request.name}")

        instance_name = InstanceName(value=request.name)

        # Get local instance
        instance = await self._repository.find_by_name(instance_name)
        if not instance:
            raise InstanceNotFoundError(request.name)

        # Get live status from Evolution API
        api_status = await self._gateway.get_instance_status(instance_name)

        # Update local instance with API status
        connection_state = api_status.get("state", "close")

        if connection_state == "open":
            phone = api_status.get("phoneNumber") or api_status.get("number")
            profile = api_status.get("pushName") or api_status.get("profileName")
            instance.mark_connected(phone_number=phone, profile_name=profile)
        elif connection_state == "close":
            instance.disconnect()

        await self._repository.save(instance)

        return GetInstanceStatusResponse(
            instance_name=str(instance_name),
            status=instance.status.value,
            connection_state=instance.connection_state.value,
            phone_number=instance.phone_number,
            profile_name=instance.profile_name,
            is_connected=instance.is_connected,
            is_ready_to_send=instance.is_ready_to_send,
        )
