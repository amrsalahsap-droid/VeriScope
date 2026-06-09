"""add_repository_production_fields

Revision ID: a1b2c3d4e5f6
Revises: 5bc554d1e627
Create Date: 2026-05-26 00:00:00.000000

Adds missing production-grade fields to the repositories table:
- installation_id, owner, visibility
- selected_for_analysis
- last_synced_at, last_webhook_at, latest_sync_status, sync_error
- Fixes workspace_id to be NOT NULL
- Replaces global unique(github_repo_id) with unique(workspace_id, github_repo_id)
- Drops stale organization_id column
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5bc554d1e627'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Fill any NULL workspace_id rows before making it NOT NULL
    op.execute("UPDATE repositories SET workspace_id = (SELECT id FROM workspaces LIMIT 1) WHERE workspace_id IS NULL")

    # 2. Make workspace_id NOT NULL
    op.alter_column('repositories', 'workspace_id', nullable=False)

    # 3. Drop the global unique index on github_repo_id (will be replaced by composite)
    op.drop_index('ix_repositories_github_repo_id', table_name='repositories')

    # 4. Drop stale organization_id column and its index
    op.drop_index('ix_repositories_organization_id', table_name='repositories')
    op.drop_column('repositories', 'organization_id')

    # 5. Add new columns
    op.add_column('repositories', sa.Column('installation_id', sa.BigInteger(), nullable=True))
    op.add_column('repositories', sa.Column('owner', sa.String(), nullable=True))
    op.add_column('repositories', sa.Column('visibility', sa.String(), nullable=False, server_default='UNKNOWN'))
    op.add_column('repositories', sa.Column('selected_for_analysis', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('repositories', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.add_column('repositories', sa.Column('last_webhook_at', sa.DateTime(), nullable=True))
    op.add_column('repositories', sa.Column('latest_sync_status', sa.String(), nullable=False, server_default='UNKNOWN'))
    op.add_column('repositories', sa.Column('sync_error', sa.Text(), nullable=True))

    # 6. Make default_branch nullable (was NOT NULL before)
    op.alter_column('repositories', 'default_branch', nullable=True)

    # 7. Add composite unique constraint: workspace_id + github_repo_id
    op.create_unique_constraint('uq_repository_workspace_github', 'repositories', ['workspace_id', 'github_repo_id'])

    # 8. Add new indexes
    op.create_index('ix_repositories_installation_id', 'repositories', ['installation_id'])
    op.create_index('ix_repositories_full_name', 'repositories', ['full_name'])


def downgrade() -> None:
    op.drop_index('ix_repositories_full_name', table_name='repositories')
    op.drop_index('ix_repositories_installation_id', table_name='repositories')
    op.drop_constraint('uq_repository_workspace_github', 'repositories', type_='unique')
    op.alter_column('repositories', 'default_branch', nullable=False)
    op.drop_column('repositories', 'sync_error')
    op.drop_column('repositories', 'latest_sync_status')
    op.drop_column('repositories', 'last_webhook_at')
    op.drop_column('repositories', 'last_synced_at')
    op.drop_column('repositories', 'selected_for_analysis')
    op.drop_column('repositories', 'visibility')
    op.drop_column('repositories', 'owner')
    op.drop_column('repositories', 'installation_id')
    op.add_column('repositories', sa.Column('organization_id', sa.UUID(), nullable=True))
    op.create_index('ix_repositories_organization_id', 'repositories', ['organization_id'])
    op.create_index('ix_repositories_github_repo_id', 'repositories', ['github_repo_id'], unique=True)
    op.alter_column('repositories', 'workspace_id', nullable=True)
