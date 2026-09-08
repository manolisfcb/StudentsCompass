"""merge parallel heads after 1720e86014a0

Revision ID: b7c3d9e2f1a4
Revises: 6e4bc7a18f21, a4f9c2d8e6b1
Create Date: 2026-03-10 10:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "b7c3d9e2f1a4"
down_revision: Union[str, Sequence[str], None] = ("6e4bc7a18f21", "a4f9c2d8e6b1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration: no schema changes.
    pass


def downgrade() -> None:
    # Merge migration: no schema changes.
    pass
