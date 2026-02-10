"""
Contacts Domain

Business entities and rules for WhatsApp contact management.
"""

from .entities import Contact
from .value_objects import ContactName
from .exceptions import ContactDomainError, ContactNotFoundError

__all__ = [
    "Contact",
    "ContactName",
    "ContactDomainError",
    "ContactNotFoundError",
]
