"""Add risk review model

Revision ID: e2b0334a4615
Revises: 002_add_source_segments
Create Date: 2026-06-12 03:05:22.980464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b0334a4615'
down_revision: Union[str, Sequence[str], None] = '002_add_source_segments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('risk_reviews',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('recommendation_run_id', sa.UUID(), nullable=False),
    sa.Column('source_requirement_id', sa.String(length=100), nullable=True),
    sa.Column('source_ac_number', sa.Integer(), nullable=True),
    sa.Column('readable_id', sa.String(length=255), nullable=True),
    sa.Column('original_risk_level', sa.String(length=50), nullable=False),
    sa.Column('original_priority', sa.String(length=50), nullable=False),
    sa.Column('reviewed_risk_level', sa.String(length=50), nullable=False),
    sa.Column('reviewed_priority', sa.String(length=50), nullable=False),
    sa.Column('review_status', sa.String(length=50), nullable=False),
    sa.Column('reviewer_id', sa.String(length=100), nullable=True),
    sa.Column('reviewer_name', sa.String(length=255), nullable=True),
    sa.Column('review_note', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('source_snapshot_hash', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['recommendation_run_id'], ['recommendation_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_risk_reviews_recommendation_run_id'), 'risk_reviews', ['recommendation_run_id'], unique=False)
    op.create_index(op.f('ix_risk_reviews_source_ac_number'), 'risk_reviews', ['source_ac_number'], unique=False)
    op.create_index(op.f('ix_risk_reviews_source_requirement_id'), 'risk_reviews', ['source_requirement_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_risk_reviews_source_requirement_id'), table_name='risk_reviews')
    op.drop_index(op.f('ix_risk_reviews_source_ac_number'), table_name='risk_reviews')
    op.drop_index(op.f('ix_risk_reviews_recommendation_run_id'), table_name='risk_reviews')
    op.drop_table('risk_reviews')
