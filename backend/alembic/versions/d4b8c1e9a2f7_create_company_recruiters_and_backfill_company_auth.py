"""create company recruiters and backfill company auth

Revision ID: d4b8c1e9a2f7
Revises: c8a6f3d4b1e2
Create Date: 2026-03-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4b8c1e9a2f7"
down_revision: Union[str, Sequence[str], None] = "c8a6f3d4b1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_recruiters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'owner'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_company_recruiters_email"),
    )
    op.create_index(
        "ix_company_recruiters_company_id",
        "company_recruiters",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_recruiters_company_id_is_active",
        "company_recruiters",
        ["company_id", "is_active"],
        unique=False,
    )

    # Backfill one owner recruiter per existing company-auth account.
    op.execute(
        sa.text(
            """
            INSERT INTO company_recruiters (
                id,
                company_id,
                email,
                hashed_password,
                is_active,
                is_superuser,
                is_verified,
                role,
                created_at,
                updated_at
            )
            SELECT
                c.id,
                c.id,
                c.email,
                c.hashed_password,
                COALESCE(c.is_active, TRUE),
                COALESCE(c.is_superuser, FALSE),
                COALESCE(c.is_verified, TRUE),
                'owner',
                COALESCE(c.created_at, NOW()),
                COALESCE(c.updated_at, NOW())
            FROM companies AS c
            WHERE c.email IS NOT NULL
              AND c.hashed_password IS NOT NULL
            ON CONFLICT (email) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_company_recruiters_company_id_is_active", table_name="company_recruiters")
    op.drop_index("ix_company_recruiters_company_id", table_name="company_recruiters")
    op.drop_table("company_recruiters")
