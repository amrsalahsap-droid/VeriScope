"""add_phase3_3_risk_aware_release_decision_fields

Revision ID: 579331fd986d
Revises: 9bdd691b538b
Create Date: 2026-06-13 02:40:01.690809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '579331fd986d'
down_revision: Union[str, Sequence[str], None] = '9bdd691b538b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add JSON columns for risk-aware release decision recommendations
    op.add_column('release_decisions', sa.Column('decision_recommendations', sa.JSON(), nullable=True))
    op.add_column('release_decisions', sa.Column('decision_reasoning', sa.JSON(), nullable=True))
    op.add_column('release_decisions', sa.Column('required_before_release', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove JSON columns for risk-aware release decision recommendations
    op.drop_column('release_decisions', 'required_before_release')
    op.drop_column('release_decisions', 'decision_reasoning')
    op.drop_column('release_decisions', 'decision_recommendations')
