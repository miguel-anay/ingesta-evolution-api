"""
PostgreSQL Metadata Repository

Infrastructure adapter that implements IMetadataRepositoryPort
for persisting image metadata to PostgreSQL with pgvector.
"""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    OcrText,
    ImageEmbedding,
    TextEmbedding,
    ProcessingStatus,
)
from ....domain.ingestion.exceptions import MetadataError, DuplicateImageError
from ..database import DatabaseManager
from ..models.image_metadata_model import ImageMetadataModel


logger = logging.getLogger(__name__)


class PostgresMetadataRepository(IMetadataRepositoryPort):
    """
    PostgreSQL repository for image metadata with pgvector support.

    Implements IMetadataRepositoryPort using SQLAlchemy async + asyncpg.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db = db_manager

    async def save(self, metadata: ImageMetadata) -> None:
        """Save a new metadata record to PostgreSQL."""
        async with self._db.get_session() as session:
            try:
                # Check for duplicates
                exists_msg = await self._exists_by_field(session, "id_mensaje", str(metadata.id_mensaje))
                if exists_msg:
                    raise DuplicateImageError(message_id=str(metadata.id_mensaje))

                exists_hash = await self._exists_by_field(session, "hash_imagen", str(metadata.hash_imagen))
                if exists_hash:
                    raise DuplicateImageError(image_hash=str(metadata.hash_imagen))

                model = ImageMetadataModel(
                    id_secuencial=metadata.id_secuencial.value,
                    id_mensaje=str(metadata.id_mensaje),
                    tipo_origen=metadata.tipo_origen.value,
                    fecha_descarga=metadata.fecha_descarga,
                    numero_celular=str(metadata.numero_celular),
                    nombre_usuario=str(metadata.nombre_usuario),
                    instancia=str(metadata.instancia),
                    ruta_archivo=str(metadata.ruta_archivo),
                    hash_imagen=str(metadata.hash_imagen),
                    s3_key=metadata.s3_key,
                    texto_ocr=str(metadata.texto_ocr) if metadata.texto_ocr else None,
                    image_embedding=metadata.image_embedding.to_list() if metadata.image_embedding else None,
                    text_embedding=metadata.text_embedding.to_list() if metadata.text_embedding else None,
                    processing_status=metadata.processing_status.value,
                )

                session.add(model)
                await session.commit()
                logger.debug(f"Saved metadata for image {metadata.id_secuencial}")

            except (DuplicateImageError, MetadataError):
                await session.rollback()
                raise
            except Exception as e:
                await session.rollback()
                raise MetadataError(operation="save", reason=str(e))

    async def exists_by_message_id(self, message_id: MessageId) -> bool:
        async with self._db.get_session() as session:
            return await self._exists_by_field(session, "id_mensaje", str(message_id))

    async def exists_by_hash(self, image_hash: ImageHash) -> bool:
        async with self._db.get_session() as session:
            return await self._exists_by_field(session, "hash_imagen", str(image_hash))

    async def get_next_sequential_id(self) -> SequentialId:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(func.coalesce(func.max(ImageMetadataModel.id_secuencial), 0))
            )
            max_id = result.scalar_one()
            return SequentialId(max_id + 1)

    async def get_all(self) -> List[ImageMetadata]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ImageMetadataModel).order_by(ImageMetadataModel.id_secuencial)
            )
            models = result.scalars().all()
            return [self._model_to_entity(m) for m in models]

    async def get_by_sequential_id(self, sequential_id: SequentialId) -> Optional[ImageMetadata]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ImageMetadataModel).where(
                    ImageMetadataModel.id_secuencial == sequential_id.value
                )
            )
            model = result.scalar_one_or_none()
            return self._model_to_entity(model) if model else None

    async def get_by_message_id(self, message_id: MessageId) -> Optional[ImageMetadata]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ImageMetadataModel).where(
                    ImageMetadataModel.id_mensaje == str(message_id)
                )
            )
            model = result.scalar_one_or_none()
            return self._model_to_entity(model) if model else None

    async def count(self) -> int:
        async with self._db.get_session() as session:
            result = await session.execute(select(func.count(ImageMetadataModel.id)))
            return result.scalar_one()

    async def ensure_storage_exists(self) -> None:
        """No-op for PostgreSQL — migrations handle schema creation."""
        pass

    # --- Extended methods for workers ---

    async def update_ocr_text(self, metadata_id: int, ocr_text: str) -> None:
        """Update OCR text for a metadata record."""
        async with self._db.get_session() as session:
            await session.execute(
                update(ImageMetadataModel)
                .where(ImageMetadataModel.id == metadata_id)
                .values(texto_ocr=ocr_text, updated_at=func.now())
            )
            await session.commit()

    async def update_image_embedding(self, metadata_id: int, embedding: list[float]) -> None:
        """Update image embedding vector for a metadata record."""
        async with self._db.get_session() as session:
            await session.execute(
                update(ImageMetadataModel)
                .where(ImageMetadataModel.id == metadata_id)
                .values(image_embedding=embedding, updated_at=func.now())
            )
            await session.commit()

    async def update_text_embedding(self, metadata_id: int, embedding: list[float]) -> None:
        """Update text embedding vector for a metadata record."""
        async with self._db.get_session() as session:
            await session.execute(
                update(ImageMetadataModel)
                .where(ImageMetadataModel.id == metadata_id)
                .values(text_embedding=embedding, updated_at=func.now())
            )
            await session.commit()

    async def update_processing_status(self, metadata_id: int, status: str) -> None:
        """Update processing status for a metadata record."""
        async with self._db.get_session() as session:
            await session.execute(
                update(ImageMetadataModel)
                .where(ImageMetadataModel.id == metadata_id)
                .values(processing_status=status, updated_at=func.now())
            )
            await session.commit()

    async def get_pending(self) -> List[ImageMetadataModel]:
        """Get all records with processing_status='pending' and s3_key set."""
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ImageMetadataModel)
                .where(
                    ImageMetadataModel.processing_status == "pending",
                    ImageMetadataModel.s3_key.isnot(None),
                )
                .order_by(ImageMetadataModel.id.asc())
            )
            return list(result.scalars().all())

    async def get_by_id(self, metadata_id: int) -> Optional[ImageMetadataModel]:
        """Get raw model by primary key (used by workers)."""
        async with self._db.get_session() as session:
            result = await session.execute(
                select(ImageMetadataModel).where(ImageMetadataModel.id == metadata_id)
            )
            return result.scalar_one_or_none()

    async def search_by_image_embedding(
        self, embedding: list[float], limit: int = 10
    ) -> list[tuple]:
        """Search by cosine similarity on image_embedding. Returns (model, distance) tuples."""
        async with self._db.get_session() as session:
            distance = ImageMetadataModel.image_embedding.cosine_distance(embedding)
            result = await session.execute(
                select(ImageMetadataModel, distance.label("distance"))
                .where(ImageMetadataModel.image_embedding.isnot(None))
                .order_by(distance)
                .limit(limit)
            )
            return [(row[0], row[1]) for row in result.all()]

    async def search_by_text_embedding(
        self, embedding: list[float], limit: int = 10
    ) -> list[tuple]:
        """Search by cosine similarity on text_embedding. Returns (model, distance) tuples."""
        async with self._db.get_session() as session:
            distance = ImageMetadataModel.text_embedding.cosine_distance(embedding)
            result = await session.execute(
                select(ImageMetadataModel, distance.label("distance"))
                .where(ImageMetadataModel.text_embedding.isnot(None))
                .order_by(distance)
                .limit(limit)
            )
            return [(row[0], row[1]) for row in result.all()]

    # --- Private helpers ---

    async def _exists_by_field(self, session: AsyncSession, field: str, value: str) -> bool:
        column = getattr(ImageMetadataModel, field)
        result = await session.execute(select(func.count()).where(column == value))
        return result.scalar_one() > 0

    def _model_to_entity(self, model: ImageMetadataModel) -> ImageMetadata:
        """Convert SQLAlchemy model to domain entity."""
        # Parse ruta_archivo - may be S3 path or local path
        ruta = model.ruta_archivo
        if "/" in ruta:
            base_dir = ruta.rsplit("/", 1)[0]
            filename = ruta.rsplit("/", 1)[1]
        else:
            base_dir = "."
            filename = ruta

        # Ensure filename matches expected pattern for ImagePath
        if not filename.endswith(".jpg"):
            filename = f"{model.id_secuencial}.jpg"
            base_dir = ruta

        return ImageMetadata(
            id_secuencial=SequentialId(model.id_secuencial),
            id_mensaje=MessageId(model.id_mensaje),
            tipo_origen=SourceType.from_string(model.tipo_origen),
            fecha_descarga=model.fecha_descarga,
            numero_celular=PhoneNumber(model.numero_celular),
            nombre_usuario=UserName(model.nombre_usuario),
            instancia=Instance(model.instancia),
            ruta_archivo=ImagePath(base_directory=base_dir, filename=filename),
            hash_imagen=ImageHash(model.hash_imagen),
            texto_ocr=OcrText(model.texto_ocr) if model.texto_ocr else None,
            image_embedding=ImageEmbedding(values=tuple(model.image_embedding)) if model.image_embedding else None,
            text_embedding=TextEmbedding(values=tuple(model.text_embedding)) if model.text_embedding else None,
            processing_status=ProcessingStatus(model.processing_status) if model.processing_status else ProcessingStatus.PENDING,
            s3_key=model.s3_key,
        )
