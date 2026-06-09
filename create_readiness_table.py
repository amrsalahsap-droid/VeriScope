"""Create the recommendation_readiness_assessments table."""
from sqlalchemy import text
from app.db.session import SessionLocal

db = SessionLocal()

# Check if table exists
result = db.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'recommendation_readiness_assessments')"))
table_exists = result.scalar()
print(f'Table exists: {table_exists}')

if not table_exists:
    # Create the table
    create_sql = '''
    CREATE TABLE recommendation_readiness_assessments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        pull_request_id UUID REFERENCES pull_requests(id) ON DELETE CASCADE,
        readiness_level VARCHAR NOT NULL,
        expected_confidence VARCHAR NOT NULL,
        readiness_score FLOAT NOT NULL,
        available_signals JSONB NOT NULL DEFAULT '[]',
        missing_signals JSONB NOT NULL DEFAULT '[]',
        blocking_gaps JSONB NOT NULL DEFAULT '[]',
        optional_gaps JSONB NOT NULL DEFAULT '[]',
        recommended_actions JSONB NOT NULL DEFAULT '[]',
        confidence_impact_summary TEXT NOT NULL,
        can_generate BOOLEAN NOT NULL,
        can_generate_reason TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    CREATE INDEX ix_recommendation_readiness_assessments_repository_id ON recommendation_readiness_assessments (repository_id);
    CREATE INDEX ix_recommendation_readiness_assessments_pull_request_id ON recommendation_readiness_assessments (pull_request_id);
    CREATE INDEX ix_recommendation_readiness_assessments_created_at ON recommendation_readiness_assessments (created_at);
    '''
    
    db.execute(text(create_sql))
    db.commit()
    print('Table created successfully')
else:
    print('Table already exists')

db.close()
