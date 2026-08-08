"""add_governance_remediation_actions

Revision ID: fcaeb34e1193
Revises: 262c03bf59f8
Create Date: 2026-06-20 05:30:04.186702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcaeb34e1193'
down_revision: Union[str, Sequence[str], None] = '262c03bf59f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create governance_remediation_actions table
    op.create_table(
        'governance_remediation_actions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('requested_by', sa.UUID(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('confirmed_by', sa.UUID(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('target_user_id', sa.UUID(), nullable=True),
        sa.Column('target_role', sa.String(length=50), nullable=True),
        sa.Column('target_assignment_id', sa.UUID(), nullable=True),
        sa.Column('target_exception_id', sa.UUID(), nullable=True),
        sa.Column('target_policy_id', sa.UUID(), nullable=True),
        sa.Column('impact_preview_json', sa.JSON(), nullable=False),
        sa.Column('execution_result_json', sa.JSON(), nullable=True),
        sa.Column('failure_reason', sa.String(length=500), nullable=True),
        sa.Column('requires_confirmation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('confirmation_message', sa.String(length=1000), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_remediation_actions_repository_id'), 'governance_remediation_actions', ['repository_id'], unique=False)
    op.create_index(op.f('ix_governance_remediation_actions_workspace_id'), 'governance_remediation_actions', ['workspace_id'], unique=False)

    # Add remediation fields to governance_access_review_items
    op.add_column('governance_access_review_items', sa.Column('remediation_action_id', sa.UUID(), nullable=True))
    op.add_column('governance_access_review_items', sa.Column('remediation_status', sa.String(length=50), nullable=True))
    op.create_foreign_key(
        'fk_governance_access_review_items_remediation_action_id',
        'governance_access_review_items',
        'governance_remediation_actions',
        ['remediation_action_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(op.f('ix_governance_access_review_items_remediation_action_id'), 'governance_access_review_items', ['remediation_action_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_governance_access_review_items_remediation_action_id'), table_name='governance_access_review_items')
    op.drop_constraint('fk_governance_access_review_items_remediation_action_id', 'governance_access_review_items', type_='foreignkey')
    op.drop_column('governance_access_review_items', 'remediation_status')
    op.drop_column('governance_access_review_items', 'remediation_action_id')

    op.drop_index(op.f('ix_governance_remediation_actions_workspace_id'), table_name='governance_remediation_actions')
    op.drop_index(op.f('ix_governance_remediation_actions_repository_id'), table_name='governance_remediation_actions')
    op.drop_table('governance_remediation_actions')

