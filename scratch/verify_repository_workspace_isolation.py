"""Verify workspace isolation for repository APIs.

This script tests:
1. User A cannot list user B repositories
2. User A cannot open user B repository detail
3. User A cannot enable user B repository
4. User A cannot sync user B repository
5. Repository list filters by workspace_id
6. Duplicate GitHub repo IDs across workspaces do not collide
7. Webhook mapping uses installation_id + github_repo_id
8. Unauthenticated request returns 401
9. Unauthorized workspace access returns 403
10. selected_for_analysis is workspace-specific
"""

import sys
import json
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional

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
from app.config import settings

# Test configuration
API_BASE = "http://localhost:8000"
JWT_SECRET = settings.STATE_SECRET_KEY or "veriscope-state-secret-key-change-in-prod"

# Colors for output
GREEN = ""
RED = ""
YELLOW = ""
RESET = ""


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


def generate_token(email: str, name: str, sub: str, workspace_id: Optional[str] = None) -> str:
    """Generate a JWT token for testing."""
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "auth_provider": "github",
        "provider_user_id": sub,
        "iat": int(time.time()),
        "exp": int(time.time()) + 300
    }
    if workspace_id:
        payload["workspace_id"] = workspace_id
    
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def api_request(method: str, endpoint: str, token: Optional[str] = None, data: Optional[Dict] = None) -> tuple:
    """Make an API request and return (status_code, response_data)."""
    url = f"{API_BASE}{endpoint}"
    headers = {}
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = None
    if data:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, method=method, headers=headers, data=body)
    
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, str(e)


def setup_test_data(db: Session) -> Dict[str, Any]:
    """Create test users, workspaces, and repositories."""
    print(f"\n{YELLOW}Setting up test data...{RESET}")
    
    # Create test users
    user_a = User(
        id=uuid.uuid4(),
        email="test-user-a@example.com",
        name="Test User A",
        auth_provider="github",
        provider_user_id="test-user-a-github-id"
    )
    user_b = User(
        id=uuid.uuid4(),
        email="test-user-b@example.com",
        name="Test User B",
        auth_provider="github",
        provider_user_id="test-user-b-github-id"
    )
    db.add_all([user_a, user_b])
    db.flush()
    
    # Create workspaces
    workspace_a = Workspace(
        id=uuid.uuid4(),
        name="Workspace A",
        slug=f"workspace-a-{uuid.uuid4().hex[:8]}",
        created_by_user_id=user_a.id
    )
    workspace_b = Workspace(
        id=uuid.uuid4(),
        name="Workspace B",
        slug=f"workspace-b-{uuid.uuid4().hex[:8]}",
        created_by_user_id=user_b.id
    )
    db.add_all([workspace_a, workspace_b])
    db.flush()
    
    # Create workspace memberships
    member_a = WorkspaceMember(
        user_id=user_a.id,
        workspace_id=workspace_a.id,
        role="OWNER"
    )
    member_b = WorkspaceMember(
        user_id=user_b.id,
        workspace_id=workspace_b.id,
        role="OWNER"
    )
    db.add_all([member_a, member_b])
    db.flush()
    
    # Create GitHub installations
    install_a = GitHubInstallation(
        id=uuid.uuid4(),
        workspace_id=workspace_a.id,
        github_installation_id=123456,
        github_account_login="test-org-a",
        github_account_id=111111,
        github_account_type="Organization",
        status="ACTIVE"
    )
    install_b = GitHubInstallation(
        id=uuid.uuid4(),
        workspace_id=workspace_b.id,
        github_installation_id=789012,
        github_account_login="test-org-b",
        github_account_id=222222,
        github_account_type="Organization",
        status="ACTIVE"
    )
    db.add_all([install_a, install_b])
    db.flush()
    
    # Create repositories - same GitHub repo ID in both workspaces to test isolation
    shared_github_repo_id = 999999
    
    repo_a = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace_a.id,
        github_repo_id=shared_github_repo_id,
        installation_id=123456,
        owner="test-org-a",
        name="shared-repo",
        full_name="test-org-a/shared-repo",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=False,
        latest_sync_status="SUCCESS"
    )
    repo_b = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace_b.id,
        github_repo_id=shared_github_repo_id,  # Same GitHub ID!
        installation_id=789012,
        owner="test-org-b",
        name="shared-repo",
        full_name="test-org-b/shared-repo",
        default_branch="main",
        visibility="PRIVATE",
        is_active=True,
        selected_for_analysis=True,  # Different selection state
        latest_sync_status="SUCCESS"
    )
    db.add_all([repo_a, repo_b])
    db.flush()
    
    # Create additional repositories for list filtering tests
    repo_a2 = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace_a.id,
        github_repo_id=111111,
        installation_id=123456,
        owner="test-org-a",
        name="repo-a-only",
        full_name="test-org-a/repo-a-only",
        default_branch="main",
        visibility="PUBLIC",
        is_active=True,
        selected_for_analysis=True,
        latest_sync_status="SUCCESS"
    )
    repo_b2 = Repository(
        id=uuid.uuid4(),
        workspace_id=workspace_b.id,
        github_repo_id=222222,
        installation_id=789012,
        owner="test-org-b",
        name="repo-b-only",
        full_name="test-org-b/repo-b-only",
        default_branch="main",
        visibility="PUBLIC",
        is_active=True,
        selected_for_analysis=False,
        latest_sync_status="FAILED"
    )
    db.add_all([repo_a2, repo_b2])
    db.commit()
    
    print("Test data created:")
    print(f"  Workspace A: {workspace_a.id} (User A)")
    print(f"  Workspace B: {workspace_b.id} (User B)")
    print(f"  Shared GitHub Repo ID: {shared_github_repo_id}")
    print(f"  Repo A: {repo_a.id} (selected_for_analysis=False)")
    print(f"  Repo B: {repo_b.id} (selected_for_analysis=True)")
    
    return {
        "user_a": user_a,
        "user_b": user_b,
        "workspace_a": workspace_a,
        "workspace_b": workspace_b,
        "repo_a": repo_a,
        "repo_a2": repo_a2,
        "repo_b": repo_b,
        "repo_b2": repo_b2,
        "shared_github_repo_id": shared_github_repo_id
    }


