"""drop legacy company auth columns

Revision ID: f3a8c1d2e4b5
Revises: e6f1a2b3c4d5
Create Date: 2026-03-10 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a8c1d2e4b5"
down_revision: Union[str, Sequence[str], None] = "e6f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_COMPANY_AUTH_COLUMNS = (
    "email",
    "hashed_password",
    "is_active",
    "is_superuser",
    "is_verified",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("companies")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("companies")}

    if "ix_companies_email" in existing_indexes:
        op.drop_index("ix_companies_email", table_name="companies")

    for column_name in LEGACY_COMPANY_AUTH_COLUMNS:
        if column_name in existing_columns:
            op.drop_column("companies", column_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("companies")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("companies")}

    if "email" not in existing_columns:
        op.add_column("companies", sa.Column("email", sa.String(length=320), nullable=True))
    if "hashed_password" not in existing_columns:
        op.add_column("companies", sa.Column("hashed_password", sa.String(length=1024), nullable=True))
    if "is_active" not in existing_columns:
        op.add_column(
            "companies",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
    if "is_superuser" not in existing_columns:
        op.add_column(
            "companies",
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "is_verified" not in existing_columns:
        op.add_column(
            "companies",
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )

    bind.execute(
        sa.text(
            """
            WITH ranked_recruiters AS (
                SELECT
                    cr.company_id,
                    cr.email,
                    cr.hashed_password,
                    cr.is_active,
                    cr.is_superuser,
                    cr.is_verified,
                    ROW_NUMBER() OVER (
                        PARTITION BY cr.company_id
                        ORDER BY
                            CASE WHEN cr.role = 'owner' THEN 0 ELSE 1 END,
                            cr.created_at,
                            cr.id
                    ) AS rn
                FROM company_recruiters AS cr
            )
            UPDATE companies AS c
            SET
                email = rr.email,
                hashed_password = rr.hashed_password,
                is_active = rr.is_active,
                is_superuser = rr.is_superuser,
                is_verified = rr.is_verified
            FROM ranked_recruiters AS rr
            WHERE rr.company_id = c.id
              AND rr.rn = 1
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE companies
            SET
                email = COALESCE(email, CONCAT(id::text, '@legacy-company.local')),
                hashed_password = COALESCE(hashed_password, 'LEGACY_COMPANY_LOGIN_DISABLED'),
                is_active = COALESCE(is_active, true),
                is_superuser = COALESCE(is_superuser, false),
                is_verified = COALESCE(is_verified, true)
            """
        )
    )

    op.alter_column("companies", "email", existing_type=sa.String(length=320), nullable=False)
    op.alter_column("companies", "hashed_password", existing_type=sa.String(length=1024), nullable=False)
    op.alter_column("companies", "is_active", existing_type=sa.Boolean(), server_default=None)
    op.alter_column("companies", "is_superuser", existing_type=sa.Boolean(), server_default=None)
    op.alter_column("companies", "is_verified", existing_type=sa.Boolean(), server_default=None)

    if "ix_companies_email" not in existing_indexes:
        op.create_index("ix_companies_email", "companies", ["email"], unique=True)
