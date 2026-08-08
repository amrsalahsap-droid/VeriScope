"""add_separate_taxonomy_fields

Revision ID: 56c568c7ba28
Revises: a49090f0e07c
Create Date: 2026-07-11 03:02:39.368620

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '56c568c7ba28'
down_revision: Union[str, Sequence[str], None] = 'a49090f0e07c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('test_cases', sa.Column('test_nature', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('primary_test_category', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('suite_purpose', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('risk_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('test_cases', sa.Column('execution_layer', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('import_source', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('execution_method', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('framework', sa.String(), nullable=True))
    op.add_column('test_cases', sa.Column('external_ac_ref', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('test_cases', 'external_ac_ref')
    op.drop_column('test_cases', 'framework')
    op.drop_column('test_cases', 'execution_method')
    op.drop_column('test_cases', 'import_source')
    op.drop_column('test_cases', 'execution_layer')
    op.drop_column('test_cases', 'risk_tags')
    op.drop_column('test_cases', 'suite_purpose')
    op.drop_column('test_cases', 'primary_test_category')
    op.drop_column('test_cases', 'test_nature')
