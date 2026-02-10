"""
Messaging Domain Exceptions

Domain-specific exceptions for the messaging capability.
These exceptions represent business rule violations.
"""


class MessagingDomainError(Exception):
    """Base exception for messaging domain errors."""

    def __init__(self, message: str, code: str = "MESSAGING_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InvalidPhoneNumberError(MessagingDomainError):
    """Raised when a phone number is invalid."""

    def __init__(self, phone_number: str, reason: str = "Invalid format"):
        super().__init__(
            message=f"Invalid phone number '{phone_number}': {reason}",
            code="INVALID_PHONE_NUMBER"
        )
        self.phone_number = phone_number
        self.reason = reason


class InvalidMessageContentError(MessagingDomainError):
    """Raised when message content is invalid."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Invalid message content: {reason}",
            code="INVALID_MESSAGE_CONTENT"
        )
        self.reason = reason


class MessageNotFoundError(MessagingDomainError):
    """Raised when a message cannot be found."""

    def __init__(self, message_id: str):
        super().__init__(
            message=f"Message not found: {message_id}",
            code="MESSAGE_NOT_FOUND"
        )
        self.message_id = message_id


class MessageDeliveryError(MessagingDomainError):
    """Raised when message delivery fails."""

    def __init__(self, message_id: str, reason: str):
        super().__init__(
            message=f"Failed to deliver message {message_id}: {reason}",
            code="MESSAGE_DELIVERY_FAILED"
        )
        self.message_id = message_id
        self.reason = reason
