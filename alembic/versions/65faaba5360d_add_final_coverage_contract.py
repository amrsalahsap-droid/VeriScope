"""add_final_coverage_contract

Revision ID: 65faaba5360d
Revises: add_external_test_case
Create Date: 2026-05-27 16:30:27.253300

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65faaba5360d'
down_revision: Union[str, Sequence[str], None] = 'add_external_test_case_tbl'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add columns to coverage_reports
    op.add_column('coverage_reports', sa.Column('workspace_id', sa.UUID(), nullable=True))
    op.add_column('coverage_reports', sa.Column('format', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('source', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('branch', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('files_total', sa.Integer(), nullable=True))
    op.add_column('coverage_reports', sa.Column('covered_lines_total', sa.Integer(), nullable=True))
    op.add_column('coverage_reports', sa.Column('uncovered_lines_total', sa.Integer(), nullable=True))
    op.add_column('coverage_reports', sa.Column('line_coverage_ratio', sa.Float(), nullable=True))
    op.add_column('coverage_reports', sa.Column('branch_coverage_ratio', sa.Float(), nullable=True))
    op.add_column('coverage_reports', sa.Column('coverage_confidence', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('evidence_health_status', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('parser_version', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('normalization_schema_version', sa.String(), nullable=True))

    # 2. Make commit_sha nullable in coverage_reports
    op.alter_column('coverage_reports', 'commit_sha', existing_type=sa.String(), nullable=True)

    # 3. Add columns to coverage_file_entries
    op.add_column('coverage_file_entries', sa.Column('repository_id', sa.UUID(), nullable=True))
    op.add_column('coverage_file_entries', sa.Column('total_lines', sa.Integer(), nullable=True))
    op.add_column('coverage_file_entries', sa.Column('line_coverage_ratio', sa.Float(), nullable=True))
    op.add_column('coverage_file_entries', sa.Column('branch_coverage_ratio', sa.Float(), nullable=True))
    op.add_column('coverage_file_entries', sa.Column('functions_covered', sa.Integer(), nullable=True))
    op.add_column('coverage_file_entries', sa.Column('functions_total', sa.Integer(), nullable=True))

    # 4. Backfill existing records
    # Fetch and backfill workspace_id from repositories table
    op.execute("""
        UPDATE coverage_reports cr
        SET workspace_id = r.workspace_id
        FROM repositories r
        WHERE cr.repository_id = r.id
    """)

    # Populate format and source
    op.execute("""
        UPDATE coverage_reports
        SET format = COALESCE(evidence_artifact_type, 'LCOV'),
            source = COALESCE(evidence_source, 'MANUAL_UPLOAD')
    """)

    # Populate line metrics & total files
    op.execute("""
        UPDATE coverage_reports
        SET covered_lines_total = COALESCE(covered_lines_count, 0),
            uncovered_lines_total = COALESCE(uncovered_lines_count, 0),
            files_total = COALESCE((
                SELECT COUNT(*) FROM coverage_file_entries cfe
                WHERE cfe.coverage_report_id = coverage_reports.id
            ), 0),
            line_coverage_ratio = COALESCE(overall_coverage_pct, 0.0),
            coverage_confidence = COALESCE(confidence_score, 'LOW'),
            evidence_health_status = 'HEALTHY',
            parser_version = '1.0.0',
            normalization_schema_version = '1.0.0'
    """)

    # Backfill repository_id on coverage_file_entries
    op.execute("""
        UPDATE coverage_file_entries cfe
        SET repository_id = cr.repository_id
        FROM coverage_reports cr
        WHERE cfe.coverage_report_id = cr.id
    """)

    # Backfill total_lines and line_coverage_ratio on coverage_file_entries
    op.execute("""
        UPDATE coverage_file_entries
        SET total_lines = COALESCE(total_lines_count, 0),
            line_coverage_ratio = CASE 
                WHEN total_lines_count > 0 THEN (covered_lines_count::float / total_lines_count::float) 
                ELSE 0.0 
            END
    """)

    # 5. Set Not Null constraints where appropriate
    op.alter_column('coverage_reports', 'workspace_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('coverage_reports', 'format', existing_type=sa.String(), nullable=False)
    op.alter_column('coverage_reports', 'source', existing_type=sa.String(), nullable=False)
    op.alter_column('coverage_reports', 'files_total', existing_type=sa.Integer(), nullable=False)
    op.alter_column('coverage_reports', 'covered_lines_total', existing_type=sa.Integer(), nullable=False)
    op.alter_column('coverage_reports', 'uncovered_lines_total', existing_type=sa.Integer(), nullable=False)
    op.alter_column('coverage_reports', 'coverage_confidence', existing_type=sa.String(), nullable=False)
    op.alter_column('coverage_reports', 'evidence_health_status', existing_type=sa.String(), nullable=False)
    op.alter_column('coverage_reports', 'parser_version', existing_type=sa.String(), nullable=False)
    op.alter_column('coverage_reports', 'normalization_schema_version', existing_type=sa.String(), nullable=False)

    op.alter_column('coverage_file_entries', 'repository_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('coverage_file_entries', 'total_lines', existing_type=sa.Integer(), nullable=False)

    # 6. Add Foreign Keys and Indexes
    op.create_foreign_key(
        'fk_coverage_reports_workspace_id',
        'coverage_reports', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_coverage_file_entries_repository_id',
        'coverage_file_entries', 'repositories',
        ['repository_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index(op.f('ix_coverage_reports_workspace_id'), 'coverage_reports', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_coverage_reports_format'), 'coverage_reports', ['format'], unique=False)
    op.create_index(op.f('ix_coverage_reports_source'), 'coverage_reports', ['source'], unique=False)
    op.create_index(op.f('ix_coverage_reports_coverage_confidence'), 'coverage_reports', ['coverage_confidence'], unique=False)
    op.create_index(op.f('ix_coverage_reports_evidence_health_status'), 'coverage_reports', ['evidence_health_status'], unique=False)
    op.create_index(op.f('ix_coverage_file_entries_repository_id'), 'coverage_file_entries', ['repository_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_coverage_file_entries_repository_id'), table_name='coverage_file_entries')
    op.drop_index(op.f('ix_coverage_reports_evidence_health_status'), table_name='coverage_reports')
    op.drop_index(op.f('ix_coverage_reports_coverage_confidence'), table_name='coverage_reports')
    op.drop_index(op.f('ix_coverage_reports_source'), table_name='coverage_reports')
    op.drop_index(op.f('ix_coverage_reports_format'), table_name='coverage_reports')
    op.drop_index(op.f('ix_coverage_reports_workspace_id'), table_name='coverage_reports')

    op.drop_constraint('fk_coverage_file_entries_repository_id', 'coverage_file_entries', type_='foreignkey')
    op.drop_constraint('fk_coverage_reports_workspace_id', 'coverage_reports', type_='foreignkey')

    op.drop_column('coverage_file_entries', 'functions_total')
    op.drop_column('coverage_file_entries', 'functions_covered')
    op.drop_column('coverage_file_entries', 'branch_coverage_ratio')
    op.drop_column('coverage_file_entries', 'line_coverage_ratio')
    op.drop_column('coverage_file_entries', 'total_lines')
    op.drop_column('coverage_file_entries', 'repository_id')

    op.alter_column('coverage_reports', 'commit_sha', existing_type=sa.String(), nullable=False)

    op.drop_column('coverage_reports', 'normalization_schema_version')
    op.drop_column('coverage_reports', 'parser_version')
    op.drop_column('coverage_reports', 'evidence_health_status')
    op.drop_column('coverage_reports', 'coverage_confidence')
    op.drop_column('coverage_reports', 'branch_coverage_ratio')
    op.drop_column('coverage_reports', 'line_coverage_ratio')
    op.drop_column('coverage_reports', 'uncovered_lines_total')
    op.drop_column('coverage_reports', 'covered_lines_total')
    op.drop_column('coverage_reports', 'files_total')
    op.drop_column('coverage_reports', 'branch')
    op.drop_column('coverage_reports', 'source')
    op.drop_column('coverage_reports', 'format')
    op.drop_column('coverage_reports', 'workspace_id')

