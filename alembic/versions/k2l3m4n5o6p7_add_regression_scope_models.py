"""add_regression_scope_models

Revision ID: k2l3m4n5o6p7
Revises: j0k3l4m5n6o7
Create Date: 2026-06-03 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'k2l3m4n5o6p7'
down_revision: Union[str, Sequence[str], None] = 'j0k3l4m5n6o7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create ENUM types
    release_type_enum = postgresql.ENUM(
        'MAJOR', 'MINOR', 'PATCH', 'HOTFIX', 'CUSTOM',
        name='release_type_enum',
        create_type=True
    )
    release_type_enum.create(op.get_bind())
    
    release_status_enum = postgresql.ENUM(
        'PLANNED', 'IN_PROGRESS', 'READY_FOR_SIGNOFF', 'RELEASED', 'ROLLED_BACK', 'CANCELLED',
        name='release_status_enum',
        create_type=True
    )
    release_status_enum.create(op.get_bind())
    
    suite_type_enum = postgresql.ENUM(
        'PR_REGRESSION', 'RELEASE_REGRESSION', 'SMOKE', 'FULL', 'HOTFIX',
        name='suite_type_enum',
        create_type=True
    )
    suite_type_enum.create(op.get_bind())
    
    suite_status_enum = postgresql.ENUM(
        'DRAFT', 'REVIEWED', 'APPROVED', 'EXECUTED', 'BLOCKED', 'ARCHIVED',
        name='suite_status_enum',
        create_type=True
    )
    suite_status_enum.create(op.get_bind())
    
    scope_item_type_enum = postgresql.ENUM(
        'AUTOMATED_TEST', 'MANUAL_TEST', 'SUGGESTED_SCENARIO', 'COVERAGE_GAP',
        name='scope_item_type_enum',
        create_type=True
    )
    scope_item_type_enum.create(op.get_bind())
    
    scope_tier_enum = postgresql.ENUM(
        'MUST_RUN', 'SHOULD_RUN', 'OPTIONAL',
        name='scope_tier_enum',
        create_type=True
    )
    scope_tier_enum.create(op.get_bind())
    
    scope_priority_enum = postgresql.ENUM(
        'CRITICAL', 'HIGH', 'MEDIUM', 'LOW',
        name='scope_priority_enum',
        create_type=True
    )
    scope_priority_enum.create(op.get_bind())
    
    execution_status_enum = postgresql.ENUM(
        'NOT_RUN', 'PASSED', 'FAILED', 'SKIPPED', 'BLOCKED', 'MANUAL_PENDING', 'UNKNOWN',
        name='execution_status_enum',
        create_type=True
    )
    execution_status_enum.create(op.get_bind())
    
    override_type_enum = postgresql.ENUM(
        'ADDED', 'REMOVED', 'TIER_CHANGED', 'PRIORITY_CHANGED', 'MARKED_REQUIRED', 'MARKED_OPTIONAL',
        name='override_type_enum',
        create_type=True
    )
    override_type_enum.create(op.get_bind())
    
    test_priority_enum = postgresql.ENUM(
        'CRITICAL', 'HIGH', 'MEDIUM', 'LOW',
        name='test_priority_enum',
        create_type=True
    )
    test_priority_enum.create(op.get_bind())
    
    test_type_enum = postgresql.ENUM(
        'UNIT', 'API', 'INTEGRATION', 'E2E', 'UI', 'SECURITY', 'PERFORMANCE', 'MANUAL', 'SMOKE',
        name='test_type_enum',
        create_type=True
    )
    test_type_enum.create(op.get_bind())
    
    business_criticality_enum = postgresql.ENUM(
        'MISSION_CRITICAL', 'IMPORTANT', 'SUPPORTING',
        name='business_criticality_enum',
        create_type=True
    )
    business_criticality_enum.create(op.get_bind())
    
    automation_status_enum = postgresql.ENUM(
        'AUTOMATED', 'MANUAL', 'PARTIALLY_AUTOMATED', 'UNKNOWN',
        name='automation_status_enum',
        create_type=True
    )
    automation_status_enum.create(op.get_bind())
    
    # Create releases table
    op.create_table('releases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('release_type', release_type_enum, nullable=False),
        sa.Column('status', release_status_enum, nullable=False),
        sa.Column('planned_date', sa.DateTime(), nullable=True),
        sa.Column('actual_date', sa.DateTime(), nullable=True),
        sa.Column('release_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'version', name='uq_releases_repo_version')
    )
    op.create_index('ix_releases_repository_id', 'releases', ['repository_id'], unique=False)
    op.create_index('ix_releases_version', 'releases', ['version'], unique=False)
    op.create_index('ix_releases_repo_status', 'releases', ['repository_id', 'status'], unique=False)
    
    # Create regression_suites table
    op.create_table('regression_suites',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('release_id', sa.UUID(), nullable=True),
        sa.Column('pull_request_id', sa.UUID(), nullable=True),
        sa.Column('recommendation_run_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('suite_type', suite_type_enum, nullable=False),
        sa.Column('status', suite_status_enum, nullable=False),
        sa.Column('confidence_level', sa.String(), nullable=True),
        sa.Column('scope_score', sa.Float(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['pull_request_id'], ['pull_requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recommendation_run_id'], ['recommendation_runs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_regression_suites_repository_id', 'regression_suites', ['repository_id'], unique=False)
    op.create_index('ix_regression_suites_release_id', 'regression_suites', ['release_id'], unique=False)
    op.create_index('ix_regression_suites_pull_request_id', 'regression_suites', ['pull_request_id'], unique=False)
    op.create_index('ix_regression_suites_recommendation_run_id', 'regression_suites', ['recommendation_run_id'], unique=False)
    op.create_index('ix_regression_suites_repo_status', 'regression_suites', ['repository_id', 'status'], unique=False)
    
    # Create regression_scope_items table
    op.create_table('regression_scope_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('regression_suite_id', sa.UUID(), nullable=False),
        sa.Column('test_case_id', sa.UUID(), nullable=True),
        sa.Column('external_test_case_id', sa.UUID(), nullable=True),
        sa.Column('suggested_scenario_id', sa.UUID(), nullable=True),
        sa.Column('behavior_id', sa.UUID(), nullable=True),
        sa.Column('journey_id', sa.UUID(), nullable=True),
        sa.Column('acceptance_criterion_id', sa.UUID(), nullable=True),
        sa.Column('item_type', scope_item_type_enum, nullable=False),
        sa.Column('tier', scope_tier_enum, nullable=False),
        sa.Column('priority', scope_priority_enum, nullable=False),
        sa.Column('selection_reason', sa.Text(), nullable=True),
        sa.Column('evidence_summary', postgresql.JSONB(), nullable=True),
        sa.Column('execution_status', execution_status_enum, nullable=False),
        sa.Column('coverage_status', sa.String(), nullable=True),
        sa.Column('is_excluded', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['regression_suite_id'], ['regression_suites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['external_test_case_id'], ['external_test_cases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['suggested_scenario_id'], ['suggested_test_scenarios.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['behavior_id'], ['behaviors.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['journey_id'], ['journeys.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['acceptance_criterion_id'], ['acceptance_criteria.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_regression_scope_items_regression_suite_id', 'regression_scope_items', ['regression_suite_id'], unique=False)
    op.create_index('ix_regression_scope_items_test_case_id', 'regression_scope_items', ['test_case_id'], unique=False)
    op.create_index('ix_regression_scope_items_external_test_case_id', 'regression_scope_items', ['external_test_case_id'], unique=False)
    op.create_index('ix_regression_scope_items_suggested_scenario_id', 'regression_scope_items', ['suggested_scenario_id'], unique=False)
    op.create_index('ix_regression_scope_items_behavior_id', 'regression_scope_items', ['behavior_id'], unique=False)
    op.create_index('ix_regression_scope_items_journey_id', 'regression_scope_items', ['journey_id'], unique=False)
    op.create_index('ix_regression_scope_items_acceptance_criterion_id', 'regression_scope_items', ['acceptance_criterion_id'], unique=False)
    op.create_index('ix_regression_scope_items_suite_tier', 'regression_scope_items', ['regression_suite_id', 'tier'], unique=False)
    op.create_index('ix_regression_scope_items_suite_type', 'regression_scope_items', ['regression_suite_id', 'item_type'], unique=False)
    
    # Create scope_overrides table
    op.create_table('scope_overrides',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('regression_scope_item_id', sa.UUID(), nullable=False),
        sa.Column('regression_suite_id', sa.UUID(), nullable=False),
        sa.Column('override_type', override_type_enum, nullable=False),
        sa.Column('original_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('overridden_by', sa.String(), nullable=True),
        sa.Column('overridden_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['regression_scope_item_id'], ['regression_scope_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['regression_suite_id'], ['regression_suites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scope_overrides_regression_suite_id', 'scope_overrides', ['regression_suite_id'], unique=False)
    op.create_index('ix_scope_overrides_regression_scope_item_id', 'scope_overrides', ['regression_scope_item_id'], unique=False)
    
    # Create test_assets table
    op.create_table('test_assets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('test_case_id', sa.UUID(), nullable=True),
        sa.Column('external_test_case_id', sa.UUID(), nullable=True),
        sa.Column('stable_identity', sa.String(), nullable=True),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('priority', test_priority_enum, nullable=False),
        sa.Column('test_type', test_type_enum, nullable=False),
        sa.Column('business_criticality', business_criticality_enum, nullable=False),
        sa.Column('automation_status', automation_status_enum, nullable=False),
        sa.Column('behavior_ids', postgresql.JSONB(), nullable=True),
        sa.Column('journey_ids', postgresql.JSONB(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['external_test_case_id'], ['external_test_cases.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_test_assets_repository_id', 'test_assets', ['repository_id'], unique=False)
    op.create_index('ix_test_assets_test_case_id', 'test_assets', ['test_case_id'], unique=False)
    op.create_index('ix_test_assets_external_test_case_id', 'test_assets', ['external_test_case_id'], unique=False)
    op.create_index('ix_test_assets_stable_identity', 'test_assets', ['stable_identity'], unique=False)
    op.create_index('ix_test_assets_repo_priority', 'test_assets', ['repository_id', 'priority'], unique=False)
    op.create_index('ix_test_assets_repo_type', 'test_assets', ['repository_id', 'test_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables
    op.drop_index('ix_test_assets_repo_type', table_name='test_assets')
    op.drop_index('ix_test_assets_repo_priority', table_name='test_assets')
    op.drop_index('ix_test_assets_stable_identity', table_name='test_assets')
    op.drop_index('ix_test_assets_external_test_case_id', table_name='test_assets')
    op.drop_index('ix_test_assets_test_case_id', table_name='test_assets')
    op.drop_index('ix_test_assets_repository_id', table_name='test_assets')
    op.drop_table('test_assets')
    
    op.drop_index('ix_scope_overrides_regression_scope_item_id', table_name='scope_overrides')
    op.drop_index('ix_scope_overrides_regression_suite_id', table_name='scope_overrides')
    op.drop_table('scope_overrides')
    
    op.drop_index('ix_regression_scope_items_suite_type', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_suite_tier', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_acceptance_criterion_id', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_journey_id', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_behavior_id', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_suggested_scenario_id', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_external_test_case_id', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_test_case_id', table_name='regression_scope_items')
    op.drop_index('ix_regression_scope_items_regression_suite_id', table_name='regression_scope_items')
    op.drop_table('regression_scope_items')
    
    op.drop_index('ix_regression_suites_repo_status', table_name='regression_suites')
    op.drop_index('ix_regression_suites_recommendation_run_id', table_name='regression_suites')
    op.drop_index('ix_regression_suites_pull_request_id', table_name='regression_suites')
    op.drop_index('ix_regression_suites_release_id', table_name='regression_suites')
    op.drop_index('ix_regression_suites_repository_id', table_name='regression_suites')
    op.drop_table('regression_suites')
    
    op.drop_index('ix_releases_repo_status', table_name='releases')
    op.drop_index('ix_releases_version', table_name='releases')
    op.drop_index('ix_releases_repository_id', table_name='releases')
    op.drop_table('releases')
    
    # Drop ENUM types
    postgresql.ENUM(name='automation_status_enum').drop(op.get_bind())
    postgresql.ENUM(name='business_criticality_enum').drop(op.get_bind())
    postgresql.ENUM(name='test_type_enum').drop(op.get_bind())
    postgresql.ENUM(name='test_priority_enum').drop(op.get_bind())
    postgresql.ENUM(name='override_type_enum').drop(op.get_bind())
    postgresql.ENUM(name='execution_status_enum').drop(op.get_bind())
    postgresql.ENUM(name='scope_priority_enum').drop(op.get_bind())
    postgresql.ENUM(name='scope_tier_enum').drop(op.get_bind())
    postgresql.ENUM(name='scope_item_type_enum').drop(op.get_bind())
    postgresql.ENUM(name='suite_status_enum').drop(op.get_bind())
    postgresql.ENUM(name='suite_type_enum').drop(op.get_bind())
    postgresql.ENUM(name='release_status_enum').drop(op.get_bind())
    postgresql.ENUM(name='release_type_enum').drop(op.get_bind())
