"""
Add ci_cd_policy_exceptions table

Revision ID: e0f1g2h3i4j5
Revises: d4e5f6g7h8i9
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e0f1g2h3i4j5'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ci_cd_policy_exceptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id'), nullable=False, index=True),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='PENDING', index=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('exception_fields', postgresql.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('decision_reason', sa.Text(), nullable=True),
    )
    
    # Create composite index for organization + repository
    op.create_index('ix_ci_cd_policy_exceptions_org_repo', 'ci_cd_policy_exceptions', ['organization_id', 'repository_id'], unique=True)


def downgrade():
    op.drop_index('ix_ci_cd_policy_exceptions_org_repo', table_name='ci_cd_policy_exceptions')
    op.drop_table('ci_cd_policy_exceptions')
