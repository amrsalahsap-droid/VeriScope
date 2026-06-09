"""Merge heads before architecture_nodes

Revision ID: ae9831957a5f
Revises: l2m3n4o5p6q7, 0e3092aff1ba
Create Date: 2026-06-01 22:49:41.039450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae9831957a5f'
down_revision: Union[str, Sequence[str], None] = ('l2m3n4o5p6q7', '0e3092aff1ba')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
