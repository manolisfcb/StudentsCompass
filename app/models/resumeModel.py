
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db import Base
from datetime import datetime
import uuid

class ResumeModel(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    view_url = Column(String(255), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    storage_file_id = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    folder_id = Column(String(255), nullable=False)
    ai_summary = Column(Text, nullable=True)
    contact_phone = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    
    user = relationship("User", back_populates="resumes")
    job_analyses = relationship("JobAnalysisModel", back_populates="resume")
    course_evaluations = relationship("ResumeCourseEvaluationModel", back_populates="resume", cascade="all, delete-orphan")
    applications = relationship("ApplicationModel", back_populates="resume")
