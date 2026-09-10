from sqlalchemy import Column, Integer, DateTime, Text, Enum as SQLEnum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Statuses a job can still be worked on from. Spelled as the labels PostgreSQL
# actually stores (SQLAlchemy persists Enum *names*), because they appear inside
# index predicates.
ACTIVE_STATUS_LABELS = ("PENDING", "PROCESSING")
_ACTIVE_PREDICATE = text("status IN ('PENDING', 'PROCESSING')")


class JobAnalysisModel(Base):
    __tablename__ = "job_analysis"
    __table_args__ = (
        # One live analysis per CV. Checking for a running job and then inserting
        # is two statements: two simultaneous POSTs both saw "none running" and
        # both created one. The database decides instead, and the loser joins the
        # winner's job.
        Index(
            "uq_job_analysis_active_per_resume",
            "user_id",
            "resume_id",
            unique=True,
            postgresql_where=_ACTIVE_PREDICATE,
            sqlite_where=_ACTIVE_PREDICATE,
        ),
        # The runner's due-work scan: only unfinished jobs are ever looked at.
        Index(
            "ix_job_analysis_active_lease",
            "lease_expires_at",
            postgresql_where=_ACTIVE_PREDICATE,
            sqlite_where=_ACTIVE_PREDICATE,
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    keywords = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    # How many times the job has been claimed. Bounds retries so a job that
    # fails the same way forever stops instead of looping.
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    # Set while a worker holds the job. A lease in the past means the worker is
    # gone (process killed, deploy) and the job may be recovered.
    lease_expires_at = Column(DateTime, nullable=True)
    # Stamped immediately before the provider call. Its presence is what makes
    # an interrupted job *uncertain*: the money may already have been spent, so
    # recovery must never silently run it again.
    provider_attempted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationship
    user = relationship("User", back_populates="job_analyses")
    resume = relationship("ResumeModel", back_populates="job_analyses")
