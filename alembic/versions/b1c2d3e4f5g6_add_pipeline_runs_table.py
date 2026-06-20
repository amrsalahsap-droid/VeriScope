"""add_pipeline_runs_table

Revision ID: b1c2d3e4f5g7
Revises: 9bdd691b538b
Create Date: 2026-06-16 23:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g7'
down_revision: Union[str, Sequence[str], None] = '9bdd691b538b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enums
    pipeline_run_status = sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='pipeline_run_status')
    pipeline_run_status.create(op.get_bind())
    
    quality_gate_status = sa.Enum('PASSED', 'PARTIAL', 'FAILED', 'BLOCKED', 'UNKNOWN', name='quality_gate_status')
    quality_gate_status.create(op.get_bind())
    
    trigger_source = sa.Enum('pull_request', 'push', 'manual', 'webhook', name='trigger_source')
    trigger_source.create(op.get_bind())
    
    # Create pipeline_runs table
    op.create_table(
        'pipeline_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recommendation_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('pull_request_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('external_run_id', sa.String(length=255), nullable=False),
        sa.Column('commit_sha', sa.String(length=255), nullable=False),
        sa.Column('branch', sa.String(length=255), nullable=True),
        sa.Column('status', pipeline_run_status, nullable=False),
        sa.Column('quality_gate', quality_gate_status, nullable=False),
        sa.Column('trigger_source', trigger_source, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recommendation_run_id'], ['recommendation_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_pipeline_runs_repository_id'), 'pipeline_runs', ['repository_id'], unique=False)
    op.create_index(op.f('ix_pipeline_runs_recommendation_run_id'), 'pipeline_runs', ['recommendation_run_id'], unique=False)
    op.create_index(op.f('ix_pipeline_runs_pull_request_id'), 'pipeline_runs', ['pull_request_id'], unique=False)
    op.create_index(op.f('ix_pipeline_runs_external_run_id'), 'pipeline_runs', ['external_run_id'], unique=False)
    op.create_index(op.f('ix_pipeline_runs_status'), 'pipeline_runs', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_pipeline_runs_status'), table_name='pipeline_runs')
    op.drop_index(op.f('ix_pipeline_runs_external_run_id'), table_name='pipeline_runs')
    op.drop_index(op.f('ix_pipeline_runs_pull_request_id'), table_name='pipeline_runs')
    op.drop_index(op.f('ix_pipeline_runs_recommendation_run_id'), table_name='pipeline_runs')
    op.drop_index(op.f('ix_pipeline_runs_repository_id'), table_name='pipeline_runs')
    
    # Drop table
    op.drop_table('pipeline_runs')
    
    # Drop enums
    sa.Enum(name='trigger_source').drop(op.get_bind())
    sa.Enum(name='quality_gate_status').drop(op.get_bind())
    sa.Enum(name='pipeline_run_status').drop(op.get_bind())
