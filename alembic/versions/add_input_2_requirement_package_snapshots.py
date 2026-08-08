"""Add Input 2 requirement package snapshot fields to RecommendationRun and RecommendationInputSnapshot

Revision ID: add_input2_req_pkg_snapshots
Revises: add_separated_sections
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_input2_req_pkg_snapshots'
down_revision = 'add_separated_sections'
branch_labels = None
depends_on = None


def upgrade():
    # Add Input 2 snapshot fields to recommendation_runs
    op.add_column('recommendation_runs', sa.Column('requirement_package_id_at_generation', sa.UUID(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('requirement_package_snapshot_json', postgresql.JSONB(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('requirement_groups_snapshot_json', postgresql.JSONB(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('acceptance_criteria_snapshot_json', postgresql.JSONB(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('stable_ac_keys_snapshot_json', postgresql.JSONB(), nullable=True))
    op.add_column('recommendation_runs', sa.Column('requirement_package_ready_at_generation', sa.Boolean(), nullable=True))

    # Add Input 2 snapshot fields to recommendation_input_snapshots
    op.add_column('recommendation_input_snapshots', sa.Column('requirement_package', postgresql.JSONB(), nullable=True))
    op.add_column('recommendation_input_snapshots', sa.Column('requirement_groups', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.add_column('recommendation_input_snapshots', sa.Column('stable_ac_keys', postgresql.JSONB(), nullable=False, server_default='[]'))


def downgrade():
    # Remove Input 2 snapshot fields from recommendation_input_snapshots
    op.drop_column('recommendation_input_snapshots', 'stable_ac_keys')
    op.drop_column('recommendation_input_snapshots', 'requirement_groups')
    op.drop_column('recommendation_input_snapshots', 'requirement_package')

    # Remove Input 2 snapshot fields from recommendation_runs
    op.drop_column('recommendation_runs', 'requirement_package_ready_at_generation')
    op.drop_column('recommendation_runs', 'stable_ac_keys_snapshot_json')
    op.drop_column('recommendation_runs', 'acceptance_criteria_snapshot_json')
    op.drop_column('recommendation_runs', 'requirement_groups_snapshot_json')
    op.drop_column('recommendation_runs', 'requirement_package_snapshot_json')
    op.drop_column('recommendation_runs', 'requirement_package_id_at_generation')
