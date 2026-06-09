"""add_phase6_outcome_tracking

Revision ID: f911ba77e9a6
Revises: d2218e8e86aa
Create Date: 2026-05-24 04:08:57.411119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f911ba77e9a6'
down_revision: Union[str, Sequence[str], None] = 'd2218e8e86aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create new table recommendation_test_outcomes
    op.create_table(
        'recommendation_test_outcomes',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('recommendation_outcome_id', sa.UUID(as_uuid=True), sa.ForeignKey('recommendation_outcomes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('test_case_id', sa.UUID(as_uuid=True), sa.ForeignKey('test_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recommendation_reason', sa.String(), nullable=True),
        sa.Column('recommended_by_veriscope', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('actually_executed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('manually_added', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('manually_removed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('execution_result', sa.String(), nullable=True),
        sa.Column('execution_duration_seconds', sa.Float(), nullable=True),
        sa.Column('flaky_influence', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('quarantine_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    op.create_index('ix_rec_test_outcomes_outcome_id', 'recommendation_test_outcomes', ['recommendation_outcome_id'])
    op.create_index('ix_rec_test_outcomes_test_case_id', 'recommendation_test_outcomes', ['test_case_id'])

    # 2. Create new table recommendation_engineer_feedbacks
    op.create_table(
        'recommendation_engineer_feedbacks',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('recommendation_outcome_id', sa.UUID(as_uuid=True), sa.ForeignKey('recommendation_outcomes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feedback_type', sa.String(), nullable=False),
        sa.Column('feedback_text', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    op.create_index('ix_rec_eng_feedbacks_outcome_id', 'recommendation_engineer_feedbacks', ['recommendation_outcome_id'])

    # 3. Modify recommendation_outcomes table (Batch operations for SQLite compatibility)
    # Add new fields as nullable initially
    with op.batch_alter_table('recommendation_outcomes') as batch_op:
        batch_op.add_column(sa.Column('repository_id', sa.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('pull_request_id', sa.UUID(as_uuid=True), sa.ForeignKey('pull_requests.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('recommendation_snapshot_hash', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('fragility_snapshot_hash', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('outcome_status', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('recommendation_presented_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('recommendation_acknowledged_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('recommendation_ignored_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deployment_completed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('escaped_defect_detected', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        batch_op.add_column(sa.Column('engineer_feedback', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('feedback_reason', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('outcome_confidence', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 4. Backfill existing records safely
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET repository_id = (SELECT repository_id FROM recommendation_runs WHERE recommendation_runs.id = recommendation_outcomes.recommendation_run_id)"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET pull_request_id = (SELECT pull_request_id FROM recommendation_runs WHERE recommendation_runs.id = recommendation_outcomes.recommendation_run_id)"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET recommendation_snapshot_hash = 'legacy_run'"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET outcome_status = CASE WHEN was_followed = TRUE THEN 'FOLLOWED' ELSE 'OVERRIDDEN' END"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET outcome_status = 'FOLLOWED' WHERE outcome_status IS NULL"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET recommendation_presented_at = (SELECT created_at FROM recommendation_runs WHERE recommendation_runs.id = recommendation_outcomes.recommendation_run_id)"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET recommendation_presented_at = created_at WHERE recommendation_presented_at IS NULL"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET escaped_defect_detected = COALESCE(escaped_defect, FALSE)"
    )
    op.execute(
        "UPDATE recommendation_outcomes "
        "SET updated_at = created_at WHERE updated_at IS NULL"
    )

    # 5. Alter newly backfilled columns to be non-nullable and make legacy columns nullable
    with op.batch_alter_table('recommendation_outcomes') as batch_op:
        batch_op.alter_column('repository_id', existing_type=sa.UUID(as_uuid=True), nullable=False)
        batch_op.alter_column('recommendation_snapshot_hash', existing_type=sa.String(), nullable=False)
        batch_op.alter_column('outcome_status', existing_type=sa.String(), nullable=False)
        batch_op.alter_column('recommendation_presented_at', existing_type=sa.DateTime(), nullable=False)
        batch_op.alter_column('updated_at', existing_type=sa.DateTime(), nullable=False)
        
        # Non-destructive legacy adjustments (making old columns nullable so they are optional going forward)
        batch_op.alter_column('executed_tests', existing_type=postgresql.JSONB, nullable=True)
        batch_op.alter_column('manually_added_tests', existing_type=postgresql.JSONB, nullable=True)
        batch_op.alter_column('manually_removed_tests', existing_type=postgresql.JSONB, nullable=True)
        batch_op.alter_column('was_followed', existing_type=sa.Boolean(), nullable=True)
        batch_op.alter_column('escaped_defect', existing_type=sa.Boolean(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop indices and new tables
    op.drop_index('ix_rec_eng_feedbacks_outcome_id', table_name='recommendation_engineer_feedbacks')
    op.drop_table('recommendation_engineer_feedbacks')
    op.drop_index('ix_rec_test_outcomes_test_case_id', table_name='recommendation_test_outcomes')
    op.drop_index('ix_rec_test_outcomes_outcome_id', table_name='recommendation_test_outcomes')
    op.drop_table('recommendation_test_outcomes')

    # 2. Revert column modifications in recommendation_outcomes
    with op.batch_alter_table('recommendation_outcomes') as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('outcome_confidence')
        batch_op.drop_column('feedback_reason')
        batch_op.drop_column('engineer_feedback')
        batch_op.drop_column('escaped_defect_detected')
        batch_op.drop_column('deployment_completed_at')
        batch_op.drop_column('recommendation_ignored_at')
        batch_op.drop_column('recommendation_acknowledged_at')
        batch_op.drop_column('recommendation_presented_at')
        batch_op.drop_column('outcome_status')
        batch_op.drop_column('fragility_snapshot_hash')
        batch_op.drop_column('recommendation_snapshot_hash')
        batch_op.drop_column('pull_request_id')
        batch_op.drop_column('repository_id')
        
        # Restore legacy columns to non-nullable
        batch_op.alter_column('was_followed', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('escaped_defect', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('manually_removed_tests', existing_type=postgresql.JSONB, nullable=False)
        batch_op.alter_column('manually_added_tests', existing_type=postgresql.JSONB, nullable=False)
        batch_op.alter_column('executed_tests', existing_type=postgresql.JSONB, nullable=False)
