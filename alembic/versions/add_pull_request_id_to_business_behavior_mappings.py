"""add pull_request_id to business_behavior_mappings

Revision ID: add_pull_request_id
Revises: f563983fd227
Create Date: 2026-07-03 06:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_pull_request_id'
down_revision: Union[str, Sequence[str], None] = 'f563983fd227'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('business_behavior_mappings', sa.Column('pull_request_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_business_behavior_mappings_pull_request_id'), 'business_behavior_mappings', ['pull_request_id'], unique=False)
    op.create_foreign_key(None, 'business_behavior_mappings', 'pull_requests', ['pull_request_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'business_behavior_mappings', type_='foreignkey')
    op.drop_index(op.f('ix_business_behavior_mappings_pull_request_id'), table_name='business_behavior_mappings')
    op.drop_column('business_behavior_mappings', 'pull_request_id')
