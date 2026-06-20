"""create_manual_test_executions

Revision ID: 9c7425950cd9
Revises: 579331fd986d
Create Date: 2026-06-13 20:03:16.405163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c7425950cd9'
down_revision: Union[str, Sequence[str], None] = '579331fd986d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('manual_test_executions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_test_case_id', sa.UUID(), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=False),
    sa.Column('pull_request_id', sa.UUID(), nullable=True),
    sa.Column('recommendation_run_id', sa.UUID(), nullable=True),
    sa.Column('outcome', sa.String(), nullable=False),
    sa.Column('executed_by_id', sa.String(), nullable=True),
    sa.Column('executed_by_name', sa.String(), nullable=True),
    sa.Column('executed_at', sa.DateTime(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('evidence_url', sa.String(), nullable=True),
    sa.Column('attachment_path', sa.String(), nullable=True),
    sa.Column('external_system', sa.String(), nullable=True),
    sa.Column('external_run_id', sa.String(), nullable=True),
    sa.Column('external_execution_id', sa.String(), nullable=True),
    sa.Column('sync_status', sa.String(), nullable=True),
    sa.Column('last_synced_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['external_test_case_id'], ['external_test_cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recommendation_run_id'], ['recommendation_runs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_test_executions_executed_at'), 'manual_test_executions', ['executed_at'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_external_run_id'), 'manual_test_executions', ['external_run_id'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_external_system'), 'manual_test_executions', ['external_system'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_external_test_case_id'), 'manual_test_executions', ['external_test_case_id'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_outcome'), 'manual_test_executions', ['outcome'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_pull_request_id'), 'manual_test_executions', ['pull_request_id'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_recommendation_run_id'), 'manual_test_executions', ['recommendation_run_id'], unique=False)
    op.create_index(op.f('ix_manual_test_executions_repository_id'), 'manual_test_executions', ['repository_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_manual_test_executions_repository_id'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_recommendation_run_id'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_pull_request_id'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_outcome'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_external_test_case_id'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_external_system'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_external_run_id'), table_name='manual_test_executions')
    op.drop_index(op.f('ix_manual_test_executions_executed_at'), table_name='manual_test_executions')
    op.drop_table('manual_test_executions')
