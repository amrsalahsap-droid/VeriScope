"""Add workspace_id to recommendation_outcomes

Revision ID: add_workspace_id_to_outcomes
Revises:
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_workspace_id_to_outcomes'
down_revision = 'add_work_item_behavior_mapping'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('recommendation_outcomes',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Backfill workspace_id from recommendation_runs
    op.execute("""
        UPDATE recommendation_outcomes ro
        SET workspace_id = rr.workspace_id
        FROM recommendation_runs rr
        WHERE ro.recommendation_run_id = rr.id
        AND ro.workspace_id IS NULL
    """)
    
    op.create_index('ix_recommendation_outcomes_workspace_id', 'recommendation_outcomes', ['workspace_id'])


def downgrade():
    op.drop_index('ix_recommendation_outcomes_workspace_id', table_name='recommendation_outcomes')
    op.drop_column('recommendation_outcomes', 'workspace_id')
