from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base


JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class SkillModel(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_skills_normalized_name"),
        Index("ix_skills_category", "category"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_name = Column(String(120), nullable=False)
    display_name = Column(String(160), nullable=False)
    category = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String(64), nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    aliases = relationship("SkillAliasModel", back_populates="skill", cascade="all, delete-orphan")
    job_skills = relationship("JobSkillModel", back_populates="skill", cascade="all, delete-orphan")
    resume_skills = relationship("ResumeSkillModel", back_populates="skill", cascade="all, delete-orphan")
    course_skills = relationship("CourseSkillModel", back_populates="skill", cascade="all, delete-orphan")


class SkillAliasModel(Base):
    __tablename__ = "skill_aliases"
    __table_args__ = (
        UniqueConstraint("alias", name="uq_skill_aliases_alias"),
        Index("ix_skill_aliases_skill_id", "skill_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(160), nullable=False)
    source = Column(String(64), nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    skill = relationship("SkillModel", back_populates="aliases")


class JobSkillModel(Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        Index("ix_job_skills_job_posting_id", "job_posting_id"),
        Index("ix_job_skills_skill_id", "skill_id"),
        Index("ix_job_skills_target_role", "target_role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_posting_id = Column(UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    target_role = Column(String(120), nullable=True)
    importance_score = Column(Float, nullable=True)
    extraction_method = Column(String(64), nullable=False, default="manual")
    evidence_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    skill = relationship("SkillModel", back_populates="job_skills")
    job_posting = relationship("JobPosting")


class ResumeSkillModel(Base):
    __tablename__ = "resume_skills"
    __table_args__ = (
        UniqueConstraint("resume_id", "skill_id", "extraction_method", name="uq_resume_skills_resume_skill_method"),
        Index("ix_resume_skills_resume_id", "resume_id"),
        Index("ix_resume_skills_user_id", "user_id"),
        Index("ix_resume_skills_skill_id", "skill_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    confidence_score = Column(Float, nullable=True)
    extraction_method = Column(String(64), nullable=False, default="manual")
    evidence_text = Column(Text, nullable=True)
    source_section = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    skill = relationship("SkillModel", back_populates="resume_skills")
    resume = relationship("ResumeModel")
    user = relationship("User")


class CourseModel(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("provider", "title", name="uq_courses_provider_title"),
        Index("ix_courses_provider", "provider"),
        Index("ix_courses_difficulty", "difficulty"),
        Index("ix_courses_is_active", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(220), nullable=False)
    provider = Column(String(120), nullable=False)
    url = Column(String(512), nullable=True)
    cost = Column(Float, nullable=True)
    currency = Column(String(3), nullable=False, default="CAD")
    duration_hours = Column(Float, nullable=True)
    difficulty = Column(String(32), nullable=True)
    rating = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    resource = relationship("ResourceModel")
    skills = relationship("CourseSkillModel", back_populates="course", cascade="all, delete-orphan")


class CourseSkillModel(Base):
    __tablename__ = "course_skills"
    __table_args__ = (
        UniqueConstraint("course_id", "skill_id", name="uq_course_skills_course_skill"),
        Index("ix_course_skills_course_id", "course_id"),
        Index("ix_course_skills_skill_id", "skill_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    coverage_score = Column(Float, nullable=True)
    is_prerequisite = Column(Boolean, nullable=False, default=False)
    evidence_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    course = relationship("CourseModel", back_populates="skills")
    skill = relationship("SkillModel", back_populates="course_skills")


class OptimizationRunModel(Base):
    __tablename__ = "optimization_runs"
    __table_args__ = (
        Index("ix_optimization_runs_user_id", "user_id"),
        Index("ix_optimization_runs_resume_id", "resume_id"),
        Index("ix_optimization_runs_target_role", "target_role"),
        Index("ix_optimization_runs_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    target_role = Column(String(120), nullable=False)
    budget = Column(Float, nullable=True)
    available_hours = Column(Float, nullable=True)
    max_courses = Column(Integer, nullable=True)
    objective_version = Column(String(40), nullable=False, default="gap_coverage_v1")
    status = Column(String(32), nullable=False, default="draft")
    total_score = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    total_hours = Column(Float, nullable=True)
    skill_coverage = Column(JSON_VARIANT, nullable=True)
    constraints = Column(JSON_VARIANT, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    resume = relationship("ResumeModel")
