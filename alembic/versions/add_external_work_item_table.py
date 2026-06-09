"""add_external_work_item_table

Revision ID: add_external_work_item
Revises: add_integration_connection
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_external_work_item'
down_revision: Union[str, Sequence[str], None] = 'add_integration_connection'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'external_work_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('integration_connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integration_connections.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(), nullable=False, index=True),
        sa.Column('external_id', sa.String(), nullable=False, index=True),
        sa.Column('external_key', sa.String(), nullable=False, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('work_item_type', sa.String(), nullable=False, default='UNKNOWN', index=True),
        sa.Column('status', sa.String(), nullable=False, index=True),
        sa.Column('priority', sa.String(), nullable=True, index=True),
        sa.Column('labels', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('acceptance_criteria', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # Create unique constraint: provider + integration_connection_id + external_id
    op.create_unique_constraint(
        'uq_provider_connection_external_id',
        'external_work_items',
        ['provider', 'integration_connection_id', 'external_id']
    )
    
    # Create composite index for workspace_id + work_item_type
    op.create_index(
        'ix_external_work_items_workspace_type',
        'external_work_items',
        ['workspace_id', 'work_item_type']
    )
    
    # Create index for repository_id
    op.create_index(
        'ix_external_work_items_repository',
        'external_work_items',
        ['repository_id']
    )
    
    # Create index for status
    op.create_index(
        'ix_external_work_items_status',
        'external_work_items',
        ['status']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_external_work_items_status', table_name='external_work_items')
    op.drop_index('ix_external_work_items_repository', table_name='external_work_items')
    op.drop_index('ix_external_work_items_workspace_type', table_name='external_work_items')
    op.drop_constraint('uq_provider_connection_external_id', table_name='external_work_items')
    op.drop_table('external_work_items')
