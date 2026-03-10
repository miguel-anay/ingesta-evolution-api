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

        Uses Evolution API as source of truth for instances,
        enriched with local repository data when available.

        Returns:
            Response with all instances and counts
        """
        logger.info("Listing all instances")

        # Get live instances from Evolution API (source of truth)
        api_instances = await self._gateway.list_instances()

        # Get local instances for enrichment
        local_instances = await self._repository.find_all()
        local_map = {
            str(inst.name): inst for inst in local_instances
        }

        summaries = []
        connected_count = 0

        for api_data in api_instances:
            name = api_data.get("instanceName", api_data.get("name", ""))
            connection_status = api_data.get("connectionStatus", "")
            # connectionStatus can be a string ("open") or dict ({"state": "open"})
            if isinstance(connection_status, dict):
                is_connected = connection_status.get("state") == "open"
            else:
                is_connected = connection_status == "open"

            if is_connected:
                connected_count += 1

            # Use local data if available for status
            local_inst = local_map.get(name)
            status = local_inst.status.value if local_inst else ("active" if is_connected else "inactive")
            phone = local_inst.phone_number if local_inst else api_data.get("ownerJid", "").split("@")[0] or None

            summaries.append(
                InstanceSummary(
                    name=name,
                    status=status,
                    connection_state="open" if is_connected else "close",
                    phone_number=phone,
                    is_connected=is_connected,
                )
            )

        return ListInstancesResponse(
            instances=summaries,
            total_count=len(summaries),
            connected_count=connected_count,
        )
