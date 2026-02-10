"""
Image Ingestion Value Objects

Immutable objects that represent domain concepts with no identity.
Value objects are compared by their attributes, not by identity.

These are PURE domain objects with NO external dependencies.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final
import re


class SourceType(Enum):
    """Type of source from which image was obtained."""

    CHAT = "chat"
    STATUS = "estado"  # User status/stories

    @classmethod
    def from_string(cls, value: str) -> "SourceType":
        """Create SourceType from string value."""
        normalized = value.lower().strip()
        if normalized in ("chat", "mensaje"):
            return cls.CHAT
        if normalized in ("estado", "status", "story", "stories"):
            return cls.STATUS
        raise ValueError(f"Invalid source type: {value}")


@dataclass(frozen=True)
class SequentialId:
    """
    Value object representing a unique sequential identifier.

    The sequential ID is:
    - Unique across all images
    - Never reset between service executions
    - Always positive integer starting from 1
    """

    value: int

    def __post_init__(self) -> None:
        """Validate sequential ID."""
        if self.value < 1:
            raise ValueError(
                f"Sequential ID must be a positive integer, got: {self.value}"
            )

    def next(self) -> "SequentialId":
        """Return the next sequential ID."""
        return SequentialId(self.value + 1)

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class ImageHash:
    """
    Value object representing an image hash for deduplication.

    Uses SHA-256 hash of image content to detect duplicates.
    """

    value: str

    # SHA-256 produces 64 hexadecimal characters
    HASH_LENGTH: Final[int] = 64
    HASH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-fA-F0-9]{64}$")

    def __post_init__(self) -> None:
        """Validate hash format."""
        if not self.value:
            raise ValueError("Image hash cannot be empty")

        normalized = self.value.lower()
        if not self.HASH_PATTERN.match(normalized):
            raise ValueError(
                f"Invalid hash format. Expected 64 hexadecimal characters, "
                f"got: {len(self.value)} characters"
            )

        # Store normalized lowercase version
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImageHash):
            return False
        return self.value.lower() == other.value.lower()


@dataclass(frozen=True)
class ImagePath:
    """
    Value object representing the path to a stored image.

    Follows the naming convention: {sequential_id}.jpg
    """

    base_directory: str
    filename: str

    def __post_init__(self) -> None:
        """Validate path components."""
        if not self.base_directory:
            raise ValueError("Base directory cannot be empty")

        if not self.filename:
            raise ValueError("Filename cannot be empty")

        # Validate filename format (must be number.jpg)
        if not re.match(r"^\d+\.jpg$", self.filename):
            raise ValueError(
                f"Invalid filename format. Expected '<number>.jpg', got: {self.filename}"
            )

    @classmethod
    def from_sequential_id(
        cls, base_directory: str, sequential_id: SequentialId
    ) -> "ImagePath":
        """Create ImagePath from a sequential ID."""
        filename = f"{sequential_id.value}.jpg"
        return cls(base_directory=base_directory, filename=filename)

    @property
    def full_path(self) -> str:
        """Return the full path to the image file."""
        # Normalize path separators
        base = self.base_directory.rstrip("/\\")
        return f"{base}/{self.filename}"

    def __str__(self) -> str:
        return self.full_path


@dataclass(frozen=True)
class MessageId:
    """
    Value object representing a message or status ID from Evolution API.

    This ID is used for idempotency checks - if a message ID exists,
    the image has already been processed.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate message ID."""
        if not self.value:
            raise ValueError("Message ID cannot be empty")

        if len(self.value) > 500:
            raise ValueError(
                f"Message ID too long. Maximum 500 characters, got: {len(self.value)}"
            )

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageId):
            return False
        return self.value == other.value


@dataclass(frozen=True)
class PhoneNumber:
    """
    Value object representing a WhatsApp phone number.

    Encapsulates validation and formatting rules for phone numbers.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate and normalize phone number."""
        if not self.value:
            raise ValueError("Phone number cannot be empty")

        # Remove common separators and non-digit characters except +
        cleaned = re.sub(r"[^\d+]", "", self.value)

        # Remove leading + if present
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]

        if len(cleaned) < 10:
            raise ValueError(
                f"Phone number must have at least 10 digits, got: {len(cleaned)}"
            )

        if len(cleaned) > 15:
            raise ValueError(
                f"Phone number cannot exceed 15 digits, got: {len(cleaned)}"
            )

        # Store normalized version
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class UserName:
    """
    Value object representing a user's display name.

    Can be empty if user has no display name set.
    """

    value: str

    MAX_LENGTH: Final[int] = 256

    def __post_init__(self) -> None:
        """Validate user name."""
        if len(self.value) > self.MAX_LENGTH:
            # Truncate silently for display names
            object.__setattr__(self, "value", self.value[: self.MAX_LENGTH])

    def __str__(self) -> str:
        return self.value

    @property
    def is_empty(self) -> bool:
        """Check if user name is empty or whitespace only."""
        return not self.value or not self.value.strip()


@dataclass(frozen=True)
class Instance:
    """
    Value object representing an Evolution API instance identifier.

    This identifies the WhatsApp instance from which images are ingested.
    Required for all ingestion operations.
    """

    value: str

    MIN_LENGTH: Final[int] = 1
    MAX_LENGTH: Final[int] = 100

    def __post_init__(self) -> None:
        """Validate instance identifier."""
        if not self.value:
            raise ValueError("Instance identifier cannot be empty")

        stripped = self.value.strip()
        if not stripped:
            raise ValueError("Instance identifier cannot be whitespace only")

        if len(stripped) < self.MIN_LENGTH:
            raise ValueError(
                f"Instance identifier must be at least {self.MIN_LENGTH} character(s)"
            )

        if len(stripped) > self.MAX_LENGTH:
            raise ValueError(
                f"Instance identifier cannot exceed {self.MAX_LENGTH} characters"
            )

        # Store normalized (stripped) version
        object.__setattr__(self, "value", stripped)

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instance):
            return False
        return self.value == other.value
