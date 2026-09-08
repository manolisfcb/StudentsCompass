from datetime import date, datetime
import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.applicationModel import ApplicationStatus


class ApplicationEventType(str, enum.Enum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    DELETED = "deleted"


class ApplicationStatusEventModel(Base):
    __tablename__ = "application_status_events"
    __table_args__ = (
        Index("ix_application_status_events_company_occurred_at", "company_id", "occurred_at"),
        Index("ix_application_status_events_application_occurred_at", "application_id", "occurred_at"),
        Index("ix_application_status_events_event_type_occurred_at", "event_type", "occurred_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    job_posting_id = Column(UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True)
    triggered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    triggered_by_company_recruiter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_recruiters.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type = Column(Enum(ApplicationEventType), nullable=False)
    from_status = Column(Enum(ApplicationStatus), nullable=True)
    to_status = Column(Enum(ApplicationStatus), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    application = relationship("ApplicationModel", back_populates="status_events")


class ApplicationDailyAggregateModel(Base):
    __tablename__ = "application_daily_aggregates"
    __table_args__ = (
        UniqueConstraint("company_id", "metric_date", name="uq_application_daily_aggregate_company_date"),
        Index("ix_application_daily_aggregates_company_metric_date", "company_id", "metric_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False, default=date.today)
    applications_created_count = Column(Integer, nullable=False, default=0)
    applications_deleted_count = Column(Integer, nullable=False, default=0)
    status_change_events_count = Column(Integer, nullable=False, default=0)
    entered_applied_count = Column(Integer, nullable=False, default=0)
    entered_in_review_count = Column(Integer, nullable=False, default=0)
    entered_interview_count = Column(Integer, nullable=False, default=0)
    entered_offer_count = Column(Integer, nullable=False, default=0)
    entered_rejected_count = Column(Integer, nullable=False, default=0)
    entered_withdrawn_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
