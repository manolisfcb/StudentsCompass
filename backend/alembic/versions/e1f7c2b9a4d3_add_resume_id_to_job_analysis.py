"""add resume_id to job_analysis

Revision ID: e1f7c2b9a4d3
Revises: d9a2c30c6f11
Create Date: 2026-02-15 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f7c2b9a4d3"
down_revision: Union[str, Sequence[str], None] = "d9a2c30c6f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_analysis", sa.Column("resume_id", sa.UUID(), nullable=True))
    op.create_index("ix_job_analysis_resume_id", "job_analysis", ["resume_id"], unique=False)
    op.create_foreign_key(
        "fk_job_analysis_resume_id_resumes",
        "job_analysis",
        "resumes",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_job_analysis_resume_id_resumes", "job_analysis", type_="foreignkey")
    op.drop_index("ix_job_analysis_resume_id", table_name="job_analysis")
    op.drop_column("job_analysis", "resume_id")
