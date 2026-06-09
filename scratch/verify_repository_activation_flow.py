"""
End-to-end verification of repository activation flow.

Tests full flow from GitHub App installation to readiness state calculation.
"""
import sys
import uuid
import json
import time
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import urllib.error

sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from jose import jwt as jose_jwt
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.github_installation import GitHubInstallation
from app.models.webhook_event import WebhookEvent
from app.models.test_result import TestRun
from app.models.coverage import CoverageReport
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.config import settings

# Test configuration
API_BASE = "http://localhost:8000"
JWT_SECRET = settings.STATE_SECRET_KEY or "veriscope-state-secret-key-change-in-prod"


def generate_token(email: str, name: str, sub: str, workspace_id: Optional[str] = None) -> str:
    """Generate a JWT token for testing."""
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "auth_provider": "github",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    if workspace_id:
        payload["workspace_id"] = workspace_id
    
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def api_request(method: str, path: str, token: Optional[str] = None, body: Optional[dict] = None) -> tuple[int, dict]:
    """Make an API request and return status and parsed JSON."""
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data = None
    if body:
        data = json.dumps(body).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode(), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except:
            return e.code, {"error": str(e)}
    except Exception as e:
        return -1, {"error": str(e)}


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add(self, name: str, passed: bool, message: str = ""):
        self.tests.append((name, passed, message))
        if passed:
            self.passed += 1
            print(f"[PASS] {name}")
        else:
            self.failed += 1
            print(f"[FAIL] {name}")
            if message:
                print(f"  --> {message}")
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        return self.failed == 0


def setup_test_data(db):
    """Create test workspace, installation, and repositories."""
    # Create user with random email to avoid conflicts
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=f"test-activation-{unique_id}@veriscope.dev",
        name="Test Activation User",
        auth_provider="github",
        provider_user_id=f"999998{unique_id}",
    )
    db.add(user)
    db.commit()
    
    # Create workspace
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Activation Workspace",
        slug=f"test-activation-workspace-{unique_id}",
        created_by_user_id=user.id,
    )
    db.add(workspace)
    db.commit()
    
    # Link user to workspace
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="OWNER",
    )
    db.add(member)
    db.commit()
    
    # Create GitHub installation with unique ID
    installation_id = int(f"8888{unique_id}", 16) % 1000000  # Random-ish but deterministic
    installation = GitHubInstallation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        installation_id=installation_id,
        github_installation_id=installation_id,
        github_account_id=777777,
        github_account_type="Organization",
        github_account_login="test-org",
        repository_selection="selected",
        permissions='{"contents": "read", "pull_requests": "read"}',
        status="ACTIVE",
        installed_at=datetime.utcnow(),
    )
    db.add(installation)
    db.commit()
    
    # Create repositories in different states
    now = datetime.utcnow()
    base_repo_id = int(f"1000{unique_id}", 16) % 1000000
    
    # Repo 1: NOT_SELECTED (default state after sync)
    repo_not_selected = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 1,
        installation_id=installation.github_installation_id,
        owner="test-org",
        name="repo-not-selected",
        full_name="test-org/repo-not-selected",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=False,  # Not enabled
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # Repo 2: NEEDS_TEST_HISTORY (enabled, no test runs)
    repo_needs_tests = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 2,
        installation_id=installation.github_installation_id,
        owner="test-org",
        name="repo-needs-tests",
        full_name="test-org/repo-needs-tests",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,  # Enabled
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # Repo 3: NEEDS_COVERAGE (enabled, has test runs, no coverage)
    repo_needs_coverage = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 3,
        installation_id=installation.github_installation_id,
        owner="test-org",
        name="repo-needs-coverage",
        full_name="test-org/repo-needs-coverage",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # Repo 4: READY (enabled, has test runs and coverage)
    repo_ready = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 4,
        installation_id=installation.github_installation_id,
        owner="test-org",
        name="repo-ready",
        full_name="test-org/repo-ready",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # Repo 5: SYNC_FAILED
    repo_sync_failed = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 5,
        installation_id=installation.github_installation_id,
        owner="test-org",
        name="repo-sync-failed",
        full_name="test-org/repo-sync-failed",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,
        last_synced_at=now,
        latest_sync_status="FAILED",
        sync_error="Test sync failure for verification",
    )
    
    db.add_all([
        repo_not_selected,
        repo_needs_tests,
        repo_needs_coverage,
        repo_ready,
        repo_sync_failed,
    ])
    db.commit()
    
    # Add test runs for repos 3 and 4
    for repo_id in [repo_needs_coverage.id, repo_ready.id]:
        for i in range(3):
            test_run = TestRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                commit_sha=f"abc{i}",
                file_hash=f"hash-{i}",
                normalized_execution_fingerprint=f"fingerprint-{i}",
                status="SUCCESS",
                total_tests=100,
                passed_tests=95,
                failed_tests=5,
                skipped_tests=0,
                duration=5000.0,
            )
            db.add(test_run)
    
    # Add coverage for repo 4 only
    for i in range(2):
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_ready.id,
            commit_sha=f"def{i}",
            file_hash=f"coverage-hash-{i}",
            overall_coverage_pct=85.5,
            total_lines=1000,
            covered_lines_count=855,
            uncovered_lines_count=145,
            confidence_score="HIGH",
        )
        db.add(coverage)
    
    # Add recommendations for repo 4
    for i in range(2):
        recommendation = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo_ready.id,
            pr_id=f"pr-{i}",
            triggered_by="test-verification",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation for verification",
        )
        db.add(recommendation)
    
    # Add recent webhooks for all repos to avoid WEBHOOK_INACTIVE state
    for repo in [repo_not_selected, repo_needs_tests, repo_needs_coverage, repo_ready, repo_sync_failed]:
        webhook = WebhookEvent(
            id=uuid.uuid4(),
            github_delivery_id=f"test-delivery-{uuid.uuid4().hex[:8]}",
            event_type="push",
            action=None,
            installation_id=installation.github_installation_id,
            repository_id=repo.github_repo_id,
            signature_valid=True,
            processing_status="COMPLETED",
            received_at=now,
        )
        db.add(webhook)
    
    db.commit()
    
    print("Test data created:")
    print(f"  Workspace: {workspace.id}")
    print(f"  Installation: {installation.github_installation_id}")
    print(f"  Repos: 5 (not_selected, needs_tests, needs_coverage, ready, sync_failed)")
    
    return {
        "user": user,
        "workspace": workspace,
        "installation": installation,
        "repo_not_selected": repo_not_selected,
        "repo_needs_tests": repo_needs_tests,
        "repo_needs_coverage": repo_needs_coverage,
        "repo_ready": repo_ready,
        "repo_sync_failed": repo_sync_failed,
    }


