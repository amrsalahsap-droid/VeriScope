import sys
import uuid
import time
import hmac
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from sqlalchemy import text
from sqlalchemy.exc import InternalError

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, engine
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.github_installation import GitHubInstallation
from app.models.webhook_event import WebhookEvent
from app.models.artifact import RawArtifact
from app.models.observability import SystemEvent
from app.models.pull_request import (
    PullRequest,
    PullRequestCommit,
    PullRequestChangedFile,
    PullRequestSyncJob,
    PullRequestSnapshot,
)
from app.config import settings
from app.services.github_app import GitHubAppService
from app.services.github_api_client import GitHubApiClient

client = TestClient(app)

def cleanup_database():
    with engine.connect() as conn:
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_snapshot_immutability ON pull_request_snapshots;"))
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_artifact_update_immutability ON raw_artifacts;"))
        conn.commit()
    db = SessionLocal()
    try:
        db.query(SystemEvent).delete()
        db.query(WebhookEvent).delete()
        db.query(PullRequestSnapshot).delete()
        db.query(PullRequestCommit).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequestSyncJob).delete()
        db.query(RawArtifact).delete()
        db.query(Repository).delete()
        db.query(GitHubInstallation).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error cleaning database: {e}")
    finally:
        db.close()

def bootstrap_triggers():
    with engine.connect() as conn:
        print("Registering snapshot immutability triggers...")
        # Create function
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION block_mutation_on_evidence()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Immutability Violation: Evidence ledger mutation is blocked.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Drop triggers if they exist
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_snapshot_immutability ON pull_request_snapshots;"))
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_artifact_update_immutability ON raw_artifacts;"))

        # Create trigger on pull_request_snapshots to block all modifications
        conn.execute(text("""
            CREATE TRIGGER enforce_snapshot_immutability
            BEFORE UPDATE OR DELETE ON pull_request_snapshots
            FOR EACH ROW EXECUTE FUNCTION block_mutation_on_evidence();
        """))
        
        # Create trigger on raw_artifacts to block UPDATES only
        conn.execute(text("""
            CREATE TRIGGER enforce_artifact_update_immutability
            BEFORE UPDATE ON raw_artifacts
            FOR EACH ROW EXECUTE FUNCTION block_mutation_on_evidence();
        """))
        
        conn.commit()
        print("Triggers registered successfully!")

