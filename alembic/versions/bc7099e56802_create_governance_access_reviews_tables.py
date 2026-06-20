"""create_governance_access_reviews_tables

Revision ID: bc7099e56802
Revises: fcbbe4fdb204
Create Date: 2026-06-19 04:58:26.651641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bc7099e56802'
down_revision: Union[str, Sequence[str], None] = 'fcbbe4fdb204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('governance_access_reviews',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('review_name', sa.String(length=100), nullable=False),
    sa.Column('review_type', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('period_start', sa.DateTime(), nullable=False),
    sa.Column('period_end', sa.DateTime(), nullable=False),
    sa.Column('summary_json', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_access_reviews_workspace_id'), 'governance_access_reviews', ['workspace_id'], unique=False)
    
    op.create_table('governance_access_review_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('review_id', sa.UUID(), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('scope_type', sa.String(length=50), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=True),
    sa.Column('assignment_id', sa.UUID(), nullable=True),
    sa.Column('risk_level', sa.String(length=50), nullable=False),
    sa.Column('finding_type', sa.String(length=100), nullable=False),
    sa.Column('finding_message', sa.String(length=500), nullable=False),
    sa.Column('recommendation', sa.String(length=500), nullable=False),
    sa.Column('review_status', sa.String(length=50), nullable=False),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('decision_reason', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['assignment_id'], ['governance_role_assignments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['review_id'], ['governance_access_reviews.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_access_review_items_assignment_id'), 'governance_access_review_items', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_governance_access_review_items_repository_id'), 'governance_access_review_items', ['repository_id'], unique=False)
    op.create_index(op.f('ix_governance_access_review_items_review_id'), 'governance_access_review_items', ['review_id'], unique=False)
    op.create_index(op.f('ix_governance_access_review_items_user_id'), 'governance_access_review_items', ['user_id'], unique=False)
    op.create_index(op.f('ix_governance_access_review_items_workspace_id'), 'governance_access_review_items', ['workspace_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_governance_access_review_items_workspace_id'), table_name='governance_access_review_items')
    op.drop_index(op.f('ix_governance_access_review_items_user_id'), table_name='governance_access_review_items')
    op.drop_index(op.f('ix_governance_access_review_items_review_id'), table_name='governance_access_review_items')
    op.drop_index(op.f('ix_governance_access_review_items_repository_id'), table_name='governance_access_review_items')
    op.drop_index(op.f('ix_governance_access_review_items_assignment_id'), table_name='governance_access_review_items')
    op.drop_table('governance_access_review_items')
    op.drop_index(op.f('ix_governance_access_reviews_workspace_id'), table_name='governance_access_reviews')
    op.drop_table('governance_access_reviews')
