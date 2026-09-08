"""Reconcile the AI usage ledger and give reservations a durable cycle

Expands ``ai_usage_events`` so a row can say *which stage of its life it is in*
(reserved / committed / released / expired / superseded) instead of only "a
spend happened", then reconciles the pre-ledger history into it **by identity**:
every historical ``job_analysis`` and ``resume_course_evaluations`` row that no
ledger row points at gets one, carrying its original ``created_at``.

That backfill is what lets the read path stop guessing. ``get_used_today`` used
``max(ledger_count, legacy_count)``, which cannot tell "the ledger is missing a
row" from "this user really did use less today"; once every legacy attempt is
represented by reference, the ledger alone is the authority.

Order is deliberate and each step is re-runnable: expand → settle duplicates →
constraints → backfill (batched, resumable) → verify. Nothing historical is
deleted; duplicate charges are marked ``superseded`` so the evidence survives.

Revision ID: d1c7e3a95b48
Revises: c3e8b1a7d240
Create Date: 2026-09-06
"""
from __future__ import annotations

import logging
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1c7e3a95b48"
down_revision: Union[str, Sequence[str], None] = "c3e8b1a7d240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

BATCH_SIZE = 500

# (legacy table, feature recorded on the ledger, reference_type used to point back)
LEGACY_SOURCES = (
    ("job_analysis", "cv_job_search", "job_analysis"),
    ("resume_course_evaluations", "resume_course_audit", "resume_course_evaluation"),
)

COMMITTED = "committed"
SUPERSEDED = "superseded"
RESERVED = "reserved"


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _mark_duplicate_references(bind) -> int:
    """Keep the first charge per referenced object; file the rest as history.

    Duplicates are exactly the defect the unique index below prevents, and they
    have to be settled before it can be created. They are *not* deleted: a
    second charge for one analysis is evidence of a replay, so it stays in the
    table marked ``superseded`` and simply stops counting.
    """
    rows = bind.execute(
        sa.text(
            """
            SELECT id FROM ai_usage_events
            WHERE reference_id IS NOT NULL
              AND status = :committed
              AND id NOT IN (
                  SELECT MIN(id::text)::uuid FROM ai_usage_events
                  WHERE reference_id IS NOT NULL AND status = :committed
                  GROUP BY reference_type, reference_id
              )
            """
        )
        if bind.dialect.name == "postgresql"
        else sa.text(
            """
            SELECT id FROM ai_usage_events
            WHERE reference_id IS NOT NULL
              AND status = :committed
              AND id NOT IN (
                  SELECT MIN(id) FROM ai_usage_events
                  WHERE reference_id IS NOT NULL AND status = :committed
                  GROUP BY reference_type, reference_id
              )
            """
        ),
        {"committed": COMMITTED},
    ).fetchall()
    if not rows:
        return 0
    bind.execute(
        sa.text("UPDATE ai_usage_events SET status = :superseded WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"superseded": SUPERSEDED, "ids": [row[0] for row in rows]},
    )
    LOGGER.warning(
        "ai_usage_events: %s duplicate charge(s) marked '%s' (kept the first per reference)",
        len(rows),
        SUPERSEDED,
    )
    return len(rows)


def _backfill_legacy(bind, table: str, feature: str, reference_type: str) -> int:
    """Give every legacy attempt a ledger row, in resumable batches.

    ``NOT EXISTS`` on the reference makes this idempotent: rerunning it after an
    interrupted upgrade inserts only what is still missing, and an attempt that
    already has a ledger row is never charged twice.
    """
    if not _table_exists(bind, table):
        return 0

    inserted = 0
    while True:
        rows = bind.execute(
            sa.text(
                f"""
                SELECT legacy.id, legacy.user_id, legacy.created_at
                FROM {table} AS legacy
                WHERE NOT EXISTS (
                    SELECT 1 FROM ai_usage_events AS ledger
                    WHERE ledger.reference_type = :reference_type
                      AND ledger.reference_id = legacy.id
                )
                ORDER BY legacy.created_at
                LIMIT :batch
                """
            ),
            {"reference_type": reference_type, "batch": BATCH_SIZE},
        ).fetchall()
        if not rows:
            break

        bind.execute(
            sa.text(
                """
                INSERT INTO ai_usage_events
                    (id, user_id, feature, units, source, reference_type, reference_id, status, created_at)
                VALUES
                    (:id, :user_id, :feature, 1, 'legacy_backfill', :reference_type, :reference_id,
                     :status, :created_at)
                """
            ),
            [
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(row[1]),
                    "feature": feature,
                    "reference_type": reference_type,
                    "reference_id": str(row[0]),
                    "status": COMMITTED,
                    "created_at": row[2],
                }
                for row in rows
            ],
        )
        inserted += len(rows)
        if len(rows) < BATCH_SIZE:
            break

    if inserted:
        LOGGER.info("ai_usage_events: backfilled %s row(s) from %s", inserted, table)
    return inserted


