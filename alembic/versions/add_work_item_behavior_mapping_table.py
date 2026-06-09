"""add_work_item_behavior_mapping_table

Revision ID: add_work_item_behavior_mapping
Revises: add_pr_work_item_link
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_work_item_behavior_mapping'
down_revision: Union[str, Sequence[str], None] = 'add_pr_work_item_link'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'work_item_behavior_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('external_work_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('external_work_items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('behavior_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('behaviors.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('journey_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journeys.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('matched_terms', postgresql.JSONB(), nullable=True, default=list),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
    
    # Create unique constraint: external_work_item_id
    op.create_unique_constraint(
        'uq_work_item_mapping',
        'work_item_behavior_mappings',
        ['external_work_item_id']
    )
    
    # Create index for behavior_id
    op.create_index(
        'ix_work_item_behavior_mappings_behavior',
        'work_item_behavior_mappings',
        ['behavior_id']
    )
    
    # Create index for journey_id
    op.create_index(
        'ix_work_item_behavior_mappings_journey',
        'work_item_behavior_mappings',
        ['journey_id']
    )
    
    # Create index for confidence
    op.create_index(
        'ix_work_item_behavior_mappings_confidence',
        'work_item_behavior_mappings',
        ['confidence']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_work_item_behavior_mappings_confidence', table_name='work_item_behavior_mappings')
    op.drop_index('ix_work_item_behavior_mappings_journey', table_name='work_item_behavior_mappings')
    op.drop_index('ix_work_item_behavior_mappings_behavior', table_name='work_item_behavior_mappings')
    op.drop_constraint('uq_work_item_mapping', table_name='work_item_behavior_mappings')
    op.drop_table('work_item_behavior_mappings')
