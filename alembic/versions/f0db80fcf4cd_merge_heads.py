"""merge heads

Revision ID: f0db80fcf4cd
Revises: 65faaba5360d, update_github_installation
Create Date: 2026-05-28 03:45:00.171311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0db80fcf4cd'
down_revision: Union[str, Sequence[str], None] = ('65faaba5360d', 'update_github_installation')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
