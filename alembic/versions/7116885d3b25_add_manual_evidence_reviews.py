"""add_manual_evidence_reviews

Revision ID: 7116885d3b25
Revises: 1ed3b0cd3a91
Create Date: 2026-06-15 05:07:17.050221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7116885d3b25'
down_revision: Union[str, Sequence[str], None] = '1ed3b0cd3a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('manual_evidence_reviews',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('manual_test_execution_id', sa.UUID(), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=False),
    sa.Column('review_status', sa.String(), nullable=False),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('reviewed_by_id', sa.UUID(), nullable=True),
    sa.Column('reviewed_by_name', sa.String(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['manual_test_execution_id'], ['manual_test_executions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_evidence_reviews_manual_test_execution_id'), 'manual_evidence_reviews', ['manual_test_execution_id'], unique=False)
    op.create_index(op.f('ix_manual_evidence_reviews_repository_id'), 'manual_evidence_reviews', ['repository_id'], unique=False)
    op.create_index(op.f('ix_manual_evidence_reviews_review_status'), 'manual_evidence_reviews', ['review_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_manual_evidence_reviews_review_status'), table_name='manual_evidence_reviews')
    op.drop_index(op.f('ix_manual_evidence_reviews_repository_id'), table_name='manual_evidence_reviews')
    op.drop_index(op.f('ix_manual_evidence_reviews_manual_test_execution_id'), table_name='manual_evidence_reviews')
    op.drop_table('manual_evidence_reviews')
