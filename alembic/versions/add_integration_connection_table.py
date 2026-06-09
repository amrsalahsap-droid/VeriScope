"""add_integration_connection_table

Revision ID: add_integration_connection
Revises: add_external_test_case
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_integration_connection'
down_revision: Union[str, Sequence[str], None] = 'f0db80fcf4cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'integration_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('provider', sa.String(), nullable=False, index=True),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='DISCONNECTED', index=True),
        sa.Column('base_url', sa.String(), nullable=True),
        sa.Column('encrypted_credentials', postgresql.JSONB(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, default=dict),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_status', sa.String(), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # Create unique constraint: workspace_id + provider + display_name
    op.create_unique_constraint(
        'uq_workspace_provider_display_name',
        'integration_connections',
        ['workspace_id', 'provider', 'display_name']
    )
    
    # Create composite index for workspace_id + status
    op.create_index(
        'ix_integration_connections_workspace_status',
        'integration_connections',
        ['workspace_id', 'status']
    )
    
    # Create index for repository_id
    op.create_index(
        'ix_integration_connections_repository',
        'integration_connections',
        ['repository_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_integration_connections_repository', table_name='integration_connections')
    op.drop_index('ix_integration_connections_workspace_status', table_name='integration_connections')
    op.drop_constraint('uq_workspace_provider_display_name', table_name='integration_connections')
    op.drop_table('integration_connections')
