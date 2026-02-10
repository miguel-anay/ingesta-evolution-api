"""
CSV Metadata Repository

Infrastructure adapter that implements IMetadataRepositoryPort
for persisting image metadata to a CSV file.
"""

import asyncio
import csv
import logging
import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Set

from ....application.ingestion.ports import IMetadataRepositoryPort
from ....domain.ingestion.entities import ImageMetadata
from ....domain.ingestion.value_objects import (
    SequentialId,
    MessageId,
    ImageHash,
    ImagePath,
    PhoneNumber,
    UserName,
    SourceType,
    Instance,
)
from ....domain.ingestion.exceptions import MetadataError, DuplicateImageError


logger = logging.getLogger(__name__)


class CsvMetadataRepository(IMetadataRepositoryPort):
    """
    Repository for managing image metadata in a CSV file.

    Implements IMetadataRepositoryPort to provide:
    - Append-only metadata storage
    - Idempotency checks by message ID and hash
    - Sequential ID management
    - Thread-safe file operations

    The CSV is the SINGLE SOURCE OF TRUTH for ingestion state.

    CSV Fields (per PROJECT_SPECS.md):
    - id_secuencial: int
    - id_mensaje: str
    - tipo_origen: str (chat|estado)
    - fecha_descarga: str (ISO format)
    - numero_celular: str
    - nombre_usuario: str
    - instancia: str
    - ruta_archivo: str
    - hash_imagen: str
    """

    # CSV header row
    HEADERS = [
        "id_secuencial",
        "id_mensaje",
        "tipo_origen",
        "fecha_descarga",
        "numero_celular",
        "nombre_usuario",
        "instancia",
        "ruta_archivo",
        "hash_imagen",
    ]

    def __init__(
        self,
        csv_file_path: str,
        images_base_directory: str,
    ) -> None:
        """
        Initialize the CSV repository.

        Args:
            csv_file_path: Absolute path to the metadata CSV file
            images_base_directory: Base directory for image paths
        """
        self._csv_path = os.path.abspath(csv_file_path)
        self._images_base_directory = images_base_directory
        self._lock = threading.Lock()

        # In-memory cache for fast lookups (populated on first access)
        self._cache_loaded = False
        self._message_ids: Set[str] = set()
        self._hashes: Set[str] = set()
        self._max_sequential_id: int = 0

        logger.info(f"Initialized CSV metadata repository at: {self._csv_path}")

    async def save(self, metadata: ImageMetadata) -> None:
        """
        Save a new metadata record.

        Appends to the CSV file atomically.

        Args:
            metadata: The metadata to save

        Raises:
            MetadataError: If unable to save
            DuplicateImageError: If image already exists
        """
        await self._ensure_cache_loaded()

        # Check for duplicates before saving
        message_id_str = str(metadata.id_mensaje)
        hash_str = str(metadata.hash_imagen)

        if message_id_str in self._message_ids:
            raise DuplicateImageError(message_id=message_id_str)

        if hash_str in self._hashes:
            raise DuplicateImageError(image_hash=hash_str)

        try:
            # Prepare row data
            row = {
                "id_secuencial": metadata.id_secuencial.value,
                "id_mensaje": message_id_str,
                "tipo_origen": metadata.tipo_origen.value,
                "fecha_descarga": metadata.fecha_descarga.isoformat(),
                "numero_celular": str(metadata.numero_celular),
                "nombre_usuario": str(metadata.nombre_usuario),
                "instancia": str(metadata.instancia),
                "ruta_archivo": str(metadata.ruta_archivo),
                "hash_imagen": hash_str,
            }

            # Write to CSV in thread pool (blocking I/O)
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._append_row,
                row,
            )

            # Update cache after successful write
            self._message_ids.add(message_id_str)
            self._hashes.add(hash_str)
            self._max_sequential_id = max(
                self._max_sequential_id,
                metadata.id_secuencial.value,
            )

            logger.debug(f"Saved metadata for image {metadata.id_secuencial}")

        except DuplicateImageError:
            raise
        except Exception as e:
            raise MetadataError(
                operation="save",
                reason=str(e),
            )

    async def exists_by_message_id(self, message_id: MessageId) -> bool:
        """
        Check if a record with the given message ID exists.

        Args:
            message_id: The message ID to check

        Returns:
            True if exists, False otherwise
        """
        await self._ensure_cache_loaded()
        return str(message_id) in self._message_ids

    async def exists_by_hash(self, image_hash: ImageHash) -> bool:
        """
        Check if a record with the given image hash exists.

        Args:
            image_hash: The hash to check

        Returns:
            True if exists, False otherwise
        """
        await self._ensure_cache_loaded()
        return str(image_hash) in self._hashes

    async def get_next_sequential_id(self) -> SequentialId:
        """
        Get the next available sequential ID.

        Returns:
            The next ID to use (highest existing + 1, or 1 if empty)
        """
        await self._ensure_cache_loaded()
        return SequentialId(self._max_sequential_id + 1)

    async def get_all(self) -> List[ImageMetadata]:
        """
        Retrieve all metadata records.

        Returns:
            List of all metadata, ordered by sequential ID
        """
        try:
            rows = await asyncio.get_event_loop().run_in_executor(
                None,
                self._read_all_rows,
            )

            metadata_list = []
            for row in rows:
                try:
                    metadata = self._row_to_metadata(row)
                    metadata_list.append(metadata)
                except Exception as e:
                    logger.warning(f"Skipping invalid row: {e}")

            # Sort by sequential ID
            metadata_list.sort(key=lambda m: m.id_secuencial.value)
            return metadata_list

        except Exception as e:
            raise MetadataError(
                operation="read_all",
                reason=str(e),
            )

    async def get_by_sequential_id(
        self, sequential_id: SequentialId
    ) -> Optional[ImageMetadata]:
        """
        Retrieve metadata by sequential ID.

        Args:
            sequential_id: The ID to look up

        Returns:
            The metadata if found, None otherwise
        """
        all_metadata = await self.get_all()

        for metadata in all_metadata:
            if metadata.id_secuencial == sequential_id:
                return metadata

        return None

    async def get_by_message_id(
        self, message_id: MessageId
    ) -> Optional[ImageMetadata]:
        """
        Retrieve metadata by message ID.

        Args:
            message_id: The message ID to look up

        Returns:
            The metadata if found, None otherwise
        """
        all_metadata = await self.get_all()

        for metadata in all_metadata:
            if metadata.id_mensaje == message_id:
                return metadata

        return None

    async def count(self) -> int:
        """
        Get the total count of metadata records.

        Returns:
            Number of records in the repository
        """
        await self._ensure_cache_loaded()
        return len(self._message_ids)

    async def ensure_storage_exists(self) -> None:
        """
        Ensure the CSV file exists and is initialized.

        Creates the file with headers if it doesn't exist.

        Raises:
            MetadataError: If unable to initialize storage
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._csv_path), exist_ok=True)

            if not os.path.exists(self._csv_path):
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._create_csv_with_headers,
                )
                logger.info(f"Created CSV file with headers: {self._csv_path}")
            else:
                logger.debug(f"CSV file already exists: {self._csv_path}")

        except Exception as e:
            raise MetadataError(
                operation="initialize",
                reason=str(e),
            )

    # Private helper methods

    async def _ensure_cache_loaded(self) -> None:
        """Load cache from CSV if not already loaded."""
        if self._cache_loaded:
            return

        try:
            await self.ensure_storage_exists()

            rows = await asyncio.get_event_loop().run_in_executor(
                None,
                self._read_all_rows,
            )

            for row in rows:
                message_id = row.get("id_mensaje", "")
                hash_value = row.get("hash_imagen", "")
                seq_id = row.get("id_secuencial", "0")

                if message_id:
                    self._message_ids.add(message_id)
                if hash_value:
                    self._hashes.add(hash_value)
                try:
                    self._max_sequential_id = max(
                        self._max_sequential_id,
                        int(seq_id),
                    )
                except ValueError:
                    pass

            self._cache_loaded = True
            logger.info(
                f"Loaded cache: {len(self._message_ids)} records, "
                f"max ID: {self._max_sequential_id}"
            )

        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            raise MetadataError(
                operation="load_cache",
                reason=str(e),
            )

    def _create_csv_with_headers(self) -> None:
        """Create a new CSV file with headers."""
        with self._lock:
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()

    def _append_row(self, row: Dict[str, any]) -> None:
        """Append a row to the CSV file atomically."""
        with self._lock:
            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writerow(row)

    def _read_all_rows(self) -> List[Dict[str, str]]:
        """Read all rows from the CSV file."""
        if not os.path.exists(self._csv_path):
            return []

        with self._lock:
            with open(self._csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader)

    def _row_to_metadata(self, row: Dict[str, str]) -> ImageMetadata:
        """Convert a CSV row to an ImageMetadata entity."""
        # Handle backward compatibility: numero_telefono -> numero_celular
        phone_value = row.get("numero_celular") or row.get("numero_telefono", "")
        # Handle backward compatibility: instancia may not exist in old CSVs
        instance_value = row.get("instancia", "unknown")

        return ImageMetadata(
            id_secuencial=SequentialId(int(row["id_secuencial"])),
            id_mensaje=MessageId(row["id_mensaje"]),
            tipo_origen=SourceType.from_string(row["tipo_origen"]),
            fecha_descarga=datetime.fromisoformat(row["fecha_descarga"]),
            numero_celular=PhoneNumber(phone_value),
            nombre_usuario=UserName(row["nombre_usuario"]),
            instancia=Instance(instance_value) if instance_value else Instance("unknown"),
            ruta_archivo=ImagePath(
                base_directory=self._images_base_directory,
                filename=os.path.basename(row["ruta_archivo"]),
            ),
            hash_imagen=ImageHash(row["hash_imagen"]),
        )
