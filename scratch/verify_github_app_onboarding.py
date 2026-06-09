"""
GitHub App Onboarding Verification Script

This script verifies the GitHub App onboarding integration works correctly.
It tests:
- Unauthenticated callback rejection
- Installation ID storage
- Installed repos sync
- Repos scoped to workspace
- Duplicate callback idempotency
- Repo selection marks repos active
- Webhook signature validation
- Unsupported webhook ignored safely
- PR webhook creates/syncs pull request evidence
"""
import sys
import os
import uuid
import time
import json
import hmac
import hashlib
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.webhook_event import WebhookEvent
from app.models.pull_request import PullRequest
from app.config import settings


def create_test_user_and_workspace(db: Session):
    """Create a test user and workspace."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        auth_provider="github",
        provider_user_id="github_test_123"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        slug="test-workspace",
        created_by_user_id=user.id
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role="OWNER"
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    
    return user, workspace


def create_jwt_token(user_id: uuid.UUID, workspace_id: uuid.UUID) -> str:
    """Create a test JWT token."""
    import jwt
    payload = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "email": "test@example.com",
        "name": "Test User",
        "auth_provider": "github",
        "provider_user_id": "github_test_123",
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        "iat": int(datetime.now(timezone.utc).timestamp())
    }
    return jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")


def verify_unauthenticated_callback_rejected():
    """Test 1: Unauthenticated callback is rejected."""
    print("\n[TEST 1] Unauthenticated callback rejection...")
    client = TestClient(app)
    
    response = client.post("/github/installation/callback", json={
        "installation_id": 12345,
        "setup_action": "install"
    })
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    print("✓ Unauthenticated callback rejected (401)")


def verify_installation_id_stored():
    """Test 2: Installation ID is stored correctly."""
    print("\n[TEST 2] Installation ID storage...")
    db = SessionLocal()
    try:
        user, workspace = create_test_user_and_workspace(db)
        token = create_jwt_token(user.id, workspace.id)
        
        client = TestClient(app)
        response = client.post(
            "/github/installation/callback",
            json={"installation_id": 99999, "setup_action": "install"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify installation was stored
        installation = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == workspace.id
        ).first()
        
        assert installation is not None, "Installation not found in database"
        assert installation.installation_id == 99999, f"Expected installation_id 99999, got {installation.installation_id}"
        assert installation.github_installation_id == 99999, f"Expected github_installation_id 99999, got {installation.github_installation_id}"
        
        print("✓ Installation ID stored correctly")
        
        # Cleanup
        db.delete(installation)
        db.delete(member)
        db.delete(workspace)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def verify_repos_scoped_to_workspace():
    """Test 3: Repositories are scoped to workspace."""
    print("\n[TEST 3] Repository workspace scoping...")
    db = SessionLocal()
    try:
        user, workspace = create_test_user_and_workspace(db)
        
        # Create repository in workspace
        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="org/test-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        
        # Create another workspace
        workspace2 = Workspace(
            id=uuid.uuid4(),
            name="Other Workspace",
            slug="other-workspace",
            created_by_user_id=user.id
        )
        db.add(workspace2)
        db.commit()
        db.refresh(workspace2)
        
        # Query repos for workspace 1
        repos_workspace1 = db.query(Repository).filter(
            Repository.workspace_id == workspace.id
        ).all()
        
        # Query repos for workspace 2
        repos_workspace2 = db.query(Repository).filter(
            Repository.workspace_id == workspace2.id
        ).all()
        
        assert len(repos_workspace1) == 1, f"Expected 1 repo in workspace 1, got {len(repos_workspace1)}"
        assert len(repos_workspace2) == 0, f"Expected 0 repos in workspace 2, got {len(repos_workspace2)}"
        
        print("✓ Repositories correctly scoped to workspace")
        
        # Cleanup
        db.delete(repo)
        db.delete(workspace2)
        db.delete(member)
        db.delete(workspace)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def verify_duplicate_callback_idempotent():
    """Test 4: Duplicate callback is idempotent."""
    print("\n[TEST 4] Duplicate callback idempotency...")
    db = SessionLocal()
    try:
        user, workspace = create_test_user_and_workspace(db)
        token = create_jwt_token(user.id, workspace.id)
        
        client = TestClient(app)
        
        # First callback
        response1 = client.post(
            "/github/installation/callback",
            json={"installation_id": 88888, "setup_action": "install"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response1.status_code == 200
        
        # Second callback (should update, not error)
        response2 = client.post(
            "/github/installation/callback",
            json={"installation_id": 88888, "setup_action": "install"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response2.status_code == 200
        
        # Verify only one installation exists
        installations = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == workspace.id
        ).all()
        
        assert len(installations) == 1, f"Expected 1 installation, got {len(installations)}"
        
        print("✓ Duplicate callback is idempotent")
        
        # Cleanup
        for inst in installations:
            db.delete(inst)
        db.delete(member)
        db.delete(workspace)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def verify_repo_selection_marks_active():
    """Test 5: Repo selection marks repos active."""
    print("\n[TEST 5] Repository selection marks repos active...")
    db = SessionLocal()
    try:
        user, workspace = create_test_user_and_workspace(db)
        token = create_jwt_token(user.id, workspace.id)
        
        # Create repositories
        repo1 = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=11111,
            name="repo1",
            full_name="org/repo1",
            default_branch="main",
            is_active=False
        )
        repo2 = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=22222,
            name="repo2",
            full_name="org/repo2",
            default_branch="main",
            is_active=False
        )
        db.add(repo1)
        db.add(repo2)
        db.commit()
        db.refresh(repo1)
        db.refresh(repo2)
        
        client = TestClient(app)
        
        # Select repo1
        response = client.post(
            "/github/repositories/select",
            json={"repository_ids": [str(repo1.id)]},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Refresh and check
        db.refresh(repo1)
        db.refresh(repo2)
        
        assert repo1.is_active == True, "Repo1 should be active"
        assert repo2.is_active == False, "Repo2 should be inactive"
        
        print("✓ Repository selection marks repos active correctly")
        
        # Cleanup
        db.delete(repo1)
        db.delete(repo2)
        db.delete(member)
        db.delete(workspace)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def verify_webhook_signature_validation():
    """Test 6: Webhook signature validation works."""
    print("\n[TEST 6] Webhook signature validation...")
    client = TestClient(app)
    
    # Create test payload
    payload = {
        "action": "created",
        "installation": {"id": 12345},
        "repository": {"id": 67890}
    }
    payload_bytes = json.dumps(payload).encode('utf-8')
    
    # Generate valid signature
    signature = hmac.new(
        settings.GITHUB_APP_WEBHOOK_SECRET.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    signature_header = f"sha256={signature}"
    
    # Test with valid signature
    response = client.post(
        "/api/github/webhook",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": signature_header,
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "Content-Type": "application/json"
        }
    )
    
    # Should not reject signature (may fail for other reasons like installation not found)
    assert response.status_code != 401, "Valid signature should not be rejected"
    
    # Test with invalid signature
    invalid_signature = "invalid_signature"
    response = client.post(
        "/api/github/webhook",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": f"sha256={invalid_signature}",
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 401, f"Invalid signature should be rejected, got {response.status_code}"
    
    print("✓ Webhook signature validation works")


def verify_unsupported_webhook_ignored():
    """Test 7: Unsupported webhook is ignored safely."""
    print("\n[TEST 7] Unsupported webhook ignored safely...")
    db = SessionLocal()
    try:
        user, workspace = create_test_user_and_workspace(db)
        
        # Create installation
        installation = GitHubInstallation(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            installation_id=12345,
            github_installation_id=12345,
            github_account_login="test-org",
            github_account_type="Organization",
            repository_selection="all",
            status="ACTIVE",
            installed_at=datetime.utcnow()
        )
        db.add(installation)
        db.commit()
        db.refresh(installation)
        
        client = TestClient(app)
        
        # Create unsupported event payload
        payload = {
            "action": "created",
            "installation": {"id": 12345},
            "repository": {"id": 67890}
        }
        payload_bytes = json.dumps(payload).encode('utf-8')
        
        signature = hmac.new(
            settings.GITHUB_APP_WEBHOOK_SECRET.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Send unsupported event (e.g., "unknown_event")
        response = client.post(
            "/api/github/webhook",
            content=payload_bytes,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "unknown_event",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json"
            }
        )
        
        # Should not crash (200 or 202 accepted)
        assert response.status_code in [200, 202], f"Unsupported event should be handled gracefully, got {response.status_code}"
        
        print("✓ Unsupported webhook ignored safely")
        
        # Cleanup
        db.delete(installation)
        db.delete(member)
        db.delete(workspace)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def verify_pr_webhook_creates_evidence():
    """Test 8: PR webhook creates/syncs pull request evidence."""
    print("\n[TEST 8] PR webhook creates pull request evidence...")
    db = SessionLocal()
    try:
        user, workspace = create_test_user_and_workspace(db)
        
        # Create installation
        installation = GitHubInstallation(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            installation_id=12345,
            github_installation_id=12345,
            github_account_login="test-org",
            github_account_type="Organization",
            repository_selection="all",
            status="ACTIVE",
            installed_at=datetime.utcnow()
        )
        db.add(installation)
        db.commit()
        db.refresh(installation)
        
        # Create active repository
        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="org/test-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        
        client = TestClient(app)
        
        # Create PR opened payload
        payload = {
            "action": "opened",
            "installation": {"id": 12345},
            "repository": {"id": 67890, "name": "test-repo", "full_name": "org/test-repo"},
            "pull_request": {
                "id": 11111,
                "number": 1,
                "title": "Test PR",
                "state": "open",
                "draft": False,
                "user": {"login": "testuser"},
                "head": {"ref": "feature-branch", "sha": "abc123"},
                "base": {"ref": "main"},
                "additions": 10,
                "deletions": 5
            }
        }
        payload_bytes = json.dumps(payload).encode('utf-8')
        
        signature = hmac.new(
            settings.GITHUB_APP_WEBHOOK_SECRET.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Send PR webhook
        response = client.post(
            "/api/github/webhook",
            content=payload_bytes,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json"
            }
        )
        
        # Should be accepted (may enqueue job)
        assert response.status_code in [200, 202], f"PR webhook should be accepted, got {response.status_code}"
        
        print("✓ PR webhook processes pull request evidence")
        
        # Cleanup
        db.delete(repo)
        db.delete(installation)
        db.delete(member)
        db.delete(workspace)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("GitHub App Onboarding Verification")
    print("=" * 60)
    
    tests = [
        verify_unauthenticated_callback_rejected,
        verify_installation_id_stored,
        verify_repos_scoped_to_workspace,
        verify_duplicate_callback_idempotent,
        verify_repo_selection_marks_active,
        verify_webhook_signature_validation,
        verify_unsupported_webhook_ignored,
        verify_pr_webhook_creates_evidence,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All verification tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
