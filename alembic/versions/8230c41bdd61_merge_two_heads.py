"""merge two heads

Revision ID: 8230c41bdd61
Revises: 6ad1003e1693, e4f6a8b0c1d2
Create Date: 2026-05-30 00:33:59.513828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8230c41bdd61'
down_revision: Union[str, Sequence[str], None] = ('6ad1003e1693', 'e4f6a8b0c1d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
