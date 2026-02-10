"""
List Instances Use Case

Application service for listing all WhatsApp instances.
"""

from dataclasses import dataclass
from typing import List, Optional
import logging

from ..ports.instance_gateway import IInstanceGateway
from ..ports.instance_repository import IInstanceRepository


logger = logging.getLogger(__name__)


@dataclass
class InstanceSummary:
    """Summary of a single instance."""

    name: str
    status: str
    connection_state: str
    phone_number: Optional[str]
    is_connected: bool


@dataclass
class ListInstancesResponse:
    """Output DTO for list instances."""

    instances: List[InstanceSummary]
    total_count: int
    connected_count: int


class ListInstancesUseCase:
    """
    Use case for listing all WhatsApp instances.

    Returns summary information for all instances.
    """

    def __init__(
        self,
        instance_gateway: IInstanceGateway,
        instance_repository: IInstanceRepository,
    ):
        self._gateway = instance_gateway
        self._repository = instance_repository

    async def execute(self) -> ListInstancesResponse:
        """
        Execute the list instances use case.

        Returns:
            Response with all instances and counts
        """
        logger.info("Listing all instances")

        # Get instances from local repository
        instances = await self._repository.find_all()

        # Get live status from Evolution API for accuracy
        api_instances = await self._gateway.list_instances()
        api_status_map = {
            inst.get("instanceName", inst.get("name", "")): inst
            for inst in api_instances
        }

        summaries = []
        connected_count = 0

        for instance in instances:
            # Merge with API status if available
            api_data = api_status_map.get(str(instance.name), {})
            is_connected = api_data.get("connectionStatus", {}).get("state") == "open"

            if is_connected:
                connected_count += 1

            summaries.append(
                InstanceSummary(
                    name=str(instance.name),
                    status=instance.status.value,
                    connection_state="open" if is_connected else "close",
                    phone_number=instance.phone_number,
                    is_connected=is_connected,
                )
            )

        return ListInstancesResponse(
            instances=summaries,
            total_count=len(summaries),
            connected_count=connected_count,
        )
