import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'app'))

from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.recommendation import RecommendationRun
from app.models.repository import Repository
from app.services.regression_suite_builder import RegressionSuiteBuilder

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Find TrustDesk repository
repo = db.query(Repository).filter(Repository.full_name.like('%trustdesk%')).first()
if repo:
    print(f'Found repository: {repo.full_name} (ID: {repo.id})')
    
    # Find latest recommendation run
    run = db.query(RecommendationRun).filter(
        RecommendationRun.repository_id == repo.id
    ).order_by(RecommendationRun.created_at.desc()).first()
    
    if run:
        print(f'Latest recommendation run ID: {run.id}')
        print(f'Created at: {run.created_at}')
        print(f'PR ID: {run.pull_request_id}')
        
        # Create regression suite
        print('\nCreating regression suite...')
        suite = RegressionSuiteBuilder.create_from_recommendation_run(
            db,
            run.id,
            created_by='validation_script',
            force_new=True
        )
        
        if suite:
            print(f'Suite created successfully: {suite["suite_id"]}')
            print(f'Suite name: {suite["name"]}')
            print(f'Suite type: {suite["suite_type"]}')
            print(f'Total scope items: {suite["total_scope_items"]}')
            print(f'Tier counts: {suite["tier_counts"]}')
            print(f'Type counts: {suite["type_counts"]}')
        else:
            print('Suite creation failed')
    else:
        print('No recommendation runs found')
else:
    print('TrustDesk repository not found')

db.close()
