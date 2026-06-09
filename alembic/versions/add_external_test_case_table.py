"""add_external_test_case_table

Revision ID: add_external_test_case
Revises: add_external_work_item
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_external_test_case_tbl'
down_revision: Union[str, Sequence[str], None] = 'add_integration_connection'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'external_test_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('integration_connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integration_connections.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(), nullable=False, index=True),
        sa.Column('external_id', sa.String(), nullable=False, index=True),
        sa.Column('external_key', sa.String(), nullable=True, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('preconditions', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('steps', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('expected_result', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(), nullable=True, index=True),
        sa.Column('test_type', sa.String(), nullable=True, index=True),
        sa.Column('automation_status', sa.String(), nullable=False, default='UNKNOWN', index=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('linked_work_item_keys', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('behavior_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('behaviors.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('journey_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journeys.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('scenario_intent_key', sa.String(), nullable=True, index=True),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # Create unique constraint: provider + integration_connection_id + external_id
    op.create_unique_constraint(
        'uq_external_test_cases_provider_connection_id',
        'external_test_cases',
        ['provider', 'integration_connection_id', 'external_id']
    )
    
    # Create composite index for workspace_id + automation_status
    op.create_index(
        'ix_external_test_cases_workspace_automation',
        'external_test_cases',
        ['workspace_id', 'automation_status']
    )
    
    # Create index for repository_id
    op.create_index(
        'ix_external_test_cases_repository',
        'external_test_cases',
        ['repository_id']
    )
    
    # Create index for priority
    op.create_index(
        'ix_external_test_cases_priority',
        'external_test_cases',
        ['priority']
    )
    
    # Create index for behavior_id
    op.create_index(
        'ix_external_test_cases_behavior',
        'external_test_cases',
        ['behavior_id']
    )
    
    # Create index for journey_id
    op.create_index(
        'ix_external_test_cases_journey',
        'external_test_cases',
        ['journey_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_external_test_cases_journey', table_name='external_test_cases')
    op.drop_index('ix_external_test_cases_behavior', table_name='external_test_cases')
    op.drop_index('ix_external_test_cases_priority', table_name='external_test_cases')
    op.drop_index('ix_external_test_cases_repository', table_name='external_test_cases')
    op.drop_index('ix_external_test_cases_workspace_automation', table_name='external_test_cases')
    op.drop_constraint('uq_external_test_cases_provider_connection_id', table_name='external_test_cases')
    op.drop_table('external_test_cases')
