import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)

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
    )