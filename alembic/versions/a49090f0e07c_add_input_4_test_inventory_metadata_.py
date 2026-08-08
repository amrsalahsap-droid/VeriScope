"""Add Input 4 test inventory metadata fields

Revision ID: a49090f0e07c
Revises: 88c5779ff440
Create Date: 2026-07-10 20:47:07.870483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a49090f0e07c'
down_revision: Union[str, Sequence[str], None] = '88c5779ff440'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add Input 4 test inventory metadata fields."""
    # Add Input 4 fields to TestCase
    op.add_column('test_cases', sa.Column('test_type', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('automation_status', sa.String(), nullable=False, server_default='UNKNOWN'))
    op.add_column('test_cases', sa.Column('source', sa.String(), nullable=False, server_default='unknown'))
    op.add_column('test_cases', sa.Column('source_metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('test_cases', sa.Column('file_path', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('dedupe_key', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('test_cases', sa.Column('last_seen_at', sa.DateTime(), nullable=True))
    op.add_column('test_cases', sa.Column('last_seen_commit_sha', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('inventory_snapshot_sha', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('module_or_area', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('owner', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('test_cases', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('test_cases', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    
    # Add indexes for Input 4 fields
    op.create_index(op.f('ix_test_cases_dedupe_key'), 'test_cases', ['dedupe_key'], unique=False)
    op.create_index(op.f('ix_test_cases_inventory_snapshot_sha'), 'test_cases', ['inventory_snapshot_sha'], unique=False)
    op.create_index(op.f('ix_test_cases_last_seen_commit_sha'), 'test_cases', ['last_seen_commit_sha'], unique=False)
    op.create_index('ix_test_cases_repo_active', 'test_cases', ['repository_id', 'is_active'], unique=False)
    op.create_index('ix_test_cases_repo_source', 'test_cases', ['repository_id', 'source'], unique=False)
    op.create_index('ix_test_cases_repo_type', 'test_cases', ['repository_id', 'test_type'], unique=False)
    
    # Add Input 4 snapshot fields to RecommendationInputSnapshot
    op.add_column('recommendation_input_snapshots', sa.Column('test_inventory', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', sa.Column('test_inventory_snapshot_hash', sa.String(), nullable=True))
    op.add_column('recommendation_input_snapshots', sa.Column('test_inventory_snapshot_generated_at', sa.DateTime(), nullable=True))
    op.add_column('recommendation_input_snapshots', sa.Column('test_inventory_status_at_generation', sa.String(), nullable=True))
    
    # Add Input 4 snapshot fields to RecommendationRun
    op.add_column('recommendation_runs', sa.Column('test_inventory_snapshot_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('recommendation_runs', sa.Column('stable_test_ids_snapshot_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('recommendation_runs', sa.Column('test_inventory_source_snapshot_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('recommendation_runs', sa.Column('test_inventory_snapshot_hash', sa.String(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('test_inventory_generated_at', sa.DateTime(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('test_inventory_status_at_generation', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema - Remove Input 4 test inventory metadata fields."""
    # Remove Input 4 snapshot fields from RecommendationRun
    op.drop_column('recommendation_runs', 'test_inventory_status_at_generation')
    op.drop_column('recommendation_runs', 'test_inventory_generated_at')
    op.drop_column('recommendation_runs', 'test_inventory_snapshot_hash')
    op.drop_column('recommendation_runs', 'test_inventory_source_snapshot_json')
    op.drop_column('recommendation_runs', 'stable_test_ids_snapshot_json')
    op.drop_column('recommendation_runs', 'test_inventory_snapshot_json')
    
    # Remove Input 4 snapshot fields from RecommendationInputSnapshot
    op.drop_column('recommendation_input_snapshots', 'test_inventory_status_at_generation')
    op.drop_column('recommendation_input_snapshots', 'test_inventory_snapshot_generated_at')
    op.drop_column('recommendation_input_snapshots', 'test_inventory_snapshot_hash')
    op.drop_column('recommendation_input_snapshots', 'test_inventory')
    
    # Remove indexes for Input 4 fields
    op.drop_index('ix_test_cases_repo_type', table_name='test_cases')
    op.drop_index('ix_test_cases_repo_source', table_name='test_cases')
    op.drop_index('ix_test_cases_repo_active', table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_last_seen_commit_sha'), table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_inventory_snapshot_sha'), table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_dedupe_key'), table_name='test_cases')
    
    # Remove Input 4 fields from TestCase
    op.drop_column('test_cases', 'updated_at')
    op.drop_column('test_cases', 'confidence')
    op.drop_column('test_cases', 'tags')
    op.drop_column('test_cases', 'owner')
    op.drop_column('test_cases', 'module_or_area')
    op.drop_column('test_cases', 'inventory_snapshot_sha')
    op.drop_column('test_cases', 'last_seen_commit_sha')
    op.drop_column('test_cases', 'last_seen_at')
    op.drop_column('test_cases', 'is_active')
    op.drop_column('test_cases', 'dedupe_key')
    op.drop_column('test_cases', 'file_path')
    op.drop_column('test_cases', 'source_metadata_json')
    op.drop_column('test_cases', 'source')
    op.drop_column('test_cases', 'automation_status')
    op.drop_column('test_cases', 'test_type')
