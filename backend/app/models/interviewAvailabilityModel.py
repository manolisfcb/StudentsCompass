from datetime import datetime
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, String, Text, text
from app.db_types import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class InterviewAvailabilityStatus(str, enum.Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    CANCELLED = "cancelled"


class InterviewAvailabilityModel(Base):
    __tablename__ = "interview_availabilities"
    __table_args__ = (
        Index("ix_interview_availabilities_application_status", "application_id", "status"),
        Index("ix_interview_availabilities_company_start", "company_id", "starts_at"),
        # At most one confirmed time per application. The slots belong to an
        # application, not to a company calendar, so this says nothing about a
        # recruiter's wider agenda — only that a candidate cannot end up with two
        # confirmed interviews for the same job. The predicate uses the stored
        # value ('booked'), because this Enum persists values, not names.
        Index(
            "uq_interview_availabilities_booked_per_application",
            "application_id",
            unique=True,
            postgresql_where=text("status = 'booked'"),
            sqlite_where=text("status = 'booked'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("company_recruiters.id", ondelete="SET NULL"), nullable=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    timezone = Column(String(64), nullable=False, default="America/Toronto")
    status = Column(
        Enum(
            InterviewAvailabilityStatus,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="interviewavailabilitystatus",
        ),
        nullable=False,
        default=InterviewAvailabilityStatus.AVAILABLE,
    )
    notes = Column(Text, nullable=True)
    booked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("ApplicationModel", back_populates="interview_availabilities")
