"""add provider cooldown

Revision ID: add_provider_cooldown
Revises: add_sync_queue_fields
Create Date: 2026-06-15 18:38:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_provider_cooldown'
down_revision = 'add_sync_queue_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create integration_provider_cooldowns table
    op.create_table(
        'integration_provider_cooldowns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('repository_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('cooldown_until', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_provider_cooldowns_repository_id', 'integration_provider_cooldowns', ['repository_id'])
    op.create_index('ix_provider_cooldowns_provider', 'integration_provider_cooldowns', ['provider'])
    op.create_index('ix_provider_cooldowns_cooldown_until', 'integration_provider_cooldowns', ['cooldown_until'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_provider_cooldowns_cooldown_until', table_name='integration_provider_cooldowns')
    op.drop_index('ix_provider_cooldowns_provider', table_name='integration_provider_cooldowns')
    op.drop_index('ix_provider_cooldowns_repository_id', table_name='integration_provider_cooldowns')
    
    # Drop table
    op.drop_table('integration_provider_cooldowns')
