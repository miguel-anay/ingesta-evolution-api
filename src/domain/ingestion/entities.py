"""
Image Ingestion Domain Entities

Core business entities for the image ingestion capability.
These are PURE domain objects with NO infrastructure dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from .value_objects import (
    SequentialId,
    MessageId,
    SourceType,
    ImageHash,
    ImagePath,
    PhoneNumber,
    UserName,
    Instance,
    OcrText,
    ImageEmbedding,
    TextEmbedding,
    ProcessingStatus,
)


@dataclass
class ImageMetadata:
    """
    Core domain entity representing metadata for an ingested image.

    This entity encapsulates all business rules related to image metadata.
    It has NO knowledge of how it's persisted (CSV) or transmitted (HTTP).

    Corresponds to a single row in the metadata CSV file:
    - id_secuencial: Unique incremental numeric ID
    - id_mensaje: Message ID or status ID
    - tipo_origen: 'chat' or 'estado'
    - fecha_descarga: Download timestamp
    - numero_celular: User phone number
    - nombre_usuario: User display name
    - instancia: Evolution API instance identifier
    - ruta_archivo: Local image path
    - hash_imagen: Hash used for deduplication
    """

    id_secuencial: SequentialId
    id_mensaje: MessageId
    tipo_origen: SourceType
    fecha_descarga: datetime
    numero_celular: PhoneNumber
    nombre_usuario: UserName
    instancia: Instance
    ruta_archivo: ImagePath
    hash_imagen: ImageHash
    # New fields for OCR + CLIP + S3 pipeline
    texto_ocr: Optional[OcrText] = None
    image_embedding: Optional[ImageEmbedding] = None
    text_embedding: Optional[TextEmbedding] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    s3_key: Optional[str] = None

    def __eq__(self, other: object) -> bool:
        """Two metadata entries are equal if they have the same sequential ID."""
        if not isinstance(other, ImageMetadata):
            return False
        return self.id_secuencial == other.id_secuencial

    def __hash__(self) -> int:
        return hash(self.id_secuencial.value)

    @property
    def is_from_chat(self) -> bool:
        """Check if image is from a chat message."""
        return self.tipo_origen == SourceType.CHAT

    @property
    def is_from_status(self) -> bool:
        """Check if image is from a user status."""
        return self.tipo_origen == SourceType.STATUS


@dataclass
class RawImageData:
    """
    Domain entity representing raw image data before processing.

    This is the image data as received from Evolution API,
    before normalization to JPEG and storage.
    """

    message_id: MessageId
    source_type: SourceType
    phone_number: PhoneNumber
    user_name: UserName
    instance: Instance
    image_bytes: bytes
    original_mime_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_valid_image_type(self) -> bool:
        """Check if the original mime type is a valid image type."""
        valid_types = {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/bmp",
            "image/tiff",
        }
        return self.original_mime_type.lower() in valid_types


@dataclass
class IngestionResult:
    """
    Domain entity representing the result of an ingestion operation.

    Provides summary information about what was processed.
    """

    total_processed: int = 0
    new_images_downloaded: int = 0
    duplicates_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    downloaded_images: List[ImageMetadata] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there were any errors during ingestion."""
        return len(self.errors) > 0

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of ingestion."""
        if self.total_processed == 0:
            return 1.0
        successful = self.new_images_downloaded + self.duplicates_skipped
        return successful / self.total_processed

    def add_success(self, metadata: ImageMetadata) -> None:
        """Record a successful image download."""
        self.total_processed += 1
        self.new_images_downloaded += 1
        self.downloaded_images.append(metadata)

    def add_duplicate(self) -> None:
        """Record a duplicate image that was skipped."""
        self.total_processed += 1
        self.duplicates_skipped += 1

    def add_error(self, error_message: str) -> None:
        """Record an error during processing."""
        self.total_processed += 1
        self.errors.append(error_message)

    def merge(self, other: "IngestionResult") -> "IngestionResult":
        """Merge another result into this one."""
        return IngestionResult(
            total_processed=self.total_processed + other.total_processed,
            new_images_downloaded=self.new_images_downloaded + other.new_images_downloaded,
            duplicates_skipped=self.duplicates_skipped + other.duplicates_skipped,
            errors=self.errors + other.errors,
            downloaded_images=self.downloaded_images + other.downloaded_images,
        )
