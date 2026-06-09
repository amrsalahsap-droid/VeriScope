"""create_pattern_memories_table

Revision ID: ff27f7249c76
Revises: f5b7b0f48f06
Create Date: 2026-05-31 01:56:05.888460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ff27f7249c76'
down_revision: Union[str, Sequence[str], None] = 'f5b7b0f48f06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pattern_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pattern_key', sa.String(), nullable=False),
        sa.Column('changed_file_pattern', sa.String(), nullable=False),
        sa.Column('recommended_test', sa.String(), nullable=True),
        sa.Column('test_identifier', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('defect_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'repository_id', 'pattern_key', 'test_identifier',
            name='uq_pattern_memory_repo_pattern_test'
        ),
        sa.CheckConstraint(
            'confidence >= 0.0 AND confidence <= 1.0',
            name='chk_pattern_memory_confidence'
        )
    )
    op.create_index(op.f('ix_pattern_memories_workspace_id'), 'pattern_memories', ['workspace_id'])
    op.create_index(op.f('ix_pattern_memories_repository_id'), 'pattern_memories', ['repository_id'])
    op.create_index(op.f('ix_pattern_memories_pattern_key'), 'pattern_memories', ['pattern_key'])
    op.create_index(op.f('ix_pattern_memories_changed_file_pattern'), 'pattern_memories', ['changed_file_pattern'])
    op.create_index(op.f('ix_pattern_memories_recommended_test'), 'pattern_memories', ['recommended_test'])
    op.create_index(op.f('ix_pattern_memories_test_identifier'), 'pattern_memories', ['test_identifier'])
    op.create_index('ix_pattern_memory_repo_key', 'pattern_memories', ['repository_id', 'pattern_key'])
    op.create_index('ix_pattern_memory_repo_identifier', 'pattern_memories', ['repository_id', 'test_identifier'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_pattern_memory_repo_identifier', table_name='pattern_memories')
    op.drop_index('ix_pattern_memory_repo_key', table_name='pattern_memories')
    op.drop_index(op.f('ix_pattern_memories_test_identifier'), table_name='pattern_memories')
    op.drop_index(op.f('ix_pattern_memories_recommended_test'), table_name='pattern_memories')
    op.drop_index(op.f('ix_pattern_memories_changed_file_pattern'), table_name='pattern_memories')
    op.drop_index(op.f('ix_pattern_memories_pattern_key'), table_name='pattern_memories')
    op.drop_index(op.f('ix_pattern_memories_repository_id'), table_name='pattern_memories')
    op.drop_index(op.f('ix_pattern_memories_workspace_id'), table_name='pattern_memories')
    op.drop_table('pattern_memories')
