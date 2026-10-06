"""Add job_targets and job_description_parses

Plan 11 §5 / TASK-077. Career Lab analyses a vacancy the user pastes. Nothing
in the schema could hold one: ``job_postings`` belongs to the recruiter side
(``company_id NOT NULL``) and ``job_skills`` already serves two masters.

* ``job_description_parses`` — keyed by the sha256 of the normalized text and
  shared across users, because a parse depends on the text alone.
* ``job_targets`` — one user's vacancy, with the lease cycle of
  ``job_analysis`` (attempts, lease, provider_attempted_at) so that recovering
  an interrupted parse never pays the provider twice.

Purely additive: two new tables and their indexes, no backfill, no change to
any existing table. Statuses and workplace types are text with CHECK
constraints rather than native ENUMs, so a replayed upgrade has no
``CREATE TYPE`` to trip on.

Revision ID: e5b2c9d4a817
Revises: d3e8a1f5c702
Create Date: 2026-10-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "e5b2c9d4a817"
down_revision: Union[str, Sequence[str], None] = "d3e8a1f5c702"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PARSES = "job_description_parses"
TARGETS = "job_targets"
JSONB = sa.JSON().with_variant(postgresql.JSONB, "postgresql")
ACTIVE = sa.text("status IN ('pending', 'parsing')")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not inspector.has_table(PARSES):
        op.create_table(
            PARSES,
            sa.Column("text_hash", sa.String(length=64), primary_key=True, nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("parsed", JSONB, nullable=False),
            sa.Column("embedding", Vector(384), nullable=True),
            sa.Column("embedding_model_name", sa.String(length=120), nullable=True),
            sa.Column("model_id", sa.String(length=120), nullable=False),
            sa.Column("prompt_version", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "(embedding IS NULL) = (embedding_model_name IS NULL)",
                name="ck_job_description_parses_embedding_has_model",
            ),
        )

    if not inspector.has_table(TARGETS):
        op.create_table(
            TARGETS,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "resume_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("resumes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("text_hash", sa.String(length=64), nullable=False),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("workplace_type", sa.String(length=16), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("provider_attempted_at", sa.DateTime(), nullable=True),
            sa.Column("match_snapshot", JSONB, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "status IN ('pending', 'parsing', 'ready', 'failed')",
                name="ck_job_targets_status",
            ),
            sa.CheckConstraint(
                "workplace_type IS NULL OR workplace_type IN ('onsite', 'hybrid', 'remote')",
                name="ck_job_targets_workplace_type",
            ),
            sa.CheckConstraint("attempts >= 0", name="ck_job_targets_attempts_non_negative"),
        )
        op.create_index("ix_job_targets_user_created", TARGETS, ["user_id", "created_at"])
        op.create_index("ix_job_targets_text_hash", TARGETS, ["text_hash"])
        op.create_index(
            "ix_job_targets_active_lease",
            TARGETS,
            ["lease_expires_at"],
            postgresql_where=ACTIVE,
            sqlite_where=ACTIVE,
        )


def downgrade() -> None:
    # Users' pasted vacancies are lost with the table. Nothing else references
    # either table, so no other data is touched.
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(TARGETS):
        op.drop_index("ix_job_targets_active_lease", table_name=TARGETS)
        op.drop_index("ix_job_targets_text_hash", table_name=TARGETS)
        op.drop_index("ix_job_targets_user_created", table_name=TARGETS)
        op.drop_table(TARGETS)
    if inspector.has_table(PARSES):
        op.drop_table(PARSES)
