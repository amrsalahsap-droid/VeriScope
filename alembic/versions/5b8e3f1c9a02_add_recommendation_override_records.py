"""add_recommendation_override_records

Revision ID: 5b8e3f1c9a02
Revises: 3c9f1a2e8d47
Create Date: 2026-05-24 04:44:00.000000

Adds `recommendation_override_records` table to store the override lineage
of a recommendation run (manual widening/narrowing detection).

One record per RecommendationOutcome. Stores counts, ratios, and test identity
lists — no judgment classification.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5b8e3f1c9a02'
down_revision: Union[str, Sequence[str], None] = '3c9f1a2e8d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recommendation_override_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recommendation_outcome_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recommendation_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('total_manually_added', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_manually_removed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('override_ratio', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('critical_tests_removed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('flaky_tests_manually_restored', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('manually_added_test_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('manually_removed_test_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('critical_removed_test_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('flaky_restored_test_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('widening_detected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('narrowing_detected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['recommendation_outcome_id'],
            ['recommendation_outcomes.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['recommendation_run_id'],
            ['recommendation_runs.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recommendation_outcome_id', name='uq_override_records_outcome_id'),
    )
    op.create_index(
        'ix_recommendation_override_records_outcome_id',
        'recommendation_override_records',
        ['recommendation_outcome_id'],
        unique=True,
    )
    op.create_index(
        'ix_recommendation_override_records_run_id',
        'recommendation_override_records',
        ['recommendation_run_id'],
    )
    op.create_index(
        'ix_recommendation_override_records_repo_id',
        'recommendation_override_records',
        ['repository_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_recommendation_override_records_repo_id', table_name='recommendation_override_records')
    op.drop_index('ix_recommendation_override_records_run_id', table_name='recommendation_override_records')
    op.drop_index('ix_recommendation_override_records_outcome_id', table_name='recommendation_override_records')
    op.drop_table('recommendation_override_records')
