"""add resource lock flag

Revision ID: a4f9c2d8e6b1
Revises: 9b72c4e1af10
Create Date: 2026-03-07 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4f9c2d8e6b1"
down_revision: Union[str, Sequence[str], None] = "9b72c4e1af10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    resource_columns = {column["name"] for column in inspector.get_columns("resources")}
    if "is_locked" not in resource_columns:
        op.add_column(
            "resources",
            sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("resources")}
    if "ix_resources_is_locked" not in existing_indexes:
        op.create_index("ix_resources_is_locked", "resources", ["is_locked"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("resources")}
    if "ix_resources_is_locked" in existing_indexes:
        op.drop_index("ix_resources_is_locked", table_name="resources")

    resource_columns = {column["name"] for column in inspector.get_columns("resources")}
    if "is_locked" in resource_columns:
        op.drop_column("resources", "is_locked")
