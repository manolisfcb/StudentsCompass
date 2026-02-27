"""add resource enrollment and progress tables

Revision ID: 6e4bc7a18f21
Revises: 1720e86014a0
Create Date: 2026-02-24 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6e4bc7a18f21"
down_revision: Union[str, Sequence[str], None] = "1720e86014a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "resource_enrollments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("last_opened_lesson_id", sa.UUID(), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["last_opened_lesson_id"], ["resource_lessons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_resource_enrollments_user_resource"),
    )
    op.create_index("ix_resource_enrollments_user_id", "resource_enrollments", ["user_id"], unique=False)
    op.create_index("ix_resource_enrollments_resource_id", "resource_enrollments", ["resource_id"], unique=False)

    op.create_table(
        "resource_lesson_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_opened_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lesson_id"], ["resource_lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_resource_lesson_progress_user_lesson"),
    )
    op.create_index("ix_resource_lesson_progress_user_id", "resource_lesson_progress", ["user_id"], unique=False)
    op.create_index("ix_resource_lesson_progress_resource_id", "resource_lesson_progress", ["resource_id"], unique=False)
    op.create_index("ix_resource_lesson_progress_lesson_id", "resource_lesson_progress", ["lesson_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_resource_lesson_progress_lesson_id", table_name="resource_lesson_progress")
    op.drop_index("ix_resource_lesson_progress_resource_id", table_name="resource_lesson_progress")
    op.drop_index("ix_resource_lesson_progress_user_id", table_name="resource_lesson_progress")
    op.drop_table("resource_lesson_progress")

    op.drop_index("ix_resource_enrollments_resource_id", table_name="resource_enrollments")
    op.drop_index("ix_resource_enrollments_user_id", table_name="resource_enrollments")
    op.drop_table("resource_enrollments")
