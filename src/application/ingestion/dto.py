"""
Image Ingestion DTOs

Data Transfer Objects for input/output of use cases.
DTOs are simple data containers that cross layer boundaries.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ...domain.ingestion.value_objects import SourceType
from ...domain.ingestion.exceptions import MissingRequiredParameterError


@dataclass(frozen=True)
class IngestImagesRequest:
    """
    Request DTO for image ingestion use cases.

    Contains all parameters needed to trigger an ingestion.

    REQUIRED PARAMETERS (per PROJECT_SPECS.md):
    - numero_celular: User phone number to ingest images from
    - instancia: Evolution API instance identifier

    Both parameters are REQUIRED. The ingestion process must NOT start
    if any parameter is missing or empty.
    """

    numero_celular: str
    instancia: str
    source_type: Optional[SourceType] = None  # None means both chat and status
    limit: Optional[int] = None  # None means no limit
    fecha_desde: Optional[datetime] = None  # Filter: only messages after this date
    fecha_hasta: Optional[datetime] = None  # Filter: only messages before this date

    def __post_init__(self) -> None:
        """Validate request parameters."""
        # Validate required parameter: numero_celular
        if not self.numero_celular:
            raise MissingRequiredParameterError(
                parameter_name="numero_celular",
                message="Phone number (numero_celular) is required for ingestion",
            )

        numero_stripped = self.numero_celular.strip()
        if not numero_stripped:
            raise MissingRequiredParameterError(
                parameter_name="numero_celular",
                message="Phone number (numero_celular) cannot be empty or whitespace",
            )

        # Validate required parameter: instancia
        if not self.instancia:
            raise MissingRequiredParameterError(
                parameter_name="instancia",
                message="Instance identifier (instancia) is required for ingestion",
            )

        instancia_stripped = self.instancia.strip()
        if not instancia_stripped:
            raise MissingRequiredParameterError(
                parameter_name="instancia",
                message="Instance identifier (instancia) cannot be empty or whitespace",
            )

        if self.limit is not None and self.limit < 1:
            raise ValueError("Limit must be a positive integer")


@dataclass(frozen=True)
class ImageMetadataDTO:
    """
    DTO representing image metadata for API responses.

    Maps from domain ImageMetadata entity to a flat structure
    suitable for JSON serialization.

    Fields (per PROJECT_SPECS.md):
    - id_secuencial: Unique incremental numeric ID
    - id_mensaje: Message ID or status ID
    - tipo_origen: 'chat' or 'estado'
    - fecha_descarga: Download timestamp
    - numero_celular: User phone number
    - nombre_usuario: User display name
    - instancia: Evolution API instance
    - ruta_archivo: Local image path
    - hash_imagen: Hash used for deduplication
    """

    id_secuencial: int
    id_mensaje: str
    tipo_origen: str
    fecha_descarga: str  # ISO format string
    numero_celular: str
    nombre_usuario: str
    instancia: str
    ruta_archivo: str
    hash_imagen: str
    # New fields for OCR + CLIP pipeline
    texto_ocr: Optional[str] = None
    has_image_embedding: bool = False
    has_text_embedding: bool = False
    processing_status: str = "pending"
    s3_key: Optional[str] = None


@dataclass
class IngestImagesResponse:
    """
    Response DTO for image ingestion use cases.

    Contains summary and details of the ingestion operation.
    """

    success: bool
    total_processed: int
    new_images_downloaded: int
    duplicates_skipped: int
    errors_count: int
    errors: List[str] = field(default_factory=list)
    downloaded_images: List[ImageMetadataDTO] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def message(self) -> str:
        """Generate a human-readable summary message."""
        if self.errors_count > 0:
            return (
                f"Ingestion completed with {self.errors_count} errors. "
                f"Downloaded {self.new_images_downloaded} new images, "
                f"skipped {self.duplicates_skipped} duplicates."
            )
        return (
            f"Ingestion completed successfully. "
            f"Downloaded {self.new_images_downloaded} new images, "
            f"skipped {self.duplicates_skipped} duplicates."
        )


@dataclass(frozen=True)
class IngestionStatusResponse:
    """
    Response DTO for checking ingestion system status.
    """

    is_healthy: bool
    total_images_ingested: int
    storage_directory: str
    metadata_file: str
    last_sequential_id: int
    available_instances: List[str]
    message: str = ""


def metadata_to_dto(metadata: "ImageMetadata") -> ImageMetadataDTO:
    """
    Convert domain ImageMetadata entity to DTO.

    This function handles the translation between domain
    value objects and simple DTO fields.
    """
    from ...domain.ingestion.entities import ImageMetadata

    return ImageMetadataDTO(
        id_secuencial=metadata.id_secuencial.value,
        id_mensaje=str(metadata.id_mensaje),
        tipo_origen=metadata.tipo_origen.value,
        fecha_descarga=metadata.fecha_descarga.isoformat(),
        numero_celular=str(metadata.numero_celular),
        nombre_usuario=str(metadata.nombre_usuario),
        instancia=str(metadata.instancia),
        ruta_archivo=str(metadata.ruta_archivo),
        hash_imagen=str(metadata.hash_imagen),
        texto_ocr=str(metadata.texto_ocr) if metadata.texto_ocr else None,
        has_image_embedding=metadata.image_embedding is not None,
        has_text_embedding=metadata.text_embedding is not None,
        processing_status=metadata.processing_status.value,
        s3_key=metadata.s3_key,
    )