def _verify_parity(bind, table: str, feature: str, reference_type: str) -> None:
    """Compare ledger and legacy per user/feature/day and log any divergence.

    Reported rather than enforced: this runs against real history, and an
    operator needs to see a mismatch, not have the upgrade die on it. After a
    successful backfill the expected output is silence.
    """
    if not _table_exists(bind, table):
        return

    missing = bind.execute(
        sa.text(
            f"""
            SELECT COUNT(*) FROM {table} AS legacy
            WHERE NOT EXISTS (
                SELECT 1 FROM ai_usage_events AS ledger
                WHERE ledger.reference_type = :reference_type
                  AND ledger.reference_id = legacy.id
            )
            """
        ),
        {"reference_type": reference_type},
    ).scalar_one()
    if missing:
        LOGGER.warning(
            "ai_usage_events: %s %s row(s) still have no ledger entry", missing, table
        )

    divergent = bind.execute(
        sa.text(
            f"""
            SELECT ledger.user_id, ledger.day, ledger.units, legacy.attempts FROM (
                SELECT user_id, DATE(created_at) AS day, SUM(units) AS units
                FROM ai_usage_events
                WHERE feature = :feature AND status = :committed
                GROUP BY user_id, DATE(created_at)
            ) AS ledger
            FULL OUTER JOIN (
                SELECT user_id, DATE(created_at) AS day, COUNT(*) AS attempts
                FROM {table}
                GROUP BY user_id, DATE(created_at)
            ) AS legacy
            ON ledger.user_id = legacy.user_id AND ledger.day = legacy.day
            WHERE COALESCE(ledger.units, 0) <> COALESCE(legacy.attempts, 0)
            """
        )
        if bind.dialect.name == "postgresql"
        else sa.text(
            f"""
            SELECT ledger.user_id, ledger.day, ledger.units, legacy.attempts FROM (
                SELECT user_id, DATE(created_at) AS day, SUM(units) AS units
                FROM ai_usage_events
                WHERE feature = :feature AND status = :committed
                GROUP BY user_id, DATE(created_at)
            ) AS ledger
            LEFT JOIN (
                SELECT user_id, DATE(created_at) AS day, COUNT(*) AS attempts
                FROM {table}
                GROUP BY user_id, DATE(created_at)
            ) AS legacy
            ON ledger.user_id = legacy.user_id AND ledger.day = legacy.day
            WHERE COALESCE(ledger.units, 0) <> COALESCE(legacy.attempts, 0)
            """
        ),
        {"feature": feature, "committed": COMMITTED},
    ).fetchall()
    for user_id, day, units, attempts in divergent:
        # A difference is legitimate when a *reserved* or released row exists, or
        # when a duplicate was superseded above; it is logged so the operator can
        # tell those apart from a genuine gap.
        LOGGER.warning(
            "ai_usage_events parity: user=%s day=%s ledger=%s %s=%s",
            user_id,
            day,
            units,
            table,
            attempts,
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "ai_usage_events"):
        return

    existing_columns = _columns(bind, "ai_usage_events")
    if "status" not in existing_columns:
        op.add_column(
            "ai_usage_events",
            # Every pre-existing row is a settled spend, so the default keeps
            # historical usage counting exactly as it did before this revision.
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=COMMITTED,
            ),
        )
    if "expires_at" not in existing_columns:
        op.add_column("ai_usage_events", sa.Column("expires_at", sa.DateTime(), nullable=True))

    _mark_duplicate_references(bind)

    existing_indexes = _indexes(bind, "ai_usage_events")
    if "uq_ai_usage_events_reference" not in existing_indexes:
        op.create_index(
            "uq_ai_usage_events_reference",
            "ai_usage_events",
            ["reference_type", "reference_id"],
            unique=True,
            postgresql_where=sa.text(f"reference_id IS NOT NULL AND status = '{COMMITTED}'"),
            sqlite_where=sa.text(f"reference_id IS NOT NULL AND status = '{COMMITTED}'"),
        )
    if "ix_ai_usage_events_reserved_expiry" not in existing_indexes:
        op.create_index(
            "ix_ai_usage_events_reserved_expiry",
            "ai_usage_events",
            ["user_id", "feature", "expires_at"],
            postgresql_where=sa.text(f"status = '{RESERVED}'"),
            sqlite_where=sa.text(f"status = '{RESERVED}'"),
        )

    for table, feature, reference_type in LEGACY_SOURCES:
        _backfill_legacy(bind, table, feature, reference_type)
        _verify_parity(bind, table, feature, reference_type)


def downgrade() -> None:
    """Drop the reservation cycle, keeping every backfilled row.

    Safe for the read path either way: without ``status`` the old
    ``max(ledger, legacy)`` comparison sees a ledger that already matches the
    legacy count, so the maximum is the same number.
    """
    bind = op.get_bind()
    if not _table_exists(bind, "ai_usage_events"):
        return

    existing_indexes = _indexes(bind, "ai_usage_events")
    if "ix_ai_usage_events_reserved_expiry" in existing_indexes:
        op.drop_index("ix_ai_usage_events_reserved_expiry", table_name="ai_usage_events")
    if "uq_ai_usage_events_reference" in existing_indexes:
        op.drop_index("uq_ai_usage_events_reference", table_name="ai_usage_events")

    existing_columns = _columns(bind, "ai_usage_events")
    if "expires_at" in existing_columns:
        op.drop_column("ai_usage_events", "expires_at")
    if "status" in existing_columns:
        op.drop_column("ai_usage_events", "status")
