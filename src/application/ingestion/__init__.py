"""
Image Ingestion Application Layer

Use cases and port definitions for the image ingestion capability.
This module orchestrates domain logic and defines interfaces for infrastructure.
"""

from .use_cases import (
    IngestImagesUseCase,
    IngestChatImagesUseCase,
    IngestStatusImagesUseCase,
)
from .ports import (
    IImageSourcePort,
    IImageStoragePort,
    IMetadataRepositoryPort,
)
from .dto import (
    IngestImagesRequest,
    IngestImagesResponse,
    ImageMetadataDTO,
)

__all__ = [
    # Use Cases
    "IngestImagesUseCase",
    "IngestChatImagesUseCase",
    "IngestStatusImagesUseCase",
    # Ports
    "IImageSourcePort",
    "IImageStoragePort",
    "IMetadataRepositoryPort",
    # DTOs
    "IngestImagesRequest",
    "IngestImagesResponse",
    "ImageMetadataDTO",
]
