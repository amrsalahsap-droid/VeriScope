"""Drop and recreate all external integration tables with full schema matching models."""
from sqlalchemy import text
from app.db.session import SessionLocal

db = SessionLocal()

# Drop in reverse dependency order (safe since tables are empty)
drops = [
    "DROP TABLE IF EXISTS external_test_scenario_mappings CASCADE",
    "DROP TABLE IF EXISTS work_item_behavior_mappings CASCADE",
    "DROP TABLE IF EXISTS pull_request_work_item_links CASCADE",
    "DROP TABLE IF EXISTS external_test_cases CASCADE",
    "DROP TABLE IF EXISTS external_work_items CASCADE",
    "DROP TABLE IF EXISTS integration_connections CASCADE",
]
for stmt in drops:
    db.execute(text(stmt))
    print(f"DROPPED: {stmt.split('DROP TABLE IF EXISTS ')[1].split(' ')[0]}")

creates = [
    """CREATE TABLE integration_connections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
        provider VARCHAR NOT NULL,
        display_name VARCHAR NOT NULL DEFAULT '',
        status VARCHAR NOT NULL DEFAULT 'DISCONNECTED',
        base_url VARCHAR,
        encrypted_credentials JSONB,
        provider_metadata JSONB,
        last_sync_at TIMESTAMP,
        last_sync_status VARCHAR,
        last_sync_error TEXT,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX ix_integration_connections_workspace_id ON integration_connections (workspace_id)",
    "CREATE INDEX ix_integration_connections_repository_id ON integration_connections (repository_id)",
    "CREATE INDEX ix_integration_connections_provider ON integration_connections (provider)",
    "CREATE INDEX ix_integration_connections_status ON integration_connections (status)",
    "CREATE INDEX ix_integration_connections_workspace_status ON integration_connections (workspace_id, status)",
    "CREATE UNIQUE INDEX uq_workspace_provider_display_name ON integration_connections (workspace_id, provider, display_name)",

    """CREATE TABLE external_work_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
        integration_connection_id UUID NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
        provider VARCHAR NOT NULL,
        external_id VARCHAR NOT NULL,
        external_key VARCHAR NOT NULL,
        title VARCHAR NOT NULL,
        description TEXT,
        work_item_type VARCHAR NOT NULL DEFAULT 'UNKNOWN',
        status VARCHAR NOT NULL DEFAULT 'UNKNOWN',
        priority VARCHAR,
        labels JSONB,
        acceptance_criteria JSONB,
        url VARCHAR,
        raw_payload JSONB,
        last_synced_at TIMESTAMP,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX ix_external_work_items_workspace_id ON external_work_items (workspace_id)",
    "CREATE INDEX ix_external_work_items_repository_id ON external_work_items (repository_id)",
    "CREATE INDEX ix_external_work_items_integration_connection_id ON external_work_items (integration_connection_id)",
    "CREATE INDEX ix_external_work_items_provider ON external_work_items (provider)",
    "CREATE INDEX ix_external_work_items_external_id ON external_work_items (external_id)",
    "CREATE INDEX ix_external_work_items_external_key ON external_work_items (external_key)",
    "CREATE INDEX ix_external_work_items_work_item_type ON external_work_items (work_item_type)",
    "CREATE INDEX ix_external_work_items_status ON external_work_items (status)",
    "CREATE INDEX ix_external_work_items_priority ON external_work_items (priority)",
    "CREATE INDEX ix_external_work_items_workspace_type ON external_work_items (workspace_id, work_item_type)",
    "CREATE INDEX ix_external_work_items_repository ON external_work_items (repository_id)",
    "CREATE UNIQUE INDEX uq_provider_connection_external_id ON external_work_items (provider, integration_connection_id, external_id)",

    """CREATE TABLE external_test_cases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
        integration_connection_id UUID NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
        provider VARCHAR NOT NULL,
        external_id VARCHAR NOT NULL,
        external_key VARCHAR,
        title VARCHAR NOT NULL,
        description TEXT,
        preconditions JSONB,
        steps JSONB,
        expected_result TEXT,
        priority VARCHAR,
        test_type VARCHAR,
        automation_status VARCHAR NOT NULL DEFAULT 'UNKNOWN',
        tags JSONB,
        linked_work_item_keys JSONB,
        behavior_id UUID REFERENCES behaviors(id) ON DELETE SET NULL,
        journey_id UUID REFERENCES journeys(id) ON DELETE SET NULL,
        scenario_intent_key VARCHAR,
        url VARCHAR,
        raw_payload JSONB,
        last_synced_at TIMESTAMP,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX ix_external_test_cases_workspace_id ON external_test_cases (workspace_id)",
    "CREATE INDEX ix_external_test_cases_repository_id ON external_test_cases (repository_id)",
    "CREATE INDEX ix_external_test_cases_integration_connection_id ON external_test_cases (integration_connection_id)",
    "CREATE INDEX ix_external_test_cases_provider ON external_test_cases (provider)",
    "CREATE INDEX ix_external_test_cases_external_id ON external_test_cases (external_id)",
    "CREATE INDEX ix_external_test_cases_external_key ON external_test_cases (external_key)",
    "CREATE INDEX ix_external_test_cases_priority ON external_test_cases (priority)",
    "CREATE INDEX ix_external_test_cases_test_type ON external_test_cases (test_type)",
    "CREATE INDEX ix_external_test_cases_automation_status ON external_test_cases (automation_status)",
    "CREATE INDEX ix_external_test_cases_behavior_id ON external_test_cases (behavior_id)",
    "CREATE INDEX ix_external_test_cases_journey_id ON external_test_cases (journey_id)",
    "CREATE INDEX ix_external_test_cases_scenario_intent_key ON external_test_cases (scenario_intent_key)",
    "CREATE INDEX ix_external_test_cases_workspace_automation ON external_test_cases (workspace_id, automation_status)",
    "CREATE INDEX ix_external_test_cases_repository ON external_test_cases (repository_id)",
    "CREATE INDEX ix_external_test_cases_behavior ON external_test_cases (behavior_id)",
    "CREATE INDEX ix_external_test_cases_journey ON external_test_cases (journey_id)",
    "CREATE UNIQUE INDEX uq_external_test_cases_provider_connection_id ON external_test_cases (provider, integration_connection_id, external_id)",

    """CREATE TABLE pull_request_work_item_links (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pull_request_id UUID NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
        external_work_item_id UUID REFERENCES external_work_items(id) ON DELETE SET NULL,
        unresolved_key VARCHAR,
        link_source VARCHAR NOT NULL DEFAULT 'TITLE',
        confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX ix_pr_work_item_links_pr ON pull_request_work_item_links (pull_request_id)",
    "CREATE INDEX ix_pr_work_item_links_work_item ON pull_request_work_item_links (external_work_item_id)",
    "CREATE INDEX ix_pr_work_item_links_unresolved ON pull_request_work_item_links (unresolved_key)",
    "CREATE UNIQUE INDEX uq_pr_work_item ON pull_request_work_item_links (pull_request_id, external_work_item_id)",

    """CREATE TABLE work_item_behavior_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
        repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
        external_work_item_id UUID NOT NULL REFERENCES external_work_items(id) ON DELETE CASCADE,
        behavior_id UUID REFERENCES behaviors(id) ON DELETE SET NULL,
        journey_id UUID REFERENCES journeys(id) ON DELETE SET NULL,
        confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
        matched_terms JSONB,
        reason TEXT,
        mapping_source VARCHAR,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",

    """CREATE TABLE external_test_scenario_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
        repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
        external_test_case_id UUID NOT NULL REFERENCES external_test_cases(id) ON DELETE CASCADE,
        behavior_id UUID REFERENCES behaviors(id) ON DELETE SET NULL,
        behavior_scenario_id UUID REFERENCES behavior_scenarios(id) ON DELETE SET NULL,
        scenario_intent_key VARCHAR,
        confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
        matched_terms JSONB,
        reason TEXT,
        mapping_source VARCHAR,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
]

for stmt in creates:
    try:
        db.execute(text(stmt))
        name = stmt.strip().split('\n')[0].strip()[:70]
        print(f"OK: {name}")
    except Exception as e:
        print(f"ERR ({stmt.strip()[:40]}): {e}")

db.commit()
print("\nAll external tables recreated with full schema.")
db.close()
