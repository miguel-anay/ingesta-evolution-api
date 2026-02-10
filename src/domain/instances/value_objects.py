"""
Instance Value Objects

Immutable objects representing instance-related domain concepts.
"""

from dataclasses import dataclass
from datetime import datetime
import re


@dataclass(frozen=True)
class InstanceName:
    """
    Value object representing an instance name.

    Instance names must follow specific rules for Evolution API compatibility.
    """

    value: str

    # Validation rules
    MIN_LENGTH: int = 3
    MAX_LENGTH: int = 50
    PATTERN: re.Pattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')

    def __post_init__(self) -> None:
        """Validate instance name."""
        if not self.value:
            raise ValueError("Instance name cannot be empty")

        if len(self.value) < self.MIN_LENGTH:
            raise ValueError(
                f"Instance name must be at least {self.MIN_LENGTH} characters"
            )

        if len(self.value) > self.MAX_LENGTH:
            raise ValueError(
                f"Instance name cannot exceed {self.MAX_LENGTH} characters"
            )

        if not self.PATTERN.match(self.value):
            raise ValueError(
                "Instance name must start with a letter and contain only "
                "alphanumeric characters, underscores, or hyphens"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class QRCode:
    """
    Value object representing a QR code for WhatsApp authentication.

    QR codes are temporary and expire after a certain time.
    """

    code: str
    base64_image: str
    created_at: datetime

    # QR codes typically expire after 60 seconds
    EXPIRY_SECONDS: int = 60

    def __post_init__(self) -> None:
        """Validate QR code data."""
        if not self.code:
            raise ValueError("QR code cannot be empty")

        if not self.base64_image:
            raise ValueError("QR code base64 image cannot be empty")

    @property
    def is_expired(self) -> bool:
        """Check if the QR code has expired."""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.EXPIRY_SECONDS

    @property
    def seconds_until_expiry(self) -> int:
        """Get seconds remaining until expiry."""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        remaining = self.EXPIRY_SECONDS - elapsed
        return max(0, int(remaining))
