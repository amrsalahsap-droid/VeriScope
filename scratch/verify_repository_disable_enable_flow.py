"""
Verification test for repository disable/enable flow.

Tests that:
1. Disabling a repository sets selected_for_analysis = false only
2. Disabled repository shows NOT_SELECTED state
3. Disabled repository shows "Enable Repository" action
4. Re-enabling returns to NEEDS_TEST_HISTORY if no test runs
5. GitHub-removed repository shows REMOVED_OR_INACTIVE
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
from app.config import settings

API_BASE = "http://localhost:8000"
JWT_SECRET = settings.STATE_SECRET_KEY or "veriscope-state-secret-key-change-in-prod"


def generate_token(email: str, name: str, sub: str, workspace_id: Optional[str] = None) -> str:
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
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=f"test-disable-{unique_id}@veriscope.dev",
        name="Test Disable User",
        auth_provider="github",
        provider_user_id=f"888888{unique_id}",
    )
    db.add(user)
    db.commit()
    
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Disable Workspace",
        slug=f"test-disable-workspace-{unique_id}",
        created_by_user_id=user.id,
    )
    db.add(workspace)
    db.commit()
    
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="OWNER",
    )
    db.add(member)
    db.commit()
    
    installation_id = int(f"7777{unique_id}", 16) % 1000000
    installation = GitHubInstallation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        installation_id=installation_id,
        github_installation_id=installation_id,
        github_account_id=666666,
        github_account_type="Organization",
        github_account_login="test-disable-org",
        repository_selection="selected",
        permissions='{"contents": "read", "pull_requests": "read"}',
        status="ACTIVE",
        installed_at=datetime.utcnow(),
    )
    db.add(installation)
    db.commit()
    
    base_repo_id = int(f"3000{unique_id}", 16) % 1000000
    now = datetime.utcnow()
    
    # Repo 1: Enabled with no test history (NEEDS_TEST_HISTORY)
    repo_enabled = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id,
        installation_id=installation.github_installation_id,
        owner="test-disable-org",
        name="repo-enabled",
        full_name="test-disable-org/repo-enabled",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # Repo 2: Disabled (NOT_SELECTED)
    repo_disabled = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 1,
        installation_id=installation.github_installation_id,
        owner="test-disable-org",
        name="repo-disabled",
        full_name="test-disable-org/repo-disabled",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=False,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    # Repo 3: Removed from GitHub (REMOVED_OR_INACTIVE)
    repo_removed = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        github_repo_id=base_repo_id + 2,
        installation_id=installation.github_installation_id,
        owner="test-disable-org",
        name="repo-removed",
        full_name="test-disable-org/repo-removed",
        default_branch="main",
        visibility="PRIVATE",
        is_active=False,  # Simulates removal
        selected_for_analysis=True,
        last_synced_at=now,
        latest_sync_status="SUCCESS",
    )
    
    db.add_all([repo_enabled, repo_disabled, repo_removed])
    db.commit()
    
    # Add webhook for enabled and disabled repos
    for repo in [repo_enabled, repo_disabled]:
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
    print(f"  Repos: enabled, disabled, removed")
    
    return {
        "user": user,
        "workspace": workspace,
        "installation": installation,
        "repo_enabled": repo_enabled,
        "repo_disabled": repo_disabled,
        "repo_removed": repo_removed,
    }


def cleanup_test_data(db, test_data):
    try:
        db.query(WebhookEvent).filter(
            WebhookEvent.installation_id == test_data["installation"].github_installation_id
        ).delete(synchronize_session=False)
        
        repo_ids = [
            test_data["repo_enabled"].id,
            test_data["repo_disabled"].id,
            test_data["repo_removed"].id,
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
    results = TestResult()
    db = SessionLocal()
    test_data = None
    
    try:
        print("Setting up test data...")
        test_data = setup_test_data(db)
        
        token = generate_token(
            test_data["user"].email,
            test_data["user"].name,
            str(test_data["user"].id),
            str(test_data["workspace"].id)
        )
        
        print("\nRunning disable/enable flow verification...\n")
        
        # Test 1: Enabled repo shows NEEDS_TEST_HISTORY
        print("Test 1: Enabled repo shows NEEDS_TEST_HISTORY")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_enabled'].id}", token=token)
        if status == 200:
            results.add(
                "Enabled repo shows NEEDS_TEST_HISTORY",
                data.get("readiness_state") == "NEEDS_TEST_HISTORY",
                f"Got {data.get('readiness_state')}"
            )
        else:
            results.add("Enabled repo shows NEEDS_TEST_HISTORY", False, f"API returned {status}")
        
        # Test 2: Disabled repo shows NOT_SELECTED
        print("\nTest 2: Disabled repo shows NOT_SELECTED")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_disabled'].id}", token=token)
        if status == 200:
            results.add(
                "Disabled repo shows NOT_SELECTED",
                data.get("readiness_state") == "NOT_SELECTED",
                f"Got {data.get('readiness_state')}"
            )
        else:
            results.add("Disabled repo shows NOT_SELECTED", False, f"API returned {status}")
        
        # Test 3: Disabled repo shows Enable Repository action
        print("\nTest 3: Disabled repo shows Enable Repository action")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_disabled'].id}", token=token)
        if status == 200:
            results.add(
                "Disabled repo shows Enable Repository action",
                data.get("next_action") == "Enable Repository",
                f"Got {data.get('next_action')}"
            )
        else:
            results.add("Disabled repo shows Enable Repository action", False, f"API returned {status}")
        
        # Test 4: Disabled repo message is correct
        print("\nTest 4: Disabled repo message is correct")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_disabled'].id}", token=token)
        if status == 200:
            reasons = data.get("readiness_reasons", [])
            has_correct_message = any("connected but not enabled" in r.lower() for r in reasons)
            results.add(
                "Disabled repo message is correct",
                has_correct_message,
                f"Reasons: {reasons}"
            )
        else:
            results.add("Disabled repo message is correct", False, f"API returned {status}")
        
        # Test 5: Removed repo shows REMOVED_OR_INACTIVE
        print("\nTest 5: Removed repo shows REMOVED_OR_INACTIVE")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_removed'].id}", token=token)
        if status == 200:
            results.add(
                "Removed repo shows REMOVED_OR_INACTIVE",
                data.get("readiness_state") == "REMOVED_OR_INACTIVE",
                f"Got {data.get('readiness_state')}"
            )
        else:
            results.add("Removed repo shows REMOVED_OR_INACTIVE", False, f"API returned {status}")
        
        # Test 6: Disable endpoint only sets selected_for_analysis = false
        print("\nTest 6: Disable endpoint only sets selected_for_analysis = false")
        status, data = api_request("POST", f"/github/repositories/{test_data['repo_enabled'].id}/disable", token=token)
        if status == 200:
            db.refresh(test_data["repo_enabled"])
            results.add(
                "Disable endpoint only sets selected_for_analysis = false",
                test_data["repo_enabled"].selected_for_analysis == False and test_data["repo_enabled"].is_active == True,
                f"selected_for_analysis={test_data['repo_enabled'].selected_for_analysis}, is_active={test_data['repo_enabled'].is_active}"
            )
        else:
            results.add("Disable endpoint only sets selected_for_analysis = false", False, f"API returned {status}")
        
        # Test 7: After disable, repo shows NOT_SELECTED
        print("\nTest 7: After disable, repo shows NOT_SELECTED")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_enabled'].id}", token=token)
        if status == 200:
            results.add(
                "After disable, repo shows NOT_SELECTED",
                data.get("readiness_state") == "NOT_SELECTED",
                f"Got {data.get('readiness_state')}"
            )
        else:
            results.add("After disable, repo shows NOT_SELECTED", False, f"API returned {status}")
        
        # Test 8: Re-enable returns to NEEDS_TEST_HISTORY
        print("\nTest 8: Re-enable returns to NEEDS_TEST_HISTORY")
        status, data = api_request("POST", f"/github/repositories/{test_data['repo_enabled'].id}/enable", token=token)
        if status == 200:
            status, data = api_request("GET", f"/github/repositories/{test_data['repo_enabled'].id}", token=token)
            if status == 200:
                results.add(
                    "Re-enable returns to NEEDS_TEST_HISTORY",
                    data.get("readiness_state") == "NEEDS_TEST_HISTORY",
                    f"Got {data.get('readiness_state')}"
                )
            else:
                results.add("Re-enable returns to NEEDS_TEST_HISTORY", False, "Failed to fetch after enable")
        else:
            results.add("Re-enable returns to NEEDS_TEST_HISTORY", False, f"Enable returned {status}")
        
        # Test 9: Disable is idempotent
        print("\nTest 9: Disable is idempotent")
        status, data = api_request("POST", f"/github/repositories/{test_data['repo_enabled'].id}/disable", token=token)
        if status == 200:
            status2, data2 = api_request("POST", f"/github/repositories/{test_data['repo_enabled'].id}/disable", token=token)
            results.add(
                "Disable is idempotent",
                status2 == 200,
                f"Second disable returned {status2}"
            )
        else:
            results.add("Disable is idempotent", False, f"First disable returned {status}")
        
        success = results.summary()
        
    finally:
        cleanup_test_data(db, test_data)
        db.close()
    
    return success


if __name__ == "__main__":
    print('='*60)
    print("Repository Disable/Enable Flow Verification")
    print('='*60)
    
    success = run_tests()
    
    if success:
        print("\nAll disable/enable flow checks passed!")
        sys.exit(0)
    else:
        print("\nSome disable/enable flow checks failed!")
        sys.exit(1)
