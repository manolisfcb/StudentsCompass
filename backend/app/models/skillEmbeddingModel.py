import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.db_types import UUID


class SkillEmbedding(Base):
    """One vector per catalog skill and embedding model.

    The catalog is finite, so each skill is embedded once in its life and read
    back from here, instead of once per gap analysis inside a request. Versioned
    exactly like ``resume_embeddings``: the vector is reused only while its
    fingerprint of (text, model, recipe version) still matches.
    """

    __tablename__ = "skill_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    dims: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    # Unlike resume_embeddings there are no legacy rows to tolerate: every row
    # is written by SkillEmbeddingService, which always knows its input.
    text_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint_version: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # One vector per skill and space; also what the upsert conflicts on.
        Index("uq_skill_embeddings_skill_model", "skill_id", "model_name", unique=True),
        # Nearest-skill search (deduplicating auto-registered skills, TASK-090).
        Index(
            "ix_skill_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": "16", "ef_construction": "64"},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
