"""merge_governance_access_review_heads

Revision ID: 262c03bf59f8
Revises: add_governance_access_review_tables, bc7099e56802
Create Date: 2026-06-20 05:29:57.377153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '262c03bf59f8'
down_revision: Union[str, Sequence[str], None] = ('add_governance_access_review_tables', 'bc7099e56802')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
