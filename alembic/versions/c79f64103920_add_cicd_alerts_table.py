"""add cicd_alerts table

Revision ID: c79f64103920
Revises: d00767b45df8
Create Date: 2026-06-18 04:31:59.213757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c79f64103920'
down_revision: Union[str, Sequence[str], None] = 'd00767b45df8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cicd_alerts',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', sa.UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=False, index=True),
        sa.Column('alert_type', sa.Enum('PIPELINE_BACKLOG_HIGH', 'PIPELINE_DEAD_LETTER_PRESENT', 'GITHUB_PUBLISHING_FAILURE_SPIKE', 'PR_COMMENT_FAILURE_SPIKE', 'ARTIFACT_FAILURE_SPIKE', 'CI_TOKEN_REJECTION_SPIKE', 'WEBHOOK_FAILURE_SPIKE', 'GITHUB_RATE_LIMIT_ACTIVE', 'NO_RECENT_SUCCESSFUL_PIPELINE', 'WORKER_STALE_OR_INACTIVE', name='alerttype'), nullable=False, index=True),
        sa.Column('severity', sa.Enum('INFO', 'WARNING', 'HIGH', 'CRITICAL', name='alertseverity'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('pipeline_run_id', sa.UUID(as_uuid=True), sa.ForeignKey('pipeline_runs.id'), nullable=True, index=True),
        sa.Column('pipeline_job_id', sa.UUID(as_uuid=True), sa.ForeignKey('pipeline_execution_jobs.id'), nullable=True, index=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cicd_alerts')
