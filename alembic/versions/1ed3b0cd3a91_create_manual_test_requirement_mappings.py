"""create_manual_test_requirement_mappings

Revision ID: 1ed3b0cd3a91
Revises: 9c7425950cd9
Create Date: 2026-06-14 00:31:41.331399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ed3b0cd3a91'
down_revision: Union[str, Sequence[str], None] = '9c7425950cd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('manual_test_requirement_mappings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_test_case_id', sa.UUID(), nullable=False),
    sa.Column('acceptance_criterion_id', sa.UUID(), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=False),
    sa.Column('mapping_source', sa.String(), nullable=False),
    sa.Column('created_by_id', sa.String(), nullable=True),
    sa.Column('created_by_name', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['acceptance_criterion_id'], ['acceptance_criteria.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['external_test_case_id'], ['external_test_cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_test_requirement_mappings_acceptance_criterion_id'), 'manual_test_requirement_mappings', ['acceptance_criterion_id'], unique=False)
    op.create_index(op.f('ix_manual_test_requirement_mappings_external_test_case_id'), 'manual_test_requirement_mappings', ['external_test_case_id'], unique=False)
    op.create_index(op.f('ix_manual_test_requirement_mappings_repository_id'), 'manual_test_requirement_mappings', ['repository_id'], unique=False)
    op.create_index('uq_active_manual_test_ac_mapping', 'manual_test_requirement_mappings', ['external_test_case_id', 'acceptance_criterion_id'], unique=True, sqlite_where=sa.text('is_active'), postgresql_where=sa.text('is_active'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_active_manual_test_ac_mapping', table_name='manual_test_requirement_mappings')
    op.drop_index(op.f('ix_manual_test_requirement_mappings_repository_id'), table_name='manual_test_requirement_mappings')
    op.drop_index(op.f('ix_manual_test_requirement_mappings_external_test_case_id'), table_name='manual_test_requirement_mappings')
    op.drop_index(op.f('ix_manual_test_requirement_mappings_acceptance_criterion_id'), table_name='manual_test_requirement_mappings')
    op.drop_table('manual_test_requirement_mappings')
