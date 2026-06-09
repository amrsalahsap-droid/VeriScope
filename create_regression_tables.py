import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'app'))

from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)

# Create ENUM types separately with error handling
enum_statements = [
    """DO $$ BEGIN
        CREATE TYPE release_type_enum AS ENUM ('MAJOR', 'MINOR', 'PATCH', 'HOTFIX', 'CUSTOM');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE release_status_enum AS ENUM ('PLANNED', 'IN_PROGRESS', 'READY_FOR_SIGNOFF', 'RELEASED', 'ROLLED_BACK', 'CANCELLED');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE suite_type_enum AS ENUM ('PR_REGRESSION', 'RELEASE_REGRESSION', 'SMOKE', 'FULL', 'HOTFIX');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE suite_status_enum AS ENUM ('DRAFT', 'REVIEWED', 'APPROVED', 'EXECUTED', 'BLOCKED', 'ARCHIVED');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE scope_item_type_enum AS ENUM ('AUTOMATED_TEST', 'MANUAL_TEST', 'COVERAGE_GAP');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE scope_tier_enum AS ENUM ('MUST_RUN', 'SHOULD_RUN', 'OPTIONAL');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE scope_priority_enum AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE execution_status_enum AS ENUM ('NOT_RUN', 'PASSED', 'FAILED', 'SKIPPED', 'BLOCKED', 'MANUAL_PENDING');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
    """DO $$ BEGIN
        CREATE TYPE override_type_enum AS ENUM ('ADDED', 'REMOVED', 'TIER_CHANGED', 'PRIORITY_CHANGED', 'MARKED_REQUIRED', 'MARKED_OPTIONAL', 'EXCLUDED', 'RESTORED');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;""",
]

# Create tables
table_statements = [
    # Create releases table
    """CREATE TABLE IF NOT EXISTS releases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        version VARCHAR(255) NOT NULL,
        release_type release_type_enum NOT NULL,
        status release_status_enum NOT NULL DEFAULT 'PLANNED',
        description TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(repository_id, version)
    );""",
    
    # Create regression_suites table
    """CREATE TABLE IF NOT EXISTS regression_suites (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        release_id UUID REFERENCES releases(id) ON DELETE SET NULL,
        pull_request_id UUID REFERENCES pull_requests(id) ON DELETE CASCADE,
        recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        suite_type suite_type_enum NOT NULL,
        status suite_status_enum NOT NULL DEFAULT 'DRAFT',
        confidence_level VARCHAR(50),
        scope_score DECIMAL(3,2),
        created_by VARCHAR(255),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        is_active BOOLEAN NOT NULL DEFAULT TRUE
    );""",
    
    # Create regression_scope_items table
    """CREATE TABLE IF NOT EXISTS regression_scope_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        regression_suite_id UUID NOT NULL REFERENCES regression_suites(id) ON DELETE CASCADE,
        test_case_id UUID REFERENCES test_cases(id) ON DELETE CASCADE,
        external_test_case_id UUID REFERENCES external_test_cases(id) ON DELETE CASCADE,
        suggested_scenario_id UUID REFERENCES suggested_test_scenarios(id) ON DELETE CASCADE,
        behavior_id UUID REFERENCES behaviors(id) ON DELETE SET NULL,
        journey_id UUID REFERENCES journeys(id) ON DELETE SET NULL,
        acceptance_criterion_id UUID REFERENCES acceptance_criteria(id) ON DELETE SET NULL,
        item_type scope_item_type_enum NOT NULL,
        tier scope_tier_enum NOT NULL,
        priority scope_priority_enum NOT NULL,
        selection_reason TEXT,
        evidence_summary JSONB,
        execution_status execution_status_enum NOT NULL DEFAULT 'NOT_RUN',
        coverage_status VARCHAR(50),
        is_excluded BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(regression_suite_id, test_case_id),
        UNIQUE(regression_suite_id, external_test_case_id),
        UNIQUE(regression_suite_id, suggested_scenario_id)
    );""",
    
    # Create scope_overrides table
    """CREATE TABLE IF NOT EXISTS scope_overrides (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        regression_scope_item_id UUID NOT NULL REFERENCES regression_scope_items(id) ON DELETE CASCADE,
        regression_suite_id UUID NOT NULL REFERENCES regression_suites(id) ON DELETE CASCADE,
        override_type override_type_enum NOT NULL,
        original_value JSONB,
        new_value JSONB,
        reason TEXT NOT NULL,
        overridden_by VARCHAR(255),
        overridden_at TIMESTAMP NOT NULL DEFAULT NOW()
    );""",
    
    # Create indexes
    """CREATE INDEX IF NOT EXISTS ix_regression_suites_repository ON regression_suites(repository_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_suites_release ON regression_suites(release_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_suites_pr ON regression_suites(pull_request_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_suites_recommendation ON regression_suites(recommendation_run_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_suite ON regression_scope_items(regression_suite_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_suite_tier ON regression_scope_items(regression_suite_id, tier);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_suite_type ON regression_scope_items(regression_suite_id, item_type);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_suite_execution ON regression_scope_items(regression_suite_id, execution_status);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_test_case ON regression_scope_items(test_case_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_external_test ON regression_scope_items(external_test_case_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_suggested ON regression_scope_items(suggested_scenario_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_behavior ON regression_scope_items(behavior_id);""",
    """CREATE INDEX IF NOT EXISTS ix_regression_scope_items_journey ON regression_scope_items(journey_id);""",
    """CREATE INDEX IF NOT EXISTS ix_scope_overrides_suite ON scope_overrides(regression_suite_id);""",
    """CREATE INDEX IF NOT EXISTS ix_scope_overrides_item ON scope_overrides(regression_scope_item_id);""",
    """CREATE INDEX IF NOT EXISTS ix_scope_overrides_type ON scope_overrides(override_type);""",
    """CREATE INDEX IF NOT EXISTS ix_scope_overrides_overridden_at ON scope_overrides(overridden_at);""",
]

with engine.connect() as conn:
    print("Creating ENUM types...")
    for sql in enum_statements:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"Created ENUM type")
        except Exception as e:
            print(f"ENUM Error: {e}")
            conn.rollback()
    
    print("\nCreating tables...")
    for sql in table_statements:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"Created table/index")
        except Exception as e:
            print(f"Table Error: {e}")
            conn.rollback()

print("\nRegression scope tables created successfully!")
