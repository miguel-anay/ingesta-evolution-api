"""
Instance Domain Entities

Core business entities for WhatsApp instance/session management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from .value_objects import InstanceName, QRCode


class InstanceStatus(Enum):
    """Overall status of an instance."""

    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DELETED = "deleted"


class ConnectionState(Enum):
    """Detailed connection state from WhatsApp."""

    OPEN = "open"
    CLOSE = "close"
    CONNECTING = "connecting"
    REFUSED = "refused"


@dataclass
class Instance:
    """
    Domain entity representing a WhatsApp instance/session.

    An instance is a connection to WhatsApp through Evolution API.
    Each instance can send/receive messages independently.
    """

    name: InstanceName
    id: UUID = field(default_factory=uuid4)
    status: InstanceStatus = InstanceStatus.CREATED
    connection_state: ConnectionState = ConnectionState.CLOSE
    phone_number: Optional[str] = None
    qr_code: Optional[QRCode] = None
    profile_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    connected_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    webhook_url: Optional[str] = None

    def connect(self) -> None:
        """Initiate connection process."""
        if self.status == InstanceStatus.DELETED:
            raise ValueError("Cannot connect deleted instance")
        self.status = InstanceStatus.CONNECTING
        self.connection_state = ConnectionState.CONNECTING

    def mark_connected(self, phone_number: str, profile_name: Optional[str] = None) -> None:
        """Mark instance as successfully connected."""
        self.status = InstanceStatus.CONNECTED
        self.connection_state = ConnectionState.OPEN
        self.phone_number = phone_number
        self.profile_name = profile_name
        self.connected_at = datetime.utcnow()
        self.last_seen_at = datetime.utcnow()
        self.qr_code = None  # Clear QR code once connected

    def disconnect(self) -> None:
        """Disconnect the instance."""
        self.status = InstanceStatus.DISCONNECTED
        self.connection_state = ConnectionState.CLOSE
        self.last_seen_at = datetime.utcnow()

    def update_qr_code(self, qr_code: QRCode) -> None:
        """Update the QR code for authentication."""
        if self.status == InstanceStatus.CONNECTED:
            raise ValueError("Cannot update QR code for connected instance")
        self.qr_code = qr_code
        self.status = InstanceStatus.CONNECTING

    def mark_deleted(self) -> None:
        """Mark instance as deleted."""
        self.status = InstanceStatus.DELETED
        self.connection_state = ConnectionState.CLOSE

    def update_last_seen(self) -> None:
        """Update the last seen timestamp."""
        self.last_seen_at = datetime.utcnow()

    @property
    def is_connected(self) -> bool:
        """Check if instance is currently connected."""
        return (
            self.status == InstanceStatus.CONNECTED
            and self.connection_state == ConnectionState.OPEN
        )

    @property
    def is_ready_to_send(self) -> bool:
        """Check if instance is ready to send messages."""
        return self.is_connected and self.phone_number is not None

    @property
    def needs_qr_scan(self) -> bool:
        """Check if instance needs QR code scanning."""
        return (
            self.status == InstanceStatus.CONNECTING
            and self.qr_code is not None
            and not self.is_connected
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instance):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
