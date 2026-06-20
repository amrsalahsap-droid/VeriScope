"""add_release_decision_tables

Revision ID: 9bdd691b538b
Revises: e2b0334a4615
Create Date: 2026-06-12 23:33:15.816023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bdd691b538b'
down_revision: Union[str, Sequence[str], None] = 'e2b0334a4615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create release_decisions table using existing enum
    op.create_table(
        'release_decisions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('recommendation_run_id', sa.UUID(), nullable=False),
        sa.Column('decision_status', sa.Enum('PENDING_REVIEW', 'APPROVED', 'REJECTED', 'CONDITIONALLY_APPROVED', name='decision_status', create_type=False), nullable=False),
        sa.Column('approver_id', sa.UUID(), nullable=True),
        sa.Column('approver_name', sa.String(), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('snapshot_hash', sa.String(), nullable=True),
        sa.Column('evidence_health_status', sa.String(), nullable=True),
        sa.Column('readiness_state', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['recommendation_run_id'], ['recommendation_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recommendation_run_id')
    )
    op.create_index(op.f('ix_release_decisions_recommendation_run_id'), 'release_decisions', ['recommendation_run_id'], unique=False)
    
    # Create release_decision_history table using existing enum
    op.create_table(
        'release_decision_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('release_decision_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.Enum('REQUESTED', 'APPROVED', 'REJECTED', 'CONDITIONALLY_APPROVED', 'RESET', 'CANCELLED', name='history_event_type', create_type=False), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('actor_name', sa.String(), nullable=True),
        sa.Column('previous_status', sa.String(), nullable=True),
        sa.Column('new_status', sa.String(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('snapshot_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['release_decision_id'], ['release_decisions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_release_decision_history_release_decision_id'), 'release_decision_history', ['release_decision_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_release_decision_history_release_decision_id'), table_name='release_decision_history')
    op.drop_table('release_decision_history')
    op.drop_index(op.f('ix_release_decisions_recommendation_run_id'), table_name='release_decisions')
    op.drop_table('release_decisions')
    
    # Drop enums
    sa.Enum(name='history_event_type').drop(op.get_bind())
    sa.Enum(name='decision_status').drop(op.get_bind())
