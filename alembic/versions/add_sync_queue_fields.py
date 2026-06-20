"""add_sync_queue_fields

Revision ID: add_sync_queue_fields
Revises: encrypt_integration_credentials
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_sync_queue_fields'
down_revision: Union[str, Sequence[str], None] = 'encrypt_integration_credentials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add queue management fields to manual_execution_sync_events."""
    
    # Add queue management fields
    op.add_column('manual_execution_sync_events', sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('manual_execution_sync_events', sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('manual_execution_sync_events', sa.Column('next_attempt_at', sa.DateTime(), nullable=True))
    op.add_column('manual_execution_sync_events', sa.Column('locked_at', sa.DateTime(), nullable=True))
    op.add_column('manual_execution_sync_events', sa.Column('locked_by', sa.String(), nullable=True))
    op.add_column('manual_execution_sync_events', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.add_column('manual_execution_sync_events', sa.Column('last_error', sa.Text(), nullable=True))
    
    # Add index on next_attempt_at for efficient polling
    op.create_index('ix_manual_execution_sync_events_next_attempt_at', 'manual_execution_sync_events', ['next_attempt_at'])


def downgrade() -> None:
    """Downgrade schema - remove queue management fields."""
    
    # Drop index
    op.drop_index('ix_manual_execution_sync_events_next_attempt_at', table_name='manual_execution_sync_events')
    
    # Drop columns
    op.drop_column('manual_execution_sync_events', 'last_error')
    op.drop_column('manual_execution_sync_events', 'completed_at')
    op.drop_column('manual_execution_sync_events', 'locked_by')
    op.drop_column('manual_execution_sync_events', 'locked_at')
    op.drop_column('manual_execution_sync_events', 'next_attempt_at')
    op.drop_column('manual_execution_sync_events', 'max_attempts')
    op.drop_column('manual_execution_sync_events', 'attempt_count')
