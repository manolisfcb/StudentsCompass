"""add hnsw index on resume_embeddings.embedding

Adds a pgvector HNSW index so cosine-distance (``<=>``) similarity search over
``resume_embeddings`` runs against the index instead of a sequential scan.

Note: the repo's migration history is pre-existing multi-head; this revision
extends ``a4f9c2d8e6b1`` because that lineage already contains the migration
(``288bb2249a43``) that creates the ``resume_embeddings`` table.

Revision ID: c7d8e9f0a1b2
Revises: a4f9c2d8e6b1
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "a4f9c2d8e6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_resume_embeddings_embedding_hnsw"


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_index(
        INDEX_NAME,
        "resume_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": "16", "ef_construction": "64"},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_index(INDEX_NAME, table_name="resume_embeddings")
