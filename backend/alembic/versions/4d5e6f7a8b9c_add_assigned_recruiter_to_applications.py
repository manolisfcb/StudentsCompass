"""add assigned recruiter to applications

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-03-10 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, Sequence[str], None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("assigned_recruiter_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_applications_assigned_recruiter_id_company_recruiters",
        "applications",
        "company_recruiters",
        ["assigned_recruiter_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_applications_company_assigned_recruiter_created_at",
        "applications",
        ["company_id", "assigned_recruiter_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_applications_company_assigned_recruiter_created_at", table_name="applications")
    op.drop_constraint(
        "fk_applications_assigned_recruiter_id_company_recruiters",
        "applications",
        type_="foreignkey",
    )
    op.drop_column("applications", "assigned_recruiter_id")
