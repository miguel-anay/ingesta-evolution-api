"""
Image Ingestion Domain

Domain entities, value objects, and exceptions for the image ingestion capability.
This module contains pure business logic with NO external dependencies.
"""

from .entities import ImageMetadata, IngestionResult, RawImageData
from .value_objects import (
    ImageHash,
    ImagePath,
    SequentialId,
    SourceType,
    MessageId,
    PhoneNumber,
    UserName,
    Instance,
)
from .exceptions import (
    IngestionError,
    DuplicateImageError,
    InvalidImageError,
    MetadataError,
    StorageError,
    ImageSourceError,
    MissingRequiredParameterError,
)

__all__ = [
    # Entities
    "ImageMetadata",
    "IngestionResult",
    "RawImageData",
    # Value Objects
    "ImageHash",
    "ImagePath",
    "SequentialId",
    "SourceType",
    "MessageId",
    "PhoneNumber",
    "UserName",
    "Instance",
    # Exceptions
    "IngestionError",
    "DuplicateImageError",
    "InvalidImageError",
    "MetadataError",
    "StorageError",
    "ImageSourceError",
    "MissingRequiredParameterError",
]
