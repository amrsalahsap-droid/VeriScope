import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.repository import Repository
from sqlalchemy import text

def main():
    db = SessionLocal()
    try:
        # Mark known test/seed repositories
        known_test_repos = [
            "gate_api_owner/gate_api_repo",
            "gate_owner/gate_repo",
            "test/test-repo"
        ]
        
        print("Starting cleanup of seed/test repositories...")
        
        # Check and update matching repos
        for full_name in known_test_repos:
            repos = db.query(Repository).filter(Repository.full_name == full_name).all()
            if repos:
                print(f"Found {len(repos)} matching '{full_name}'. Marking source=TEST, is_active=False...")
                for repo in repos:
                    repo.source = "TEST"
                    repo.is_active = False
            else:
                print(f"No repositories found matching '{full_name}'")
                
        # Also clean up any repositories starting with test/ or test_owner/
        additional_test_repos = db.query(Repository).filter(
            (Repository.full_name.like("test/%")) | 
            (Repository.full_name.like("test_owner/%"))
        ).all()
        
        if additional_test_repos:
            print(f"Found {len(additional_test_repos)} other test repositories. Marking source=TEST, is_active=False...")
            for repo in additional_test_repos:
                repo.source = "TEST"
                repo.is_active = False
                
        db.commit()
        print("Cleanup completed successfully.")
        
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
