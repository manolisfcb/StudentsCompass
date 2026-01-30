"""add user_stats table

Revision ID: 7e1b9a4f2c10
Revises: 462d490a97a1
Create Date: 2026-01-28 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e1b9a4f2c10'
down_revision: Union[str, Sequence[str], None] = '462d490a97a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_stats',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('resume_progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('linkedin_progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('interview_progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_user_stats_user_id')
    )
    op.create_index('ix_user_stats_user_id', 'user_stats', ['user_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_stats_user_id', table_name='user_stats')
    op.drop_table('user_stats')
