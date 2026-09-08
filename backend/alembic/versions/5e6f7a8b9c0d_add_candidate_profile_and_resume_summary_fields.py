"""add candidate profile and resume summary fields

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-03-10 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e6f7a8b9c0d"
down_revision: Union[str, Sequence[str], None] = "4d5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("address", sa.String(), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("users", sa.Column("sex", sa.String(), nullable=True))
    op.add_column("users", sa.Column("age", sa.Integer(), nullable=True))

    op.add_column("resumes", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column("resumes", sa.Column("contact_phone", sa.String(length=64), nullable=True))

    op.add_column("job_analysis", sa.Column("summary", sa.Text(), nullable=True))

    op.add_column("applications", sa.Column("resume_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_applications_resume_id_resumes",
        "applications",
        "resumes",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_applications_resume_id", "applications", ["resume_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_applications_resume_id", table_name="applications")
    op.drop_constraint("fk_applications_resume_id_resumes", "applications", type_="foreignkey")
    op.drop_column("applications", "resume_id")

    op.drop_column("job_analysis", "summary")

    op.drop_column("resumes", "contact_phone")
    op.drop_column("resumes", "ai_summary")

    op.drop_column("users", "age")
    op.drop_column("users", "sex")
    op.drop_column("users", "phone")
    op.drop_column("users", "address")
