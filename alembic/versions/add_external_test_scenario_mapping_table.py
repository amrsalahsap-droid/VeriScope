"""add_external_test_scenario_mapping_table

Revision ID: add_external_test_scenario_mapping
Revises: add_work_item_behavior_mapping
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_external_test_scenario_mapping'
down_revision: Union[str, Sequence[str], None] = '65faaba5360d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'external_test_scenario_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('external_test_case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('external_test_cases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('behavior_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('behaviors.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('behavior_scenario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('behavior_scenarios.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('scenario_intent_key', sa.String(), nullable=True, index=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('matched_terms', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
    
    # Create unique constraint: external_test_case_id
    op.create_unique_constraint(
        'uq_external_test_scenario_mapping',
        'external_test_scenario_mappings',
        ['external_test_case_id']
    )
    
    # Create index for behavior_id
    op.create_index(
        'ix_external_test_scenario_mappings_behavior',
        'external_test_scenario_mappings',
        ['behavior_id']
    )
    
    # Create index for behavior_scenario_id
    op.create_index(
        'ix_external_test_scenario_mappings_scenario',
        'external_test_scenario_mappings',
        ['behavior_scenario_id']
    )
    
    # Create index for scenario_intent_key
    op.create_index(
        'ix_external_test_scenario_mappings_intent_key',
        'external_test_scenario_mappings',
        ['scenario_intent_key']
    )
    
    # Create index for confidence
    op.create_index(
        'ix_external_test_scenario_mappings_confidence',
        'external_test_scenario_mappings',
        ['confidence']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_external_test_scenario_mappings_confidence', table_name='external_test_scenario_mappings')
    op.drop_index('ix_external_test_scenario_mappings_intent_key', table_name='external_test_scenario_mappings')
    op.drop_index('ix_external_test_scenario_mappings_scenario', table_name='external_test_scenario_mappings')
    op.drop_index('ix_external_test_scenario_mappings_behavior', table_name='external_test_scenario_mappings')
    op.drop_constraint('uq_external_test_scenario_mapping', table_name='external_test_scenario_mappings')
    op.drop_table('external_test_scenario_mappings')
