"""Add sync scalability indexes

Revision ID: add_sync_scalability_indexes
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_sync_scalability_indexes'
down_revision = None  # Set to the latest migration if needed
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index on manual_execution_sync_events for filtering and pagination
    op.create_index(
        'ix_manual_execution_sync_events_provider_status_created_at',
        'manual_execution_sync_events',
        ['provider', 'status', 'created_at']
    )
    
    # Add composite index on manual_execution_sync_events for cursor pagination
    op.create_index(
        'ix_manual_execution_sync_events_created_at_id',
        'manual_execution_sync_events',
        ['created_at', 'id']
    )
    
    # Add index on manual_test_executions sync_status for filtering
    op.create_index(
        'ix_manual_test_executions_sync_status',
        'manual_test_executions',
        ['sync_status']
    )
    
    # Add index on manual_test_executions last_synced_at for time-based queries
    op.create_index(
        'ix_manual_test_executions_last_synced_at',
        'manual_test_executions',
        ['last_synced_at']
    )


def downgrade() -> None:
    op.drop_index('ix_manual_test_executions_last_synced_at', table_name='manual_test_executions')
    op.drop_index('ix_manual_test_executions_sync_status', table_name='manual_test_executions')
    op.drop_index('ix_manual_execution_sync_events_created_at_id', table_name='manual_execution_sync_events')
    op.drop_index('ix_manual_execution_sync_events_provider_status_created_at', table_name='manual_execution_sync_events')