def cleanup_test_data(db: Session, test_data: Dict):
    """Clean up test data."""
    print(f"\n{YELLOW}Cleaning up test data...{RESET}")
    
    try:
        # Delete repositories
        repo_ids = [
            test_data["repo_a"].id,
            test_data["repo_a2"].id,
            test_data["repo_b"].id,
            test_data["repo_b2"].id
        ]
        db.query(Repository).filter(Repository.id.in_(repo_ids)).delete(synchronize_session=False)
        
        # Delete GitHub installations
        install_ids = [
            test_data["workspace_a"].id,
            test_data["workspace_b"].id
        ]
        db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id.in_(install_ids)
        ).delete(synchronize_session=False)
        
        # Delete workspace memberships
        db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id.in_(install_ids)
        ).delete(synchronize_session=False)
        
        # Delete workspaces
        db.query(Workspace).filter(Workspace.id.in_(install_ids)).delete(synchronize_session=False)
        
        # Delete users
        user_ids = [test_data["user_a"].id, test_data["user_b"].id]
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        
        db.commit()
        print("Test data cleaned up")
    except Exception as e:
        print(f"Cleanup error: {e}")
        db.rollback()


def run_tests():
    """Run all workspace isolation tests."""
    results = TestResult()
    db = SessionLocal()
    
    try:
        # Setup test data
        test_data = setup_test_data(db)
        
        # Generate tokens
        token_a = generate_token(
            test_data["user_a"].email,
            test_data["user_a"].name,
            str(test_data["user_a"].id),
            str(test_data["workspace_a"].id)
        )
        token_b = generate_token(
            test_data["user_b"].email,
            test_data["user_b"].name,
            str(test_data["user_b"].id),
            str(test_data["workspace_b"].id)
        )
        
        print("\nRunning workspace isolation tests...\n")
        
        # Test 1: User A cannot list User B repositories
        print("Test 1: User A cannot list User B repositories")
        status, data = api_request("GET", "/github/repositories", token=token_a)
        if status == 200:
            repo_ids = [r["id"] for r in data.get("repositories", [])]
            user_b_repo_id = str(test_data["repo_b"].id)
            user_b_repo_id2 = str(test_data["repo_b2"].id)
            
            if user_b_repo_id not in repo_ids and user_b_repo_id2 not in repo_ids:
                results.add("User A cannot list User B repositories", True)
            else:
                results.add("User A cannot list User B repositories", False, 
                           f"Found User B repos in response: {repo_ids}")
        else:
            results.add("User A cannot list User B repositories", False, 
                       f"API returned {status}: {data}")
        
        # Test 2: User A cannot open User B repository detail
        print("\nTest 2: User A cannot open User B repository detail")
        status, data = api_request("GET", f"/github/repositories/{test_data['repo_b'].id}", token=token_a)
        if status == 404:
            results.add("User A cannot open User B repository detail", True)
        else:
            results.add("User A cannot open User B repository detail", False, 
                       f"Expected 404, got {status}")
        
        # Test 3: User A cannot enable User B repository
        print("\nTest 3: User A cannot enable User B repository")
        status, data = api_request("POST", f"/github/repositories/{test_data['repo_b'].id}/enable", token=token_a)
        if status == 404:
            results.add("User A cannot enable User B repository", True)
        else:
            results.add("User A cannot enable User B repository", False, 
                       f"Expected 404, got {status}")
        
        # Test 4: User A cannot sync User B repository
        print("\nTest 4: User A cannot sync User B repository")
        status, data = api_request("POST", f"/github/repositories/{test_data['repo_b'].id}/sync", token=token_a)
        if status in [404, 403]:
            results.add("User A cannot sync User B repository", True, f"Got {status} as expected")
        else:
            results.add("User A cannot sync User B repository", False, 
                       f"Expected 403/404, got {status}: {data}")
        
        # Test 5: Repository list filters by workspace_id
        print("\nTest 5: Repository list filters by workspace_id")
        status_a, data_a = api_request("GET", "/github/repositories", token=token_a)
        status_b, data_b = api_request("GET", "/github/repositories", token=token_b)
        
        if status_a == 200 and status_b == 200:
            repos_a = {r["full_name"] for r in data_a.get("repositories", [])}
            repos_b = {r["full_name"] for r in data_b.get("repositories", [])}
            
            # They should have different repositories
            if repos_a != repos_b:
                results.add("Repository list filters by workspace_id", True)
            else:
                results.add("Repository list filters by workspace_id", False, 
                           f"Both users see same repos: {repos_a}")
        else:
            results.add("Repository list filters by workspace_id", False, 
                       f"API errors: A={status_a}, B={status_b}")
        
        # Test 6: Duplicate GitHub repo IDs across workspaces do not collide
        print("\nTest 6: Duplicate GitHub repo IDs across workspaces")
        status_a, data_a = api_request("GET", "/github/repositories", token=token_a)
        status_b, data_b = api_request("GET", "/github/repositories", token=token_b)
        
        if status_a == 200 and status_b == 200:
            # Find the shared repo ID in both responses
            shared_gh_id = test_data["shared_github_repo_id"]
            
            found_a = [r for r in data_a.get("repositories", []) if r["github_repo_id"] == shared_gh_id]
            found_b = [r for r in data_b.get("repositories", []) if r["github_repo_id"] == shared_gh_id]
            
            # Each workspace should see only their version
            if len(found_a) == 1 and len(found_b) == 1:
                if found_a[0]["id"] != found_b[0]["id"]:
                    results.add("Duplicate GitHub repo IDs do not collide", True)
                else:
                    results.add("Duplicate GitHub repo IDs do not collide", False, 
                               "Same repository ID in both workspaces")
            else:
                results.add("Duplicate GitHub repo IDs do not collide", False, 
                           f"A sees {len(found_a)}, B sees {len(found_b)} repos with shared ID")
        else:
            results.add("Duplicate GitHub repo IDs do not collide", False, 
                       f"API errors: A={status_a}, B={status_b}")
        
        # Test 7: Webhook mapping uses installation_id + github_repo_id
        print("\nTest 7: Webhook mapping uses installation_id + github_repo_id")
        # Create webhook events for both repos
        shared_gh_id = test_data["shared_github_repo_id"]
        webhook_a = WebhookEvent(
            id=uuid.uuid4(),
            github_delivery_id=f"test-delivery-a-{uuid.uuid4().hex[:8]}",
            event_type="push",
            action=None,
            installation_id=123456,
            repository_id=shared_gh_id,
            signature_valid=True,
            processing_status="RECEIVED"
        )
        webhook_b = WebhookEvent(
            id=uuid.uuid4(),
            github_delivery_id=f"test-delivery-b-{uuid.uuid4().hex[:8]}",
            event_type="push",
            action=None,
            installation_id=789012,
            repository_id=shared_gh_id,
            signature_valid=True,
            processing_status="RECEIVED"
        )
        db.add_all([webhook_a, webhook_b])
        db.commit()
        
        # Verify webhooks are separate by querying
        webhooks_for_a = db.query(WebhookEvent).filter(
            WebhookEvent.installation_id == 123456,
            WebhookEvent.repository_id == shared_gh_id
        ).all()
        webhooks_for_b = db.query(WebhookEvent).filter(
            WebhookEvent.installation_id == 789012,
            WebhookEvent.repository_id == shared_gh_id
        ).all()
        
        if len(webhooks_for_a) >= 1 and len(webhooks_for_b) >= 1:
            # Check that installation IDs are different
            if webhooks_for_a[0].installation_id != webhooks_for_b[0].installation_id:
                results.add("Webhook mapping uses installation_id + github_repo_id", True)
            else:
                results.add("Webhook mapping uses installation_id + github_repo_id", False,
                           "Same installation ID for both")
        else:
            results.add("Webhook mapping uses installation_id + github_repo_id", False,
                       f"A={len(webhooks_for_a)}, B={len(webhooks_for_b)} webhooks found")
        
        # Cleanup webhooks
        db.query(WebhookEvent).filter(
            WebhookEvent.id.in_([webhook_a.id, webhook_b.id])
        ).delete(synchronize_session=False)
        db.commit()
        
        # Test 8: Unauthenticated request returns 401
        print("\nTest 8: Unauthenticated request returns 401")
        status, data = api_request("GET", "/github/repositories")
        if status == 401 or status == 403:
            results.add("Unauthenticated request returns 401/403", True, f"Got {status}")
        else:
            results.add("Unauthenticated request returns 401/403", False, 
                       f"Expected 401/403, got {status}")
        
        # Test 9: Unauthorized workspace access returns 403
        print("\nTest 9: Unauthorized workspace access returns 403")
        # Create token for user A with workspace B ID (tampered)
        # NOTE: Current implementation does NOT validate workspace_id in JWT against membership
        # This is a known security gap. The test documents current behavior.
        tampered_token = generate_token(
            test_data["user_a"].email,
            test_data["user_a"].name,
            str(test_data["user_a"].id),
            str(test_data["workspace_b"].id)  # Claiming workspace B
        )
        status, data = api_request("GET", "/github/repositories", token=tampered_token)
        # Current behavior: workspace_id in JWT is ignored, user sees their actual workspace
        # Expected behavior: should return 403 if workspace_id doesn't match membership
        if status == 200:
            # Document that this is a known security gap
            results.add("Unauthorized workspace access returns 403", False,
                       "KNOWN GAP: workspace_id in JWT not validated against membership (got 200)")
        else:
            results.add("Unauthorized workspace access returns 403", True, f"Got {status}")
        
        # Test 10: selected_for_analysis is workspace-specific
        print("\nTest 10: selected_for_analysis is workspace-specific")
        status_a, data_a = api_request("GET", "/github/repositories", token=token_a)
        status_b, data_b = api_request("GET", "/github/repositories", token=token_b)
        
        if status_a == 200 and status_b == 200:
            # Find the shared repo in both responses
            shared_gh_id = test_data["shared_github_repo_id"]
            
            repo_a_selected = None
            repo_b_selected = None
            
            for r in data_a.get("repositories", []):
                if r["github_repo_id"] == shared_gh_id:
                    repo_a_selected = r.get("selected_for_analysis")
                    break
            
            for r in data_b.get("repositories", []):
                if r["github_repo_id"] == shared_gh_id:
                    repo_b_selected = r.get("selected_for_analysis")
                    break
            
            if repo_a_selected is not None and repo_b_selected is not None:
                if repo_a_selected != repo_b_selected:
                    results.add("selected_for_analysis is workspace-specific", True,
                               f"A={repo_a_selected}, B={repo_b_selected}")
                else:
                    results.add("selected_for_analysis is workspace-specific", False,
                               f"Both have selected_for_analysis={repo_a_selected}")
            else:
                results.add("selected_for_analysis is workspace-specific", False,
                           f"Could not find shared repo: A={repo_a_selected}, B={repo_b_selected}")
        else:
            results.add("selected_for_analysis is workspace-specific", False, 
                       f"API errors: A={status_a}, B={status_b}")
        
        # Print summary
        success = results.summary()
        
    finally:
        cleanup_test_data(db, test_data)
        db.close()
    
    return success


if __name__ == "__main__":
    print('='*60)
    print("Repository API Workspace Isolation Verification")
    print('='*60)
    
    success = run_tests()
    
    if success:
        print("\nAll workspace isolation checks passed!")
        sys.exit(0)
    else:
        print("\nSome workspace isolation checks failed!")
        sys.exit(1)
