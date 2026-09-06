"""Allow at most one booked interview slot per application

Reading a slot as AVAILABLE, marking it BOOKED and cancelling the alternatives
is three statements with nothing serialising them, so two clicks that arrived
together could each confirm a different time and each cancel the other's. The
application layer now locks the candidature; this index is what makes the rule
true even when something bypasses that path.

Duplicates that already exist are **resolved, not deleted**: an availability
someone was told about is a fact, and the log of it matters more than a tidy
table. The earliest confirmation per application is kept — it is the one the
candidate and the recruiter were told about first — and the rest become
CANCELLED, with every conflict logged so an operator can follow up.

Revision ID: f4c9a17be205
Revises: e8b4d2f7a316
Create Date: 2026-09-06
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4c9a17be205"
down_revision: Union[str, Sequence[str], None] = "e8b4d2f7a316"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

BOOKED_PREDICATE = "status = 'booked'"


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _inventory_duplicates(bind) -> list[tuple]:
    """Applications with more than one confirmed interview, listed before anything changes."""
    return bind.execute(
        sa.text(
            """
            SELECT application_id, COUNT(*) AS booked_count
            FROM interview_availabilities
            WHERE status = 'booked'
            GROUP BY application_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()


def _resolve_duplicates(bind) -> int:
    conflicts = _inventory_duplicates(bind)
    if not conflicts:
        return 0

    for application_id, booked_count in conflicts:
        LOGGER.warning(
            "interview_availabilities: application %s has %s booked slots; keeping the earliest",
            application_id,
            booked_count,
        )

    losers = bind.execute(
        sa.text(
            """
            SELECT id FROM interview_availabilities AS slot
            WHERE status = 'booked'
              AND EXISTS (
                  SELECT 1 FROM interview_availabilities AS earlier
                  WHERE earlier.application_id = slot.application_id
                    AND earlier.status = 'booked'
                    AND (
                        COALESCE(earlier.booked_at, earlier.created_at)
                            < COALESCE(slot.booked_at, slot.created_at)
                        OR (
                            COALESCE(earlier.booked_at, earlier.created_at)
                                = COALESCE(slot.booked_at, slot.created_at)
                            AND CAST(earlier.id AS VARCHAR) < CAST(slot.id AS VARCHAR)
                        )
                    )
              )
            """
        )
    ).fetchall()
    if not losers:
        return 0

    bind.execute(
        sa.text(
            "UPDATE interview_availabilities SET status = 'cancelled', "
            "updated_at = CURRENT_TIMESTAMP WHERE id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)),
        {"ids": [row[0] for row in losers]},
    )
    LOGGER.warning(
        "interview_availabilities: %s duplicate booking(s) moved to 'cancelled' (none deleted)",
        len(losers),
    )
    return len(losers)


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "interview_availabilities"):
        return

    _resolve_duplicates(bind)

    if "uq_interview_availabilities_booked_per_application" not in _indexes(
        bind, "interview_availabilities"
    ):
        op.create_index(
            "uq_interview_availabilities_booked_per_application",
            "interview_availabilities",
            ["application_id"],
            unique=True,
            postgresql_where=sa.text(BOOKED_PREDICATE),
            sqlite_where=sa.text(BOOKED_PREDICATE),
        )


def downgrade() -> None:
    """Drop the constraint. Slots that were cancelled above stay cancelled.

    Reinstating them would recreate exactly the ambiguity this revision
    resolved — two confirmed times for one interview — so it is left as a
    deliberate, separate decision.
    """
    bind = op.get_bind()
    if not _table_exists(bind, "interview_availabilities"):
        return
    if "uq_interview_availabilities_booked_per_application" in _indexes(
        bind, "interview_availabilities"
    ):
        op.drop_index(
            "uq_interview_availabilities_booked_per_application",
            table_name="interview_availabilities",
        )
