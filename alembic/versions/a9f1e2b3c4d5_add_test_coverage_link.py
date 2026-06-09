"""add_test_coverage_link

Revision ID: a9f1e2b3c4d5
Revises: 65faaba5360d
Create Date: 2026-05-29 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a9f1e2b3c4d5'
down_revision: Union[str, Sequence[str], None] = '65faaba5360d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the test_coverage_links table."""
    op.create_table(
        'test_coverage_links',
        # Primary key
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Scoping
        sa.Column(
            'workspace_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('workspaces.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'repository_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('repositories.id', ondelete='CASCADE'),
            nullable=False,
        ),

        # Knowledge-graph edge identity
        sa.Column('test_identifier', sa.String(), nullable=False),
        sa.Column('file_path',       sa.String(), nullable=False),

        # Edge quality signals (nullable — can be populated by different sources)
        sa.Column('link_strength', sa.Float(),   nullable=True),   # 0.0 – 1.0
        sa.Column('confidence',    sa.Float(),   nullable=True),   # 0.0 – 1.0
        sa.Column('source',        sa.String(),  nullable=True),   # e.g. STATIC, DYNAMIC, HEURISTIC

        # Execution telemetry counters
        sa.Column('run_count',     sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),

        # Temporal tracking
        sa.Column('first_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at',  sa.DateTime(), nullable=True),

        # Row lifecycle
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Unique constraint: one row per (repository, test, file)
    op.create_unique_constraint(
        'uq_test_coverage_links_repo_test_file',
        'test_coverage_links',
        ['repository_id', 'test_identifier', 'file_path'],
    )

    # Single-column indexes for FK columns (used in joins and deletes)
    op.create_index(
        'ix_test_coverage_links_workspace_id',
        'test_coverage_links',
        ['workspace_id'],
    )
    op.create_index(
        'ix_test_coverage_links_repository_id',
        'test_coverage_links',
        ['repository_id'],
    )

    # Composite indexes as specified in the schema
    op.create_index(
        'ix_test_coverage_links_repo_file',
        'test_coverage_links',
        ['repository_id', 'file_path'],
    )
    op.create_index(
        'ix_test_coverage_links_repo_test',
        'test_coverage_links',
        ['repository_id', 'test_identifier'],
    )
    op.create_index(
        'ix_test_coverage_links_repo_file_test',
        'test_coverage_links',
        ['repository_id', 'file_path', 'test_identifier'],
    )


def downgrade() -> None:
    """Drop the test_coverage_links table and all associated indexes."""
    op.drop_index('ix_test_coverage_links_repo_file_test', table_name='test_coverage_links')
    op.drop_index('ix_test_coverage_links_repo_test',      table_name='test_coverage_links')
    op.drop_index('ix_test_coverage_links_repo_file',      table_name='test_coverage_links')
    op.drop_index('ix_test_coverage_links_repository_id',  table_name='test_coverage_links')
    op.drop_index('ix_test_coverage_links_workspace_id',   table_name='test_coverage_links')
    op.drop_constraint('uq_test_coverage_links_repo_test_file', 'test_coverage_links', type_='unique')
    op.drop_table('test_coverage_links')
