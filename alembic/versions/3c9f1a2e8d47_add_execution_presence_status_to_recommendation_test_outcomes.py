"""add_execution_presence_status_to_recommendation_test_outcomes

Revision ID: 3c9f1a2e8d47
Revises: 1fa172047bbf
Create Date: 2026-05-24 04:34:00.000000

Adds `execution_presence_status` column to `recommendation_test_outcomes`.
Values: EXECUTED, PRESENT_SKIPPED, ABSENT, UNKNOWN (nullable String).

This decouples analytical presence state from the MVP boolean flags
(actually_executed, manually_removed, manually_added) for richer downstream
querying without changing any existing flag semantics.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9f1a2e8d47'
down_revision: Union[str, Sequence[str], None] = '1fa172047bbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'recommendation_test_outcomes',
        sa.Column('execution_presence_status', sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('recommendation_test_outcomes', 'execution_presence_status')
