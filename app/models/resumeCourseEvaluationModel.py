from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class ResumeCourseEvaluationStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeCourseEvaluationModel(Base):
    __tablename__ = "resume_course_evaluations"
    # Declared here because the index exists in every deployed database:
    # an autogenerate run against metadata that omits it proposes dropping
    # it, which is how a previous revision silently removed a batch of them.
    __table_args__ = (
        Index("ix_resume_course_evaluations_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        SQLEnum(
            ResumeCourseEvaluationStatus,
            name="resumecourseevaluationstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ResumeCourseEvaluationStatus.PENDING,
    )

    overall_score = Column(Float, nullable=True)
    llm_confidence = Column(Float, nullable=True)
    pass_status = Column(Boolean, nullable=True)
    report_text = Column(Text, nullable=True)
    structured_payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    prompt_version = Column(String(40), nullable=False, default="resume_audit_v2")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="resume_course_evaluations")
    resume = relationship("ResumeModel", back_populates="course_evaluations")
