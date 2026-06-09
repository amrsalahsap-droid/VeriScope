import sys
import uuid
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun
from app.models.test_result import TestCase, TestRun
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate
from app.services.pr_impact_analyzer import PRImpactAnalyzer

def verify_pr_impact_flow():
    print("Starting PRImpactAnalyzer E2E Database Persistence Verification...")
    db = SessionLocal()
    try:
        # Cleanup
        db.query(RecommendationRun).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(TestCase).delete()
        db.query(TestRun).delete()
        db.query(Repository).delete()
        db.query(WorkspaceMember).delete()
        db.query(Workspace).delete()
        db.query(User).delete()
        db.commit()

        # Seed minimal data
        user = User(email="Alice@acme.com", name="Alice", auth_provider="github", provider_user_id="git-999")
        db.add(user)
        db.flush()

        workspace = Workspace(name="Billing Space", slug="billing-space", created_by_user_id=user.id)
        db.add(workspace)
        db.flush()

        repo = Repository(workspace_id=workspace.id, github_repo_id=1212, name="acme-repo", full_name="acme/acme-repo", default_branch="main", is_active=True, selected_for_analysis=True)
        db.add(repo)
        db.flush()

        # Seeding a TestCase and TestRun to satisfy minimal engine V3 requirements
        tc = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="billing",
            test_name="should_charge_customer",
            stable_identity="billing::should_charge_customer",
            raw_test_name="should_charge_customer",
            normalized_test_name="should_charge_customer",
            normalized_identity_strategy="EXACT",
            framework_name="pytest",
            framework_version="1.0",
            identity_normalization_version=1,
            canonical_identity_hash="hash-123",
            identity_lineage_root_hash="hash-123",
            identity_version=1,
            identity_resolution_strategy="EXACT"
        )
        db.add(tc)
        
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            commit_sha="aabbccddeeff",
            status="success",
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            skipped_tests=0,
            duration=1.2,
            file_hash="hash-test-run",
            normalized_execution_fingerprint="fingerprint-test-run",
            created_at=datetime.datetime.utcnow()
        )
        db.add(test_run)
        db.flush()

        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=555,
            number=1,
            title="Implement credit card payments and fix billing settings",
            author="Alice",
            source_branch="feat-payments",
            target_branch="main",
            state="open",
            additions=120,
            deletions=10,
            changed_files_count=2,
            head_commit_sha="aabbccddeeff",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr)
        db.flush()

        cf1 = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="src/app/api/billing/charge/route.ts",
            status="added",
            additions=100,
            deletions=0
        )
        cf2 = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="config/billing-settings.json",
            status="modified",
            additions=20,
            deletions=10
        )
        db.add(cf1)
        db.add(cf2)
        db.commit()

        # Run Recommendation run creation
        service = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=repo.id,
            pr_id=str(pr.id),
            triggered_by="verify_pr_impact",
            engine_version="v3.0.0"
        )
        run = service.create_recommendation_run(run_in)

        # Assert ImpactProfile is populated and persisted correctly
        print("\nVerifying persisted RecommendationRun properties...")
        assert run.impact_profile is not None, "ImpactProfile was not persisted on the run."
        
        profile = run.impact_profile
        print(f"Persisted Impact Profile:\n{profile}")

        assert "billing" in profile["affected_domains"], "Expected 'billing' in affected_domains."
        assert "PAYMENTS" in profile["risk_categories"], "Expected 'PAYMENTS' in risk_categories."
        assert "API_CHANGE" in profile["change_types"], "Expected 'API_CHANGE' in change_types."
        assert "CONFIG_CHANGE" in profile["change_types"], "Expected 'CONFIG_CHANGE' in change_types."
        assert "API" in profile["recommended_testing_types"], "Expected 'API' in recommended_testing_types."
        
        print("\nSUCCESS: PRImpactAnalyzer E2E Database Persistence verified successfully!")

    except Exception as e:
        db.rollback()
        print(f"E2E Verification Error: {e}")
        raise
    finally:
        # Cleanup
        try:
            db.query(RecommendationRun).delete()
            db.query(PullRequestChangedFile).delete()
            db.query(PullRequest).delete()
            db.query(TestCase).delete()
            db.query(TestRun).delete()
            db.query(Repository).delete()
            db.query(WorkspaceMember).delete()
            db.query(Workspace).delete()
            db.query(User).delete()
            db.commit()
        except Exception:
            pass
        db.close()

if __name__ == "__main__":
    verify_pr_impact_flow()
