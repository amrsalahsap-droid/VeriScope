"""add_dependency_type

Revision ID: b1cb35183ccb
Revises: 9da8a3ea539f
Create Date: 2026-05-22 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1cb35183ccb'
down_revision: Union[str, Sequence[str], None] = '9da8a3ea539f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'file_dependencies',
        sa.Column('dependency_type', sa.String(), nullable=False, server_default='import')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('file_dependencies', 'dependency_type')
