"""Give the mandatory courses a stable identity

Progress on the three core courses was keyed on ``resources.title``. A title is
editable content: renaming "Resume Templates" would have silently zeroed every
student's resume progress on the dashboard while the course page kept counting,
because the two screens looked the course up differently.

``core_code`` is that identity. It is **nullable** — ordinary resources carry no
code — and the backfill only claims a row when the match is unambiguous: exactly
one published resource with the seeded title. Ambiguous or missing matches are
logged and left alone for an operator to decide; nothing is renamed, merged or
deleted here.

The unique index constrains only the rows that carry a code: both PostgreSQL and
SQLite treat NULLs as distinct in a unique index.

Revision ID: a7d3f81c9e64
Revises: f4c9a17be205
Create Date: 2026-09-07
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7d3f81c9e64"
down_revision: Union[str, Sequence[str], None] = "f4c9a17be205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

INDEX_NAME = "ix_resources_core_code"

# (code, seeded title). Keep in step with app.services.learning.courseProgress.
CORE_COURSES: tuple[tuple[str, str], ...] = (
    ("resume_templates", "Resume Templates"),
    ("linkedin_optimization", "LinkedIn Optimization"),
    ("interview_preparation", "Interview Preparation"),
)


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(item["name"] == column for item in inspector.get_columns(table))


def _has_index(bind, table: str, name: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(item["name"] == name for item in inspector.get_indexes(table))


def _backfill(bind) -> None:
    """Claim one row per core course, only when the title match is unique."""
    for code, title in CORE_COURSES:
        already = bind.execute(
            sa.text("SELECT COUNT(*) FROM resources WHERE core_code = :code"),
            {"code": code},
        ).scalar_one()
        if already:
            LOGGER.info("core_code %s already assigned; leaving it alone", code)
            continue

        candidates = bind.execute(
            sa.text(
                "SELECT id FROM resources "
                "WHERE TRIM(title) = :title AND is_published = TRUE AND core_code IS NULL"
            ),
            {"title": title},
        ).scalars().all()

        if len(candidates) == 1:
            bind.execute(
                sa.text("UPDATE resources SET core_code = :code WHERE id = :id"),
                {"code": code, "id": candidates[0]},
            )
            LOGGER.info("core_code %s assigned to resource %s", code, candidates[0])
        elif not candidates:
            LOGGER.warning(
                "core_code %s left unassigned: no published resource titled %r", code, title
            )
        else:
            LOGGER.warning(
                "core_code %s left unassigned: %d published resources titled %r "
                "(an operator must choose)",
                code,
                len(candidates),
                title,
            )


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("resources"):
        LOGGER.info("resources table absent; nothing to do")
        return

    if not _has_column(bind, "resources", "core_code"):
        op.add_column("resources", sa.Column("core_code", sa.String(length=64), nullable=True))

    _backfill(bind)

    if not _has_index(bind, "resources", INDEX_NAME):
        op.create_index(INDEX_NAME, "resources", ["core_code"], unique=True)


def downgrade() -> None:
    """Drops the identity, keeping every course row.

    The column holds no information that is not recoverable from the titles the
    backfill read, so this is reversible without data loss.
    """
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("resources"):
        return
    if _has_index(bind, "resources", INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name="resources")
    if _has_column(bind, "resources", "core_code"):
        op.drop_column("resources", "core_code")
