"""add interview availability and email logs

Revision ID: a1b2c3d4e5f6
Revises: 9f1c2d3e4b5a
Create Date: 2026-03-13 17:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9f1c2d3e4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


interview_availability_status = postgresql.ENUM(
    "available",
    "booked",
    "cancelled",
    name="interviewavailabilitystatus",
    create_type=False,
)


def _uuid_type():
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    interview_availability_status.create(bind, checkfirst=True)

    op.create_table(
        "interview_availabilities",
        sa.Column("id", _uuid_type(), nullable=False),
        sa.Column("application_id", _uuid_type(), nullable=False),
        sa.Column("company_id", _uuid_type(), nullable=False),
        sa.Column("recruiter_id", _uuid_type(), nullable=True),
        sa.Column("candidate_id", _uuid_type(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/Toronto"),
        sa.Column("status", interview_availability_status, nullable=False, server_default="available"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("booked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recruiter_id"], ["company_recruiters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_availabilities_application_status",
        "interview_availabilities",
        ["application_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_interview_availabilities_company_start",
        "interview_availabilities",
        ["company_id", "starts_at"],
        unique=False,
    )

    op.create_table(
        "email_notification_logs",
        sa.Column("id", _uuid_type(), nullable=False),
        sa.Column("application_id", _uuid_type(), nullable=True),
        sa.Column("company_id", _uuid_type(), nullable=True),
        sa.Column("recruiter_id", _uuid_type(), nullable=True),
        sa.Column("user_id", _uuid_type(), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("template_key", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body_preview", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.String(length=32), nullable=False, server_default="mocked"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("sent_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recruiter_id"], ["company_recruiters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_notification_logs_application_created_at",
        "email_notification_logs",
        ["application_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_notification_logs_recipient_created_at",
        "email_notification_logs",
        ["recipient_email", "created_at"],
        unique=False,
    )

    op.alter_column("interview_availabilities", "timezone", server_default=None)
    op.alter_column("interview_availabilities", "status", server_default=None)
    op.alter_column("email_notification_logs", "delivery_status", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_email_notification_logs_recipient_created_at", table_name="email_notification_logs")
    op.drop_index("ix_email_notification_logs_application_created_at", table_name="email_notification_logs")
    op.drop_table("email_notification_logs")

    op.drop_index("ix_interview_availabilities_company_start", table_name="interview_availabilities")
    op.drop_index("ix_interview_availabilities_application_status", table_name="interview_availabilities")
    op.drop_table("interview_availabilities")
    interview_availability_status.drop(op.get_bind(), checkfirst=True)
