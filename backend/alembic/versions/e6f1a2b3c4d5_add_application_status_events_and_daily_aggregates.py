"""add application status events and daily aggregates

Revision ID: e6f1a2b3c4d5
Revises: d4b8c1e9a2f7
Create Date: 2026-03-10 11:30:00.000000

"""
from typing import Sequence, Union
from collections import defaultdict
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e6f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d4b8c1e9a2f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


application_event_type = postgresql.ENUM(
    "CREATED",
    "STATUS_CHANGED",
    "DELETED",
    name="applicationeventtype",
    create_type=False,
)

application_status_type = postgresql.ENUM(
    name="applicationstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    existing_indexes = {
        table_name: {index["name"] for index in inspector.get_indexes(table_name)}
        for table_name in existing_tables
    }

    application_event_type.create(bind, checkfirst=True)

    if "application_status_events" not in existing_tables:
        op.create_table(
            "application_status_events",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("application_id", sa.UUID(), nullable=True),
            sa.Column("company_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=True),
            sa.Column("job_posting_id", sa.UUID(), nullable=True),
            sa.Column("triggered_by_user_id", sa.UUID(), nullable=True),
            sa.Column("triggered_by_company_recruiter_id", sa.UUID(), nullable=True),
            sa.Column("event_type", application_event_type, nullable=False),
            sa.Column("from_status", application_status_type, nullable=True),
            sa.Column("to_status", application_status_type, nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["triggered_by_company_recruiter_id"],
                ["company_recruiters.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        existing_indexes["application_status_events"] = set()

    if "ix_application_status_events_company_occurred_at" not in existing_indexes.get("application_status_events", set()):
        op.create_index(
            "ix_application_status_events_company_occurred_at",
            "application_status_events",
            ["company_id", "occurred_at"],
            unique=False,
        )
    if "ix_application_status_events_application_occurred_at" not in existing_indexes.get("application_status_events", set()):
        op.create_index(
            "ix_application_status_events_application_occurred_at",
            "application_status_events",
            ["application_id", "occurred_at"],
            unique=False,
        )
    if "ix_application_status_events_event_type_occurred_at" not in existing_indexes.get("application_status_events", set()):
        op.create_index(
            "ix_application_status_events_event_type_occurred_at",
            "application_status_events",
            ["event_type", "occurred_at"],
            unique=False,
        )

    if "application_daily_aggregates" not in existing_tables:
        op.create_table(
            "application_daily_aggregates",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("company_id", sa.UUID(), nullable=False),
            sa.Column("metric_date", sa.Date(), nullable=False),
            sa.Column("applications_created_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("applications_deleted_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status_change_events_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_applied_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_in_review_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_interview_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_offer_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_rejected_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entered_withdrawn_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("company_id", "metric_date", name="uq_application_daily_aggregate_company_date"),
        )
        existing_indexes["application_daily_aggregates"] = set()

    if "ix_application_daily_aggregates_company_metric_date" not in existing_indexes.get(
        "application_daily_aggregates", set()
    ):
        op.create_index(
            "ix_application_daily_aggregates_company_metric_date",
            "application_daily_aggregates",
            ["company_id", "metric_date"],
            unique=False,
        )

    # Backfill creation events and day-level aggregates from existing applications.
    application_rows = bind.execute(
        sa.text(
            """
            SELECT
                id,
                company_id,
                user_id,
                job_posting_id,
                status,
                application_date,
                created_at
            FROM applications
            """
        )
    ).mappings().all()

    aggregate_rows: dict[tuple[object, object], dict[str, object]] = defaultdict(
        lambda: {
            "applications_created_count": 0,
            "applications_deleted_count": 0,
            "status_change_events_count": 0,
            "entered_applied_count": 0,
            "entered_in_review_count": 0,
            "entered_interview_count": 0,
            "entered_offer_count": 0,
            "entered_rejected_count": 0,
            "entered_withdrawn_count": 0,
        }
    )

    for row in application_rows:
        occurred_at = row["application_date"] or row["created_at"] or datetime.utcnow()
        bind.execute(
            sa.text(
                """
                INSERT INTO application_status_events (
                    id,
                    application_id,
                    company_id,
                    user_id,
                    job_posting_id,
                    triggered_by_user_id,
                    event_type,
                    from_status,
                    to_status,
                    occurred_at
                )
                SELECT
                    :id,
                    :application_id,
                    :company_id,
                    :user_id,
                    :job_posting_id,
                    :triggered_by_user_id,
                    :event_type,
                    :from_status,
                    :to_status,
                    :occurred_at
                )
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM application_status_events
                    WHERE application_id = :application_id
                      AND event_type = :event_type
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "application_id": row["id"],
                "company_id": row["company_id"],
                "user_id": row["user_id"],
                "job_posting_id": row["job_posting_id"],
                "triggered_by_user_id": row["user_id"],
                "event_type": "CREATED",
                "from_status": None,
                "to_status": row["status"],
                "occurred_at": occurred_at,
            },
        )

        key = (row["company_id"], occurred_at.date())
        aggregate_rows[key]["applications_created_count"] += 1
        status_field = {
            "APPLIED": "entered_applied_count",
            "IN_REVIEW": "entered_in_review_count",
            "INTERVIEW": "entered_interview_count",
            "OFFER": "entered_offer_count",
            "REJECTED": "entered_rejected_count",
            "WITHDRAWN": "entered_withdrawn_count",
        }[str(row["status"])]
        aggregate_rows[key][status_field] += 1

    for (company_id, metric_date), counters in aggregate_rows.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO application_daily_aggregates (
                    id,
                    company_id,
                    metric_date,
                    applications_created_count,
                    applications_deleted_count,
                    status_change_events_count,
                    entered_applied_count,
                    entered_in_review_count,
                    entered_interview_count,
                    entered_offer_count,
                    entered_rejected_count,
                    entered_withdrawn_count,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :company_id,
                    :metric_date,
                    :applications_created_count,
                    :applications_deleted_count,
                    :status_change_events_count,
                    :entered_applied_count,
                    :entered_in_review_count,
                    :entered_interview_count,
                    :entered_offer_count,
                    :entered_rejected_count,
                    :entered_withdrawn_count,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (company_id, metric_date) DO NOTHING
                """
            ),
            {
                "id": uuid.uuid4(),
                "company_id": company_id,
                "metric_date": metric_date,
                "applications_created_count": counters["applications_created_count"],
                "applications_deleted_count": counters["applications_deleted_count"],
                "status_change_events_count": counters["status_change_events_count"],
                "entered_applied_count": counters["entered_applied_count"],
                "entered_in_review_count": counters["entered_in_review_count"],
                "entered_interview_count": counters["entered_interview_count"],
                "entered_offer_count": counters["entered_offer_count"],
                "entered_rejected_count": counters["entered_rejected_count"],
                "entered_withdrawn_count": counters["entered_withdrawn_count"],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )


def downgrade() -> None:
    op.drop_index("ix_application_daily_aggregates_company_metric_date", table_name="application_daily_aggregates")
    op.drop_table("application_daily_aggregates")

    op.drop_index("ix_application_status_events_event_type_occurred_at", table_name="application_status_events")
    op.drop_index("ix_application_status_events_application_occurred_at", table_name="application_status_events")
    op.drop_index("ix_application_status_events_company_occurred_at", table_name="application_status_events")
    op.drop_table("application_status_events")

    application_event_type.drop(op.get_bind(), checkfirst=True)
