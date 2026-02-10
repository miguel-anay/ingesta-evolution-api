"""
In-Memory Instance Repository

Implementation of IInstanceRepository for development and testing.
"""

from typing import Dict, List, Optional
from uuid import UUID
import asyncio

from ....application.instances.ports.instance_repository import IInstanceRepository
from ....domain.instances.entities import Instance, InstanceStatus
from ....domain.instances.value_objects import InstanceName


class InMemoryInstanceRepository(IInstanceRepository):
    """
    In-memory implementation of IInstanceRepository.

    Stores instances in a dictionary. Useful for:
    - Development without database setup
    - Unit testing
    - Quick prototyping

    NOT SUITABLE FOR PRODUCTION - no persistence.
    """

    def __init__(self):
        """Initialize empty instance storage."""
        self._instances: Dict[UUID, Instance] = {}
        self._by_name: Dict[str, UUID] = {}
        self._lock = asyncio.Lock()

    async def save(self, instance: Instance) -> None:
        """Save an instance to memory."""
        async with self._lock:
            self._instances[instance.id] = instance
            self._by_name[str(instance.name)] = instance.id

    async def find_by_id(self, instance_id: UUID) -> Optional[Instance]:
        """Find instance by ID."""
        return self._instances.get(instance_id)

    async def find_by_name(self, name: InstanceName) -> Optional[Instance]:
        """Find instance by name."""
        instance_id = self._by_name.get(str(name))
        if instance_id:
            return self._instances.get(instance_id)
        return None

    async def find_all(self) -> List[Instance]:
        """Get all instances."""
        return list(self._instances.values())

    async def find_by_status(self, status: InstanceStatus) -> List[Instance]:
        """Find instances by status."""
        return [
            inst for inst in self._instances.values()
            if inst.status == status
        ]

    async def delete(self, instance_id: UUID) -> None:
        """Delete an instance."""
        async with self._lock:
            instance = self._instances.pop(instance_id, None)
            if instance:
                self._by_name.pop(str(instance.name), None)

    async def exists_by_name(self, name: InstanceName) -> bool:
        """Check if instance exists by name."""
        return str(name) in self._by_name

    # Utility methods for testing

    async def clear(self) -> None:
        """Clear all instances. For testing only."""
        async with self._lock:
            self._instances.clear()
            self._by_name.clear()

    async def count(self) -> int:
        """Get total instance count."""
        return len(self._instances)
