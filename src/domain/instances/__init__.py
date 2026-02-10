"""
Instances Domain

Business entities and rules for WhatsApp instance management.
An instance represents a WhatsApp connection/session.
"""

from .entities import Instance, InstanceStatus, ConnectionState
from .value_objects import InstanceName, QRCode
from .exceptions import (
    InstanceDomainError,
    InstanceNotFoundError,
    InstanceNotConnectedError,
    InvalidInstanceNameError,
)

__all__ = [
    "Instance",
    "InstanceStatus",
    "ConnectionState",
    "InstanceName",
    "QRCode",
    "InstanceDomainError",
    "InstanceNotFoundError",
    "InstanceNotConnectedError",
    "InvalidInstanceNameError",
]
