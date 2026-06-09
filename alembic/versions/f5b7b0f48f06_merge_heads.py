"""merge heads

Revision ID: f5b7b0f48f06
Revises: a3c7e9f12b04, b2c4d6e8f0a1
Create Date: 2026-05-31 01:55:27.559947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5b7b0f48f06'
down_revision: Union[str, Sequence[str], None] = ('a3c7e9f12b04', 'b2c4d6e8f0a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
