"""merge_ci_cd_policies_and_alerts

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f9, c79f64103920
Create Date: 2026-06-18 05:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f9', 'c79f64103920')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Merge migration - no changes needed
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Merge migration - no changes needed
    pass
