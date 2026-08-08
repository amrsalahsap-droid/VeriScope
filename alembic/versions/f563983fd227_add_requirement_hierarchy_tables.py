"""add_requirement_hierarchy_tables

Revision ID: f563983fd227
Revises: add_pr_package_snapshot_fields
Create Date: 2026-07-02 23:15:30.669726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f563983fd227'
down_revision: Union[str, Sequence[str], None] = 'add_pr_package_snapshot_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create requirement_packages
    op.create_table('requirement_packages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('pull_request_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=100), nullable=False),
        sa.Column('source_id', sa.String(length=200), nullable=True),
        sa.Column('package_version', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_requirement_packages_pull_request_id', 'requirement_packages', ['pull_request_id'], unique=False)
    op.create_index('ix_requirement_packages_repository_id', 'requirement_packages', ['repository_id'], unique=False)

    # 2. Create requirement_groups
    op.create_table('requirement_groups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('requirement_package_id', sa.UUID(), nullable=False),
        sa.Column('pull_request_id', sa.UUID(), nullable=False),
        sa.Column('group_number', sa.Integer(), nullable=False),
        sa.Column('group_type', sa.String(length=50), nullable=False),
        sa.Column('stable_group_key', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('business_flow', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=50), nullable=True),
        sa.Column('risk_level', sa.String(length=50), nullable=True),
        sa.Column('source_type', sa.String(length=100), nullable=True),
        sa.Column('source_id', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requirement_package_id'], ['requirement_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_requirement_groups_pull_request_id', 'requirement_groups', ['pull_request_id'], unique=False)
    op.create_index('ix_requirement_groups_requirement_package_id', 'requirement_groups', ['requirement_package_id'], unique=False)
    op.create_index('ix_requirement_groups_stable_group_key', 'requirement_groups', ['stable_group_key'], unique=False)

    # 3. Create testable_scenarios
    op.create_table('testable_scenarios',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('acceptance_criterion_id', sa.UUID(), nullable=False),
        sa.Column('scenario_key', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('preconditions', sa.Text(), nullable=True),
        sa.Column('steps', sa.Text(), nullable=True),
        sa.Column('expected_result', sa.Text(), nullable=True),
        sa.Column('scenario_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['acceptance_criterion_id'], ['acceptance_criteria.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_testable_scenarios_acceptance_criterion_id', 'testable_scenarios', ['acceptance_criterion_id'], unique=False)
    op.create_index('ix_testable_scenarios_scenario_key', 'testable_scenarios', ['scenario_key'], unique=False)

    # 4. Modify acceptance_criteria table
    op.add_column('acceptance_criteria', sa.Column('requirement_group_id', sa.UUID(), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('ac_number', sa.Integer(), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('stable_ac_key', sa.String(length=500), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('title', sa.String(length=500), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('raw_text', sa.Text(), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('normalized_text', sa.Text(), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('source_type', sa.String(length=100), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('source_id', sa.String(length=200), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('priority', sa.String(length=50), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('criticality', sa.String(length=50), nullable=True))
    op.add_column('acceptance_criteria', sa.Column('status', sa.String(length=50), nullable=False, server_default='NEEDS_REVIEW'))
    op.add_column('acceptance_criteria', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.create_index('ix_acceptance_criteria_requirement_group_id', 'acceptance_criteria', ['requirement_group_id'], unique=False)
    op.create_index('ix_acceptance_criteria_stable_ac_key', 'acceptance_criteria', ['stable_ac_key'], unique=False)
    op.create_foreign_key('fk_acceptance_criteria_requirement_group_id', 'acceptance_criteria', 'requirement_groups', ['requirement_group_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # 1. Drop foreign key and index changes from acceptance_criteria
    op.drop_constraint('fk_acceptance_criteria_requirement_group_id', 'acceptance_criteria', type_='foreignkey')
    op.drop_index('ix_acceptance_criteria_stable_ac_key', table_name='acceptance_criteria')
    op.drop_index('ix_acceptance_criteria_requirement_group_id', table_name='acceptance_criteria')
    op.drop_column('acceptance_criteria', 'version')
    op.drop_column('acceptance_criteria', 'status')
    op.drop_column('acceptance_criteria', 'criticality')
    op.drop_column('acceptance_criteria', 'priority')
    op.drop_column('acceptance_criteria', 'source_id')
    op.drop_column('acceptance_criteria', 'source_type')
    op.drop_column('acceptance_criteria', 'normalized_text')
    op.drop_column('acceptance_criteria', 'raw_text')
    op.drop_column('acceptance_criteria', 'description')
    op.drop_column('acceptance_criteria', 'title')
    op.drop_column('acceptance_criteria', 'stable_ac_key')
    op.drop_column('acceptance_criteria', 'ac_number')
    op.drop_column('acceptance_criteria', 'requirement_group_id')

    # 2. Drop testable_scenarios
    op.drop_index('ix_testable_scenarios_scenario_key', table_name='testable_scenarios')
    op.drop_index('ix_testable_scenarios_acceptance_criterion_id', table_name='testable_scenarios')
    op.drop_table('testable_scenarios')

    # 3. Drop requirement_groups
    op.drop_index('ix_requirement_groups_stable_group_key', table_name='requirement_groups')
    op.drop_index('ix_requirement_groups_requirement_package_id', table_name='requirement_groups')
    op.drop_index('ix_requirement_groups_pull_request_id', table_name='requirement_groups')
    op.drop_table('requirement_groups')

    # 4. Drop requirement_packages
    op.drop_index('ix_requirement_packages_repository_id', table_name='requirement_packages')
    op.drop_index('ix_requirement_packages_pull_request_id', table_name='requirement_packages')
    op.drop_table('requirement_packages')
