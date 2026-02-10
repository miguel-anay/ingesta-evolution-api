"""
Contact Domain Entities

Core business entities for contact management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from .value_objects import ContactName
from ..messaging.value_objects import PhoneNumber


@dataclass
class Contact:
    """
    Domain entity representing a WhatsApp contact.

    Contains profile information synced from WhatsApp.
    """

    phone_number: PhoneNumber
    id: UUID = field(default_factory=uuid4)
    name: Optional[ContactName] = None
    push_name: Optional[str] = None  # Name set by the contact in their profile
    profile_picture_url: Optional[str] = None
    is_business: bool = False
    is_blocked: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_interaction_at: Optional[datetime] = None

    @property
    def display_name(self) -> str:
        """Get the best available name for display."""
        if self.name:
            return str(self.name)
        if self.push_name:
            return self.push_name
        return str(self.phone_number)

    def update_profile(
        self,
        push_name: Optional[str] = None,
        profile_picture_url: Optional[str] = None,
        is_business: Optional[bool] = None,
    ) -> None:
        """Update contact profile information."""
        if push_name is not None:
            self.push_name = push_name
        if profile_picture_url is not None:
            self.profile_picture_url = profile_picture_url
        if is_business is not None:
            self.is_business = is_business
        self.updated_at = datetime.utcnow()

    def set_name(self, name: ContactName) -> None:
        """Set a custom name for the contact."""
        self.name = name
        self.updated_at = datetime.utcnow()

    def block(self) -> None:
        """Block this contact."""
        self.is_blocked = True
        self.updated_at = datetime.utcnow()

    def unblock(self) -> None:
        """Unblock this contact."""
        self.is_blocked = False
        self.updated_at = datetime.utcnow()

    def record_interaction(self) -> None:
        """Record an interaction with this contact."""
        self.last_interaction_at = datetime.utcnow()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Contact):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
