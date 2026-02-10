"""
Evolution API Exceptions

Infrastructure-level exceptions for Evolution API integration.
"""


class EvolutionApiError(Exception):
    """Base exception for Evolution API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = None,
        response_body: dict = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body or {}
        super().__init__(self.message)


class EvolutionApiConnectionError(EvolutionApiError):
    """Raised when unable to connect to Evolution API."""

    def __init__(self, message: str = "Failed to connect to Evolution API"):
        super().__init__(message=message)


class EvolutionApiAuthenticationError(EvolutionApiError):
    """Raised when API authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, status_code=401)


class EvolutionApiNotFoundError(EvolutionApiError):
    """Raised when requested resource is not found."""

    def __init__(self, resource: str):
        super().__init__(
            message=f"Resource not found: {resource}",
            status_code=404,
        )


class EvolutionApiRateLimitError(EvolutionApiError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(
            message="Rate limit exceeded",
            status_code=429,
        )
