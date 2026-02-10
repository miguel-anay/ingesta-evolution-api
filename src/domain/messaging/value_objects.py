"""
Messaging Value Objects

Immutable objects that represent domain concepts with no identity.
Value objects are compared by their attributes, not by identity.
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass(frozen=True)
class PhoneNumber:
    """
    Value object representing a WhatsApp phone number.

    Encapsulates validation and formatting rules for phone numbers.
    Immutable - any change creates a new instance.
    """

    number: str
    country_code: str = "52"  # Default to Mexico

    def __post_init__(self) -> None:
        """Validate phone number format."""
        # Remove any non-digit characters for validation
        digits_only = re.sub(r'\D', '', self.number)

        if len(digits_only) < 10:
            raise ValueError(
                f"Phone number must have at least 10 digits, got: {len(digits_only)}"
            )

        if len(digits_only) > 15:
            raise ValueError(
                f"Phone number cannot exceed 15 digits, got: {len(digits_only)}"
            )

        # Store normalized version (we need to use object.__setattr__ due to frozen)
        object.__setattr__(self, 'number', digits_only)

    @property
    def full_number(self) -> str:
        """Return full international format number."""
        if self.number.startswith(self.country_code):
            return self.number
        return f"{self.country_code}{self.number}"

    @property
    def whatsapp_id(self) -> str:
        """Return WhatsApp JID format (number@s.whatsapp.net)."""
        return f"{self.full_number}@s.whatsapp.net"

    def __str__(self) -> str:
        return self.full_number


@dataclass(frozen=True)
class MessageContent:
    """
    Value object representing the content of a message.

    Validates message content according to business rules.
    """

    text: str

    MAX_LENGTH: int = 4096  # WhatsApp message limit

    def __post_init__(self) -> None:
        """Validate message content."""
        if not self.text or not self.text.strip():
            raise ValueError("Message content cannot be empty")

        if len(self.text) > self.MAX_LENGTH:
            raise ValueError(
                f"Message exceeds maximum length of {self.MAX_LENGTH} characters"
            )

    @property
    def preview(self) -> str:
        """Return a preview of the message (first 50 chars)."""
        if len(self.text) <= 50:
            return self.text
        return f"{self.text[:47]}..."

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class MediaAttachment:
    """
    Value object representing a media attachment.

    Contains metadata about media files attached to messages.
    """

    url: str
    mime_type: str
    filename: Optional[str] = None
    file_size: Optional[int] = None  # Size in bytes
    caption: Optional[str] = None

    ALLOWED_MIME_TYPES = {
        # Images
        "image/jpeg", "image/png", "image/gif", "image/webp",
        # Audio
        "audio/mpeg", "audio/ogg", "audio/wav", "audio/aac",
        # Video
        "video/mp4", "video/3gpp", "video/quicktime",
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
    }

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

    def __post_init__(self) -> None:
        """Validate media attachment."""
        if not self.url:
            raise ValueError("Media URL cannot be empty")

        if self.mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported mime type: {self.mime_type}")

        if self.file_size and self.file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File size exceeds maximum of {self.MAX_FILE_SIZE // (1024*1024)} MB"
            )

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def is_audio(self) -> bool:
        return self.mime_type.startswith("audio/")

    @property
    def is_video(self) -> bool:
        return self.mime_type.startswith("video/")

    @property
    def is_document(self) -> bool:
        return self.mime_type.startswith("application/") or self.mime_type == "text/plain"
