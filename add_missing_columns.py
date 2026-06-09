"""Add all missing columns to recommendation tables and input snapshots."""
from sqlalchemy import text
from app.db.session import SessionLocal

db = SessionLocal()

# recommendation_test_outcomes missing columns
test_outcome_cols = [
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE CASCADE",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS recommended_test_id UUID REFERENCES recommended_tests(id) ON DELETE SET NULL",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS test_identifier VARCHAR",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS recommendation_action VARCHAR DEFAULT 'RUN_EXISTING_TEST'",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS execution_status VARCHAR DEFAULT 'NOT_RUN'",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS engineer_decision VARCHAR DEFAULT 'NOT_DECIDED'",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS actual_test_result_id UUID",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS actual_test_run_id UUID",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS failure_message VARCHAR",
    "ALTER TABLE recommendation_test_outcomes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
]

# recommendation_input_snapshots missing columns
input_snapshot_cols = [
    "ALTER TABLE recommendation_input_snapshots ADD COLUMN IF NOT EXISTS linked_work_items JSONB",
    "ALTER TABLE recommendation_input_snapshots ADD COLUMN IF NOT EXISTS acceptance_criteria JSONB",
    "ALTER TABLE recommendation_input_snapshots ADD COLUMN IF NOT EXISTS external_test_cases JSONB",
    "ALTER TABLE recommendation_input_snapshots ADD COLUMN IF NOT EXISTS external_requirement_coverage JSONB",
    "ALTER TABLE recommendation_input_snapshots ADD COLUMN IF NOT EXISTS integration_sync_status JSONB",
    "ALTER TABLE recommendation_input_snapshots ADD COLUMN IF NOT EXISTS external_context_gaps JSONB",
]

all_statements = test_outcome_cols + input_snapshot_cols

for stmt in all_statements:
    try:
        db.execute(text(stmt))
        print(f"OK: {stmt.split('ADD COLUMN IF NOT EXISTS ')[1].split(' ')[0]}")
    except Exception as e:
        print(f"ERR: {e}")

# Backfill test_identifier from test_case_id where null
db.execute(text("""
    UPDATE recommendation_test_outcomes
    SET test_identifier = test_case_id::text
    WHERE test_identifier IS NULL AND test_case_id IS NOT NULL
"""))

# Create indexes
indexes = [
    "CREATE INDEX IF NOT EXISTS ix_rto_recommendation_run_id ON recommendation_test_outcomes (recommendation_run_id)",
    "CREATE INDEX IF NOT EXISTS ix_rto_recommended_test_id ON recommendation_test_outcomes (recommended_test_id)",
    "CREATE INDEX IF NOT EXISTS ix_rto_test_identifier ON recommendation_test_outcomes (test_identifier)",
]

for stmt in indexes:
    try:
        db.execute(text(stmt))
        print(f"OK: index created")
    except Exception as e:
        print(f"ERR: {e}")

db.commit()
print("\nAll missing columns added successfully.")
db.close()
