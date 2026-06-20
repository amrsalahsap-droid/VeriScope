"""add_workspace_governance_audit_event_columns

Revision ID: 8d36600b36af
Revises: refactor_governance_to_workspace
Create Date: 2026-06-19 04:06:35.965650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d36600b36af'
down_revision: Union[str, Sequence[str], None] = 'refactor_governance_to_workspace'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('workspace_governance_audit_events', sa.Column('target_user_id', sa.UUID(), nullable=True))
    op.add_column('workspace_governance_audit_events', sa.Column('repository_id', sa.UUID(), nullable=True))
    op.add_column('workspace_governance_audit_events', sa.Column('permission', sa.String(), nullable=True))
    op.add_column('workspace_governance_audit_events', sa.Column('role', sa.String(), nullable=True))
    op.add_column('workspace_governance_audit_events', sa.Column('decision', sa.String(), nullable=True))

    # Add foreign key constraints
    op.create_foreign_key('fk_workspace_gov_audit_target_user', 'workspace_governance_audit_events', 'users', ['target_user_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_workspace_gov_audit_repository', 'workspace_governance_audit_events', 'repositories', ['repository_id'], ['id'], ondelete='SET NULL')

    # Add indexes
    op.create_index('ix_workspace_governance_audit_events_target_user_id', 'workspace_governance_audit_events', ['target_user_id'])
    op.create_index('ix_workspace_governance_audit_events_repository_id', 'workspace_governance_audit_events', ['repository_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_workspace_governance_audit_events_repository_id', 'workspace_governance_audit_events')
    op.drop_index('ix_workspace_governance_audit_events_target_user_id', 'workspace_governance_audit_events')

    # Drop foreign key constraints
    op.drop_constraint('fk_workspace_gov_audit_repository', 'workspace_governance_audit_events', type_='foreignkey')
    op.drop_constraint('fk_workspace_gov_audit_target_user', 'workspace_governance_audit_events', type_='foreignkey')

    # Drop columns
    op.drop_column('workspace_governance_audit_events', 'decision')
    op.drop_column('workspace_governance_audit_events', 'role')
    op.drop_column('workspace_governance_audit_events', 'permission')
    op.drop_column('workspace_governance_audit_events', 'repository_id')
    op.drop_column('workspace_governance_audit_events', 'target_user_id')
