"""update_github_installation_for_workspace_scoping

Revision ID: update_github_installation
Revises: 4752970181af
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'update_github_installation'
down_revision: Union[str, Sequence[str], None] = '4752970181af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspect_obj = sa.inspect(bind)
    
    # 1. github_installations
    github_installations_cols = {c['name']: c for c in inspect_obj.get_columns('github_installations')}
    github_installations_indexes = {idx['name'] for idx in inspect_obj.get_indexes('github_installations')}
    
    # Drop old unique constraint/index on organization_id if present
    if 'ix_github_installations_organization_id' in github_installations_indexes:
        op.drop_index('ix_github_installations_organization_id', table_name='github_installations')
        
    # Rename organization_id to workspace_id if present
    if 'organization_id' in github_installations_cols and 'workspace_id' not in github_installations_cols:
        op.alter_column('github_installations', 'organization_id',
                        new_column_name='workspace_id',
                        existing_type=sa.UUID(),
                        nullable=False)
                        
    # Rename account_login to github_account_login if present
    if 'account_login' in github_installations_cols and 'github_account_login' not in github_installations_cols:
        op.alter_column('github_installations', 'account_login',
                        new_column_name='github_account_login',
                        existing_type=sa.String(),
                        nullable=False)
                        
    # Add new columns if missing
    new_cols = [
        ('installation_id', sa.Column('installation_id', sa.BigInteger(), nullable=False, server_default='0')),
        ('github_account_login', sa.Column('github_account_login', sa.String(), nullable=False, server_default='')),
        ('github_account_id', sa.Column('github_account_id', sa.BigInteger(), nullable=True)),
        ('github_account_type', sa.Column('github_account_type', sa.String(), nullable=False, server_default='User')),
        ('permissions', sa.Column('permissions', postgresql.JSONB(), nullable=True)),
        ('repository_selection', sa.Column('repository_selection', sa.String(), nullable=False, server_default='all')),
        ('installed_by', sa.Column('installed_by', sa.String(), nullable=True)),
        ('installed_at', sa.Column('installed_at', sa.DateTime(), nullable=False, server_default=sa.func.now())),
        ('suspended_at', sa.Column('suspended_at', sa.DateTime(), nullable=True)),
        ('updated_at', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())),
    ]
    
    # Refresh column list after potential renames
    inspect_obj = sa.inspect(bind)
    github_installations_cols = {c['name']: c for c in inspect_obj.get_columns('github_installations')}
    
    for col_name, col_obj in new_cols:
        if col_name not in github_installations_cols:
            op.add_column('github_installations', col_obj)
            
    # Foreign key for workspace_id
    op.execute('ALTER TABLE github_installations DROP CONSTRAINT IF EXISTS github_installations_organization_id_fkey')
    op.execute('ALTER TABLE github_installations DROP CONSTRAINT IF EXISTS fk_github_installations_workspace_id')
    op.create_foreign_key('fk_github_installations_workspace_id', 'github_installations', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')
    
    # Indices/unique constraints
    if 'ix_github_installations_installation_id' not in github_installations_indexes:
        op.create_index('ix_github_installations_installation_id', 'github_installations', ['installation_id'])
    if 'ix_github_installations_workspace_id' not in github_installations_indexes:
        op.create_index('ix_github_installations_workspace_id', 'github_installations', ['workspace_id'])
        
    op.execute('ALTER TABLE github_installations DROP CONSTRAINT IF EXISTS uq_workspace_installation')
    op.create_unique_constraint('uq_workspace_installation', 'github_installations', ['workspace_id', 'installation_id'])
    
    # 2. repository_sync_jobs
    repo_sync_cols = {c['name']: c for c in inspect_obj.get_columns('repository_sync_jobs')}
    repo_sync_indexes = {idx['name'] for idx in inspect_obj.get_indexes('repository_sync_jobs')}
    
    if 'ix_repository_sync_jobs_organization_id' in repo_sync_indexes:
        op.drop_index('ix_repository_sync_jobs_organization_id', table_name='repository_sync_jobs')
        
    if 'organization_id' in repo_sync_cols and 'workspace_id' not in repo_sync_cols:
        op.alter_column('repository_sync_jobs', 'organization_id',
                        new_column_name='workspace_id',
                        existing_type=sa.UUID(),
                        nullable=False)
                        
    op.execute('ALTER TABLE repository_sync_jobs DROP CONSTRAINT IF EXISTS repository_sync_jobs_organization_id_fkey')
    op.execute('ALTER TABLE repository_sync_jobs DROP CONSTRAINT IF EXISTS fk_repository_sync_jobs_workspace_id')
    op.create_foreign_key('fk_repository_sync_jobs_workspace_id', 'repository_sync_jobs', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')
    
    if 'ix_repository_sync_jobs_workspace_id' not in repo_sync_indexes:
        op.create_index('ix_repository_sync_jobs_workspace_id', 'repository_sync_jobs', ['workspace_id'])
        
    # 3. pilot_repository_enrollments & pilot_report_snapshots
    target_table = 'pilot_workspace_profiles' if inspect_obj.has_table('pilot_workspace_profiles') else 'pilot_organization_profiles'
    
    op.execute('ALTER TABLE pilot_repository_enrollments DROP CONSTRAINT IF EXISTS pilot_repository_enrollments_pilot_profile_id_fkey')
    op.execute('ALTER TABLE pilot_repository_enrollments DROP CONSTRAINT IF EXISTS fk_pilot_repository_enrollments_pilot_profile_id')
    op.create_foreign_key('fk_pilot_repository_enrollments_pilot_profile_id', 'pilot_repository_enrollments', target_table, ['pilot_profile_id'], ['id'], ondelete='CASCADE')
    
    op.execute('ALTER TABLE pilot_report_snapshots DROP CONSTRAINT IF EXISTS pilot_report_snapshots_pilot_profile_id_fkey')
    op.execute('ALTER TABLE pilot_report_snapshots DROP CONSTRAINT IF EXISTS fk_pilot_report_snapshots_pilot_profile_id')
    op.create_foreign_key('fk_pilot_report_snapshots_pilot_profile_id', 'pilot_report_snapshots', target_table, ['pilot_profile_id'], ['id'], ondelete='CASCADE')



def downgrade() -> None:
    """Downgrade schema."""
    # Drop new foreign keys
    op.drop_constraint('fk_pilot_report_snapshots_pilot_profile_id', 'pilot_report_snapshots', type_='foreignkey')
    op.drop_constraint('fk_pilot_repository_enrollments_pilot_profile_id', 'pilot_repository_enrollments', type_='foreignkey')
    
    # Restore old foreign keys
    op.create_foreign_key('pilot_repository_enrollments_pilot_profile_id_fkey', 'pilot_repository_enrollments', 'pilot_organization_profiles', ['pilot_profile_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('pilot_report_snapshots_pilot_profile_id_fkey', 'pilot_report_snapshots', 'pilot_organization_profiles', ['pilot_profile_id'], ['id'], ondelete='CASCADE')
    
    # Revert repository_sync_jobs
    op.drop_index('ix_repository_sync_jobs_workspace_id', table_name='repository_sync_jobs')
    op.drop_constraint('fk_repository_sync_jobs_workspace_id', 'repository_sync_jobs', type_='foreignkey')
    op.alter_column('repository_sync_jobs', 'workspace_id',
                    new_column_name='organization_id',
                    existing_type=sa.UUID(),
                    nullable=False)
    op.create_foreign_key('repository_sync_jobs_organization_id_fkey', 'repository_sync_jobs', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_repository_sync_jobs_organization_id', 'repository_sync_jobs', ['organization_id'])
    
    # Drop new columns and constraints from github_installations
    op.drop_constraint('uq_workspace_installation', 'github_installations', type_='unique')
    op.drop_index('ix_github_installations_workspace_id', table_name='github_installations')
    op.drop_index('ix_github_installations_installation_id', table_name='github_installations')
    op.drop_column('github_installations', 'updated_at')
    op.drop_column('github_installations', 'suspended_at')
    op.drop_column('github_installations', 'installed_at')
    op.drop_column('github_installations', 'installed_by')
    op.drop_column('github_installations', 'repository_selection')
    op.drop_column('github_installations', 'permissions')
    op.drop_column('github_installations', 'github_account_type')
    op.drop_column('github_installations', 'github_account_id')
    op.drop_column('github_installations', 'github_account_login')
    op.drop_column('github_installations', 'installation_id')
    
    # Revert workspace_id to organization_id
    op.drop_constraint('fk_github_installations_workspace_id', 'github_installations', type_='foreignkey')
    op.alter_column('github_installations', 'workspace_id',
                    new_column_name='organization_id',
                    existing_type=sa.UUID(),
                    nullable=False)
    op.create_foreign_key('github_installations_organization_id_fkey', 'github_installations', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_github_installations_organization_id', 'github_installations', ['organization_id'], unique=True)
