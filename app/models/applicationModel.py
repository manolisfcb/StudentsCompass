from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.models.jobPostingModel import JobPosting
from app.models.interviewAvailabilityModel import InterviewAvailabilityStatus
from app.db import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import enum
from sqlalchemy import text


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    IN_REVIEW = "in_review"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationMatchStrength(str, enum.Enum):
    STRONG_MATCH = "strong_match"
    MATCH = "match"
    WEAK_MATCH = "weak_match"


class ApplicationModel(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(job_title)) > 0",
            name="ck_applications_job_title_not_blank",
        ),
        ForeignKeyConstraint(
            ["job_posting_id", "company_id"],
            ["job_postings.id", "job_postings.company_id"],
            name="fk_applications_job_posting_id_company_id_job_postings",
        ),
        Index("ix_applications_user_created_at", "user_id", "created_at"),
        Index("ix_applications_company_status_created_at", "company_id", "status", "created_at"),
        Index("ix_applications_job_posting_created_at", "job_posting_id", "created_at"),
        Index(
            "ux_applications_user_job_posting_not_null",
            "user_id",
            "job_posting_id",
            unique=True,
            postgresql_where=text("job_posting_id IS NOT NULL"),
        ),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    assigned_recruiter_id = Column(UUID(as_uuid=True), ForeignKey("company_recruiters.id"), nullable=True)
    job_posting_id = Column(UUID(as_uuid=True), nullable=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)
    
    job_title = Column(String, nullable=False)
    status = Column(Enum(ApplicationStatus), nullable=False, default=ApplicationStatus.APPLIED)
    match_strength = Column(
        Enum(
            ApplicationMatchStrength,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="applicationmatchstrength",
        ),
        nullable=False,
        default=ApplicationMatchStrength.MATCH,
    )
    application_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    application_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    company = relationship("Company", back_populates="applications", overlaps="job_posting,applications")
    assigned_recruiter = relationship("CompanyRecruiter")
    job_posting = relationship("JobPosting", back_populates="applications", overlaps="company,applications")
    resume = relationship("ResumeModel", back_populates="applications")
    status_events = relationship("ApplicationStatusEventModel", back_populates="application")
    interview_availabilities = relationship(
        "InterviewAvailabilityModel",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="InterviewAvailabilityModel.starts_at.asc()",
    )

    @property
    def company_name(self) -> str | None:
        company = self.__dict__.get("company")
        return company.company_name if company else None

    @property
    def company_location(self) -> str | None:
        company = self.__dict__.get("company")
        return company.location if company else None

    @property
    def selected_interview_slot(self):
        for slot in self.interview_availabilities or []:
            normalized_status = slot.status.value if hasattr(slot.status, "value") else str(slot.status)
            if normalized_status == InterviewAvailabilityStatus.BOOKED.value:
                return slot
        return None

    @property
    def available_interview_slots(self):
        return [
            slot for slot in (self.interview_availabilities or [])
            if (slot.status.value if hasattr(slot.status, "value") else str(slot.status))
            == InterviewAvailabilityStatus.AVAILABLE.value
        ]
