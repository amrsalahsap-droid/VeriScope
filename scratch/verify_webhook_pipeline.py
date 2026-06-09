import sys
import uuid
import time
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.github_installation import GitHubInstallation
from app.models.pull_request import PullRequest, PullRequestSyncJob
from app.models.webhook_event import WebhookEvent
from app.models.artifact import RawArtifact
from app.config import settings

client = TestClient(app)

def cleanup_database():
    """Safely clean up database records."""
    db = SessionLocal()
    try:
        db.query(PullRequestSyncJob).delete()
        db.query(PullRequest).delete()
        db.query(WebhookEvent).delete()
        db.query(RawArtifact).delete()
        db.query(Repository).delete()
        db.query(GitHubInstallation).delete()
        db.query(Organization).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error cleaning database: {e}")
    finally:
        db.close()

def run_tests():
    print("==================================================")
    print("STARTING WEBHOOK PIPELINE INTEGRATION TESTS...")
    print("==================================================")
    
    db = SessionLocal()
    
    # 1. Setup multi-tenant core models
    org = Organization(name="Pipeline Ops", slug="pipeline-ops")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    installation_id = 776655
    installation = GitHubInstallation(
        organization_id=org.id,
        github_installation_id=installation_id,
        account_login="pipeline-ops",
        status="ACTIVE",
        evidence_health_status="HEALTHY"
    )
    db.add(installation)
    
    # Active repository
    repo_active = Repository(
        organization_id=org.id,
        github_repo_id=90001,
        name="active-service",
        full_name="pipeline-ops/active-service",
        default_branch="main",
        is_active=True
    )
    db.add(repo_active)
    
    # Inactive repository (Rule 3)
    repo_inactive = Repository(
        organization_id=org.id,
        github_repo_id=90002,
        name="inactive-service",
        full_name="pipeline-ops/inactive-service",
        default_branch="main",
        is_active=False
    )
    db.add(repo_inactive)
    
    db.commit()
    print("Test models seeded successfully.")
    
    webhook_secret = "secret-token"
    settings.GITHUB_WEBHOOK_SECRET = webhook_secret

    def get_sig_headers(payload_bytes, event_type="pull_request"):
        sig = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return {
            "X-Github-Delivery": str(uuid.uuid4()),
            "X-Github-Event": event_type,
            "X-Hub-Signature-256": sig
        }

    # ----------------------------------------------------
    # Verification A: Rule 3 (Ignore Inactive / Unsupported Repositories)
    # ----------------------------------------------------
    print("\n--- Testing Rule 3: Ignore Inactive Repositories ---")
    inactive_payload = {
        "action": "synchronize",
        "installation": {"id": installation_id},
        "repository": {"id": 90002, "full_name": "pipeline-ops/inactive-service"},
        "pull_request": {
            "id": 5001,
            "number": 1,
            "state": "open",
            "draft": False,
            "head": {"sha": "sha123", "ref": "feat-branch"},
            "base": {"ref": "main"}
        }
    }
    payload_bytes = json.dumps(inactive_payload).encode("utf-8")
    headers = get_sig_headers(payload_bytes)
    
    response = client.post("/github/webhook", content=payload_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert "inactive" in response.json()["detail"].lower()
    print("[OK] Inactive repository webhook successfully ignored.")

    # ----------------------------------------------------
    # Verification B: Rule 1 (Ignore Draft PRs initially)
    # ----------------------------------------------------
    print("\n--- Testing Rule 1: Ignore Draft PRs ---")
    draft_payload = {
        "action": "opened",
        "installation": {"id": installation_id},
        "repository": {"id": 90001, "full_name": "pipeline-ops/active-service"},
        "pull_request": {
            "id": 5002,
            "number": 2,
            "state": "open",
            "draft": True,  # Draft
            "head": {"sha": "sha456", "ref": "feat-draft"},
            "base": {"ref": "main"}
        }
    }
    payload_bytes = json.dumps(draft_payload).encode("utf-8")
    headers = get_sig_headers(payload_bytes)
    
    response = client.post("/github/webhook", content=payload_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert "draft" in response.json()["detail"].lower()
    print("[OK] Draft PR webhook successfully ignored.")

    # ----------------------------------------------------
    # Verification C: Rule 2 (Ignore Closed PRs)
    # ----------------------------------------------------
    print("\n--- Testing Rule 2: Ignore Closed PRs ---")
    closed_payload = {
        "action": "synchronize",
        "installation": {"id": installation_id},
        "repository": {"id": 90001, "full_name": "pipeline-ops/active-service"},
        "pull_request": {
            "id": 5003,
            "number": 3,
            "state": "closed",  # Closed
            "draft": False,
            "head": {"sha": "sha789", "ref": "feat-closed"},
            "base": {"ref": "main"}
        }
    }
    payload_bytes = json.dumps(closed_payload).encode("utf-8")
    headers = get_sig_headers(payload_bytes)
    
    response = client.post("/github/webhook", content=payload_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert "closed" in response.json()["detail"].lower()
    print("[OK] Closed PR webhook successfully ignored.")

    # ----------------------------------------------------
    # Verification D: Valid Webhook enqueues PR sync
    # ----------------------------------------------------
    print("\n--- Testing Webhook Sync Enqueueing & Duplication ---")
    valid_payload = {
        "action": "opened",
        "installation": {"id": installation_id},
        "repository": {"id": 90001, "full_name": "pipeline-ops/active-service"},
        "pull_request": {
            "id": 5004,
            "number": 4,
            "title": "Good PR",
            "user": {"login": "developer"},
            "state": "open",
            "draft": False,
            "head": {"sha": "headsha1", "ref": "feat-good"},
            "base": {"ref": "main"},
            "additions": 10,
            "deletions": 5,
            "changed_files": 2
        }
    }
    payload_bytes = json.dumps(valid_payload).encode("utf-8")
    headers = get_sig_headers(payload_bytes)
    
    with patch("app.services.github_app.get_rq_queue") as mock_rq:
        mock_queue = MagicMock()
        mock_rq.return_value = mock_queue
        
        response = client.post("/github/webhook", content=payload_bytes, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["action"] == "opened"
        
        # Verify sync job enqueued in background
        mock_queue.enqueue.assert_called_once()
        print("[OK] Valid webhook successfully initialized sync jobs.")

    # ----------------------------------------------------
    # Verification E: `check_suite.completed` triggers
    # ----------------------------------------------------
    print("\n--- Testing check_suite.completed Triggers ---")
    cs_payload = {
        "action": "completed",
        "installation": {"id": installation_id},
        "repository": {"id": 90001, "full_name": "pipeline-ops/active-service"},
        "check_suite": {
            "id": 8881,
            "status": "completed",
            "conclusion": "success",
            "head_sha": "headsha1",
            "head_branch": "feat-good",
            "pull_requests": [
                {
                    "id": 5004,
                    "number": 4,
                    "head": {"sha": "headsha1", "ref": "feat-good"},
                    "base": {"ref": "main"}
                }
            ]
        }
    }
    payload_bytes = json.dumps(cs_payload).encode("utf-8")
    headers = get_sig_headers(payload_bytes, event_type="check_suite")
    
    # Pre-setup a completed sync state in DB so that it triggers recommendation directly
    db_pr = db.query(PullRequest).filter(PullRequest.number == 4).first()
    db_pr.sync_integrity_status = "FULL_SUCCESS"
    db_pr.head_commit_sha = "headsha1"
    db.commit()

    with patch("app.services.github_app.get_rq_queue") as mock_rq, \
         patch("app.services.github_api_client.GitHubApiClient.get_pull_request") as mock_get_pr:
        mock_queue = MagicMock()
        mock_rq.return_value = mock_queue
        
        # Mock get_pull_request to return active open non-draft PR details
        mock_get_pr.return_value = {
            "id": 5004,
            "number": 4,
            "title": "Good PR",
            "user": {"login": "developer"},
            "state": "open",
            "draft": False,
            "head": {"sha": "headsha1", "ref": "feat-good"},
            "base": {"ref": "main"},
            "additions": 10,
            "deletions": 5,
            "changed_files": 2
        }
        
        response = client.post("/github/webhook", content=payload_bytes, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["prs_processed"] == 1
        
        # Verify recommendation task was enqueued directly
        mock_queue.enqueue.assert_called_once()
        args, kwargs = mock_queue.enqueue.call_args
        assert kwargs.get("job_id") == f"generate_recommendation_{db_pr.id}_headsha1"
        print("[OK] check_suite.completed correctly enqueued recommendation generation directly since PR was already synced.")

    # ----------------------------------------------------
    # Verification F: Integration - Sync Job enqueues Recommendation Generation on success
    # ----------------------------------------------------
    print("\n--- Testing End-to-End Pipeline Chaining ---")
    sync_job = db.query(PullRequestSyncJob).first()
    
    with patch("app.services.github_app.get_rq_queue") as mock_rq:
        mock_queue = MagicMock()
        mock_rq.return_value = mock_queue
        
        # Execute PR sync job completion handler (Phase B logic mock-trigger)
        from app.services.github_app import GitHubAppService
        service = GitHubAppService(db)
        
        # We manually call execute_pull_request_sync_job with patched client calls
        with patch.object(service.client, "get_pull_request_commits", return_value=([], True, 1, 1, None)), \
             patch.object(service.client, "get_pull_request_files", return_value=([], True, 1, 1, None)):
             
             service.execute_pull_request_sync_job(db_pr.id, installation_id, sync_job.id)
             
             # Verify it enqueued recommendation generation
             mock_queue.enqueue.assert_called_once()
             args, kwargs = mock_queue.enqueue.call_args
             assert "generate_recommendation_task_wrapper" in str(args[0])
             assert kwargs.get("job_id") == f"generate_recommendation_{db_pr.id}_{db_pr.head_commit_sha}"
             
             print("[OK] Successful execute_pull_request_sync_job successfully enqueued recommendation generation.")

    db.close()
    print("\n==================================================")
    print("ALL WEBHOOK PIPELINE INTEGRATION TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
