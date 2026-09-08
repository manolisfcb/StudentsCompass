"""add resume course evaluations table

Revision ID: 9b72c4e1af10
Revises: 8c1d4a2b9f77
Create Date: 2026-03-07 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9b72c4e1af10"
down_revision: Union[str, Sequence[str], None] = "8c1d4a2b9f77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = postgresql.ENUM(
        "pending",
        "completed",
        "failed",
        name="resumecourseevaluationstatus",
        create_type=False,
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "resume_course_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        sa.Column("pass_status", sa.Boolean(), nullable=True),
        sa.Column("report_text", sa.Text(), nullable=True),
        sa.Column("structured_payload", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=False, server_default="resume_audit_v1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resume_course_evaluations_user_id",
        "resume_course_evaluations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_resume_course_evaluations_resume_id",
        "resume_course_evaluations",
        ["resume_id"],
        unique=False,
    )
    op.create_index(
        "ix_resume_course_evaluations_created_at",
        "resume_course_evaluations",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_resume_course_evaluations_created_at", table_name="resume_course_evaluations")
    op.drop_index("ix_resume_course_evaluations_resume_id", table_name="resume_course_evaluations")
    op.drop_index("ix_resume_course_evaluations_user_id", table_name="resume_course_evaluations")
    op.drop_table("resume_course_evaluations")
    postgresql.ENUM(name="resumecourseevaluationstatus").drop(op.get_bind(), checkfirst=True)
