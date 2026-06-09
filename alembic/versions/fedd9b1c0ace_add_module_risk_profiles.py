"""add_module_risk_profiles

Revision ID: fedd9b1c0ace
Revises: 8230c41bdd61
Create Date: 2026-05-30 00:41:57.915443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fedd9b1c0ace'
down_revision: Union[str, Sequence[str], None] = '8230c41bdd61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'module_risk_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('module_path', sa.String(), nullable=False),
        sa.Column('change_frequency', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_frequency', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escaped_defects', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rollback_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recommendations_presented', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recommendations_accepted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('score_components', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('scoring_formula_version', sa.String(), nullable=False, server_default='module_risk.v1'),
        sa.Column('last_scored_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'module_path', name='uq_repo_module_path')
    )
    op.create_index(op.f('ix_module_risk_profiles_repository_id'), 'module_risk_profiles', ['repository_id'], unique=False)
    op.create_index(op.f('ix_module_risk_profiles_module_path'), 'module_risk_profiles', ['module_path'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_module_risk_profiles_module_path'), table_name='module_risk_profiles')
    op.drop_index(op.f('ix_module_risk_profiles_repository_id'), table_name='module_risk_profiles')
    op.drop_table('module_risk_profiles')

