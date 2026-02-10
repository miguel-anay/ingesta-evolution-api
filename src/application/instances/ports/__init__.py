"""
Instance Ports (Interfaces)

Interfaces for instance management infrastructure.
"""

from .instance_gateway import IInstanceGateway
from .instance_repository import IInstanceRepository

__all__ = [
    "IInstanceGateway",
    "IInstanceRepository",
]
