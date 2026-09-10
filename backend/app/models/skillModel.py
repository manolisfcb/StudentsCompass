from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db_types import UUID
from sqlalchemy.orm import relationship

from app.db import Base


JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")

#: The statuses ``resume_skills.status`` may hold. The column is a plain string
#: with a default, so anything at all could be written into it; these four are
#: what the service defines and what every reader switches on.
#: See ``capstoneAnalyticsService.RESUME_SKILL_STATUS_*``.
RESUME_SKILL_STATUSES = ("detected", "confirmed", "rejected", "manual")

#: Scores in this schema are fractions. The learning-route optimiser reads them
#: through ``_clamp(value, 0.0, 1.0)``, which means an out-of-range value is not
#: rejected today — it is silently reinterpreted as 0 or 1, and the number the
#: product acts on stops being the number that was stored. A CHECK turns that
#: into a refused write, which is the only place the difference is still visible.
_FRACTION = "{column} IS NULL OR ({column} >= 0 AND {column} <= 1)"

#: ``rating`` is a five-star scale: the optimiser scores it as ``rating / 5.0``
#: clamped to [0, 1], so a 9 means the same as a 5 and a −1 the same as a 0.
_FIVE_STAR = "rating IS NULL OR (rating >= 0 AND rating <= 5)"

#: Money and time. ``LearningRouteConstraintsPayload`` already declares
#: ``budget`` and ``available_hours`` as ``ge=0``; the catalogue they are
#: compared against had no such rule.
_NON_NEGATIVE = "{column} IS NULL OR {column} >= 0"


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
        # Partial, not a plain UniqueConstraint: ``job_posting_id`` is nullable
        # and PostgreSQL lets unlimited NULLs through a unique constraint, so
        # the rule is stated where it applies. Mirrors
        # ``uq_resume_skills_resume_skill_method`` on the resume side.
        Index(
            "uq_job_skills_posting_skill_method",
            "job_posting_id",
            "skill_id",
            "extraction_method",
            unique=True,
            postgresql_where=text("job_posting_id IS NOT NULL"),
            sqlite_where=text("job_posting_id IS NOT NULL"),
        ),
        Index("ix_job_skills_job_posting_id", "job_posting_id"),
        Index("ix_job_skills_skill_id", "skill_id"),
        Index("ix_job_skills_target_role", "target_role"),
        CheckConstraint(
            _FRACTION.format(column="importance_score"),
            name="ck_job_skills_importance_score_fraction",
        ),
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
        Index("ix_resume_skills_status", "status"),
        CheckConstraint(
            "status IN ('" + "', '".join(RESUME_SKILL_STATUSES) + "')",
            name="ck_resume_skills_status",
        ),
        CheckConstraint(
            _FRACTION.format(column="confidence_score"),
            name="ck_resume_skills_confidence_score_fraction",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    confidence_score = Column(Float, nullable=True)
    extraction_method = Column(String(64), nullable=False, default="manual")
    evidence_text = Column(Text, nullable=True)
    source_section = Column(String(80), nullable=True)
    status = Column(String(32), nullable=False, default="detected")
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    skill = relationship("SkillModel", back_populates="resume_skills")
    resume = relationship("ResumeModel")
    user = relationship("User", foreign_keys=[user_id])
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by_user_id])


class CourseModel(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("provider", "title", name="uq_courses_provider_title"),
        Index("ix_courses_provider", "provider"),
        Index("ix_courses_difficulty", "difficulty"),
        Index("ix_courses_is_active", "is_active"),
        CheckConstraint(_NON_NEGATIVE.format(column="cost"), name="ck_courses_cost_non_negative"),
        CheckConstraint(
            _NON_NEGATIVE.format(column="duration_hours"),
            name="ck_courses_duration_hours_non_negative",
        ),
        CheckConstraint(_FIVE_STAR, name="ck_courses_rating_five_star"),
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
        CheckConstraint(
            _FRACTION.format(column="coverage_score"),
            name="ck_course_skills_coverage_score_fraction",
        ),
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
