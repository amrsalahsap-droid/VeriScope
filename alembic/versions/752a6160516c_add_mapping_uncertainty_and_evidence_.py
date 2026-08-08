"""add_mapping_uncertainty_and_evidence_path_to_recommended_tests

Revision ID: 752a6160516c
Revises: b1c2d3e4f5a6
Create Date: 2026-07-17 03:16:00.335870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '752a6160516c'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('recommended_tests', sa.Column('mapping_uncertainty', sa.String(), nullable=True))
    op.add_column('recommended_tests', sa.Column('evidence_path', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('recommended_tests', 'evidence_path')
    op.drop_column('recommended_tests', 'mapping_uncertainty')
