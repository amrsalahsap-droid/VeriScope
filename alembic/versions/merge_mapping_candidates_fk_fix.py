"""merge_mapping_candidates_fk_fix

Revision ID: merge_mapping_candidates_fk_fix
Revises: 752a6160516c, fix_mapping_candidates_semantic_fk
Create Date: 2026-07-25 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_mapping_fk_fix'
down_revision: Union[str, Sequence[str], None] = ('752a6160516c', 'm1n2o3p4q5r6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
