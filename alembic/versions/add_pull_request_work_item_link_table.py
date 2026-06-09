"""add_pull_request_work_item_link_table

Revision ID: add_pr_work_item_link
Revises: add_external_test_case
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_pr_work_item_link'
down_revision: Union[str, Sequence[str], None] = 'add_external_work_item'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pull_request_work_item_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pull_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pull_requests.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('external_work_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('external_work_items.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('unresolved_key', sa.String(), nullable=True, index=True),
        sa.Column('link_source', sa.String(), nullable=False, index=True),
        sa.Column('confidence', sa.Float(), nullable=False, default=0.5),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
    
    # Create unique constraint: pull_request_id + external_work_item_id (conditional)
    # PostgreSQL doesn't support partial unique constraints directly in CREATE TABLE
    # We'll create it separately with a condition
    op.execute("""
        CREATE UNIQUE INDEX uq_pr_work_item 
        ON pull_request_work_item_links (pull_request_id, external_work_item_id)
        WHERE external_work_item_id IS NOT NULL
    """)
    
    # Create index for pull_request_id
    op.create_index(
        'ix_pr_work_item_links_pr',
        'pull_request_work_item_links',
        ['pull_request_id']
    )
    
    # Create index for external_work_item_id
    op.create_index(
        'ix_pr_work_item_links_work_item',
        'pull_request_work_item_links',
        ['external_work_item_id']
    )
    
    # Create index for unresolved_key
    op.create_index(
        'ix_pr_work_item_links_unresolved',
        'pull_request_work_item_links',
        ['unresolved_key']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_pr_work_item_links_unresolved', table_name='pull_request_work_item_links')
    op.drop_index('ix_pr_work_item_links_work_item', table_name='pull_request_work_item_links')
    op.drop_index('ix_pr_work_item_links_pr', table_name='pull_request_work_item_links')
    op.drop_index('uq_pr_work_item', table_name='pull_request_work_item_links')
    op.drop_table('pull_request_work_item_links')
