"""add coverage pr sha context

Revision ID: add_coverage_pr_sha_context
Revises: ac_map_semantic_audit
Create Date: 2026-07-31 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_coverage_pr_sha_context'
down_revision = 'ac_map_semantic_audit'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('coverage_reports', sa.Column('current_pr_head_sha', sa.String(), nullable=True))
    op.add_column('coverage_reports', sa.Column('commit_sha_source', sa.String(), nullable=False, server_default='MANUAL'))
    op.add_column('coverage_reports', sa.Column('sha_mismatch', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('coverage_reports', sa.Column('is_current', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('coverage_reports', sa.Column('coverage_uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')))
    op.add_column('coverage_reports', sa.Column('changed_files_total', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('coverage_reports', sa.Column('changed_files_with_coverage', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('coverage_reports', sa.Column('changed_files_without_coverage', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('coverage_reports', sa.Column('current_pr_coverage_confidence', sa.String(), nullable=True))


def downgrade():
    op.drop_column('coverage_reports', 'current_pr_coverage_confidence')
    op.drop_column('coverage_reports', 'changed_files_without_coverage')
    op.drop_column('coverage_reports', 'changed_files_with_coverage')
    op.drop_column('coverage_reports', 'changed_files_total')
    op.drop_column('coverage_reports', 'coverage_uploaded_at')
    op.drop_column('coverage_reports', 'is_current')
    op.drop_column('coverage_reports', 'sha_mismatch')
    op.drop_column('coverage_reports', 'commit_sha_source')
    op.drop_column('coverage_reports', 'current_pr_head_sha')
