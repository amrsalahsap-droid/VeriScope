"""add pipeline execution jobs table

Revision ID: add_pipeline_execution_jobs
Revises: b1c2d3e4f5g6
Create Date: 2026-06-17 22:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_pipeline_execution_jobs'
down_revision = 'b1c2d3e4f5g6'  # References the pipeline_runs migration
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pipeline_execution_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pipeline_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pipeline_runs.id'), nullable=False, index=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=False, index=True),
        sa.Column('pull_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pull_requests.id'), nullable=True, index=True),
        sa.Column('recommendation_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recommendation_runs.id'), nullable=True, index=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'RETRY_PENDING', 'COMPLETED', 'FAILED', 'DEAD_LETTER', 'CANCELLED', name='pipelinejobstatus'), nullable=False, index=True, default='PENDING'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_attempts', sa.Integer(), nullable=False, default=5),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_type', sa.String(255), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for common query patterns
    op.create_index('ix_pipeline_execution_jobs_status_next_attempt', 'pipeline_execution_jobs', ['status', 'next_attempt_at'])
    op.create_index('ix_pipeline_execution_jobs_repository_status', 'pipeline_execution_jobs', ['repository_id', 'status'])


def downgrade():
    op.drop_index('ix_pipeline_execution_jobs_repository_status', table_name='pipeline_execution_jobs')
    op.drop_index('ix_pipeline_execution_jobs_status_next_attempt', table_name='pipeline_execution_jobs')
    op.drop_table('pipeline_execution_jobs')
