"""
Image Ingestion Domain Exceptions

Custom exceptions for the image ingestion capability.
These are PURE domain exceptions with NO infrastructure dependencies.
"""

from typing import Optional


class IngestionError(Exception):
    """Base exception for all ingestion-related errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class DuplicateImageError(IngestionError):
    """
    Raised when attempting to ingest an image that already exists.

    This is not necessarily an error condition - it's expected behavior
    for idempotent operations. The caller decides how to handle it.
    """

    def __init__(
        self,
        message_id: Optional[str] = None,
        image_hash: Optional[str] = None,
    ):
        details_parts = []
        if message_id:
            details_parts.append(f"message_id={message_id}")
        if image_hash:
            details_parts.append(f"hash={image_hash}")

        details = ", ".join(details_parts) if details_parts else None
        super().__init__(
            message="Image already exists in the system",
            details=details,
        )
        self.message_id = message_id
        self.image_hash = image_hash


class InvalidImageError(IngestionError):
    """
    Raised when an image fails validation.

    This includes:
    - Invalid or corrupted image data
    - Unsupported image format
    - Image too large or too small
    """

    def __init__(
        self,
        reason: str,
        message_id: Optional[str] = None,
    ):
        super().__init__(
            message="Invalid image data",
            details=reason,
        )
        self.reason = reason
        self.message_id = message_id


class MetadataError(IngestionError):
    """
    Raised when there's an error with metadata operations.

    This includes:
    - Failure to read existing metadata
    - Failure to write new metadata
    - Corrupted metadata file
    """

    def __init__(
        self,
        operation: str,
        reason: str,
    ):
        super().__init__(
            message=f"Metadata {operation} failed",
            details=reason,
        )
        self.operation = operation
        self.reason = reason


class StorageError(IngestionError):
    """
    Raised when there's an error with image storage operations.

    This includes:
    - Failure to write image to disk
    - Failure to create directories
    - Disk full or permissions errors
    """

    def __init__(
        self,
        operation: str,
        path: str,
        reason: str,
    ):
        super().__init__(
            message=f"Storage {operation} failed for {path}",
            details=reason,
        )
        self.operation = operation
        self.path = path
        self.reason = reason


class ImageSourceError(IngestionError):
    """
    Raised when there's an error fetching images from source.

    This includes:
    - API connection errors
    - Authentication failures
    - Invalid response format
    """

    def __init__(
        self,
        source: str,
        reason: str,
    ):
        super().__init__(
            message=f"Failed to fetch images from {source}",
            details=reason,
        )
        self.source = source
        self.reason = reason


class MissingRequiredParameterError(IngestionError):
    """
    Raised when a required parameter is missing from the ingestion request.

    According to the specs, both numero_celular and instancia are required
    and the ingestion process must not start if any is missing.
    """

    def __init__(
        self,
        parameter_name: str,
        message: Optional[str] = None,
    ):
        super().__init__(
            message=message or f"Required parameter '{parameter_name}' is missing",
            details=f"Parameter: {parameter_name}",
        )
        self.parameter_name = parameter_name


class OcrError(IngestionError):
    """Raised when OCR text extraction fails."""

    def __init__(self, reason: str, message_id: Optional[str] = None):
        super().__init__(
            message="OCR text extraction failed",
            details=reason,
        )
        self.reason = reason
        self.message_id = message_id


class VectorizationError(IngestionError):
    """Raised when vector embedding generation fails."""

    def __init__(self, reason: str, vector_type: str = "image"):
        super().__init__(
            message=f"Vectorization failed for {vector_type}",
            details=reason,
        )
        self.reason = reason
        self.vector_type = vector_type
