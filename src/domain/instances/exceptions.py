"""
Instance Domain Exceptions

Domain-specific exceptions for instance management.
"""


class InstanceDomainError(Exception):
    """Base exception for instance domain errors."""

    def __init__(self, message: str, code: str = "INSTANCE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InstanceNotFoundError(InstanceDomainError):
    """Raised when an instance cannot be found."""

    def __init__(self, instance_name: str):
        super().__init__(
            message=f"Instance not found: {instance_name}",
            code="INSTANCE_NOT_FOUND"
        )
        self.instance_name = instance_name


class InstanceNotConnectedError(InstanceDomainError):
    """Raised when trying to perform action on disconnected instance."""

    def __init__(self, instance_name: str):
        super().__init__(
            message=f"Instance is not connected: {instance_name}",
            code="INSTANCE_NOT_CONNECTED"
        )
        self.instance_name = instance_name


class InvalidInstanceNameError(InstanceDomainError):
    """Raised when instance name is invalid."""

    def __init__(self, name: str, reason: str):
        super().__init__(
            message=f"Invalid instance name '{name}': {reason}",
            code="INVALID_INSTANCE_NAME"
        )
        self.name = name
        self.reason = reason


class InstanceAlreadyExistsError(InstanceDomainError):
    """Raised when trying to create an instance that already exists."""

    def __init__(self, instance_name: str):
        super().__init__(
            message=f"Instance already exists: {instance_name}",
            code="INSTANCE_ALREADY_EXISTS"
        )
        self.instance_name = instance_name


class InstanceConnectionError(InstanceDomainError):
    """Raised when there's an error connecting the instance."""

    def __init__(self, instance_name: str, reason: str):
        super().__init__(
            message=f"Failed to connect instance '{instance_name}': {reason}",
            code="INSTANCE_CONNECTION_ERROR"
        )
        self.instance_name = instance_name
        self.reason = reason
