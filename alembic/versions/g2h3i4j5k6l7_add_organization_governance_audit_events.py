"""
Add organization_governance_audit_events table

Revision ID: g2h3i4j5k6l7
Revises: f1g2h3i4j5k6
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'g2h3i4j5k6l7'
down_revision = 'f1g2h3i4j5k6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'organization_governance_audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False, index=True),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('requested_count', sa.Integer(), nullable=True),
        sa.Column('succeeded_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('skipped_count', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('audit_metadata', postgresql.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
    )


def downgrade():
    op.drop_table('organization_governance_audit_events')
