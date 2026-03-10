"""
SQLAlchemy Model for image_metadata table.

Uses pgvector for vector columns (image_embedding, text_embedding).
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ImageMetadataModel(Base):
    """SQLAlchemy model mapping to the image_metadata table."""

    __tablename__ = "image_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_secuencial = Column(Integer, unique=True, nullable=False)
    id_mensaje = Column(String(500), unique=True, nullable=False)
    tipo_origen = Column(String(20), nullable=False)
    fecha_descarga = Column(DateTime, nullable=False)
    numero_celular = Column(String(20), nullable=False)
    nombre_usuario = Column(String(256), nullable=False)
    instancia = Column(String(100), nullable=False)
    ruta_archivo = Column(String(512), nullable=False)
    hash_imagen = Column(String(64), unique=True, nullable=False)
    s3_key = Column(String(512), nullable=True)
    texto_ocr = Column(Text, nullable=True)
    image_embedding = Column(Vector(1024), nullable=True)
    text_embedding = Column(Vector(1024), nullable=True)
    processing_status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_image_metadata_id_secuencial", "id_secuencial"),
        Index("ix_image_metadata_id_mensaje", "id_mensaje"),
        Index("ix_image_metadata_hash_imagen", "hash_imagen"),
        Index("ix_image_metadata_numero_celular", "numero_celular"),
        Index("ix_image_metadata_instancia", "instancia"),
        Index("ix_image_metadata_processing_status", "processing_status"),
    )

    def __repr__(self) -> str:
        return f"<ImageMetadataModel(id={self.id}, id_secuencial={self.id_secuencial})>"
