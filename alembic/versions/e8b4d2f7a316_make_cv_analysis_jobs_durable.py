"""Turn job_analysis into a durable queue with claims, leases and one live job per CV

Additive by design: the four statuses keep their meaning and the API keeps
returning ``job_id`` / ``status``. What is new is the bookkeeping a queue needs
to survive the process that filled it — how many times a job has been claimed,
until when the current worker owns it, and whether the provider was already
called (the one fact that makes an interrupted job unsafe to re-run).

The partial unique index is the other half: "is one already running?" followed by
an INSERT is two statements, and two simultaneous requests both got past the
first one. Now the database decides and the loser joins the winner's job.

Historical rows are classified, not restarted. Anything left PROCESSING by an
older deployment has no lease, so this revision gives it a terminal state
explicitly rather than letting a runner re-run work that may already have been
paid for.

Revision ID: e8b4d2f7a316
Revises: d1c7e3a95b48
Create Date: 2026-09-06
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8b4d2f7a316"
down_revision: Union[str, Sequence[str], None] = "d1c7e3a95b48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

ACTIVE_PREDICATE = "status IN ('PENDING', 'PROCESSING')"

STRANDED_MESSAGE = (
    "This analysis was interrupted by a restart before job recovery existed. "
    "Please start a new one."
)


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _resolve_duplicate_active_jobs(bind) -> int:
    """Keep the newest active job per CV; close the rest.

    A database that already contains two live jobs for one CV cannot take the
    unique index. Those extras are the bug this index prevents, so they are
    given a terminal status — never deleted — and the most recent one survives
    as the job the user is polling.
    """
    rows = bind.execute(
        sa.text(
            f"""
            SELECT id FROM job_analysis AS outer_job
            WHERE {ACTIVE_PREDICATE}
              AND resume_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM job_analysis AS newer
                  WHERE newer.user_id = outer_job.user_id
                    AND newer.resume_id = outer_job.resume_id
                    AND newer.status IN ('PENDING', 'PROCESSING')
                    AND (newer.created_at, newer.id::text) > (outer_job.created_at, outer_job.id::text)
              )
            """
            if bind.dialect.name == "postgresql"
            else f"""
            SELECT id FROM job_analysis AS outer_job
            WHERE {ACTIVE_PREDICATE}
              AND resume_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM job_analysis AS newer
                  WHERE newer.user_id = outer_job.user_id
                    AND newer.resume_id = outer_job.resume_id
                    AND newer.status IN ('PENDING', 'PROCESSING')
                    AND (newer.created_at > outer_job.created_at
                         OR (newer.created_at = outer_job.created_at AND newer.id > outer_job.id))
              )
            """
        )
    ).fetchall()
    if not rows:
        return 0

    bind.execute(
        sa.text(
            "UPDATE job_analysis SET status = 'FAILED', error_message = :message, "
            "completed_at = CURRENT_TIMESTAMP WHERE id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)),
        {"message": STRANDED_MESSAGE, "ids": [row[0] for row in rows]},
    )
    LOGGER.warning("job_analysis: closed %s duplicate active job(s) for the same CV", len(rows))
    return len(rows)


def _close_stranded_processing_jobs(bind) -> int:
    """Give pre-lease PROCESSING rows an end.

    They are indistinguishable from a job whose worker is still alive, except
    that no worker from before this revision can still be alive: they were never
    leased. Left alone they would block their CV forever — the symptom this task
    exists to remove — and a runner that adopted them might repeat a call that
    was already paid for.
    """
    result = bind.execute(
        sa.text(
            "UPDATE job_analysis SET status = 'FAILED', error_message = :message, "
            "completed_at = CURRENT_TIMESTAMP "
            "WHERE status = 'PROCESSING' AND lease_expires_at IS NULL"
        ),
        {"message": STRANDED_MESSAGE},
    )
    closed = int(result.rowcount or 0)
    if closed:
        LOGGER.warning("job_analysis: closed %s job(s) stranded on PROCESSING", closed)
    return closed


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "job_analysis"):
        return

    existing_columns = _columns(bind, "job_analysis")
    if "attempts" not in existing_columns:
        op.add_column(
            "job_analysis",
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )
    if "lease_expires_at" not in existing_columns:
        op.add_column("job_analysis", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    if "provider_attempted_at" not in existing_columns:
        op.add_column(
            "job_analysis", sa.Column("provider_attempted_at", sa.DateTime(), nullable=True)
        )

    _close_stranded_processing_jobs(bind)
    _resolve_duplicate_active_jobs(bind)

    existing_indexes = _indexes(bind, "job_analysis")
    if "uq_job_analysis_active_per_resume" not in existing_indexes:
        op.create_index(
            "uq_job_analysis_active_per_resume",
            "job_analysis",
            ["user_id", "resume_id"],
            unique=True,
            postgresql_where=sa.text(ACTIVE_PREDICATE),
            sqlite_where=sa.text(ACTIVE_PREDICATE),
        )
    if "ix_job_analysis_active_lease" not in existing_indexes:
        op.create_index(
            "ix_job_analysis_active_lease",
            "job_analysis",
            ["lease_expires_at"],
            postgresql_where=sa.text(ACTIVE_PREDICATE),
            sqlite_where=sa.text(ACTIVE_PREDICATE),
        )


def downgrade() -> None:
    """Drop the queue bookkeeping. Job history and statuses are untouched."""
    bind = op.get_bind()
    if not _table_exists(bind, "job_analysis"):
        return

    existing_indexes = _indexes(bind, "job_analysis")
    if "ix_job_analysis_active_lease" in existing_indexes:
        op.drop_index("ix_job_analysis_active_lease", table_name="job_analysis")
    if "uq_job_analysis_active_per_resume" in existing_indexes:
        op.drop_index("uq_job_analysis_active_per_resume", table_name="job_analysis")

    existing_columns = _columns(bind, "job_analysis")
    for column in ("provider_attempted_at", "lease_expires_at", "attempts"):
        if column in existing_columns:
            op.drop_column("job_analysis", column)
