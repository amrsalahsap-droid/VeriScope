"""Add organization CI/CD policy defaults

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-06-18 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    # Create organization_ci_cd_policy_defaults table
    op.create_table(
        'organization_ci_cd_policy_defaults',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('default_preset', sa.String(50), nullable=False, server_default='STANDARD'),
        sa.Column('default_policy_json', sa.JSON(), nullable=True),
        sa.Column('auto_apply_to_new_repositories', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('allow_repository_override', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('require_override_reason', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    
    # Create index on organization_id
    op.create_index('ix_organization_ci_cd_policy_defaults_organization_id', 'organization_ci_cd_policy_defaults', ['organization_id'])


def downgrade():
    # Drop index
    op.drop_index('ix_organization_ci_cd_policy_defaults_organization_id', table_name='organization_ci_cd_policy_defaults')
    
    # Drop table
    op.drop_table('organization_ci_cd_policy_defaults')
