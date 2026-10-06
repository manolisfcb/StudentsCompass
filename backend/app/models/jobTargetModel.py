"""A job description a user brought in, and the shared parse of its text.

Plan 11 §5. Career Lab does not discover vacancies: the user pastes one. Two
tables, split by what depends on whom:

* ``job_description_parses`` depends only on the text, so it is shared across
  users and keyed by the hash of the normalized text. Ten students pasting the
  same posting pay for one parse.
* ``job_targets`` is one user's vacancy: their text, their CV, their status
  and the match computed for them.

Neither touches ``job_postings`` (recruiter side, ``company_id NOT NULL``) nor
``job_skills``.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db import Base
from app.db_types import UUID

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")

JOB_TARGET_STATUS_PENDING = "pending"
JOB_TARGET_STATUS_PARSING = "parsing"
JOB_TARGET_STATUS_READY = "ready"
JOB_TARGET_STATUS_FAILED = "failed"
JOB_TARGET_STATUSES = (
    JOB_TARGET_STATUS_PENDING,
    JOB_TARGET_STATUS_PARSING,
    JOB_TARGET_STATUS_READY,
    JOB_TARGET_STATUS_FAILED,
)
WORKPLACE_TYPES = ("onsite", "hybrid", "remote")

#: Where the text came from. Only pasted text exists today; the column is there
#: so a later source (a public ATS API, plan 11 §11) needs no migration — which
#: is also why it has no CHECK.
JOB_SOURCE_PASTED = "pasted"

_ACTIVE_PREDICATE = text("status IN ('pending', 'parsing')")


def _in(column: str, values: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({listed})"


class JobDescriptionParseModel(Base):
    __tablename__ = "job_description_parses"

    #: sha256 of ``normalize_job_text(raw_text)``.
    text_hash = Column(String(64), primary_key=True)
    source = Column(String(32), nullable=False, default=JOB_SOURCE_PASTED)
    #: Requirements (required vs nice-to-have, importance), seniority, and
    #: whatever else the producer extracted. Its shape is versioned by
    #: ``prompt_version``, not by this column.
    parsed = Column(JSON_VARIANT, nullable=False)
    #: NULL until a real-vector provider embeds it. Always read together with
    #: ``embedding_model_name``: a vector without its space is not comparable.
    embedding = Column(Vector(384), nullable=True)
    embedding_model_name = Column(String(120), nullable=True)
    #: What produced ``parsed``: a model id, or a rules engine for C1.
    model_id = Column(String(120), nullable=False)
    prompt_version = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "(embedding IS NULL) = (embedding_model_name IS NULL)",
            name="ck_job_description_parses_embedding_has_model",
        ),
    )


class JobTargetModel(Base):
    __tablename__ = "job_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Deleting a CV does not delete the vacancies a user saved against it.
    resume_id = Column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    #: Points at ``job_description_parses.text_hash`` without a foreign key: the
    #: target exists (pending) before its parse does, and parses may expire.
    text_hash = Column(String(64), nullable=False)
    raw_text = Column(Text, nullable=False)
    source = Column(String(32), nullable=False, default=JOB_SOURCE_PASTED)
    # From the parse, editable by the user.
    title = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    workplace_type = Column(String(16), nullable=True)

    status = Column(String(16), nullable=False, default=JOB_TARGET_STATUS_PENDING)
    error_message = Column(Text, nullable=True)
    # The job_analysis lease cycle, copied as is.
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    lease_expires_at = Column(DateTime, nullable=True)
    #: Stamped immediately before a paid provider call. Its presence makes an
    #: interrupted target *uncertain*, so recovery fails it instead of paying
    #: again (plan 11 §7, leak 4).
    provider_attempted_at = Column(DateTime, nullable=True)

    #: Score and breakdown at the time of the analysis (plan 11 §4.1).
    match_snapshot = Column(JSON_VARIANT, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(_in("status", JOB_TARGET_STATUSES), name="ck_job_targets_status"),
        CheckConstraint(
            "workplace_type IS NULL OR " + _in("workplace_type", WORKPLACE_TYPES),
            name="ck_job_targets_workplace_type",
        ),
        CheckConstraint("attempts >= 0", name="ck_job_targets_attempts_non_negative"),
        # A user's list, newest first.
        Index("ix_job_targets_user_created", "user_id", "created_at"),
        Index("ix_job_targets_text_hash", "text_hash"),
        # The worker's due-work scan: only unfinished targets are looked at.
        Index(
            "ix_job_targets_active_lease",
            "lease_expires_at",
            postgresql_where=_ACTIVE_PREDICATE,
            sqlite_where=_ACTIVE_PREDICATE,
        ),
    )
