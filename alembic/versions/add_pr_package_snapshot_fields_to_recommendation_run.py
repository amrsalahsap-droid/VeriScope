"""Add PR package snapshot fields to RecommendationRun

Revision ID: add_pr_package_snapshot_fields
Revises: 
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_pr_package_snapshot_fields'
down_revision = 'c96a41da899b'  # Set to the current head
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to recommendation_runs table
    op.add_column('recommendation_runs', sa.Column('head_commit_sha_at_generation', sa.String(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('base_commit_sha_at_generation', sa.String(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('merge_commit_sha_at_generation', sa.String(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('changed_files_snapshot_json', postgresql.JSONB(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('pr_package_ready_at_generation', sa.Boolean(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('input_package_version', sa.String(), nullable=True))


def downgrade():
    # Remove the columns
    op.drop_column('recommendation_runs', 'input_package_version')
    op.drop_column('recommendation_runs', 'pr_package_ready_at_generation')
    op.drop_column('recommendation_runs', 'changed_files_snapshot_json')
    op.drop_column('recommendation_runs', 'merge_commit_sha_at_generation')
    op.drop_column('recommendation_runs', 'base_commit_sha_at_generation')
    op.drop_column('recommendation_runs', 'head_commit_sha_at_generation')
