"""create traceability edges

Revision ID: 7a3d2e1c4b9f
Revises: 9e8d7c6b5a4a
Create Date: 2026-07-11 23:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a3d2e1c4b9f'
down_revision: Union[str, Sequence[str], None] = '9e8d7c6b5a4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'traceability_edges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('pull_request_id', sa.UUID(), nullable=True),
        sa.Column('source_node_type', sa.String(), nullable=False),
        sa.Column('source_node_id', sa.String(), nullable=False),
        sa.Column('target_node_type', sa.String(), nullable=False),
        sa.Column('target_node_id', sa.String(), nullable=False),
        sa.Column('edge_type', sa.String(), nullable=False),
        sa.Column('edge_source', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence_json', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('review_status', sa.String(), nullable=False, server_default='system_suggested'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('confirmed_by', sa.String(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'repository_id',
            'source_node_type',
            'source_node_id',
            'target_node_type',
            'target_node_id',
            'edge_type',
            'edge_source',
            name='uq_traceability_edges_unique_active'
        )
    )
    # Add indexes for performance
    op.create_index('ix_traceability_edges_repo', 'traceability_edges', ['repository_id'])
    op.create_index('ix_traceability_edges_pr', 'traceability_edges', ['pull_request_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_traceability_edges_pr', table_name='traceability_edges')
    op.drop_index('ix_traceability_edges_repo', table_name='traceability_edges')
    op.drop_table('traceability_edges')
