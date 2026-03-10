from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_company_name", "company_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    location = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    recruiters = relationship("CompanyRecruiter", back_populates="company", cascade="all, delete-orphan")
    job_postings = relationship("JobPosting", back_populates="company", cascade="all, delete-orphan")
    applications = relationship("ApplicationModel", back_populates="company", overlaps="job_posting,applications")
