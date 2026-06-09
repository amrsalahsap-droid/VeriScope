"""Add external context fields to recommendation input snapshot

Revision ID: add_external_context_to_snapshot
Revises: 
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_external_context_to_snapshot'
down_revision = 'add_latest_pr_synced_at_to_repository'
branch_labels = None
depends_on = None


def upgrade():
    # Add external context columns to recommendation_input_snapshots table
    op.add_column('recommendation_input_snapshots', 
        sa.Column('linked_work_items', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', 
        sa.Column('acceptance_criteria', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', 
        sa.Column('external_test_cases', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', 
        sa.Column('external_requirement_coverage', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', 
        sa.Column('integration_sync_status', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', 
        sa.Column('external_context_gaps', postgresql.JSONB(), nullable=False, server_default='[]'))


def downgrade():
    # Remove external context columns from recommendation_input_snapshots table
    op.drop_column('recommendation_input_snapshots', 'external_context_gaps')
    op.drop_column('recommendation_input_snapshots', 'integration_sync_status')
    op.drop_column('recommendation_input_snapshots', 'external_requirement_coverage')
    op.drop_column('recommendation_input_snapshots', 'external_test_cases')
    op.drop_column('recommendation_input_snapshots', 'acceptance_criteria')
    op.drop_column('recommendation_input_snapshots', 'linked_work_items')
