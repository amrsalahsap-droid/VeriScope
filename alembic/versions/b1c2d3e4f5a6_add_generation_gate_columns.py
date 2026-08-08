"""add_generation_gate_columns

Adds is_draft, generation_mode, generation_blocked_reason to recommendation_runs.

Revision ID: b1c2d3e4f5a6
Revises: 88c5779ff440
Create Date: 2026-07-13 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '7a3d2e1c4b9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'recommendation_runs',
        sa.Column('is_draft', sa.Boolean(), nullable=False,
                  server_default=sa.text('false'))
    )
    op.add_column(
        'recommendation_runs',
        sa.Column('generation_mode', sa.String(), nullable=True)
    )
    op.add_column(
        'recommendation_runs',
        sa.Column('generation_blocked_reason', sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('recommendation_runs', 'generation_blocked_reason')
    op.drop_column('recommendation_runs', 'generation_mode')
    op.drop_column('recommendation_runs', 'is_draft')
