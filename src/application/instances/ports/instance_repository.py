"""
Instance Repository Port

Interface for instance persistence operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ....domain.instances.entities import Instance, InstanceStatus
from ....domain.instances.value_objects import InstanceName


class IInstanceRepository(ABC):
    """
    Port (interface) for instance persistence.

    Stores local instance metadata and status.
    The actual instance management happens via IInstanceGateway.

    IMPLEMENTATIONS:
    - InMemoryInstanceRepository: For development/testing
    - PostgresInstanceRepository: For production
    """

    @abstractmethod
    async def save(self, instance: Instance) -> None:
        """
        Save an instance.

        Args:
            instance: Instance entity to save
        """
        pass

    @abstractmethod
    async def find_by_id(self, instance_id: UUID) -> Optional[Instance]:
        """
        Find an instance by its ID.

        Args:
            instance_id: UUID of the instance

        Returns:
            Instance if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_name(self, name: InstanceName) -> Optional[Instance]:
        """
        Find an instance by its name.

        Args:
            name: Instance name

        Returns:
            Instance if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_all(self) -> List[Instance]:
        """
        Get all instances.

        Returns:
            List of all instances
        """
        pass

    @abstractmethod
    async def find_by_status(self, status: InstanceStatus) -> List[Instance]:
        """
        Find instances by status.

        Args:
            status: Instance status to filter by

        Returns:
            List of instances with the given status
        """
        pass

    @abstractmethod
    async def delete(self, instance_id: UUID) -> None:
        """
        Delete an instance.

        Args:
            instance_id: UUID of the instance to delete
        """
        pass

    @abstractmethod
    async def exists_by_name(self, name: InstanceName) -> bool:
        """
        Check if an instance with the given name exists.

        Args:
            name: Instance name to check

        Returns:
            True if exists, False otherwise
        """
        pass
