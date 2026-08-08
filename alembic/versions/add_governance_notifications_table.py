"""Add governance_notifications table

Revision ID: add_governance_notifications
Revises: refactor_governance_to_workspace
Create Date: 2026-06-20

This migration creates the governance_notifications table for workspace governance notifications.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_governance_notifications'
down_revision = 'refactor_governance_to_workspace'
branch_labels = None
depends_on = None


def upgrade():
    """Create governance_notifications table."""
    op.create_table(
        'governance_notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recipient_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notification_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('source_entity_type', sa.String(100), nullable=True),
        sa.Column('source_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(), nullable=True),
        sa.Column('delivery_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_governance_notifications_workspace_id', 'governance_notifications', ['workspace_id'])
    op.create_index('ix_governance_notifications_repository_id', 'governance_notifications', ['repository_id'])
    op.create_index('ix_governance_notifications_recipient_user_id', 'governance_notifications', ['recipient_user_id'])
    op.create_index('ix_governance_notifications_notification_type', 'governance_notifications', ['notification_type'])
    op.create_index('ix_governance_notifications_severity', 'governance_notifications', ['severity'])
    op.create_index('ix_governance_notifications_source_entity_type', 'governance_notifications', ['source_entity_type'])
    op.create_index('ix_governance_notifications_source_entity_id', 'governance_notifications', ['source_entity_id'])
    op.create_index('ix_governance_notifications_status', 'governance_notifications', ['status'])
    op.create_index('ix_governance_notifications_created_at', 'governance_notifications', ['created_at'])


def downgrade():
    """Drop governance_notifications table."""
    op.drop_index('ix_governance_notifications_created_at', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_status', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_source_entity_id', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_source_entity_type', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_severity', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_notification_type', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_recipient_user_id', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_repository_id', table_name='governance_notifications')
    op.drop_index('ix_governance_notifications_workspace_id', table_name='governance_notifications')
    op.drop_table('governance_notifications')
