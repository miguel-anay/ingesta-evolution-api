"""
Image Ingestion Ports

Abstract interfaces (ports) that define what the application needs
from infrastructure. Adapters implement these interfaces.
"""

from .image_source_port import IImageSourcePort
from .image_storage_port import IImageStoragePort
from .metadata_repository_port import IMetadataRepositoryPort

__all__ = [
    "IImageSourcePort",
    "IImageStoragePort",
    "IMetadataRepositoryPort",
]