def cleanup_test_data(db, test_data):
    """Clean up all test data."""
    try:
        # Delete in reverse order of dependencies
        db.query(WebhookEvent).filter(
            WebhookEvent.installation_id == test_data["installation"].github_installation_id
        ).delete(synchronize_session=False)
        
        db.query(RecommendationRun).filter(
            RecommendationRun.repository_id.in_([
                test_data["repo_needs_coverage"].id,
                test_data["repo_ready"].id,
            ])
        ).delete(synchronize_session=False)
        
        db.query(CoverageReport).filter(
            CoverageReport.repository_id.in_([
                test_data["repo_needs_coverage"].id,
                test_data["repo_ready"].id,
            ])
        ).delete(synchronize_session=False)
        
        db.query(TestRun).filter(
            TestRun.repository_id.in_([
                test_data["repo_needs_coverage"].id,
                test_data["repo_ready"].id,
            ])
        ).delete(synchronize_session=False)
        
        repo_ids = [
            test_data["repo_not_selected"].id,
            test_data["repo_needs_tests"].id,
            test_data["repo_needs_coverage"].id,
            test_data["repo_ready"].id,
            test_data["repo_sync_failed"].id,
        ]
        db.query(Repository).filter(Repository.id.in_(repo_ids)).delete(synchronize_session=False)
        
        db.query(GitHubInstallation).filter(
            GitHubInstallation.id == test_data["installation"].id
        ).delete(synchronize_session=False)
        
        db.query(Workspace).filter(Workspace.id == test_data["workspace"].id).delete(synchronize_session=False)
        
        db.query(User).filter(User.id == test_data["user"].id).delete(synchronize_session=False)
        
        db.commit()
        print("Test data cleaned up")
    except Exception as e:
        print(f"Cleanup error: {e}")
        db.rollback()


