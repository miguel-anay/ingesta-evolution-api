"""Create image_metadata table with pgvector support

Revision ID: 001
Revises: None
Create Date: 2026-03-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create image_metadata table
    op.create_table(
        "image_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_secuencial", sa.Integer(), nullable=False),
        sa.Column("id_mensaje", sa.String(500), nullable=False),
        sa.Column("tipo_origen", sa.String(20), nullable=False),
        sa.Column("fecha_descarga", sa.DateTime(), nullable=False),
        sa.Column("numero_celular", sa.String(20), nullable=False),
        sa.Column("nombre_usuario", sa.String(256), nullable=False),
        sa.Column("instancia", sa.String(100), nullable=False),
        sa.Column("ruta_archivo", sa.String(512), nullable=False),
        sa.Column("hash_imagen", sa.String(64), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=True),
        sa.Column("texto_ocr", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_secuencial"),
        sa.UniqueConstraint("id_mensaje"),
        sa.UniqueConstraint("hash_imagen"),
    )

    # Add vector columns (pgvector)
    op.execute("ALTER TABLE image_metadata ADD COLUMN image_embedding vector(512)")
    op.execute("ALTER TABLE image_metadata ADD COLUMN text_embedding vector(512)")

    # Create indexes
    op.create_index("ix_image_metadata_id_secuencial", "image_metadata", ["id_secuencial"])
    op.create_index("ix_image_metadata_id_mensaje", "image_metadata", ["id_mensaje"])
    op.create_index("ix_image_metadata_hash_imagen", "image_metadata", ["hash_imagen"])
    op.create_index("ix_image_metadata_numero_celular", "image_metadata", ["numero_celular"])
    op.create_index("ix_image_metadata_instancia", "image_metadata", ["instancia"])
    op.create_index("ix_image_metadata_processing_status", "image_metadata", ["processing_status"])

    # HNSW indexes for vector similarity search
    op.execute(
        "CREATE INDEX ix_image_metadata_image_embedding_hnsw "
        "ON image_metadata USING hnsw (image_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_image_metadata_text_embedding_hnsw "
        "ON image_metadata USING hnsw (text_embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("image_metadata")
    op.execute("DROP EXTENSION IF EXISTS vector")
