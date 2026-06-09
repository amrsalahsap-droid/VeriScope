"""add latest_pr_synced_at to repository

Revision ID: add_latest_pr_synced_at_to_repository
Revises: 
Create Date: 2026-06-04 22:36:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_latest_pr_synced_at_to_repository'
down_revision = 'add_workspace_id_to_outcomes'
branch_labels = None
depends_on = None


def upgrade():
    # Add latest_pr_synced_at column to repositories table
    op.add_column('repositories', sa.Column('latest_pr_synced_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove latest_pr_synced_at column from repositories table
    op.drop_column('repositories', 'latest_pr_synced_at')