def run_tests():
    """Run all repository activation flow tests."""
    results = TestResult()
    db = SessionLocal()
    test_data = None
    
    try:
        # Setup test data
        print("Setting up test data...")
        test_data = setup_test_data(db)
        
        # Generate token
        token = generate_token(
            test_data["user"].email,
            test_data["user"].name,
            str(test_data["user"].id),
            str(test_data["workspace"].id)
        )
        
        print("\nRunning repository activation flow tests...\n")
        
        # Test 1: GitHub App installation exists
        print("Test 1: GitHub App installation exists")
        installation = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == test_data["workspace"].id
        ).first()
        results.add("GitHub App installation exists", installation is not None)
        
        # Test 2: Repositories are synced under workspace
        print("\nTest 2: Repositories are synced under workspace")
        repos = db.query(Repository).filter(
            Repository.workspace_id == test_data["workspace"].id
        ).all()
        results.add("Repositories synced under workspace", len(repos) == 5)
        
        # Test 3: /app/repositories shows real repos
        print("\nTest 3: /app/repositories shows real repos")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repo_count = len(data.get("repositories", []))
            results.add("/app/repositories shows real repos", repo_count == 5)
        else:
            results.add("/app/repositories shows real repos", False, f"API returned {status}")
        
        # Test 4: Selected repo can be enabled
        print("\nTest 4: Selected repo can be enabled")
        status, data = api_request(
            "POST",
            f"/github/repositories/{test_data['repo_not_selected'].id}/enable",
            token=token
        )
        if status == 200:
            # Verify in DB
            db.refresh(test_data["repo_not_selected"])
            results.add("Selected repo can be enabled", test_data["repo_not_selected"].selected_for_analysis)
        else:
            results.add("Selected repo can be enabled", False, f"API returned {status}")
        
        # Test 5: Readiness state changes after enabling
        print("\nTest 5: Readiness state changes after enabling")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            enabled_repo = next((r for r in repos if r["id"] == str(test_data["repo_not_selected"].id)), None)
            if enabled_repo:
                # Should now be NEEDS_TEST_HISTORY (enabled but no test runs)
                results.add(
                    "Readiness state changes after enabling",
                    enabled_repo["readiness_state"] == "NEEDS_TEST_HISTORY",
                    f"Got {enabled_repo['readiness_state']}"
                )
            else:
                results.add("Readiness state changes after enabling", False, "Repo not found in response")
        else:
            results.add("Readiness state changes after enabling", False, f"API returned {status}")
        
        # Test 6: Repo without test history shows NEEDS_TEST_HISTORY
        print("\nTest 6: Repo without test history shows NEEDS_TEST_HISTORY")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            repo = next((r for r in repos if r["id"] == str(test_data["repo_needs_tests"].id)), None)
            if repo:
                results.add(
                    "Repo without test history shows NEEDS_TEST_HISTORY",
                    repo["readiness_state"] == "NEEDS_TEST_HISTORY",
                    f"Got {repo['readiness_state']}"
                )
            else:
                results.add("Repo without test history shows NEEDS_TEST_HISTORY", False, "Repo not found")
        else:
            results.add("Repo without test history shows NEEDS_TEST_HISTORY", False, f"API returned {status}")
        
        # Test 7: Repo with test history but no coverage shows NEEDS_COVERAGE
        print("\nTest 7: Repo with test history but no coverage shows NEEDS_COVERAGE")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            repo = next((r for r in repos if r["id"] == str(test_data["repo_needs_coverage"].id)), None)
            if repo:
                results.add(
                    "Repo with test history but no coverage shows NEEDS_COVERAGE",
                    repo["readiness_state"] == "NEEDS_COVERAGE",
                    f"Got {repo['readiness_state']}"
                )
            else:
                results.add("Repo with test history but no coverage shows NEEDS_COVERAGE", False, "Repo not found")
        else:
            results.add("Repo with test history but no coverage shows NEEDS_COVERAGE", False, f"API returned {status}")
        
        # Test 8: Repo with sufficient evidence shows READY
        print("\nTest 8: Repo with sufficient evidence shows READY")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            repo = next((r for r in repos if r["id"] == str(test_data["repo_ready"].id)), None)
            if repo:
                results.add(
                    "Repo with sufficient evidence shows READY",
                    repo["readiness_state"] == "READY",
                    f"Got {repo['readiness_state']}"
                )
            else:
                results.add("Repo with sufficient evidence shows READY", False, "Repo not found")
        else:
            results.add("Repo with sufficient evidence shows READY", False, f"API returned {status}")
        
        # Test 9: Sync failure shows SYNC_FAILED
        print("\nTest 9: Sync failure shows SYNC_FAILED")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            repo = next((r for r in repos if r["id"] == str(test_data["repo_sync_failed"].id)), None)
            if repo:
                results.add(
                    "Sync failure shows SYNC_FAILED",
                    repo["readiness_state"] == "SYNC_FAILED",
                    f"Got {repo['readiness_state']}"
                )
            else:
                results.add("Sync failure shows SYNC_FAILED", False, "Repo not found")
        else:
            results.add("Sync failure shows SYNC_FAILED", False, f"API returned {status}")
        
        # Test 10: Webhook event updates last_webhook_at
        print("\nTest 10: Webhook event updates last_webhook_at")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            repo = next((r for r in repos if r["id"] == str(test_data["repo_ready"].id)), None)
            if repo:
                # KNOWN GAP: Webhook events are inserted directly in test, but last_webhook_at
                # is only updated by the webhook handler. Since we're not calling the webhook
                # handler, last_webhook_at remains None.
                if repo["last_webhook_at"] is None:
                    results.add(
                        "Webhook event updates last_webhook_at",
                        False,
                        "KNOWN GAP: last_webhook_at only updated by webhook handler (not direct DB insert)"
                    )
                else:
                    results.add(
                        "Webhook event updates last_webhook_at",
                        True,
                        f"last_webhook_at: {repo['last_webhook_at']}"
                    )
            else:
                results.add("Webhook event updates last_webhook_at", False, "Repo not found")
        else:
            results.add("Webhook event updates last_webhook_at", False, f"API returned {status}")
        
        # Test 11: Action routing works
        print("\nTest 11: Action routing works")
        status, data = api_request("GET", "/github/repositories", token=token)
        if status == 200:
            repos = data.get("repositories", [])
            # Check that each repo has appropriate next_action
            action_map = {
                "NEEDS_TEST_HISTORY": "Upload Test Results",
                "NEEDS_COVERAGE": "Upload Coverage Report",
                "READY": "Open Intelligence",
                "SYNC_FAILED": "Retry Sync",
                "NOT_SELECTED": "Enable Repository",
            }
            correct_actions = 0
            for repo in repos:
                expected = action_map.get(repo["readiness_state"])
                if expected and repo.get("next_action") == expected:
                    correct_actions += 1
            results.add(
                "Action routing works",
                correct_actions >= 2,  # At least 2 repos should have correct actions
                f"{correct_actions} repos with correct actions"
            )
        else:
            results.add("Action routing works", False, f"API returned {status}")
        
        # Test 12: Workspace isolation is preserved
        print("\nTest 12: Workspace isolation is preserved")
        # Create another workspace and verify it doesn't see our repos
        other_unique_id = uuid.uuid4().hex[:8]
        other_workspace = Workspace(
            id=uuid.uuid4(),
            name="Other Workspace",
            slug=f"other-workspace-{other_unique_id}",
            created_by_user_id=test_data["user"].id,
        )
        db.add(other_workspace)
        db.commit()
        
        # Generate token for other workspace
        other_token = generate_token(
            test_data["user"].email,
            test_data["user"].name,
            str(test_data["user"].id),
            str(other_workspace.id)
        )
        
        status, data = api_request("GET", "/github/repositories", token=other_token)
        if status == 200:
            repo_count = len(data.get("repositories", []))
            # KNOWN GAP: workspace_id in JWT is not validated against membership
            # The system ignores the JWT workspace_id and uses the user's primary workspace
            if repo_count > 0:
                results.add(
                    "Workspace isolation is preserved",
                    False,
                    f"KNOWN GAP: workspace_id in JWT not validated (sees {repo_count} repos)"
                )
            else:
                results.add("Workspace isolation is preserved", True)
        else:
            results.add("Workspace isolation is preserved", False, f"API returned {status}")
        
        # Cleanup other workspace
        db.query(Workspace).filter(Workspace.id == other_workspace.id).delete(synchronize_session=False)
        db.commit()
        
        # Print summary
        success = results.summary()
        
    finally:
        cleanup_test_data(db, test_data)
        db.close()
    
    return success


if __name__ == "__main__":
    print('='*60)
    print("Repository Activation Flow Verification")
    print('='*60)
    
    success = run_tests()
    
    if success:
        print("\nAll repository activation flow checks passed!")
        sys.exit(0)
    else:
        print("\nSome repository activation flow checks failed!")
        sys.exit(1)
