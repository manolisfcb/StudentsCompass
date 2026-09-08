"""add resume skill review status

Revision ID: d3e4f5a6b7c8
Revises: a9b1c2d3e4f6
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "a9b1c2d3e4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


uuid_type = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "resume_skills",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="detected"),
    )
    op.add_column("resume_skills", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("resume_skills", sa.Column("reviewed_by_user_id", uuid_type, nullable=True))
    op.create_foreign_key(
        "fk_resume_skills_reviewed_by_user_id_users",
        "resume_skills",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_resume_skills_status", "resume_skills", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_resume_skills_status", table_name="resume_skills")
    op.drop_constraint(
        "fk_resume_skills_reviewed_by_user_id_users",
        "resume_skills",
        type_="foreignkey",
    )
    op.drop_column("resume_skills", "reviewed_by_user_id")
    op.drop_column("resume_skills", "reviewed_at")
    op.drop_column("resume_skills", "status")
