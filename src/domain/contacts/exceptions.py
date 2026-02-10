"""
Contact Domain Exceptions

Domain-specific exceptions for contact management.
"""


class ContactDomainError(Exception):
    """Base exception for contact domain errors."""

    def __init__(self, message: str, code: str = "CONTACT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ContactNotFoundError(ContactDomainError):
    """Raised when a contact cannot be found."""

    def __init__(self, identifier: str):
        super().__init__(
            message=f"Contact not found: {identifier}",
            code="CONTACT_NOT_FOUND"
        )
        self.identifier = identifier


class ContactBlockedError(ContactDomainError):
    """Raised when trying to interact with a blocked contact."""

    def __init__(self, phone_number: str):
        super().__init__(
            message=f"Contact is blocked: {phone_number}",
            code="CONTACT_BLOCKED"
        )
        self.phone_number = phone_number
