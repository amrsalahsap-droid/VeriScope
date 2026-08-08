"""merge governance notifications with existing head

Revision ID: cda47bebedda
Revises: add_governance_notifications, fcaeb34e1193
Create Date: 2026-06-20 07:42:03.605434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cda47bebedda'
down_revision: Union[str, Sequence[str], None] = ('add_governance_notifications', 'fcaeb34e1193')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
