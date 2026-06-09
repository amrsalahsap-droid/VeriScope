"""
Create a test pull request in the database for AC lifecycle testing.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from sqlalchemy import text

def create_test_pr():
    db = SessionLocal()
    try:
        # Get first repository
        repo = db.query(Repository).first()
        if not repo:
            print("ERROR: No repositories found in database")
            return False
        
        # Check if PR already exists
        existing_pr = db.query(PullRequest).filter(
            PullRequest.repository_id == repo.id,
            PullRequest.title == "Test PR for AC Lifecycle"
        ).first()
        
        if existing_pr:
            print(f"Test PR already exists: {existing_pr.id}")
            return str(existing_pr.id)
        
        # Create a test PR
        import uuid
        from datetime import datetime
        
        test_pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=99999,
            number=99999,
            title="Test PR for AC Lifecycle",
            author="veriscope-test",
            source_branch="feature/test-ac-lifecycle",
            target_branch="main",
            head_commit_sha="0000000000000000000000000000000000000000",
            state="open",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        
        db.add(test_pr)
        db.commit()
        
        print(f"Created test PR: {test_pr.id}")
        print(f"Repository ID: {repo.id}")
        print(f"PR Title: {test_pr.title}")
        
        return str(test_pr.id)
        
    except Exception as e:
        db.rollback()
        print(f"ERROR creating test PR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    pr_id = create_test_pr()
    if pr_id:
        print(f"\nTest PR ID: {pr_id}")
        sys.exit(0)
    else:
        sys.exit(1)
