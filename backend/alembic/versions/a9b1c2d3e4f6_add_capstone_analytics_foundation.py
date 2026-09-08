"""add capstone analytics foundation

Revision ID: a9b1c2d3e4f6
Revises: 3f8a2c9d1e7b
Create Date: 2026-06-18 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a9b1c2d3e4f6"
down_revision: Union[str, Sequence[str], None] = "3f8a2c9d1e7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


uuid_type = postgresql.UUID(as_uuid=True)
json_variant = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_skills_normalized_name"),
    )
    op.create_index("ix_skills_category", "skills", ["category"], unique=False)

    op.create_table(
        "skill_aliases",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("skill_id", uuid_type, nullable=False),
        sa.Column("alias", sa.String(length=160), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias", name="uq_skill_aliases_alias"),
    )
    op.create_index("ix_skill_aliases_skill_id", "skill_aliases", ["skill_id"], unique=False)

    op.create_table(
        "courses",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("resource_id", uuid_type, nullable=True),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "title", name="uq_courses_provider_title"),
    )
    op.create_index("ix_courses_difficulty", "courses", ["difficulty"], unique=False)
    op.create_index("ix_courses_is_active", "courses", ["is_active"], unique=False)
    op.create_index("ix_courses_provider", "courses", ["provider"], unique=False)

    op.create_table(
        "job_skills",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("job_posting_id", uuid_type, nullable=True),
        sa.Column("skill_id", uuid_type, nullable=False),
        sa.Column("target_role", sa.String(length=120), nullable=True),
        sa.Column("importance_score", sa.Float(), nullable=True),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_skills_job_posting_id", "job_skills", ["job_posting_id"], unique=False)
    op.create_index("ix_job_skills_skill_id", "job_skills", ["skill_id"], unique=False)
    op.create_index("ix_job_skills_target_role", "job_skills", ["target_role"], unique=False)

    op.create_table(
        "resume_skills",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("resume_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=True),
        sa.Column("skill_id", uuid_type, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("source_section", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_id", "skill_id", "extraction_method", name="uq_resume_skills_resume_skill_method"),
    )
    op.create_index("ix_resume_skills_resume_id", "resume_skills", ["resume_id"], unique=False)
    op.create_index("ix_resume_skills_skill_id", "resume_skills", ["skill_id"], unique=False)
    op.create_index("ix_resume_skills_user_id", "resume_skills", ["user_id"], unique=False)

    op.create_table(
        "course_skills",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("course_id", uuid_type, nullable=False),
        sa.Column("skill_id", uuid_type, nullable=False),
        sa.Column("coverage_score", sa.Float(), nullable=True),
        sa.Column("is_prerequisite", sa.Boolean(), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "skill_id", name="uq_course_skills_course_skill"),
    )
    op.create_index("ix_course_skills_course_id", "course_skills", ["course_id"], unique=False)
    op.create_index("ix_course_skills_skill_id", "course_skills", ["skill_id"], unique=False)

    op.create_table(
        "optimization_runs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=True),
        sa.Column("resume_id", uuid_type, nullable=True),
        sa.Column("target_role", sa.String(length=120), nullable=False),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("available_hours", sa.Float(), nullable=True),
        sa.Column("max_courses", sa.Integer(), nullable=True),
        sa.Column("objective_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("total_hours", sa.Float(), nullable=True),
        sa.Column("skill_coverage", json_variant, nullable=True),
        sa.Column("constraints", json_variant, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_runs_resume_id", "optimization_runs", ["resume_id"], unique=False)
    op.create_index("ix_optimization_runs_status", "optimization_runs", ["status"], unique=False)
    op.create_index("ix_optimization_runs_target_role", "optimization_runs", ["target_role"], unique=False)
    op.create_index("ix_optimization_runs_user_id", "optimization_runs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_optimization_runs_user_id", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_target_role", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_status", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_resume_id", table_name="optimization_runs")
    op.drop_table("optimization_runs")

    op.drop_index("ix_course_skills_skill_id", table_name="course_skills")
    op.drop_index("ix_course_skills_course_id", table_name="course_skills")
    op.drop_table("course_skills")

    op.drop_index("ix_resume_skills_user_id", table_name="resume_skills")
    op.drop_index("ix_resume_skills_skill_id", table_name="resume_skills")
    op.drop_index("ix_resume_skills_resume_id", table_name="resume_skills")
    op.drop_table("resume_skills")

    op.drop_index("ix_job_skills_target_role", table_name="job_skills")
    op.drop_index("ix_job_skills_skill_id", table_name="job_skills")
    op.drop_index("ix_job_skills_job_posting_id", table_name="job_skills")
    op.drop_table("job_skills")

    op.drop_index("ix_courses_provider", table_name="courses")
    op.drop_index("ix_courses_is_active", table_name="courses")
    op.drop_index("ix_courses_difficulty", table_name="courses")
    op.drop_table("courses")

    op.drop_index("ix_skill_aliases_skill_id", table_name="skill_aliases")
    op.drop_table("skill_aliases")

    op.drop_index("ix_skills_category", table_name="skills")
    op.drop_table("skills")
