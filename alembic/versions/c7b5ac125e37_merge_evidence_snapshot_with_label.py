"""merge_evidence_snapshot_with_label

Revision ID: c7b5ac125e37
Revises: add_label_to_acceptance_criteria, e5a63079a236
Create Date: 2026-06-10 06:03:31.092224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7b5ac125e37'
down_revision: Union[str, Sequence[str], None] = ('add_label_to_acceptance_criteria', 'e5a63079a236')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
