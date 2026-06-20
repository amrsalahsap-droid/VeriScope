"""Refactor governance models from organization to workspace

Revision ID: refactor_governance_to_workspace
Revises: 
Create Date: 2026-06-19

This migration refactors the governance architecture to use Workspace-based
multi-tenancy instead of the deprecated Organization model.

Changes:
- Renames governance tables to use workspace-based naming
- Migrates organization_id to workspace_id
- Updates ScopeType.ORGANIZATION to ScopeType.WORKSPACE
- Creates new workspace-scoped tables
- Drops old organization-scoped tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import uuid

# revision identifiers, used by Alembic.
revision = 'refactor_governance_to_workspace'
down_revision = ('b1c2d3e4f5g7', 'g2h3i4j5k6l7')  # Merge these two heads
branch_labels = None
depends_on = None


def upgrade():
    """Migrate governance tables from organization to workspace."""
    
    # Step 1: Create new workspace-based tables
    # ========================================
    
    # Create workspace_governance_audit_event table
    op.create_table(
        'workspace_governance_audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('operation_id', sa.UUID(), nullable=True),
        sa.Column('requested_count', sa.Integer(), nullable=True),
        sa.Column('succeeded_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('skipped_count', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('audit_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workspace_governance_audit_events_workspace_id', 'workspace_governance_audit_events', ['workspace_id'])
    op.create_index('ix_workspace_governance_audit_events_actor_id', 'workspace_governance_audit_events', ['actor_id'])
    op.create_index('ix_workspace_governance_audit_events_event_type', 'workspace_governance_audit_events', ['event_type'])
    
    # Create workspace_ci_cd_policy_default table
    op.create_table(
        'workspace_ci_cd_policy_defaults',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False, unique=True),
        sa.Column('preset_name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workspace_ci_cd_policy_defaults_workspace_id', 'workspace_ci_cd_policy_defaults', ['workspace_id'])
    
    # Step 2: Migrate data from old tables to new tables
    # =================================================
    
    # Migrate organization_governance_audit_events -> workspace_governance_audit_events
    op.execute("""
        INSERT INTO workspace_governance_audit_events (
            id, workspace_id, actor_id, event_type, operation_id,
            requested_count, succeeded_count, failed_count, skipped_count,
            reason, audit_metadata, created_at
        )
        SELECT 
            id, organization_id as workspace_id, actor_id, event_type, operation_id,
            requested_count, succeeded_count, failed_count, skipped_count,
            reason, audit_metadata, created_at
        FROM organization_governance_audit_events
    """)
    
    # Migrate organization_ci_cd_policy_defaults -> workspace_ci_cd_policy_defaults
    op.execute("""
        INSERT INTO workspace_ci_cd_policy_defaults (
            id, workspace_id, preset_name, created_at, updated_at
        )
        SELECT 
            id, organization_id as workspace_id, preset_name, created_at, updated_at
        FROM organization_ci_cd_policy_defaults
    """)
    
    # Update governance_role_assignments table
    # Add workspace_id column if it doesn't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('governance_role_assignments')]
    
    if 'workspace_id' not in columns:
        op.add_column('governance_role_assignments', sa.Column('workspace_id', sa.UUID(), nullable=True))
        
        # Migrate organization_id to workspace_id
        op.execute("""
            UPDATE governance_role_assignments
            SET workspace_id = organization_id
            WHERE organization_id IS NOT NULL
        """)
        
        # Make workspace_id not nullable after migration
        op.alter_column('governance_role_assignments', 'workspace_id', nullable=False)
        
        # Drop organization_id column
        op.drop_column('governance_role_assignments', 'organization_id')
    
    # Update scope_type values from ORGANIZATION to WORKSPACE
    op.execute("""
        UPDATE governance_role_assignments
        SET scope_type = 'WORKSPACE'
        WHERE scope_type = 'ORGANIZATION'
    """)
    
    # Update governance_notifications table
    columns = [col['name'] for col in inspector.get_columns('governance_notifications')]
    
    if 'workspace_id' not in columns:
        op.add_column('governance_notifications', sa.Column('workspace_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE governance_notifications
            SET workspace_id = organization_id
            WHERE organization_id IS NOT NULL
        """)
        
        op.alter_column('governance_notifications', 'workspace_id', nullable=False)
        op.drop_column('governance_notifications', 'organization_id')
    
    # Update governance_notification_preferences table
    columns = [col['name'] for col in inspector.get_columns('governance_notification_preferences')]
    
    if 'workspace_id' not in columns:
        op.add_column('governance_notification_preferences', sa.Column('workspace_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE governance_notification_preferences
            SET workspace_id = organization_id
            WHERE organization_id IS NOT NULL
        """)
        
        op.alter_column('governance_notification_preferences', 'workspace_id', nullable=False)
        op.drop_column('governance_notification_preferences', 'organization_id')
    
    # Update ci_cd_policy_exceptions table
    columns = [col['name'] for col in inspector.get_columns('ci_cd_policy_exceptions')]
    
    if 'workspace_id' not in columns:
        op.add_column('ci_cd_policy_exceptions', sa.Column('workspace_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE ci_cd_policy_exceptions
            SET workspace_id = organization_id
            WHERE organization_id IS NOT NULL
        """)
        
        op.alter_column('ci_cd_policy_exceptions', 'workspace_id', nullable=False)
        op.drop_column('ci_cd_policy_exceptions', 'organization_id')
    
    # Update ci_cd_governance_review_snapshots table
    columns = [col['name'] for col in inspector.get_columns('ci_cd_governance_review_snapshots')]
    
    if 'workspace_id' not in columns:
        op.add_column('ci_cd_governance_review_snapshots', sa.Column('workspace_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE ci_cd_governance_review_snapshots
            SET workspace_id = organization_id
            WHERE organization_id IS NOT NULL
        """)
        
        op.alter_column('ci_cd_governance_review_snapshots', 'workspace_id', nullable=False)
        op.drop_column('ci_cd_governance_review_snapshots', 'organization_id')
    
    # Step 3: Drop old organization-based tables
    # =========================================
    
    op.drop_table('organization_governance_audit_events')
    op.drop_table('organization_ci_cd_policy_defaults')


def downgrade():
    """Revert governance tables from workspace back to organization."""
    
    # Step 1: Recreate old organization-based tables
    # =============================================
    
    op.create_table(
        'organization_governance_audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('operation_id', sa.UUID(), nullable=True),
        sa.Column('requested_count', sa.Integer(), nullable=True),
        sa.Column('succeeded_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('skipped_count', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('audit_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'organization_ci_cd_policy_defaults',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False, unique=True),
        sa.Column('preset_name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Step 2: Migrate data back from new tables to old tables
    # ======================================================
    
    op.execute("""
        INSERT INTO organization_governance_audit_events (
            id, organization_id, actor_id, event_type, operation_id,
            requested_count, succeeded_count, failed_count, skipped_count,
            reason, audit_metadata, created_at
        )
        SELECT 
            id, workspace_id as organization_id, actor_id, event_type, operation_id,
            requested_count, succeeded_count, failed_count, skipped_count,
            reason, audit_metadata, created_at
        FROM workspace_governance_audit_events
    """)
    
    op.execute("""
        INSERT INTO organization_ci_cd_policy_defaults (
            id, organization_id, preset_name, created_at, updated_at
        )
        SELECT 
            id, workspace_id as organization_id, preset_name, created_at, updated_at
        FROM workspace_ci_cd_policy_defaults
    """)
    
    # Step 3: Revert workspace_id columns back to organization_id
    # ============================================================
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Revert governance_role_assignments
    columns = [col['name'] for col in inspector.get_columns('governance_role_assignments')]
    if 'organization_id' not in columns:
        op.add_column('governance_role_assignments', sa.Column('organization_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE governance_role_assignments
            SET organization_id = workspace_id
            WHERE workspace_id IS NOT NULL
        """)
        
        op.alter_column('governance_role_assignments', 'organization_id', nullable=False)
        op.drop_column('governance_role_assignments', 'workspace_id')
    
    # Revert scope_type values
    op.execute("""
        UPDATE governance_role_assignments
        SET scope_type = 'ORGANIZATION'
        WHERE scope_type = 'WORKSPACE'
    """)
    
    # Revert governance_notifications
    columns = [col['name'] for col in inspector.get_columns('governance_notifications')]
    if 'organization_id' not in columns:
        op.add_column('governance_notifications', sa.Column('organization_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE governance_notifications
            SET organization_id = workspace_id
            WHERE workspace_id IS NOT NULL
        """)
        
        op.alter_column('governance_notifications', 'organization_id', nullable=False)
        op.drop_column('governance_notifications', 'workspace_id')
    
    # Revert governance_notification_preferences
    columns = [col['name'] for col in inspector.get_columns('governance_notification_preferences')]
    if 'organization_id' not in columns:
        op.add_column('governance_notification_preferences', sa.Column('organization_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE governance_notification_preferences
            SET organization_id = workspace_id
            WHERE workspace_id IS NOT NULL
        """)
        
        op.alter_column('governance_notification_preferences', 'organization_id', nullable=False)
        op.drop_column('governance_notification_preferences', 'workspace_id')
    
    # Revert ci_cd_policy_exceptions
    columns = [col['name'] for col in inspector.get_columns('ci_cd_policy_exceptions')]
    if 'organization_id' not in columns:
        op.add_column('ci_cd_policy_exceptions', sa.Column('organization_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE ci_cd_policy_exceptions
            SET organization_id = workspace_id
            WHERE workspace_id IS NOT NULL
        """)
        
        op.alter_column('ci_cd_policy_exceptions', 'organization_id', nullable=False)
        op.drop_column('ci_cd_policy_exceptions', 'workspace_id')
    
    # Revert ci_cd_governance_review_snapshots
    columns = [col['name'] for col in inspector.get_columns('ci_cd_governance_review_snapshots')]
    if 'organization_id' not in columns:
        op.add_column('ci_cd_governance_review_snapshots', sa.Column('organization_id', sa.UUID(), nullable=True))
        
        op.execute("""
            UPDATE ci_cd_governance_review_snapshots
            SET organization_id = workspace_id
            WHERE workspace_id IS NOT NULL
        """)
        
        op.alter_column('ci_cd_governance_review_snapshots', 'organization_id', nullable=False)
        op.drop_column('ci_cd_governance_review_snapshots', 'workspace_id')
    
    # Step 4: Drop new workspace-based tables
    # =======================================
    
    op.drop_table('workspace_governance_audit_events')
    op.drop_table('workspace_ci_cd_policy_defaults')
