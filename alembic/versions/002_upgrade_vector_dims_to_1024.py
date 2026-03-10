"""Upgrade vector columns from 512 to 1024 dimensions (Titan Multimodal)

Revision ID: 002
Revises: 001
Create Date: 2026-03-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing HNSW indexes (must drop before altering column type)
    op.execute("DROP INDEX IF EXISTS ix_image_metadata_image_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_image_metadata_text_embedding_hnsw")

    # Alter vector columns from 512 to 1024 dimensions
    # Existing data must be cleared since dimensions changed
    op.execute("UPDATE image_metadata SET image_embedding = NULL, text_embedding = NULL")
    op.execute("ALTER TABLE image_metadata ALTER COLUMN image_embedding TYPE vector(1024)")
    op.execute("ALTER TABLE image_metadata ALTER COLUMN text_embedding TYPE vector(1024)")

    # Recreate HNSW indexes
    op.execute(
        "CREATE INDEX ix_image_metadata_image_embedding_hnsw "
        "ON image_metadata USING hnsw (image_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_image_metadata_text_embedding_hnsw "
        "ON image_metadata USING hnsw (text_embedding vector_cosine_ops)"
    )

    # Reset processing status since old embeddings are cleared
    op.execute(
        "UPDATE image_metadata SET processing_status = 'pending' "
        "WHERE processing_status = 'completed'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_image_metadata_image_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_image_metadata_text_embedding_hnsw")

    op.execute("UPDATE image_metadata SET image_embedding = NULL, text_embedding = NULL")
    op.execute("ALTER TABLE image_metadata ALTER COLUMN image_embedding TYPE vector(512)")
    op.execute("ALTER TABLE image_metadata ALTER COLUMN text_embedding TYPE vector(512)")

    op.execute(
        "CREATE INDEX ix_image_metadata_image_embedding_hnsw "
        "ON image_metadata USING hnsw (image_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_image_metadata_text_embedding_hnsw "
        "ON image_metadata USING hnsw (text_embedding vector_cosine_ops)"
    )
