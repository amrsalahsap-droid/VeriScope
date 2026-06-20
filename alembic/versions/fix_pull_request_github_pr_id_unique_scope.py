"""fix_pull_request_github_pr_id_unique_scope

Replace the global unique constraint on pull_requests.github_pr_id with a
composite unique constraint on (repository_id, github_pr_id).

Root cause: the global constraint caused cross-workspace/cross-repository
collisions where a PR sync for workspace B would find and reuse the row
already created by workspace A (same github_pr_id, different repository_id),
producing a response of "Synced 1 PR · 6 changed files" while the subsequent
GET /pull-requests returned 0 rows because the row belonged to a different
repository_id.

Revision ID: fix_pr_github_pr_id_unique_scope
Revises: encrypt_integration_credentials
Create Date: 2026-06-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'fix_pr_github_pr_id_unique_scope'
down_revision: Union[str, Sequence[str], None] = 'encrypt_integration_credentials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the global unique index on github_pr_id (confirmed name: ix_pull_requests_github_pr_id)
    op.drop_index('ix_pull_requests_github_pr_id', table_name='pull_requests')

    # Recreate as a plain (non-unique) index for query performance
    op.create_index(
        'ix_pull_requests_github_pr_id',
        'pull_requests',
        ['github_pr_id'],
        unique=False
    )

    # Add the composite unique constraint scoped to (repository_id, github_pr_id)
    op.create_unique_constraint(
        'uq_pull_request_repo_github_pr_id',
        'pull_requests',
        ['repository_id', 'github_pr_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_pull_request_repo_github_pr_id', 'pull_requests', type_='unique')
    op.drop_index('ix_pull_requests_github_pr_id', table_name='pull_requests')
    op.create_index(
        'ix_pull_requests_github_pr_id',
        'pull_requests',
        ['github_pr_id'],
        unique=True
    )
