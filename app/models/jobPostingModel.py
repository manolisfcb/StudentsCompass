from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.db import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime


class JobPosting(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_job_postings_id_company_id"),
        CheckConstraint(
            "expires_at IS NULL OR expires_at >= created_at",
            name="ck_job_postings_expires_after_created",
        ),
        Index("ix_job_postings_company_created_at", "company_id", "created_at"),
        Index(
            "ix_job_postings_company_active_expires_created",
            "company_id",
            "is_active",
            "expires_at",
            "created_at",
        ),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    job_type = Column(String, nullable=True)  # full-time, part-time, internship, etc.
    salary_range = Column(String, nullable=True)
    application_url = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    company = relationship("Company", back_populates="job_postings")
    applications = relationship("ApplicationModel", back_populates="job_posting", overlaps="company,applications")
