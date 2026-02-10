"""
Delete Instance Use Case

Application service for deleting WhatsApp instances.
"""

from dataclasses import dataclass
import logging

from ....domain.instances.value_objects import InstanceName
from ....domain.instances.exceptions import InstanceNotFoundError
from ..ports.instance_gateway import IInstanceGateway
from ..ports.instance_repository import IInstanceRepository


logger = logging.getLogger(__name__)


@dataclass
class DeleteInstanceRequest:
    """Input DTO for deleting an instance."""

    name: str
    force: bool = False  # Delete even if connected


@dataclass
class DeleteInstanceResponse:
    """Output DTO for instance deletion result."""

    instance_name: str
    deleted: bool
    message: str


class DeleteInstanceUseCase:
    """
    Use case for deleting a WhatsApp instance.

    Removes the instance from both Evolution API and local storage.
    """

    def __init__(
        self,
        instance_gateway: IInstanceGateway,
        instance_repository: IInstanceRepository,
    ):
        self._gateway = instance_gateway
        self._repository = instance_repository

    async def execute(self, request: DeleteInstanceRequest) -> DeleteInstanceResponse:
        """
        Execute the delete instance use case.

        Args:
            request: Contains instance name and force flag

        Returns:
            Response indicating if deletion was successful

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        logger.info(f"Deleting instance: {request.name}")

        instance_name = InstanceName(value=request.name)

        # Get local instance
        instance = await self._repository.find_by_name(instance_name)
        if not instance:
            raise InstanceNotFoundError(request.name)

        # Check if connected and force not set
        if instance.is_connected and not request.force:
            return DeleteInstanceResponse(
                instance_name=request.name,
                deleted=False,
                message="Instance is connected. Use force=true to delete anyway.",
            )

        # Delete from Evolution API
        try:
            await self._gateway.delete_instance(instance_name)
        except Exception as e:
            logger.warning(f"Failed to delete from API (may not exist): {e}")

        # Delete from local repository
        instance.mark_deleted()
        await self._repository.delete(instance.id)

        logger.info(f"Instance deleted successfully: {request.name}")

        return DeleteInstanceResponse(
            instance_name=request.name,
            deleted=True,
            message="Instance deleted successfully",
        )