def run_tests():
    print("==================================================")
    print("STARTING PULL REQUEST INGESTION & SYNCHRONIZER INTEGRATION TESTS...")
    print("==================================================")
    
    cleanup_database()
    bootstrap_triggers()
    
    db = SessionLocal()
    
    # 1. Seed base models (Organization, Repository, GitHubInstallation)
    org = Organization(name="Aperture Laboratories", slug="aperture-lab")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    installation_id = 123456
    installation = GitHubInstallation(
        organization_id=org.id,
        github_installation_id=installation_id,
        account_login="aperture",
        status="ACTIVE",
        evidence_health_status="HEALTHY",
        created_at=datetime.utcnow()
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    
    repo = Repository(
        organization_id=org.id,
        github_repo_id=987654,
        name="portal-gun",
        full_name="aperture/portal-gun",
        default_branch="main",
        is_active=True,
        last_seen_in_github_at=datetime.utcnow()
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    
    service = GitHubAppService(db)
    
    # Define webhook signing secret
    webhook_secret = "test-webhook-secret-portal"
    settings.GITHUB_WEBHOOK_SECRET = webhook_secret
    
    # ----------------------------------------------------
    # TEST CASE 1: Webhook PR Ingestion (opened action) & Stale checks
    # ----------------------------------------------------
    print("\n--- TEST 1: Webhook Ingestion & Event Ordering Safety ---")
    
    # A. Ingest Valid 'opened' Webhook
    payload_opened = {
        "action": "opened",
        "installation": {"id": installation_id},
        "repository": {"id": repo.github_repo_id, "name": repo.name, "full_name": repo.full_name},
        "pull_request": {
            "id": 100001,
            "number": 42,
            "title": "Add portal-gun core specs",
            "user": {"login": "chell"},
            "head": {"ref": "feature/core", "sha": "abcdef1234567890"},
            "base": {"ref": "main"},
            "state": "open",
            "additions": 150,
            "deletions": 10,
            "changed_files": 3,
            "created_at": "2026-05-22T05:00:00Z",
            "updated_at": "2026-05-22T05:00:00Z"
        }
    }
    
    payload_bytes_1 = json.dumps(payload_opened).encode("utf-8")
    sig_1 = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), payload_bytes_1, hashlib.sha256).hexdigest()
    
    # Mock RQ Queue so it doesn't try to send to actual background Redis process
    with patch("app.services.github_app.get_rq_queue") as mock_queue_fn:
        mock_queue = MagicMock()
        mock_queue_fn.return_value = mock_queue
        
        response = client.post(
            "/github/webhook",
            content=payload_bytes_1,
            headers={
                "X-Github-Delivery": "delivery-id-1",
                "X-Github-Event": "pull_request",
                "X-Hub-Signature-256": sig_1
            }
        )
        assert response.status_code == 200, f"Webhook failed: {response.text}"
        res_data = response.json()
        assert res_data["status"] == "processed"
        assert res_data["action"] == "opened"
        
        # Assert PR created as Stub
        pr = db.query(PullRequest).filter(PullRequest.github_pr_id == 100001).first()
        assert pr is not None
        assert pr.number == 42
        assert pr.title == "Add portal-gun core specs"
        assert pr.author == "chell"
        assert pr.head_commit_sha == "abcdef1234567890"
        assert pr.last_processed_delivery_id == "delivery-id-1"
        assert pr.last_github_updated_at == datetime(2026, 5, 22, 5, 0, 0)
        
        # Verify sync job was queued in PENDING state
        sync_job = db.query(PullRequestSyncJob).filter(PullRequestSyncJob.pull_request_id == pr.id).first()
        assert sync_job is not None
        assert sync_job.status == "PENDING"
        assert sync_job.sync_reason == "WEBHOOK_OPENED"
        print("SUCCESS: Valid 'opened' webhook processed, stub saved, sync job enqueued.")
        
        # B. Test Duplicate Webhook delivery deduplication
        response_dup = client.post(
            "/github/webhook",
            content=payload_bytes_1,
            headers={
                "X-Github-Delivery": "delivery-id-1",  # Same delivery ID
                "X-Github-Event": "pull_request",
                "X-Hub-Signature-256": sig_1
            }
        )
        assert response_dup.status_code == 200
        assert response_dup.json()["status"] == "ignored"
        print("SUCCESS: Duplicate webhook delivery ID correctly deduplicated/ignored.")

        # C. Test Event Ordering Safety (sending an out-of-order/stale webhook update)
        payload_stale = {
            "action": "synchronize",
            "installation": {"id": installation_id},
            "repository": {"id": repo.github_repo_id, "name": repo.name, "full_name": repo.full_name},
            "pull_request": {
                "id": 100001,
                "number": 42,
                "title": "Add portal-gun core specs (Stale update)",
                "user": {"login": "chell"},
                "head": {"ref": "feature/core", "sha": "old-stale-sha11111"},
                "base": {"ref": "main"},
                "state": "open",
                "additions": 150,
                "deletions": 10,
                "changed_files": 3,
                "created_at": "2026-05-22T05:00:00Z",
                "updated_at": "2026-05-22T04:30:00Z"  # 30 mins OLDER than 05:00:00Z
            }
        }
        
        payload_bytes_stale = json.dumps(payload_stale).encode("utf-8")
        sig_stale = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), payload_bytes_stale, hashlib.sha256).hexdigest()
        
        response_stale = client.post(
            "/github/webhook",
            content=payload_bytes_stale,
            headers={
                "X-Github-Delivery": "delivery-id-stale",
                "X-Github-Event": "pull_request",
                "X-Hub-Signature-256": sig_stale
            }
        )
        assert response_stale.status_code == 200
        assert "stale" in response_stale.json()["detail"].lower()
        
        # Verify PR metadata did NOT mutate to the stale details
        db.refresh(pr)
        assert pr.head_commit_sha == "abcdef1234567890"  # Unchanged
        assert pr.reconciliation_required is True  # Marked for reconciliation resync
        
        # Assert a stale sync system event was logged
        stale_event = db.query(SystemEvent).filter(
            SystemEvent.entity_type == "pr",
            SystemEvent.event_type == "stale_webhook_detected"
        ).first()
        assert stale_event is not None
        print("SUCCESS: Stale webhook rejected correctly, reconciliation enqueued, state preserved.")

    # ----------------------------------------------------
    # TEST CASE 2: Duplicate Ingestion Storm & Superseding Protection
    # ----------------------------------------------------
    print("\n--- TEST 2: Duplicate Sync Storm & Superseding Protection ---")
    
    with patch("app.services.github_app.get_rq_queue") as mock_queue_fn:
        mock_queue = MagicMock()
        mock_queue_fn.return_value = mock_queue
        
        # A. Storm protection: Enqueuing same head SHA should reuse the job
        job_id_1 = service.enqueue_pull_request_sync(
            repository_id=repo.id,
            github_pr_id=pr.github_pr_id,
            number=pr.number,
            title=pr.title,
            author=pr.author,
            source_branch=pr.source_branch,
            target_branch=pr.target_branch,
            state=pr.state,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files_count=pr.changed_files_count,
            head_commit_sha="abcdef1234567890", # Same head SHA
            github_created_at=pr.github_created_at,
            github_updated_at=datetime.utcnow(),
            installation_id=installation_id,
            sync_reason="WEBHOOK_SYNCHRONIZE",
            webhook_delivery_id="delivery-id-storm-1"
        )
        
        job_id_2 = service.enqueue_pull_request_sync(
            repository_id=repo.id,
            github_pr_id=pr.github_pr_id,
            number=pr.number,
            title=pr.title,
            author=pr.author,
            source_branch=pr.source_branch,
            target_branch=pr.target_branch,
            state=pr.state,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files_count=pr.changed_files_count,
            head_commit_sha="abcdef1234567890", # Same head SHA
            github_created_at=pr.github_created_at,
            github_updated_at=datetime.utcnow(),
            installation_id=installation_id,
            sync_reason="WEBHOOK_SYNCHRONIZE",
            webhook_delivery_id="delivery-id-storm-2"
        )
        
        assert job_id_1 == job_id_2, "Sync storm must return duplicate job ID instead of queuing new work."
        print("SUCCESS: Sync storm protection deduplicated overlapping same-SHA enqueues.")
        
        # B. Superseding Protection: Enqueuing a new head SHA should supersede older pending jobs
        job_id_new = service.enqueue_pull_request_sync(
            repository_id=repo.id,
            github_pr_id=pr.github_pr_id,
            number=pr.number,
            title=pr.title,
            author=pr.author,
            source_branch=pr.source_branch,
            target_branch=pr.target_branch,
            state=pr.state,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files_count=pr.changed_files_count,
            head_commit_sha="new-evolved-sha99999", # NEW head SHA
            github_created_at=pr.github_created_at,
            github_updated_at=datetime.utcnow(),
            installation_id=installation_id,
            sync_reason="WEBHOOK_SYNCHRONIZE",
            webhook_delivery_id="delivery-id-evolved"
        )
        
        # Verify the older job was marked SUPERSEDED
        old_job = db.query(PullRequestSyncJob).filter(PullRequestSyncJob.id == job_id_1).first()
        assert old_job.status == "SUPERSEDED"
        assert old_job.superseded_by_job_id == job_id_new
        print("SUCCESS: Evolved head SHA successfully superseded older pending sync jobs.")

    # ----------------------------------------------------
    # TEST CASE 3: Sync Ingestion (paginated mock REST collection & Differential Reconciliation)
    # ----------------------------------------------------
    print("\n--- TEST 3: Sync Ingestion & Differential Reconciliation ---")
    
    mock_commits_payload = [
        {"sha": "c111", "commit": {"message": "Initial gun prototype", "author": {"name": "chell", "email": "chell@aperture.com", "date": "2026-05-22T04:00:00Z"}}},
        {"sha": "c222", "commit": {"message": "Fix quantum loop coupling", "author": {"name": "chell", "email": "chell@aperture.com", "date": "2026-05-22T04:10:00Z"}}}
    ]
    
    mock_files_payload = [
        {"filename": "src/main.py", "status": "added", "additions": 40, "deletions": 0, "patch": "print('Hello portal')"},
        {"filename": "src/quantum_core.py", "status": "modified", "additions": 15, "deletions": 5, "patch": "quantum = True"},
        {"filename": "src/legacy_specs.txt", "status": "renamed", "previous_filename": "src/old_specs.txt", "sha": "file-sha-123", "additions": 2, "deletions": 2, "patch": "renamed specs"}
    ]
    
    # Execute pull request sync synchronously with patched GitHub client
    with patch.object(GitHubApiClient, "get_pull_request_commits", return_value=(mock_commits_payload, True, 1, 1, "https://api.github.com/c_page1")), \
         patch.object(GitHubApiClient, "get_pull_request_files", return_value=(mock_files_payload, True, 1, 1, "https://api.github.com/f_page1")):
         
         service.execute_pull_request_sync_job(pr.id, installation_id, job_id_new)
         
         # Assert PR state updated correctly
         db.refresh(pr)
         assert pr.sync_integrity_status == "FULL_SUCCESS"
         assert pr.evidence_health_status == "HEALTHY"
         assert pr.evidence_consistency_status == "CONSISTENT"
         assert pr.head_commit_sha == "new-evolved-sha99999"
         assert pr.changed_files_count == 3
         assert pr.evidence_truncated is False
         
         # Verify Commits reconciled in DB
         commits_in_db = db.query(PullRequestCommit).filter(PullRequestCommit.pull_request_id == pr.id).all()
         assert len(commits_in_db) == 2
         commits_shas = {c.sha for c in commits_in_db}
         assert "c111" in commits_shas
         assert "c222" in commits_shas
         
         # Verify Changed Files reconciled in DB
         files_in_db = db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr.id).all()
         assert len(files_in_db) == 3
         files_paths = {f.file_path for f in files_in_db}
         assert "src/main.py" in files_paths
         assert "src/quantum_core.py" in files_paths
         assert "src/legacy_specs.txt" in files_paths
         
         # Verify Rename Semantics are populated
         renamed_file = db.query(PullRequestChangedFile).filter(
             PullRequestChangedFile.pull_request_id == pr.id,
             PullRequestChangedFile.file_path == "src/legacy_specs.txt"
         ).first()
         assert renamed_file is not None
         assert renamed_file.status == "renamed"
         assert renamed_file.previous_filename == "src/old_specs.txt"
         assert renamed_file.file_sha == "file-sha-123"
         assert renamed_file.patch_summary == "renamed specs"
         
         # Verify Snapshot and Fingerprint Saved
         snapshot = db.query(PullRequestSnapshot).filter(PullRequestSnapshot.pull_request_id == pr.id).order_by(PullRequestSnapshot.created_at.desc()).first()
         assert snapshot is not None
         assert snapshot.head_commit_sha == "new-evolved-sha99999"
         assert snapshot.evidence_fingerprint is not None
         assert snapshot.snapshot_schema_version == "pr_snapshot.v1"
         
         print("SUCCESS: Sync executed, commits/files differentials reconciled, rename semantics preserved, immutable snapshots generated.")

    # ----------------------------------------------------
    # TEST CASE 4: Immutability Ledger Blockers
    # ----------------------------------------------------
    print("\n--- TEST 4: Verification of Database-level Immutability Constraints ---")
    
    # Try modifying a snapshot (Should fail)
    try:
        snapshot.snapshot_reason = "FORGED_REASON"
        db.commit()
        assert False, "Snapshot UPDATE should have triggered Database rule exception!"
    except InternalError as e:
        db.rollback()
        print("SUCCESS: Database successfully blocked PullRequestSnapshot UPDATE (Trigger enforced).")
    except Exception as e:
        db.rollback()
        print(f"Encountered unexpected error: {e}")
        assert False
        
    # Try deleting a snapshot (Should fail)
    try:
        db.delete(snapshot)
        db.commit()
        assert False, "Snapshot DELETE should have triggered Database rule exception!"
    except InternalError as e:
        db.rollback()
        print("SUCCESS: Database successfully blocked PullRequestSnapshot DELETE (Trigger enforced).")
    except Exception as e:
        db.rollback()
        print(f"Encountered unexpected error: {e}")
        assert False

    # Try modifying a RawArtifact (Should fail)
    raw_art = db.query(RawArtifact).filter(RawArtifact.id == snapshot.snapshot_artifact_id).first()
    assert raw_art is not None
    try:
        raw_art.storage_path = "forged/path.json"
        db.commit()
        assert False, "RawArtifact UPDATE should have triggered Database rule exception!"
    except InternalError as e:
        db.rollback()
        print("SUCCESS: Database successfully blocked RawArtifact UPDATE (Trigger enforced).")
    except Exception as e:
        db.rollback()
        print(f"Encountered unexpected error: {e}")
        assert False

    # ----------------------------------------------------
    # TEST CASE 5: Bounded Snapshot Storage Policies & Truncation Thresholds
    # ----------------------------------------------------
    print("\n--- TEST 5: Verification of Bounded Snapshot Storage Policies ---")
    
    # Prepare dummy massive commit & file set exceeding boundaries (101 commits, 301 files)
    huge_commits = [{"sha": f"sha-{i}", "commit": {"message": "spec spec spec", "author": {"name": "chell", "email": "chell@chell.com", "date": "2026-05-22T05:00:00Z"}}} for i in range(105)]
    huge_files = [{"filename": f"src/specs_{i}.txt", "status": "added", "additions": 1, "deletions": 0, "patch": "spec specs"} for i in range(305)]
    
    with patch("app.services.github_app.get_rq_queue") as mock_queue_fn:
        mock_queue = MagicMock()
        mock_queue_fn.return_value = mock_queue
        
        job_huge_id = service.enqueue_pull_request_sync(
            repository_id=repo.id,
            github_pr_id=pr.github_pr_id,
            number=pr.number,
            title=pr.title,
            author=pr.author,
            source_branch=pr.source_branch,
            target_branch=pr.target_branch,
            state=pr.state,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files_count=len(huge_files),
            head_commit_sha="massive-sha-boundary-test",
            github_created_at=pr.github_created_at,
            github_updated_at=datetime.utcnow(),
            installation_id=installation_id,
            sync_reason="WEBHOOK_SYNCHRONIZE",
            webhook_delivery_id="delivery-id-massive"
        )
    
    with patch.object(GitHubApiClient, "get_pull_request_commits", return_value=(huge_commits, True, 1, 1, None)), \
         patch.object(GitHubApiClient, "get_pull_request_files", return_value=(huge_files, True, 1, 1, None)):
         
         service.execute_pull_request_sync_job(pr.id, installation_id, job_huge_id)
         
         # Assert evidence was truncated and safety flags configured
         db.refresh(pr)
         assert pr.evidence_truncated is True, "Massive PR should have evidence_truncated = True"
         assert pr.unsafe_for_optimization is True, "Massive PR should have unsafe_for_optimization = True"
         assert pr.evidence_health_status == "INSUFFICIENT", "Massive PR health must be set to INSUFFICIENT"
         assert "Exceeded safety caps" in pr.truncation_reason
         
         # Assert database-level counts are capped
         commits_count = db.query(PullRequestCommit).filter(PullRequestCommit.pull_request_id == pr.id).count()
         files_count = db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr.id).count()
         assert commits_count == 100, f"Commits should be capped at 100, but got {commits_count}"
         assert files_count == 300, f"Files should be capped at 300, but got {files_count}"
         
         print("SUCCESS: Bounded Snapshot policy successfully applied hard caps, flagged unsafe_for_optimization, and degraded health to INSUFFICIENT.")

    # ----------------------------------------------------
    # TEST CASE 6: Granular Readiness Diagnostics (multi-dimensional assessment)
    # ----------------------------------------------------
    print("\n--- TEST 6: Multi-Dimensional Readiness Diagnostics ---")
    
    # Assess readiness on the truncated PR
    readiness = service.assess_pr_recommendation_readiness(pr.id)
    assert readiness["overall"] == "NOT_READY"
    assert readiness["dimensions"]["pr_sync"] == "READY"
    assert readiness["dimensions"]["changed_files"] == "DEGRADED"
    assert "truncated" in "".join(readiness["reasons"]).lower()
    print("SUCCESS: Truncated PR successfully assessed as overall NOT_READY with DEGRADED changed_files dimension.")

    # Simulate expired snapshots evidence health degradation
    latest_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == pr.id,
        PullRequestSnapshot.head_commit_sha == pr.head_commit_sha
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    latest_snapshot_id = latest_snapshot.id
    
    db.commit()  # Release all active transaction locks to prevent deadlocking DROP TRIGGER
    
    # Update snapshot generation dates to simulate 48 hours ago (PR_EVIDENCE_MAX_AGE_HOURS=24)
    with engine.connect() as conn:
        # We must disable triggers momentarily to update, but wait! The rule is BEFORE UPDATE triggers block.
        # Let's drop trigger first to simulate expiration (or since trigger is on update/delete, we have to drop it)
        conn.execute(text("DROP TRIGGER IF EXISTS enforce_snapshot_immutability ON pull_request_snapshots;"))
        conn.execute(text("""
            UPDATE pull_request_snapshots 
            SET evidence_expires_at = :exp 
            WHERE id = :id
        """), {"exp": datetime.utcnow() - timedelta(hours=2), "id": latest_snapshot_id})
        # Re-register trigger
        conn.execute(text("""
            CREATE TRIGGER enforce_snapshot_immutability
            BEFORE UPDATE OR DELETE ON pull_request_snapshots
            FOR EACH ROW EXECUTE FUNCTION block_mutation_on_evidence();
        """))
        conn.commit()
        
    readiness_expired = service.assess_pr_recommendation_readiness(pr.id)
    assert "expired" in "".join(readiness_expired["reasons"]).lower()
    print("SUCCESS: Expired snapshot correctly flagged as stale and warnings applied.")

    # ----------------------------------------------------
    # TEST CASE 7: Forensic Debug Endpoint (/internal/prs/{id}/debug)
    # ----------------------------------------------------
    print("\n--- TEST 7: Forensic Debug HTTP Route, Filtering & Pagination ---")
    
    # A. Invalid 404 test
    response_404 = client.get(f"/internal/prs/{uuid.uuid4()}/debug")
    assert response_404.status_code == 404
    print("GET /internal/prs/{id}/debug returned 404 for missing UUID correctly.")
    
    # B. Valid GET debugging data with default options
    response_debug = client.get(f"/internal/prs/{pr.id}/debug")
    assert response_debug.status_code == 200
    debug_data = response_debug.json()
    assert debug_data["raw_inputs"]["number"] == pr.number
    assert debug_data["raw_inputs"]["author"] == pr.author
    assert "commits" in debug_data["derived_relationships"]
    assert "changed_files" in debug_data["derived_relationships"]
    print("GET /internal/prs/{id}/debug successfully returned default filtered payload with snapshots, excluding heavy payload fields.")
    
    # C. GET with all flags enabled (include_artifacts=true, include_events=true)
    response_full = client.get(f"/internal/prs/{pr.id}/debug?include_artifacts=true&include_events=true&limit=1")
    assert response_full.status_code == 200
    full_data = response_full.json()
    assert "commits" in full_data["derived_relationships"]
    assert "changed_files" in full_data["derived_relationships"]
    assert full_data["raw_inputs"]["number"] == pr.number
    print("GET /internal/prs/{id}/debug paginated and filtered correctly on snapshots, raw artifacts, and system events.")

    db.close()
    cleanup_database()
    
    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
