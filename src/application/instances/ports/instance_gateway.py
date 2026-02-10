"""
Instance Gateway Port

Interface for WhatsApp instance management operations via Evolution API.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from ....domain.instances.entities import Instance, InstanceStatus
from ....domain.instances.value_objects import InstanceName, QRCode


class IInstanceGateway(ABC):
    """
    Port (interface) for WhatsApp instance management.

    Provides operations to create, connect, disconnect, and manage
    WhatsApp instances via the underlying API (Evolution API).

    IMPLEMENTATIONS:
    - EvolutionApiInstanceAdapter: Uses Evolution API
    - MockInstanceAdapter: For testing
    """

    @abstractmethod
    async def create_instance(
        self,
        name: InstanceName,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new WhatsApp instance.

        Args:
            name: Name for the new instance
            webhook_url: Optional webhook URL for events

        Returns:
            Instance creation response data

        Raises:
            InstanceAlreadyExistsError: If instance name already exists
        """
        pass

    @abstractmethod
    async def connect_instance(self, name: InstanceName) -> QRCode:
        """
        Initiate connection and get QR code for authentication.

        Args:
            name: Name of the instance to connect

        Returns:
            QR code for WhatsApp authentication

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        pass

    @abstractmethod
    async def disconnect_instance(self, name: InstanceName) -> None:
        """
        Disconnect/logout a connected instance.

        Args:
            name: Name of the instance to disconnect

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        pass

    @abstractmethod
    async def delete_instance(self, name: InstanceName) -> None:
        """
        Delete an instance completely.

        Args:
            name: Name of the instance to delete

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        pass

    @abstractmethod
    async def get_instance_status(self, name: InstanceName) -> Dict[str, Any]:
        """
        Get current status of an instance.

        Args:
            name: Name of the instance

        Returns:
            Status information including connection state

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        pass

    @abstractmethod
    async def list_instances(self) -> List[Dict[str, Any]]:
        """
        List all instances.

        Returns:
            List of instance data
        """
        pass

    @abstractmethod
    async def restart_instance(self, name: InstanceName) -> None:
        """
        Restart an instance.

        Args:
            name: Name of the instance to restart

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        pass

    @abstractmethod
    async def set_webhook(
        self,
        name: InstanceName,
        webhook_url: str,
        events: Optional[List[str]] = None,
    ) -> None:
        """
        Configure webhook for an instance.

        Args:
            name: Name of the instance
            webhook_url: URL to receive webhook events
            events: List of events to subscribe to

        Raises:
            InstanceNotFoundError: If instance doesn't exist
        """
        pass
