"""add_manual_execution_sync_events

Revision ID: ab3ae270c1dd
Revises: 7116885d3b25
Create Date: 2026-06-15 07:45:03.388121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ab3ae270c1dd'
down_revision: Union[str, Sequence[str], None] = '7116885d3b25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'manual_execution_sync_events',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('execution_id', sa.UUID(as_uuid=True), sa.ForeignKey('manual_test_executions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(), nullable=False, index=True),
        sa.Column('status', sa.String(), nullable=False, index=True),
        sa.Column('request_payload', postgresql.JSONB(), nullable=True),
        sa.Column('response_payload', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('external_run_id', sa.String(), nullable=True, index=True),
        sa.Column('external_execution_id', sa.String(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('manual_execution_sync_events')
