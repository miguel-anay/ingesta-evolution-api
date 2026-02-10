"""
Storage Infrastructure

Adapters for file storage and persistence.
"""

from .filesystem_image_storage import FileSystemImageStorageAdapter

__all__ = [
    "FileSystemImageStorageAdapter",
]
