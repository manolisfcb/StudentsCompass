"""add indexes and integrity constraints for company domain

Revision ID: c8a6f3d4b1e2
Revises: b7c3d9e2f1a4
Create Date: 2026-03-10 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a6f3d4b1e2"
down_revision: Union[str, Sequence[str], None] = "b7c3d9e2f1a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_by_columns(
    table_name: str,
    constrained_columns: list[str],
    referred_table: str | None = None,
) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        columns = fk.get("constrained_columns") or []
        if columns != constrained_columns:
            continue
        if referred_table and fk.get("referred_table") != referred_table:
            continue
        fk_name = fk.get("name")
        if fk_name:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")
        return


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # Normalize legacy inconsistent rows before adding strict FK constraints.
    op.execute(
        sa.text(
            """
            UPDATE applications AS a
            SET job_posting_id = NULL
            FROM job_postings AS j
            WHERE a.job_posting_id = j.id
              AND a.company_id <> j.company_id
            """
        )
    )

    # Guard unique index creation with a readable error if duplicates exist.
    duplicate_pairs = bind.execute(
        sa.text(
            """
            SELECT user_id, job_posting_id, COUNT(*) AS total
            FROM applications
            WHERE job_posting_id IS NOT NULL
            GROUP BY user_id, job_posting_id
            HAVING COUNT(*) > 1
            LIMIT 5
            """
        )
    ).fetchall()
    if duplicate_pairs:
        preview = "; ".join(
            f"user_id={row[0]}, job_posting_id={row[1]}, total={row[2]}"
            for row in duplicate_pairs
        )
        raise RuntimeError(
            "Cannot add unique applications(user_id, job_posting_id) index because duplicate rows exist. "
            f"Examples: {preview}"
        )

    op.create_unique_constraint(
        "uq_job_postings_id_company_id",
        "job_postings",
        ["id", "company_id"],
    )

    op.create_check_constraint(
        "ck_job_postings_expires_after_created",
        "job_postings",
        "expires_at IS NULL OR expires_at >= created_at",
    )
    op.create_check_constraint(
        "ck_applications_job_title_not_blank",
        "applications",
        "char_length(btrim(job_title)) > 0",
    )

    _drop_fk_by_columns("applications", ["job_posting_id"], referred_table="job_postings")
    op.create_foreign_key(
        "fk_applications_job_posting_id_company_id_job_postings",
        "applications",
        "job_postings",
        ["job_posting_id", "company_id"],
        ["id", "company_id"],
    )

    op.create_index(
        "ix_companies_company_name",
        "companies",
        ["company_name"],
        unique=False,
    )
    op.create_index(
        "ix_job_postings_company_created_at",
        "job_postings",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_job_postings_company_active_expires_created",
        "job_postings",
        ["company_id", "is_active", "expires_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_applications_user_created_at",
        "applications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_applications_company_status_created_at",
        "applications",
        ["company_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_applications_job_posting_created_at",
        "applications",
        ["job_posting_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ux_applications_user_job_posting_not_null",
        "applications",
        ["user_id", "job_posting_id"],
        unique=True,
        postgresql_where=sa.text("job_posting_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_applications_user_job_posting_not_null", table_name="applications")
    op.drop_index("ix_applications_job_posting_created_at", table_name="applications")
    op.drop_index("ix_applications_company_status_created_at", table_name="applications")
    op.drop_index("ix_applications_user_created_at", table_name="applications")
    op.drop_index("ix_job_postings_company_active_expires_created", table_name="job_postings")
    op.drop_index("ix_job_postings_company_created_at", table_name="job_postings")
    op.drop_index("ix_companies_company_name", table_name="companies")

    op.drop_constraint(
        "fk_applications_job_posting_id_company_id_job_postings",
        "applications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_applications_job_posting_id_job_postings",
        "applications",
        "job_postings",
        ["job_posting_id"],
        ["id"],
    )

    op.drop_constraint("ck_applications_job_title_not_blank", "applications", type_="check")
    op.drop_constraint("ck_job_postings_expires_after_created", "job_postings", type_="check")
    op.drop_constraint("uq_job_postings_id_company_id", "job_postings", type_="unique")
