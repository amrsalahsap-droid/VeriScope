"""Test the detailed readiness API implementation."""
from app.services.detailed_readiness_service import DetailedReadinessService
from app.db.session import SessionLocal

def ensure_test_data(db):
    from app.models.user import Workspace
    from app.models.repository import Repository
    from app.models.pull_request import PullRequest
    from datetime import datetime
    import uuid

    # 1. Workspace
    workspace = db.query(Workspace).first()
    if not workspace:
        workspace = Workspace(
            id=uuid.UUID("361e6878-c1a7-4b71-b0db-b0352ef29b8c"),
            name="Test Workspace",
            slug="test-workspace",
            created_at=datetime.utcnow()
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
    workspace_id = workspace.id

    # 2. Repository
    repo_id = uuid.UUID("a5de7396-88ca-49f5-af9d-8937aecfcfab")
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        repo = Repository(
            id=repo_id,
            workspace_id=workspace_id,
            github_repo_id=12345,
            name="test_repo",
            full_name="test_owner/test_repo",
            visibility="PUBLIC",
            is_active=True,
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()

    # 3. Pull Request
    pr_id = uuid.UUID("805e8062-b20f-4831-81aa-f6e7d0e796fd")
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=54321,
            number=1,
            title="Test PR",
            author="test_author",
            source_branch="main",
            target_branch="main",
            state="open",
            changed_files_count=1,
            head_commit_sha="abcdef",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(pr)
        db.commit()

def test_detailed_readiness_service():
    """Test the detailed readiness service with sample data."""
    db = SessionLocal()
    
    try:
        # Seed test data if missing
        ensure_test_data(db)
        
        # Create the service
        service = DetailedReadinessService(db)
        
        # Test with a repository ID that exists
        repository_id = "a5de7396-88ca-49f5-af9d-8937aecfcfab"
        pull_request_id = "805e8062-b20f-4831-81aa-f6e7d0e796fd"
        
        print(f"Testing detailed readiness assessment for repo {repository_id}, PR {pull_request_id}")
        
        # Perform the detailed assessment
        detailed_readiness = service.get_detailed_readiness(
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        # Print results
        print(f"Readiness Level: {detailed_readiness.readiness_level}")
        print(f"Expected Confidence: {detailed_readiness.expected_confidence}")
        print(f"Readiness Score: {detailed_readiness.readiness_score}")
        print(f"Can Generate: {detailed_readiness.can_generate}")
        
        print(f"\nAvailable Signals ({len(detailed_readiness.available_signals)}):")
        for signal in detailed_readiness.available_signals:
            print(f"  - {signal.label}: {signal.impact} (+{signal.confidence_contribution})")
        
        print(f"\nMissing Signals ({len(detailed_readiness.missing_signals)}):")
        for signal in detailed_readiness.missing_signals:
            print(f"  - {signal.label} [{signal.severity}]: {signal.impact} (+{signal.estimated_confidence_gain})")
            if signal.actions:
                print(f"    Actions: {', '.join(signal.actions)}")
        
        print(f"\nRecommended Actions ({len(detailed_readiness.recommended_actions)}):")
        for action in detailed_readiness.recommended_actions:
            print(f"  - {action.label} [{action.priority}]: +{action.estimated_confidence_gain}% confidence")
        
        # Test confidence impact summary
        available_signals = set(s.key for s in detailed_readiness.available_signals)
        missing_signals = set(s.key for s in detailed_readiness.missing_signals)
        
        impact_summary = service.calculate_confidence_impact_summary(
            available_signals, missing_signals
        )
        print(f"\nConfidence Impact Summary: {impact_summary}")
        
        print("\nDetailed readiness assessment completed successfully!")
        
    except Exception as e:
        print(f"Error during detailed readiness assessment: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    test_detailed_readiness_service()
