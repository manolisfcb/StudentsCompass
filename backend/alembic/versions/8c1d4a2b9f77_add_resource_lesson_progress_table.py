"""add resource lesson progress table

Revision ID: 8c1d4a2b9f77
Revises: f2b6c1d7e8f9
Create Date: 2026-03-07 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c1d4a2b9f77"
down_revision: Union[str, Sequence[str], None] = "f2b6c1d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resource_lesson_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_opened_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lesson_id"], ["resource_lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_resource_lesson_progress_user_lesson"),
    )
    op.create_index(
        "ix_resource_lesson_progress_user_id",
        "resource_lesson_progress",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_resource_lesson_progress_lesson_id",
        "resource_lesson_progress",
        ["lesson_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_resource_lesson_progress_lesson_id", table_name="resource_lesson_progress")
    op.drop_index("ix_resource_lesson_progress_user_id", table_name="resource_lesson_progress")
    op.drop_table("resource_lesson_progress")
