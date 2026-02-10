"""
Contact Value Objects

Immutable objects representing contact-related domain concepts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContactName:
    """
    Value object representing a contact's custom name.

    This is the name assigned by the user, not the push name from WhatsApp.
    """

    first_name: str
    last_name: str = ""

    MAX_LENGTH: int = 100

    def __post_init__(self) -> None:
        """Validate contact name."""
        if not self.first_name or not self.first_name.strip():
            raise ValueError("First name cannot be empty")

        full_length = len(self.first_name) + len(self.last_name)
        if full_length > self.MAX_LENGTH:
            raise ValueError(
                f"Contact name cannot exceed {self.MAX_LENGTH} characters"
            )

    @property
    def full_name(self) -> str:
        """Get the full name."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def __str__(self) -> str:
        return self.full_name
