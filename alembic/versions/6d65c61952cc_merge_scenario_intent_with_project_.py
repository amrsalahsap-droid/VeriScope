"""merge_scenario_intent_with_project_context

Revision ID: 6d65c61952cc
Revises: 9ac3ae02d250, a1b2c3d4e5f7
Create Date: 2026-06-01 05:21:02.854829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d65c61952cc'
down_revision: Union[str, Sequence[str], None] = ('9ac3ae02d250', 'a1b2c3d4e5f7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
