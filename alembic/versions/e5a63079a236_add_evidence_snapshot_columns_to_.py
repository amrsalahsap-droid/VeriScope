"""add_evidence_snapshot_columns_to_recommendation_runs

Revision ID: e5a63079a236
Revises: merge_external_integration_heads
Create Date: 2026-06-10 05:16:25.202928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a63079a236'
down_revision: Union[str, Sequence[str], None] = 'merge_external_integration_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
