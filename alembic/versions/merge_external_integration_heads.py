"""merge external integration heads

Revision ID: merge_external_integration_heads
Revises: 666839ec232c, add_created_by_to_releases, add_external_test_case_ref, add_external_test_scenario_mapping, k2l3m4n5o6p7
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_external_integration_heads'
down_revision: Union[str, Sequence[str], None] = ('666839ec232c', 'add_created_by_to_releases', 'add_external_test_case_ref', 'add_external_test_scenario_mapping', 'k2l3m4n5o6p7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
