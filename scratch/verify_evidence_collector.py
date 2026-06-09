import os
import sys
import uuid
import datetime
from pathlib import Path
from fastapi import HTTPException

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import (
    PullRequest,
    PullRequestChangedFile,
    PullRequestSnapshot,
)
from app.models.artifact import RawArtifact
from app.services.recommendation_evidence_collector import RecommendationEvidenceCollector


def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(PullRequestSnapshot).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.query(RawArtifact).delete()
        db.commit()
        print("Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_verification():
    print("======================================================================")
    print("STARTING PR EVIDENCE COLLECTOR SERVICE INTEGRATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seed base Organization and Repository
        org = Organization(id=org_id, name="Evidence Test Corp", slug="evidence-test-corp")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=999111,
            name="evidence-core",
            full_name="evidence-test-corp/evidence-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # ----------------------------------------------------
        # TEST 1: Healthy PR, deterministic file sorting, and lookup methods
        # ----------------------------------------------------
        print("\n--- TEST 1: Healthy PR & Multi-format Lookup & Sorting ---")
        pr1_id = uuid.uuid4()
        pr1_commit = "sha_healthy_11111111111111111111"
        pr1 = PullRequest(
            id=pr1_id,
            repository_id=repo_id,
            github_pr_id=10001,
            number=42,
            title="Healthy PR",
            author="engineer-alice",
            source_branch="alice-patch",
            target_branch="main",
            state="open",
            additions=30,
            deletions=5,
            changed_files_count=3,
            head_commit_sha=pr1_commit,
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr1)

        # Add changed files out of order to verify sorting
        file_c = PullRequestChangedFile(
            pull_request_id=pr1_id,
            file_path="src/controllers/user.py",
            status="modified",
            additions=10,
            deletions=2
        )
        file_a = PullRequestChangedFile(
            pull_request_id=pr1_id,
            file_path="app/main.py",
            status="modified",
            additions=5,
            deletions=1
        )
        file_b = PullRequestChangedFile(
            pull_request_id=pr1_id,
            file_path="src/auth.py",
            status="added",
            additions=15,
            deletions=2
        )
        db.add(file_c)
        db.add(file_a)
        db.add(file_b)

        # Seed raw artifact for snapshot
        art1 = RawArtifact(
            id=uuid.uuid4(),
            artifact_type="github_pr_snapshot",
            storage_path="snapshots/dummy.json",
            artifact_metadata={"dummy": True}
        )
        db.add(art1)
        db.flush()

        # Seed Snapshot to verify binding
        snap1 = PullRequestSnapshot(
            id=uuid.uuid4(),
            pull_request_id=pr1_id,
            repository_id=repo_id,
            head_commit_sha=pr1_commit,
            github_pr_updated_at=datetime.datetime.utcnow(),
            snapshot_reason="TEST",
            snapshot_schema_version="pr_snapshot.v1",
            normalization_engine_version="1.0.0",
            snapshot_artifact_id=art1.id,
            evidence_health_status="HEALTHY",
            sync_integrity_status="FULL_SUCCESS"
        )
        db.add(snap1)
        db.commit()

        # A. Verify lookup by UUID
        bundle_uuid = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, pr1_id)
        assert bundle_uuid.pull_request_id == pr1_id
        assert bundle_uuid.repository_id == repo_id
        assert bundle_uuid.head_commit_sha == pr1_commit
        assert bundle_uuid.pr_snapshot_id == snap1.id
        assert bundle_uuid.recommendation_readiness_state == "READY"
        assert bundle_uuid.unsafe_for_optimization is False

        # Verify deterministic alphabetical sorting by file_path
        files = bundle_uuid.changed_files
        assert len(files) == 3
        assert files[0].file_path == "app/main.py"
        assert files[1].file_path == "src/auth.py"
        assert files[2].file_path == "src/controllers/user.py"
        print("  - Lookup by UUID and deterministic sorting verified.")

        # B. Verify lookup by string UUID
        bundle_str_uuid = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, str(pr1_id))
        assert bundle_str_uuid.pull_request_id == pr1_id
        print("  - Lookup by string UUID verified.")

        # C. Verify lookup by PR number (int)
        bundle_num_int = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, 42)
        assert bundle_num_int.pull_request_id == pr1_id
        print("  - Lookup by integer PR number verified.")

        # D. Verify lookup by PR number (string)
        bundle_num_str = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, "42")
        assert bundle_num_str.pull_request_id == pr1_id
        print("  - Lookup by string PR number verified.")

        # E. Verify lookup by head commit SHA
        bundle_sha = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, pr1_commit)
        assert bundle_sha.pull_request_id == pr1_id
        print("  - Lookup by head commit SHA verified.")

        # ----------------------------------------------------
        # TEST 2: Rule 1 - Sync Integrity FAILED/PARTIAL_FAILURE
        # ----------------------------------------------------
        print("\n--- TEST 2: Sync Integrity Failures (Rule 1) ---")
        pr2_id = uuid.uuid4()
        pr2 = PullRequest(
            id=pr2_id,
            repository_id=repo_id,
            github_pr_id=10002,
            number=43,
            title="Failed Sync PR",
            author="engineer-alice",
            source_branch="failed-patch",
            target_branch="main",
            state="open",
            additions=0,
            deletions=0,
            changed_files_count=0,
            head_commit_sha="sha_failed_22222222222222222222",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FAILED",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr2)
        db.commit()

        # Since sync integrity is FAILED and there are no changed files,
        # unsafe_for_optimization must be True.
        bundle_failed_sync = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, pr2_id)
        assert bundle_failed_sync.unsafe_for_optimization is True
        assert any("sync integrity" in r.lower() for r in bundle_failed_sync.readiness_reasons)
        assert any("changed files" in r.lower() for r in bundle_failed_sync.readiness_reasons)
        assert bundle_failed_sync.recommendation_readiness_state == "NOT_READY"
        print("  - FAILED sync integrity with missing files marked unsafe and NOT_READY.")

        # ----------------------------------------------------
        # TEST 3: Rule 2 - Evidence Health Status INSUFFICIENT
        # ----------------------------------------------------
        print("\n--- TEST 3: Insufficient Evidence Health (Rule 2) ---")
        pr3_id = uuid.uuid4()
        pr3 = PullRequest(
            id=pr3_id,
            repository_id=repo_id,
            github_pr_id=10003,
            number=44,
            title="Insufficient PR",
            author="engineer-alice",
            source_branch="insufficient-patch",
            target_branch="main",
            state="open",
            additions=10,
            deletions=2,
            changed_files_count=1,
            head_commit_sha="sha_insufficient_3333333333333333",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="INSUFFICIENT",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr3)
        # Add one changed file so changed files are not empty
        db.add(PullRequestChangedFile(
            pull_request_id=pr3_id,
            file_path="src/core.py",
            status="modified",
            additions=10,
            deletions=2
        ))
        db.commit()

        bundle_insufficient = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, pr3_id)
        assert bundle_insufficient.evidence_health_status == "INSUFFICIENT"
        assert bundle_insufficient.recommendation_readiness_state == "NOT_READY"
        assert any("insufficient" in r.lower() for r in bundle_insufficient.readiness_reasons)
        print("  - Insufficient health state detected correctly.")

        # ----------------------------------------------------
        # TEST 4: Rule 3 - Empty Changed Files List
        # ----------------------------------------------------
        print("\n--- TEST 4: Empty Changed Files List (Rule 3) ---")
        pr4_id = uuid.uuid4()
        pr4 = PullRequest(
            id=pr4_id,
            repository_id=repo_id,
            github_pr_id=10004,
            number=45,
            title="Empty Files PR",
            author="engineer-alice",
            source_branch="empty-patch",
            target_branch="main",
            state="open",
            additions=0,
            deletions=0,
            changed_files_count=0,
            head_commit_sha="sha_empty_444444444444444444444",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr4)
        db.commit()

        bundle_empty = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, pr4_id)
        assert bundle_empty.unsafe_for_optimization is True
        assert any("no changed files available" in r.lower() for r in bundle_empty.readiness_reasons)
        print("  - Empty changed files list correctly flagged unsafe_for_optimization.")

        # ----------------------------------------------------
        # TEST 5: Rule 4 - Evidence Truncated
        # ----------------------------------------------------
        print("\n--- TEST 5: Truncated Evidence (Rule 4) ---")
        pr5_id = uuid.uuid4()
        pr5 = PullRequest(
            id=pr5_id,
            repository_id=repo_id,
            github_pr_id=10005,
            number=46,
            title="Truncated PR",
            author="engineer-alice",
            source_branch="trunc-patch",
            target_branch="main",
            state="open",
            additions=1000,
            deletions=500,
            changed_files_count=400,
            head_commit_sha="sha_truncated_555555555555555555",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT",
            evidence_truncated=True,
            truncation_reason="Exceeded safety cap of 300 files"
        )
        db.add(pr5)
        db.add(PullRequestChangedFile(
            pull_request_id=pr5_id,
            file_path="src/huge.py",
            status="modified",
            additions=1000,
            deletions=500
        ))
        db.commit()

        bundle_truncated = RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, pr5_id)
        assert bundle_truncated.unsafe_for_optimization is True
        assert any("truncated" in r.lower() for r in bundle_truncated.readiness_reasons)
        assert any("exceeded safety cap" in r.lower() for r in bundle_truncated.readiness_reasons)
        print("  - Truncated evidence correctly flagged unsafe_for_optimization with reasons.")

        # ----------------------------------------------------
        # TEST 6: PR Not Found & Invalid UUID
        # ----------------------------------------------------
        print("\n--- TEST 6: Error Handling for Non-existent PRs ---")
        try:
            RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, uuid.uuid4())
            assert False, "Should have raised HTTPException for missing UUID!"
        except HTTPException as e:
            assert e.status_code == 404
            print("  - Correctly raised 404 for missing UUID.")

        try:
            RecommendationEvidenceCollector.collect_pr_evidence(db, repo_id, 99999)
            assert False, "Should have raised HTTPException for missing number!"
        except HTTPException as e:
            assert e.status_code == 404
            print("  - Correctly raised 404 for missing PR number.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL PR EVIDENCE COLLECTOR INTEGRATION VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
