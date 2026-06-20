"""add ci token audit events

Revision ID: add_ci_token_audit_events
Revises: 
Create Date: 2026-06-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_ci_token_audit_events'
down_revision = 'add_repository_ci_tokens'
branch_labels = None
depends_on = None


def upgrade():
    # Create ci_token_audit_events table
    op.create_table(
        'ci_token_audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('metadata_json', postgresql.JSON(), nullable=True),
    )
    
    # Create indexes
    op.create_index('idx_ci_token_audit_events_repository_id', 'ci_token_audit_events', ['repository_id'])
    op.create_index('idx_ci_token_audit_events_token_id', 'ci_token_audit_events', ['token_id'])
    op.create_index('idx_ci_token_audit_events_event_type', 'ci_token_audit_events', ['event_type'])
    op.create_index('idx_ci_token_audit_events_created_at', 'ci_token_audit_events', ['created_at'])
    
    # Add foreign key constraints
    op.create_foreign_key(
        'fk_ci_token_audit_events_repository_id',
        'ci_token_audit_events', 'repositories',
        ['repository_id'], ['id']
    )
    op.create_foreign_key(
        'fk_ci_token_audit_events_token_id',
        'ci_token_audit_events', 'repository_ci_tokens',
        ['token_id'], ['id']
    )


def downgrade():
    # Drop foreign key constraints
    op.drop_constraint('fk_ci_token_audit_events_token_id', 'ci_token_audit_events', type_='foreignkey')
    op.drop_constraint('fk_ci_token_audit_events_repository_id', 'ci_token_audit_events', type_='foreignkey')
    
    # Drop indexes
    op.drop_index('idx_ci_token_audit_events_created_at', 'ci_token_audit_events')
    op.drop_index('idx_ci_token_audit_events_event_type', 'ci_token_audit_events')
    op.drop_index('idx_ci_token_audit_events_token_id', 'ci_token_audit_events')
    op.drop_index('idx_ci_token_audit_events_repository_id', 'ci_token_audit_events')
    
    # Drop table
    op.drop_table('ci_token_audit_events')
