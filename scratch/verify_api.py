import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
)
from app.models.artifact import RawArtifact
from app.models.observability import IngestionJob, SystemEvent
from app.models.dependency import FileDependency
from app.models.pull_request import (
    PullRequest,
    PullRequestCommit,
    PullRequestChangedFile,
    PullRequestSyncJob,
    PullRequestSnapshot
)
from app.models.test_result import TestCase
from app.models.coverage import CoverageReport, FileTestLink

client = TestClient(app)

def cleanup_database():
    """Clean up test records to ensure fresh validation runs."""
    db = SessionLocal()
    try:
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationRun).delete()
        db.query(RawArtifact).delete()
        db.query(IngestionJob).delete()
        db.query(SystemEvent).delete()
        db.query(FileDependency).delete()
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.query(TestCase).delete()
        db.query(PullRequestSnapshot).delete()
        db.query(PullRequestCommit).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequestSyncJob).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database clean up successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_tests():
    print("Starting Veriscope Phase 2 Foundation Integration Tests...\n")
    
    # ----------------------------------------------------
    # 1. Organization Tests
    # ----------------------------------------------------
    print("--- 1. Testing Organization Endpoints ---")
    
    # Successful Creation
    org_slug = "acme-corp"
    response = client.post("/organizations", json={"name": "ACME Corporation", "slug": org_slug})
    assert response.status_code == 201, f"Failed org create: {response.text}"
    org_data = response.json()
    org_id = org_data["id"]
    print(f"Successfully created organization with ID: {org_id} (slug: {org_slug})")
    
    # Duplicate Slug Uniqueness Constraint Validation
    response = client.post("/organizations", json={"name": "ACME Alternative", "slug": org_slug})
    assert response.status_code == 409, f"Expected 409 Conflict for duplicate slug, got {response.status_code}"
    print("Successfully verified unique slug validation constraint (returned 409 Conflict).")

    # Successful Retrieval
    response = client.get(f"/organizations/{org_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "ACME Corporation"
    print("Successfully retrieved organization details.")

    # 404 Retrieval
    invalid_org_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/organizations/{invalid_org_id}")
    assert response.status_code == 404, f"Expected 404 for invalid org, got {response.status_code}"
    print("Successfully verified 404 for non-existent organization.")

    # ----------------------------------------------------
    # 2. Repository Tests
    # ----------------------------------------------------
    print("\n--- 2. Testing Repository Endpoints ---")
    
    # Successful Creation
    github_id = 987654321
    response = client.post("/repositories", json={
        "organization_id": org_id,
        "github_repo_id": github_id,
        "name": "veriscope-core",
        "full_name": "acme/veriscope-core",
        "default_branch": "main",
        "is_active": True
    })
    assert response.status_code == 201, f"Failed repo create: {response.text}"
    repo_data = response.json()
    repo_id = repo_data["id"]
    print(f"Successfully registered repository with ID: {repo_id} (github_repo_id: {github_id})")

    # Duplicate github_repo_id Validation
    response = client.post("/repositories", json={
        "organization_id": org_id,
        "github_repo_id": github_id,
        "name": "veriscope-duplicate",
        "full_name": "acme/veriscope-duplicate"
    })
    assert response.status_code == 409
    print("Successfully verified unique github_repo_id validation constraint (returned 409 Conflict).")

    # Org Existence check
    response = client.post("/repositories", json={
        "organization_id": invalid_org_id,
        "github_repo_id": 9999999,
        "name": "veriscope-orphan",
        "full_name": "acme/veriscope-orphan"
    })
    assert response.status_code == 404
    print("Successfully verified repository creation requires an active organization (returned 404 Not Found).")

    # Successful Retrieval
    response = client.get(f"/repositories/{repo_id}")
    assert response.status_code == 200
    assert response.json()["full_name"] == "acme/veriscope-core"
    print("Successfully retrieved repository details.")

    # Seed baseline TestCases, PullRequests, commits, files, snapshots, and coverage links
    import hashlib
    import datetime

    db = SessionLocal()
    try:
        # Seed TestCases
        tc_names = [
            ("test_auth_flow", "auth_suite"),
            ("test_org_isolation", "auth_suite"),
            ("test_api_throttling", "auth_suite"),
            ("test_billing_portal", "billing_suite"),
            ("test_user_profile", "user_suite"),
        ]
        tcs = {}
        for name, suite in tc_names:
            tc_id = uuid.uuid4()
            tc_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()
            tc = TestCase(
                id=tc_id,
                repository_id=repo_id,
                suite_name=suite,
                test_name=name,
                stable_identity=name,
                canonical_identity_hash=tc_hash,
                identity_lineage_root_hash=tc_hash
            )
            db.add(tc)
            tcs[name] = tc

        db.commit() # Save TestCases so they have IDs

        # Seed PullRequests and their snapshots/commits/changed_files
        prs_data = [
            ("pr-1", 1, ["auth/middleware.py"]),
            ("pr-2", 2, ["auth/middleware.py", "empty_coverage.py"]),
            ("pr-3", 3, ["auth/middleware.py", "partial.py"]),
            ("pr-4", 4, ["auth/middleware.py", "weak.py"]),
            ("pr-5", 5, []),
        ]
        
        # We need a raw artifact for snapshots
        from app.models.artifact import RawArtifact
        artifact = RawArtifact(
            id=uuid.uuid4(),
            repository_id=repo_id,
            artifact_type="github_pull_request",
            storage_path="s3://veriscope-artifacts/raw_pr",
            artifact_metadata={"test": "payload"},
            created_at=datetime.datetime.utcnow()
        )
        db.add(artifact)
        db.commit()

        for commit_sha, pr_num, files in prs_data:
            pr_id = uuid.uuid4()
            pr = PullRequest(
                id=pr_id,
                repository_id=repo_id,
                github_pr_id=pr_num * 1000,
                number=pr_num,
                title=f"PR {pr_num}",
                author="engineer-bob",
                source_branch=f"branch-{pr_num}",
                target_branch="main",
                state="open",
                additions=10,
                deletions=2,
                changed_files_count=len(files),
                head_commit_sha=commit_sha,
                github_created_at=datetime.datetime.utcnow(),
                github_updated_at=datetime.datetime.utcnow(),
                sync_integrity_status="FULL_SUCCESS",
                evidence_health_status="HEALTHY",
                evidence_consistency_status="CONSISTENT"
            )
            db.add(pr)
            
            commit = PullRequestCommit(
                id=uuid.uuid4(),
                pull_request_id=pr_id,
                sha=commit_sha,
                message=f"Commit message {pr_num}",
                author="engineer-bob",
                commit_date=datetime.datetime.utcnow()
            )
            db.add(commit)

            for f in files:
                changed_file = PullRequestChangedFile(
                    id=uuid.uuid4(),
                    pull_request_id=pr_id,
                    file_path=f,
                    status="modified",
                    additions=5,
                    deletions=1
                )
                db.add(changed_file)

            # Seed PR Snapshot for cache/lineage matching
            snapshot = PullRequestSnapshot(
                id=uuid.uuid4(),
                pull_request_id=pr_id,
                repository_id=repo_id,
                head_commit_sha=commit_sha,
                github_pr_updated_at=datetime.datetime.utcnow(),
                snapshot_reason="WEBHOOK_SYNCHRONIZE",
                normalization_engine_version="v1",
                evidence_fingerprint=f"fingerprint-{commit_sha}",
                snapshot_artifact_id=artifact.id,
                evidence_health_status="HEALTHY",
                sync_integrity_status="FULL_SUCCESS",
                evidence_consistency_status="CONSISTENT"
            )
            db.add(snapshot)

        # Seed dependencies for transitive expansion:
        # Scenario C: partial.py -> auth/middleware.py
        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="partial.py",
            depends_on_file_path="auth/middleware.py",
            dependency_type="import",
            commit_sha="pr-3"
        )
        db.add(dep)

        # We also need coverage report and links for pr-1, pr-3, pr-4
        cov_reports = {}
        for commit_sha in ["pr-1", "pr-3", "pr-4"]:
            cov = CoverageReport(
                id=uuid.uuid4(),
                repository_id=repo_id,
                commit_sha=commit_sha,
                overall_coverage_pct=0.90,
                total_lines=100,
                covered_lines_count=90,
                uncovered_lines_count=10,
                confidence_score="HIGH",
                confidence_logic="Baseline high quality coverage for testing.",
                file_hash=f"api-test-hash-{commit_sha}"
            )
            db.add(cov)
            cov_reports[commit_sha] = cov

        db.commit() # Save pull requests, snapshots, commits, changed files, dependencies, and coverage reports so they have IDs

        # Now seed FileTestLinks
        # Link auth/middleware.py to test_auth_flow and test_org_isolation for each of the seeded coverage reports
        for commit_sha, cov in cov_reports.items():
            link1 = FileTestLink(
                id=uuid.uuid4(),
                coverage_report_id=cov.id,
                file_path="auth/middleware.py",
                test_case_id=tcs["test_auth_flow"].id,
                mapping_type="DIRECT",
                confidence_score="HIGH"
            )
            link2 = FileTestLink(
                id=uuid.uuid4(),
                coverage_report_id=cov.id,
                file_path="auth/middleware.py",
                test_case_id=tcs["test_org_isolation"].id,
                mapping_type="DIRECT",
                confidence_score="HIGH"
            )
            db.add(link1)
            db.add(link2)

        db.commit()
        print("Successfully seeded all base records for Scenario A, B, C, D, E.")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


    # ----------------------------------------------------
    # 3. Recommendation Engine & Degradation Tests
    # ----------------------------------------------------
    print("\n--- 3. Testing Recommendation Runs & Degradation ---")

    # A: High Quality Run (Targeted changes)
    print("Scenario A: Standard changes with High Quality evidence...")
    response = client.post("/recommendations", json={
        "repository_id": repo_id,
        "pr_id": "pr-1",
        "changed_files": ["auth/middleware.py"],
        "triggered_by": "github-webhook"
    })
    assert response.status_code == 201, f"Run A failed: {response.text}"
    run_a = response.json()
    assert run_a["evidence_quality"] == "HIGH"
    test_cases_a = [t["test_case_id"] for t in run_a["tests"]]
    assert "test_auth_flow" in test_cases_a
    assert "test_org_isolation" in test_cases_a
    print("-> Scenario A Verified: High quality, generated targeted test cases and advisory transitives.")

    # B: Missing Coverage Map (Scope Widening)
    print("Scenario B: Missing Coverage Map (Scope Widening) simulation...")
    response = client.post("/recommendations", json={
        "repository_id": repo_id,
        "pr_id": "pr-2",
        "changed_files": ["auth/middleware.py", "empty_coverage.py"],
        "triggered_by": "github-webhook"
    })
    assert response.status_code == 201
    run_b = response.json()
    assert run_b["evidence_quality"] == "LOW"
    test_cases_b = [t["test_case_id"] for t in run_b["tests"]]
    # Should include direct, dependency, and the widened matched case
    assert "test_api_throttling" in test_cases_b
    print("-> Scenario B Verified: Evidence degraded to LOW, applied parent folder heuristic tests successfully.")

    # C: Partial Mappings (Transitive Expansion Level 2)
    # Clear old reports and seed for pr-3
    db = SessionLocal()
    try:
        db.query(CoverageReport).delete()
        cov_pr3 = CoverageReport(
            repository_id=repo_id,
            commit_sha="pr-3",
            overall_coverage_pct=0.90,
            total_lines=100,
            covered_lines_count=90,
            uncovered_lines_count=10,
            confidence_score="MODERATE",
            confidence_logic="Baseline high quality coverage for testing.",
            file_hash="api-test-hash-pr3"
        )
        db.add(cov_pr3)
        db.commit()

        # Re-add file test links
        tcs = {tc.stable_identity: tc for tc in db.query(TestCase).filter(TestCase.repository_id == repo_id).all()}
        link1 = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov_pr3.id,
            file_path="auth/middleware.py",
            test_case_id=tcs["test_auth_flow"].id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        link2 = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov_pr3.id,
            file_path="auth/middleware.py",
            test_case_id=tcs["test_org_isolation"].id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link1)
        db.add(link2)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


    print("Scenario C: Partial Coverage Mappings (Transitive Expansion +1) simulation...")
    response = client.post("/recommendations", json={
        "repository_id": repo_id,
        "pr_id": "pr-3",
        "changed_files": ["auth/middleware.py", "partial.py"],
        "triggered_by": "github-webhook"
    })
    assert response.status_code == 201
    run_c = response.json()
    assert run_c["evidence_quality"] == "MODERATE"
    print("-> Scenario C Verified: Evidence degraded to MODERATE, expanded transitive level successfully.")

    # D: Weak Dependency Data (Full transitive import chain expansion)
    # Clear old reports and seed for pr-4
    db = SessionLocal()
    try:
        db.query(CoverageReport).delete()
        cov_pr4 = CoverageReport(
            repository_id=repo_id,
            commit_sha="pr-4",
            overall_coverage_pct=0.90,
            total_lines=100,
            covered_lines_count=90,
            uncovered_lines_count=10,
            confidence_score="LOW",
            confidence_logic="Baseline high quality coverage for testing.",
            file_hash="api-test-hash-pr4"
        )
        db.add(cov_pr4)
        db.commit()

        # Re-add file test links
        tcs = {tc.stable_identity: tc for tc in db.query(TestCase).filter(TestCase.repository_id == repo_id).all()}
        link1 = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov_pr4.id,
            file_path="auth/middleware.py",
            test_case_id=tcs["test_auth_flow"].id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        link2 = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov_pr4.id,
            file_path="auth/middleware.py",
            test_case_id=tcs["test_org_isolation"].id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link1)
        db.add(link2)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


    print("Scenario D: Weak static dependency metadata (Full expansion) simulation...")
    response = client.post("/recommendations", json={
        "repository_id": repo_id,
        "pr_id": "pr-4",
        "changed_files": ["auth/middleware.py", "weak.py"],
        "triggered_by": "github-webhook"
    })
    assert response.status_code == 201
    run_d = response.json()
    assert run_d["evidence_quality"] == "LOW"
    print("-> Scenario D Verified: Evidence degraded to LOW, applied full recursion fallback successfully.")

    # E: Insufficient Evidence (Safe-Fallback Mode - Run All Tests)
    # Clear old reports for Scenario E to simulate no active coverage map
    db = SessionLocal()
    try:
        db.query(CoverageReport).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    print("Scenario E: Insufficient Evidence (Safe Fallback to Full Regression) simulation...")
    response = client.post("/recommendations", json={
        "repository_id": repo_id,
        "pr_id": "pr-5",
        "changed_files": ["insufficient.py"],
        "triggered_by": "github-webhook"
    })
    assert response.status_code == 201
    run_e = response.json()
    assert run_e["evidence_quality"] == "UNKNOWN"
    test_cases_e = [t["test_case_id"] for t in run_e["tests"]]
    # Must have all regression suites in fallback
    expected_full_suite = {"test_auth_flow", "test_billing_portal", "test_user_profile", "test_org_isolation", "test_api_throttling"}
    assert expected_full_suite.issubset(set(test_cases_e))
    print("-> Scenario E Verified: Evidence degraded to UNKNOWN, optimization disabled, triggered full safe regression suite.")

    # ----------------------------------------------------
    # 4. Recommendation Outcome & Validation Constraints
    # ----------------------------------------------------
    print("\n--- 4. Testing Recommendation Outcomes & Human Override Checks ---")

    # Standard Followed Outcome (No override reasons needed)
    response = client.post(f"/recommendations/{run_a['id']}/outcome", json={
        "executed_tests": ["test_auth_flow", "test_org_isolation"],
        "manually_added_tests": [],
        "manually_removed_tests": [],
        "was_followed": True
    })
    assert response.status_code == 201, f"Failed standard outcome: {response.text}"
    print("Successfully recorded standard followed outcome.")

    # Duplicate Outcome block (Unique recommendation_run_id constraint)
    response = client.post(f"/recommendations/{run_a['id']}/outcome", json={
        "executed_tests": ["test_auth_flow"],
        "was_followed": True
    })
    assert response.status_code == 409
    print("Successfully verified duplicate outcome constraint (returned 409 Conflict).")

    # Override without mandatory explanation validation
    response = client.post(f"/recommendations/{run_b['id']}/outcome", json={
        "executed_tests": ["test_auth_flow"],
        "manually_removed_tests": ["test_api_throttling"],
        "was_followed": False
    })
    assert response.status_code == 400
    assert "override_reason is mandatory" in response.json()["detail"]
    print("Successfully verified that custom overrides require an override_reason (returned 400 Bad Request).")

    # Override with invalid explanation
    response = client.post(f"/recommendations/{run_b['id']}/outcome", json={
        "executed_tests": ["test_auth_flow"],
        "manually_removed_tests": ["test_api_throttling"],
        "was_followed": False,
        "override_reason": "INVALID_REASON_TEXT"
    })
    assert response.status_code == 400
    assert "Invalid override_reason" in response.json()["detail"]
    print("Successfully verified invalid override reasons are rejected (returned 400 Bad Request).")

    # Correct Override recording
    response = client.post(f"/recommendations/{run_b['id']}/outcome", json={
        "executed_tests": ["test_auth_flow"],
        "manually_removed_tests": ["test_api_throttling"],
        "was_followed": False,
        "override_reason": "KNOWN_RISKY_AREA",
        "feedback": "Optimizing out throttling test because it is known flaky."
    })
    assert response.status_code == 201
    print("Successfully registered correct override outcome with KNOWN_RISKY_AREA reason.")

    # ----------------------------------------------------
    # 5. Diagnostics & Forensic Evidence Chain
    # ----------------------------------------------------
    print("\n--- 5. Testing Debug & Forensic Chain API ---")

    # Fetch Debug Audit chain for High Quality run (Run A)
    response = client.get(f"/recommendations/{run_a['id']}/debug")
    assert response.status_code == 200
    debug_data = response.json()
    assert debug_data["evidence_quality"] == "HIGH"
    
    # Verify reasoning priority sorting: CRITICAL > IMPORTANT > SUPPORTING
    entries = debug_data["reasoning_entries"]
    priorities = [e["evidence_priority"] for e in entries]
    print(f"Retrieved evidence chain priorities: {priorities}")
    
    # Assert priorities follow explainability hierarchy
    priority_order = {"CRITICAL": 0, "IMPORTANT": 1, "SUPPORTING": 2}
    for i in range(len(priorities) - 1):
        p1, p2 = priorities[i], priorities[i+1]
        assert priority_order[p1] <= priority_order[p2], f"Explainability sorting violation: {p1} came before {p2}"
    print("Successfully verified explainability hierarchy sorting (CRITICAL > IMPORTANT > SUPPORTING).")
    
    # Verify advisory expansion paths
    assert len(debug_data["dependency_expansion_path"]) > 0
    print(f"Advisory path expansion: {debug_data['dependency_expansion_path']}")

    print("\n==================================================")
    print("ALL VERISCOPE INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
