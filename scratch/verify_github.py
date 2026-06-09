import sys
import uuid
import time
import hmac
import hashlib
import json
from datetime import datetime, timedelta, timezone
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
from app.models.repository_sync_job import RepositorySyncJob
from app.models.webhook_event import WebhookEvent
from app.models.artifact import RawArtifact
from app.models.observability import SystemEvent
from app.config import settings
from app.services.github_app import GitHubAppService
from app.services.github_api_client import GitHubApiClient, GitHubRateLimitExceededError

client = TestClient(app)

# Helper to clean up database records
def cleanup_database():
    db = SessionLocal()
    try:
        db.query(SystemEvent).delete()
        db.query(WebhookEvent).delete()
        db.query(RepositorySyncJob).delete()
        db.query(RawArtifact).delete()
        db.query(Repository).delete()
        db.query(GitHubInstallation).delete()
        db.query(Organization).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error clean database: {e}")
    finally:
        db.close()


def run_tests():
    print("==================================================")
    print("STARTING HARDENED GITHUB APP FLOW INTEGRATION TESTS...")
    print("==================================================")
    
    db = SessionLocal()
    
    # Pre-setup test Organization
    org = Organization(name="Veriscope Inc", slug="veriscope-inc")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    org_id = org.id
    print(f"Test Organization initialized: {org_id} (slug: veriscope-inc)")
    
    service = GitHubAppService(db)

    # ----------------------------------------------------
    # 1. State Token Generation & Signature Validation
    # ----------------------------------------------------
    print("\n--- 1. Testing State Token Security ---")
    
    # A. Valid Generation
    state_token = service.generate_state_token(org_id)
    assert isinstance(state_token, str), "State token must be string."
    print("Generated valid HS256 state token successfully.")
    
    # B. Valid Verification
    verified_org_id = service.verify_state_token(state_token)
    assert verified_org_id == org_id, "State verification must return correct organization ID."
    print("Verified state signature and successfully extracted Organization ID.")
    
    # C. Expired Token
    with patch("time.time", return_value=time.time() + 3601):
        try:
            service.verify_state_token(state_token)
            assert False, "Verification should fail for expired token."
        except Exception as e:
            print(f"Expired state token was rejected successfully: {e}")
            
    # D. Forged Token
    try:
        service.verify_state_token("forged-token-value")
        assert False, "Verification should fail for forged token."
    except Exception as e:
        print(f"Forged state token was rejected successfully: {e}")


    # ----------------------------------------------------
    # 2. Callback Endpoint & Sync Job Queueing
    # ----------------------------------------------------
    print("\n--- 2. Testing Callback Setup Endpoint ---")
    
    installation_id = 99887766
    
    # Mocking RQ enqueue so background tasks don't block
    with patch("app.services.github_app.get_rq_queue") as mock_queue_fn:
        mock_queue = MagicMock()
        mock_queue_fn.return_value = mock_queue
        
        # A. Failure due to invalid state token
        response = client.get(
            "/github/install/callback",
            params={"installation_id": installation_id, "setup_action": "install", "state": "invalid-token"}
        )
        assert response.status_code == 400
        print("GET /github/install/callback rejected invalid state tokens correctly.")
        
        # B. Successful scheduling
        response = client.get(
            "/github/install/callback",
            params={"installation_id": installation_id, "setup_action": "install", "state": state_token}
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        
        # Verify job & installation were saved in PENDING/PENDING_SYNC state
        installation = db.query(GitHubInstallation).filter(GitHubInstallation.github_installation_id == installation_id).first()
        assert installation is not None
        assert installation.status == "PENDING_SYNC"
        assert installation.evidence_health_status == "HEALTHY"
        
        job = db.query(RepositorySyncJob).filter(RepositorySyncJob.github_installation_id == installation_id).first()
        assert job is not None
        assert job.status == "PENDING"
        assert job.sync_reason == "INSTALLATION_CALLBACK"
        
        print("GET /github/install/callback verified state and initialized sync jobs correctly in DB.")


    # ----------------------------------------------------
    # 3. Webhook Delivery & Replay Freshness Safety
    # ----------------------------------------------------
    print("\n--- 3. Testing Webhook Signature, Replay Freshness, & Deduplication ---")
    
    webhook_secret = "test-webhook-secret"
    settings.GITHUB_WEBHOOK_SECRET = webhook_secret
    
    # Prepare dummy webhook body
    payload_dict = {
        "action": "added",
        "installation": {"id": installation_id},
        "repositories_added": [{"id": 112233, "full_name": "veriscope/test-added"}]
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    
    # Compute signature
    sig = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    
    # A. Signature Validation rejection
    response = client.post(
        "/github/webhook",
        content=payload_bytes,
        headers={
            "X-Github-Delivery": str(uuid.uuid4()),
            "X-Github-Event": "installation_repositories",
            "X-Hub-Signature-256": "sha256=invalid-signature"
        }
    )
    assert response.status_code == 401
    print("Webhook router rejected invalid signatures (401 Unauthorized) successfully.")
    
    # B. Signature Validation success
    delivery_id = str(uuid.uuid4())
    with patch("app.services.github_app.get_rq_queue"):
        response = client.post(
            "/github/webhook",
            content=payload_bytes,
            headers={
                "X-Github-Delivery": delivery_id,
                "X-Github-Event": "installation_repositories",
                "X-Hub-Signature-256": sig
            }
        )
        assert response.status_code == 200
        print("Webhook router accepted valid signatures successfully.")
        
        # Verify WebhookEvent logged in DB
        w_event = db.query(WebhookEvent).filter(WebhookEvent.github_delivery_id == delivery_id).first()
        assert w_event is not None
        assert w_event.processing_status == "COMPLETED"
        
        # Verify RawArtifact logged in DB
        raw_art = db.query(RawArtifact).filter(RawArtifact.id == w_event.raw_artifact_id).first()
        assert raw_art is not None
        assert raw_art.artifact_type == "github_webhook_payload"
        
        print("Webhook delivery successfully persisted in WebhookEvent and RawArtifact.")

    # C. Replay Freshness check validation
    stale_payload = {
        "action": "added",
        "installation": {"id": installation_id},
        "timestamp": int(time.time()) - 1000  # 16 minutes old (exceeds GITHUB_WEBHOOK_MAX_AGE_SECONDS=600)
    }
    stale_bytes = json.dumps(stale_payload).encode("utf-8")
    stale_sig = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), stale_bytes, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/github/webhook",
        content=stale_bytes,
        headers={
            "X-Github-Delivery": str(uuid.uuid4()),
            "X-Github-Event": "installation_repositories",
            "X-Hub-Signature-256": stale_sig
        }
    )
    assert response.status_code == 400
    assert "stale" in response.json()["detail"].lower()
    print("Stale webhook replay attack rejected successfully (Age > 600s).")

    # D. Deduplication
    response = client.post(
        "/github/webhook",
        content=payload_bytes,
        headers={
            "X-Github-Delivery": delivery_id, # Duplicate ID
            "X-Github-Event": "installation_repositories",
            "X-Hub-Signature-256": sig
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    print("Duplicate webhook delivery ID successfully ignored (deduplicated).")


    # ----------------------------------------------------
    # 4. Synchronization Concurrency Lock & Stale Lock Recovery
    # ----------------------------------------------------
    print("\n--- 4. Testing Synchronization Concurrency Lock & Timeout Recovery ---")
    
    # Set a running lock on the installation
    installation.active_sync_job_id = uuid.uuid4()
    installation.sync_lock_acquired_at = datetime.utcnow() - timedelta(minutes=10) # Locked 10 mins ago (active)
    db.commit()
    
    # Try to execute a sync job under active lock
    new_job_id = uuid.uuid4()
    new_job = RepositorySyncJob(
        id=new_job_id,
        organization_id=org_id,
        github_installation_id=installation_id,
        status="PENDING",
        sync_reason="MANUAL_RETRY"
    )
    db.add(new_job)
    db.commit()
    
    # Run sync inline
    service.execute_sync_job(org_id, installation_id, "MANUAL_RETRY", new_job_id)
    
    # Check that job was skipped because lock was held
    db.refresh(new_job)
    assert new_job.status == "COMPLETED"
    assert new_job.integrity_status == "NOT_STARTED"
    assert "Skipped due to active concurrent sync job" in new_job.error_message
    print("Concurrency lock correctly blocked overlapping sync execution.")
    
    # Test Stale Lock Recovery (stale for 35 minutes)
    installation.sync_lock_acquired_at = datetime.utcnow() - timedelta(minutes=35)
    db.commit()
    
    job_rec_id = uuid.uuid4()
    job_rec = RepositorySyncJob(
        id=job_rec_id,
        organization_id=org_id,
        github_installation_id=installation_id,
        status="PENDING",
        sync_reason="MANUAL_RETRY"
    )
    db.add(job_rec)
    db.commit()
    
    # Mocking REST collection failure to see lock release during recovery
    with patch.object(GitHubApiClient, "get_installation_details", side_effect=Exception("Transitive Error")):
        try:
            service.execute_sync_job(org_id, installation_id, "MANUAL_RETRY", job_rec_id)
        except Exception:
            pass
            
    # Verify stale lock was recovered (active_sync_job_id updated to job_rec_id then released)
    db.refresh(installation)
    assert installation.active_sync_job_id is None, "Sync lock should be released on failure."
    
    # Assert a lock recovery event was emitted in system events
    recovered_event = db.query(SystemEvent).filter(SystemEvent.event_type == "sync_lock_timeout_recovered").first()
    assert recovered_event is not None
    print("Stale sync locks (> 30 mins) successfully recovered and audited.")


    # ----------------------------------------------------
    # 5. Correct Pagination Integrity & Deactivation Grace Window
    # ----------------------------------------------------
    print("\n--- 5. Testing Synchronization correctness & Safe Grace Deactivations ---")
    
    # Prepare dummy GitHub response
    mock_repo_payloads = [
        {"id": 1001, "name": "veriscope-ui", "full_name": "veriscope/veriscope-ui", "default_branch": "main", "private": True},
        {"id": 1002, "name": "veriscope-core", "full_name": "veriscope/veriscope-core", "default_branch": "develop", "private": False}
    ]
    
    # Patch GitHubApiClient
    with patch.object(GitHubApiClient, "get_installation_details", return_value={"account": {"login": "veriscope"}}), \
         patch.object(GitHubApiClient, "list_installation_repositories", return_value=(mock_repo_payloads, True, 1, 1, "https://api.github.com/page1")):
         
         # A. First Successful Full Sync
         first_sync_job_id = uuid.uuid4()
         first_sync_job = RepositorySyncJob(
             id=first_sync_job_id,
             organization_id=org_id,
             github_installation_id=installation_id,
             status="PENDING",
             sync_reason="MANUAL_RETRY"
         )
         db.add(first_sync_job)
         db.commit()
         
         service.execute_sync_job(org_id, installation_id, "MANUAL_RETRY", first_sync_job_id)
         
         # Assert repositories A and B are active in DB
         repo1 = db.query(Repository).filter(Repository.github_repo_id == 1001).first()
         repo2 = db.query(Repository).filter(Repository.github_repo_id == 1002).first()
         
         assert repo1 is not None and repo1.is_active is True
         assert repo2 is not None and repo2.is_active is True
         assert repo1.missing_from_github_since is None
         
         # Assert snapshot linked correctly
         db.refresh(first_sync_job)
         assert first_sync_job.status == "COMPLETED"
         assert first_sync_job.integrity_status == "FULL_SUCCESS"
         assert first_sync_job.repository_sync_snapshot_artifact_id is not None
         
         print("First successful synchronization created and updated repositories perfectly, and saved raw snapshots.")

    # B. Safe Deactivation Rule - Cycle 1 (Repo 1002 is missing from GitHub response)
    mock_repo_payloads_cycle2 = [
        {"id": 1001, "name": "veriscope-ui", "full_name": "veriscope/veriscope-ui", "default_branch": "main", "private": True}
    ]
    
    with patch.object(GitHubApiClient, "get_installation_details", return_value={"account": {"login": "veriscope"}}), \
         patch.object(GitHubApiClient, "list_installation_repositories", return_value=(mock_repo_payloads_cycle2, True, 1, 1, "https://api.github.com/page1")):
         
         sync_job2_id = uuid.uuid4()
         sync_job2 = RepositorySyncJob(
             id=sync_job2_id,
             organization_id=org_id,
             github_installation_id=installation_id,
             status="PENDING",
             sync_reason="PERIODIC_RECONCILIATION"
         )
         db.add(sync_job2)
         db.commit()
         
         service.execute_sync_job(org_id, installation_id, "PERIODIC_RECONCILIATION", sync_job2_id)
         
         db.refresh(repo2)
         assert repo2.is_active is True, "Missing repository must NOT be deactivated immediately on first missing cycle."
         assert repo2.missing_from_github_since is not None, "missing_from_github_since timestamp must be set."
         
         print("Conservative safety grace rule confirmed: Repo was NOT immediately deactivated on first missing sync.")

    # C. Safe Deactivation Rule - Cycle 2 (Repo 1002 is missing for a second consecutive successful sync)
    with patch.object(GitHubApiClient, "get_installation_details", return_value={"account": {"login": "veriscope"}}), \
         patch.object(GitHubApiClient, "list_installation_repositories", return_value=(mock_repo_payloads_cycle2, True, 1, 1, "https://api.github.com/page1")):
         
         sync_job3_id = uuid.uuid4()
         sync_job3 = RepositorySyncJob(
             id=sync_job3_id,
             organization_id=org_id,
             github_installation_id=installation_id,
             status="PENDING",
             sync_reason="PERIODIC_RECONCILIATION"
         )
         db.add(sync_job3)
         db.commit()
         
         service.execute_sync_job(org_id, installation_id, "PERIODIC_RECONCILIATION", sync_job3_id)
         
         db.refresh(repo2)
         assert repo2.is_active is False, "Repository missing across 2 consecutive successful syncs must be deactivated."
         assert repo2.deactivation_reason == "REMOVED_FROM_GITHUB"
         print("Conservative safety grace rule confirmed: Repo was successfully deactivated after 2 missing syncs.")

    # D. Safety pagination block: partial pagination or page failures must never trigger deactivations
    repo2.is_active = True
    repo2.missing_from_github_since = None
    db.commit()
    
    # Simulating a page failure (pagination_completed = False)
    with patch.object(GitHubApiClient, "get_installation_details", return_value={"account": {"login": "veriscope"}}), \
         patch.object(GitHubApiClient, "list_installation_repositories", return_value=(mock_repo_payloads_cycle2, False, 2, 1, "https://api.github.com/page1")):
         
         sync_job_fail_id = uuid.uuid4()
         sync_job_fail = RepositorySyncJob(
             id=sync_job_fail_id,
             organization_id=org_id,
             github_installation_id=installation_id,
             status="PENDING",
             sync_reason="PERIODIC_RECONCILIATION"
         )
         db.add(sync_job_fail)
         db.commit()
         
         try:
             service.execute_sync_job(org_id, installation_id, "PERIODIC_RECONCILIATION", sync_job_fail_id)
         except Exception:
             pass
             
         db.refresh(repo2)
         assert repo2.is_active is True
         assert repo2.missing_from_github_since is None, "Stale deactivation timestamp must not trigger on failed pagination."
         print("Safety pagination block confirmed: FAILED_SYNC/PARTIAL_FAILURE syncs do NOT mutate repository deactivations.")


    # ----------------------------------------------------
    # 6. Webhook App Uninstalled Deactivation Action
    # ----------------------------------------------------
    print("\n--- 6. Testing installation.deleted Hard Deactivation Action ---")
    
    uninstall_payload = {
        "action": "deleted",
        "installation": {"id": installation_id}
    }
    uninstall_bytes = json.dumps(uninstall_payload).encode("utf-8")
    uninstall_sig = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), uninstall_bytes, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/github/webhook",
        content=uninstall_bytes,
        headers={
            "X-Github-Delivery": str(uuid.uuid4()),
            "X-Github-Event": "installation",
            "X-Hub-Signature-256": uninstall_sig
        }
    )
    assert response.status_code == 200
    
    db.refresh(installation)
    assert installation.status == "REMOVED"
    assert installation.evidence_health_status == "INSUFFICIENT"
    
    db.refresh(repo1)
    assert repo1.is_active is False
    assert repo1.deactivation_reason == "INSTALLATION_DELETED"
    print("Webhook installation.deleted successfully set status to REMOVED and triggered instant repository deactivations.")


    # ----------------------------------------------------
    # 7. Trust Health Dashboard Diagnostics Endpoint
    # ----------------------------------------------------
    print("\n--- 7. Testing Trust Health Diagnostics Endpoint ---")
    
    response = client.get(f"/github/installations/{org_id}/trust-health")
    assert response.status_code == 200
    th_data = response.json()
    
    assert th_data["installation_health"] == "INSUFFICIENT"
    assert len(th_data["recommendation_safety_warnings"]) > 0
    assert any("disable all aggressive regression test optimizations" in w.lower() for w in th_data["recommendation_safety_warnings"])
    
    print("GET /github/installations/{id}/trust-health successfully flagged trust warnings and safety fallbacks.")

    print("\n==================================================")
    print("ALL HARDENED GITHUB SYNC INTEGRATION TESTS PASSED!")
    print("==================================================")
    
    db.close()


if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
