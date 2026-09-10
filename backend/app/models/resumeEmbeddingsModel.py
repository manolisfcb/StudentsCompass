import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db import Base

class ResumeEmbedding(Base):
    __tablename__ = "resume_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Para que puedas versionar embeddings si cambias de modelo
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="all-MiniLM-L6-v2")
    dims: Mapped[int] = mapped_column(Integer, nullable=False, default=384)

    # Vector pgvector (debe coincidir dims con el modelo)
    # Desactivado: embedding puede ser nulo
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)

    # What this vector was made from: the fingerprint of the exact text handed
    # to the provider, together with the model name and the fingerprint scheme
    # version. Equal fingerprint means regenerating would produce the same
    # vector, so both the generation and the write are skipped.
    #
    # NULL means "no demonstrable provenance": rows written before the column
    # existed cannot be given a fingerprint, because the text that produced
    # them is not recoverable. They are regenerated once, on demand, rather
    # than labelled with an invented hash.
    text_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

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
        # Índice para no guardar duplicados del mismo resume + modelo (opcional)
        Index("ix_resume_embeddings_resume_model", "resume_id", "model_name", unique=True),
        # The HNSW index is what makes nearest-neighbour search usable; it was
        # only declared in a migration, so autogenerate saw an index with no
        # counterpart in metadata and proposed dropping it. The pgvector options
        # are ignored by other dialects, which fall back to a plain index.
        Index(
            "ix_resume_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": "16", "ef_construction": "64"},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )