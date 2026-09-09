"""Constrain analytics statuses, score fractions, money and time

``resume_skills.status`` is a plain string with a default, so any value at all
could be written into it while every reader switches on four. The scores —
``importance_score``, ``confidence_score``, ``coverage_score`` — are fractions,
but nothing said so: the learning-route optimiser reads them through
``_clamp(value, 0.0, 1.0)``, which means an out-of-range value is **not**
rejected today, it is silently reinterpreted, and the number the product acts on
stops being the number that was stored. ``rating`` is scored as ``rating / 5.0``
clamped the same way, so a 9 and a 5 are the same star rating. ``cost`` and
``duration_hours`` are compared against a budget the API already declares as
``ge=0``, while the catalogue itself accepted negatives.

Nothing is deleted or rewritten. Rows that would violate a constraint are
**counted and logged, per table and per rule**, and then the constraint is
created — which fails loudly if any remain. A migration that silently repaired
analytics data would be deciding, on its own, what a bad measurement should have
said.

Not changed, deliberately: ``courses.cost`` stays ``Float``. It is a catalogue
price used as a budget bound — the solver converts it to integer cents through
``_scale_money`` before it reaches CP-SAT, and the only float arithmetic on it is
a ``round(sum(...), 2)`` for display. It is not a payment ledger, and there is no
evidence of accumulated error to justify a type migration. F-23 asked for the
decision to be recorded rather than assumed; this is the record.

Revision ID: e7c2d940ab15
Revises: d5b83f1a6c27
Create Date: 2026-09-08
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7c2d940ab15"
down_revision: Union[str, Sequence[str], None] = "d5b83f1a6c27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

RESUME_SKILL_STATUSES = ("detected", "confirmed", "rejected", "manual")

#: ``(table, constraint name, SQL predicate)``. The predicate is what must hold;
#: the inventory counts the rows for which it does not.
CHECKS: tuple[tuple[str, str, str], ...] = (
    (
        "job_skills",
        "ck_job_skills_importance_score_fraction",
        "importance_score IS NULL OR (importance_score >= 0 AND importance_score <= 1)",
    ),
    (
        "resume_skills",
        "ck_resume_skills_status",
        "status IN ('" + "', '".join(RESUME_SKILL_STATUSES) + "')",
    ),
    (
        "resume_skills",
        "ck_resume_skills_confidence_score_fraction",
        "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
    ),
    ("courses", "ck_courses_cost_non_negative", "cost IS NULL OR cost >= 0"),
    (
        "courses",
        "ck_courses_duration_hours_non_negative",
        "duration_hours IS NULL OR duration_hours >= 0",
    ),
    ("courses", "ck_courses_rating_five_star", "rating IS NULL OR (rating >= 0 AND rating <= 5)"),
    (
        "course_skills",
        "ck_course_skills_coverage_score_fraction",
        "coverage_score IS NULL OR (coverage_score >= 0 AND coverage_score <= 1)",
    ),
)


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _constraints(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {
        constraint["name"]
        for constraint in inspector.get_check_constraints(table)
        if constraint.get("name")
    }


def inventory(bind) -> list[dict]:
    """Rows that would violate each rule, counted before anything is created.

    Returned as data so a test — and an operator running the query by hand —
    can see exactly what a failed upgrade is complaining about.
    """
    findings: list[dict] = []
    for table, name, predicate in CHECKS:
        if not _table_exists(bind, table):
            continue
        violations = int(
            bind.execute(
                sa.text(f"SELECT COUNT(*) FROM {table} WHERE NOT ({predicate})")
            ).scalar()
            or 0
        )
        findings.append(
            {"table": table, "constraint": name, "predicate": predicate, "violations": violations}
        )
    return findings


def upgrade() -> None:
    bind = op.get_bind()

    for finding in inventory(bind):
        if finding["violations"]:
            LOGGER.warning(
                "%s: %s row(s) violate %s (%s). Nothing was deleted or rewritten; "
                "the constraint below will refuse to be created until they are resolved.",
                finding["table"],
                finding["violations"],
                finding["constraint"],
                finding["predicate"],
            )

    for table, name, predicate in CHECKS:
        if not _table_exists(bind, table):
            continue
        if name in _constraints(bind, table):
            continue
        op.create_check_constraint(name, table, sa.text(predicate))


def downgrade() -> None:
    """Drop the constraints. No data was changed on the way up, so none is on the way down."""
    bind = op.get_bind()
    for table, name, _predicate in reversed(CHECKS):
        if not _table_exists(bind, table):
            continue
        if name in _constraints(bind, table):
            op.drop_constraint(name, table, type_="check")
