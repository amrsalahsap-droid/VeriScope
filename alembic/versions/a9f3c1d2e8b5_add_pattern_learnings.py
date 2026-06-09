"""add_pattern_learnings

Revision ID: a9f3c1d2e8b5
Revises: 6589ecbfee06
Create Date: 2026-05-30

Adds the pattern_learnings table for incremental PR-pattern → test learning.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a9f3c1d2e8b5'
down_revision = '6589ecbfee06'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pattern_learnings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pattern_key', sa.String(), nullable=False),
        sa.Column('test_identifier', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('strength', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('last_outcome_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['last_outcome_id'], ['recommendation_outcomes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'repository_id', 'pattern_key', 'test_identifier', 'source',
            name='uq_pattern_learning_repo_pattern_test_source'
        ),
    )
    op.create_index('ix_pattern_learning_repo_pattern', 'pattern_learnings', ['repository_id', 'pattern_key'])
    op.create_index('ix_pattern_learning_repo_test',    'pattern_learnings', ['repository_id', 'test_identifier'])
    op.create_index(op.f('ix_pattern_learnings_repository_id'), 'pattern_learnings', ['repository_id'])
    op.create_index(op.f('ix_pattern_learnings_pattern_key'),   'pattern_learnings', ['pattern_key'])
    op.create_index(op.f('ix_pattern_learnings_test_identifier'),'pattern_learnings', ['test_identifier'])


def downgrade() -> None:
    op.drop_index(op.f('ix_pattern_learnings_test_identifier'), table_name='pattern_learnings')
    op.drop_index(op.f('ix_pattern_learnings_pattern_key'),     table_name='pattern_learnings')
    op.drop_index(op.f('ix_pattern_learnings_repository_id'),   table_name='pattern_learnings')
    op.drop_index('ix_pattern_learning_repo_test',    table_name='pattern_learnings')
    op.drop_index('ix_pattern_learning_repo_pattern', table_name='pattern_learnings')
    op.drop_table('pattern_learnings')
