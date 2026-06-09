"""add_evidence_source_fields

Revision ID: add_evidence_source
Revises: a1b2c3d4e5f6
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_evidence_source'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add evidence source fields to test_runs
    op.add_column('test_runs', sa.Column('evidence_source', sa.String(), nullable=False, server_default='MANUAL_UPLOAD'))
    op.add_column('test_runs', sa.Column('evidence_artifact_type', sa.String(), nullable=False, server_default='JUNIT_XML'))
    op.create_index('ix_test_runs_evidence_source', 'test_runs', ['evidence_source'])
    op.create_index('ix_test_runs_evidence_artifact_type', 'test_runs', ['evidence_artifact_type'])
    
    # Add evidence source fields to coverage_reports
    op.add_column('coverage_reports', sa.Column('evidence_source', sa.String(), nullable=False, server_default='MANUAL_UPLOAD'))
    op.add_column('coverage_reports', sa.Column('evidence_artifact_type', sa.String(), nullable=False, server_default='LCOV'))
    op.create_index('ix_coverage_reports_evidence_source', 'coverage_reports', ['evidence_source'])
    op.create_index('ix_coverage_reports_evidence_artifact_type', 'coverage_reports', ['evidence_artifact_type'])
    
    # Add evidence source fields to raw_artifacts
    op.add_column('raw_artifacts', sa.Column('evidence_source', sa.String(), nullable=False, server_default='MANUAL_UPLOAD'))
    op.add_column('raw_artifacts', sa.Column('evidence_artifact_type', sa.String(), nullable=False, server_default='UNKNOWN'))
    op.add_column('raw_artifacts', sa.Column('evidence_health_status', sa.String(), nullable=False, server_default='HEALTHY'))
    op.create_index('ix_raw_artifacts_evidence_source', 'raw_artifacts', ['evidence_source'])
    op.create_index('ix_raw_artifacts_evidence_artifact_type', 'raw_artifacts', ['evidence_artifact_type'])
    op.create_index('ix_raw_artifacts_evidence_health_status', 'raw_artifacts', ['evidence_health_status'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove evidence source fields from test_runs
    op.drop_index('ix_test_runs_evidence_artifact_type', table_name='test_runs')
    op.drop_index('ix_test_runs_evidence_source', table_name='test_runs')
    op.drop_column('test_runs', 'evidence_artifact_type')
    op.drop_column('test_runs', 'evidence_source')
    
    # Remove evidence source fields from coverage_reports
    op.drop_index('ix_coverage_reports_evidence_artifact_type', table_name='coverage_reports')
    op.drop_index('ix_coverage_reports_evidence_source', table_name='coverage_reports')
    op.drop_column('coverage_reports', 'evidence_artifact_type')
    op.drop_column('coverage_reports', 'evidence_source')
    
    # Remove evidence source fields from raw_artifacts
    op.drop_index('ix_raw_artifacts_evidence_health_status', table_name='raw_artifacts')
    op.drop_index('ix_raw_artifacts_evidence_artifact_type', table_name='raw_artifacts')
    op.drop_index('ix_raw_artifacts_evidence_source', table_name='raw_artifacts')
    op.drop_column('raw_artifacts', 'evidence_health_status')
    op.drop_column('raw_artifacts', 'evidence_artifact_type')
    op.drop_column('raw_artifacts', 'evidence_source')
