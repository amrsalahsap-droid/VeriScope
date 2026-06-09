"""Create the missing recommendation_overrides table."""
from sqlalchemy import text
from app.db.session import SessionLocal

db = SessionLocal()

# Check if table exists
result = db.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'recommendation_overrides')"))
table_exists = result.scalar()
print(f'Table exists: {table_exists}')

if not table_exists:
    # Create the table
    create_sql = '''
    CREATE TABLE recommendation_overrides (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        recommendation_outcome_id UUID NOT NULL REFERENCES recommendation_outcomes(id) ON DELETE CASCADE,
        recommendation_run_id UUID NOT NULL REFERENCES recommendation_runs(id) ON DELETE CASCADE,
        override_type VARCHAR NOT NULL,
        test_identifier VARCHAR,
        scenario_intent_key VARCHAR,
        reason VARCHAR,
        source VARCHAR NOT NULL DEFAULT 'MANUAL_UI',
        created_by VARCHAR,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    CREATE INDEX ix_recommendation_overrides_recommendation_outcome_id ON recommendation_overrides (recommendation_outcome_id);
    CREATE INDEX ix_recommendation_overrides_recommendation_run_id ON recommendation_overrides (recommendation_run_id);
    CREATE INDEX ix_recommendation_overrides_test_identifier ON recommendation_overrides (test_identifier);
    CREATE INDEX ix_recommendation_overrides_scenario_intent_key ON recommendation_overrides (scenario_intent_key);
    '''
    
    db.execute(text(create_sql))
    db.commit()
    print('Table created successfully')
else:
    print('Table already exists')

db.close()
