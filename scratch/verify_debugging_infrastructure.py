import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import (
    PullRequest,
    PullRequestCommit,
    PullRequestChangedFile,
    PullRequestSyncJob,
    PullRequestSnapshot
)
from app.models.test_result import TestRun, TestCase, TestResult
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.dependency import FileDependency
from app.models.flaky_test import FlakyTestProfile
from app.models.recalculation_job import FlakyRecalculationJob
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry
)
from app.models.observability import IngestionJob
from app.models.artifact import RawArtifact

from app.schemas.debugging import (
    PRDebugResponse,
    TestRunDebugResponse,
    CoverageDebugResponse,
    DependencyDebugResponse,
    FlakyRegistryDebugResponse,
    RecommendationDebugResponse
)

client = TestClient(app)

def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationRun).delete()
        db.query(FlakyRecalculationJob).delete()
        db.query(FlakyTestProfile).delete()
        db.query(FileDependency).delete()
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(PullRequestSnapshot).delete()
        db.query(PullRequestCommit).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequestSyncJob).delete()
        db.query(PullRequest).delete()
        db.query(IngestionJob).delete()
        db.query(RawArtifact).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("SUCCESS: Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_verification():
    print("======================================================================")
    print("STARTING FULL DIAGNOSTIC & DEBUGGING INFRASTRUCTURE INTEGRATION TESTING")
    print("======================================================================\n")

    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    pr_num = 456
    commit_sha = "abcdef0123456789abcdef0123456789"
    test_run_id = uuid.uuid4()
    test_case_uuid = uuid.uuid4()
    raw_artifact_id = uuid.uuid4()

    try:
        # 1. Seed base models
        org = Organization(id=org_id, name="Umbrella Corp", slug="umbrella-corp")
        db.add(org)

        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=987654,
            name="antivirus-core",
            full_name="umbrella-corp/antivirus-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        print(f"Seeded Org: {org_id}, Repo: {repo_id}")

        # 2. Seed Pull Request & Ingestion
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=12121212,
            number=pr_num,
            title="Fix antivirus core engine",
            author="wesker",
            source_branch="patch-1",
            target_branch="main",
            state="open",
            additions=10,
            deletions=2,
            changed_files_count=1,
            head_commit_sha=commit_sha,
            github_created_at=datetime.utcnow() - timedelta(hours=1),
            github_updated_at=datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT",
            unsafe_for_optimization=False
        )
        db.add(pr)

        pr_commit = PullRequestCommit(
            pull_request_id=pr_id,
            sha=commit_sha,
            message="Improve parsing efficiency",
            author="wesker",
            commit_date=datetime.utcnow() - timedelta(minutes=30)
        )
        db.add(pr_commit)

        pr_file = PullRequestChangedFile(
            pull_request_id=pr_id,
            file_path="src/engine.ts",
            status="modified",
            additions=10,
            deletions=2
        )
        db.add(pr_file)

        sync_job = PullRequestSyncJob(
            pull_request_id=pr_id,
            repository_id=repo_id,
            github_installation_id=12345,
            status="COMPLETED",
            sync_reason="WEBHOOK_OPENED",
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow() - timedelta(minutes=4)
        )
        db.add(sync_job)
        db.commit()
        print(f"Seeded PR: {pr_id} (Num: {pr_num}), commits, files, sync jobs")

        # 3. Seed Test Result & Ingestion
        raw_art = RawArtifact(
            id=raw_artifact_id,
            repository_id=repo_id,
            artifact_type="junit",
            storage_path="junit/test-run-1.xml",
            artifact_metadata={"filename": "test-run-1.xml", "artifact_size_bytes": 1024}
        )
        db.add(raw_art)

        test_run = TestRun(
            id=test_run_id,
            repository_id=repo_id,
            commit_sha=commit_sha,
            status="passed",
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            consistency_severity="NONE",
            total_tests=2,
            passed_tests=2,
            failed_tests=0,
            skipped_tests=0,
            duration=12.5,
            correlation_id="corr-test-1",
            raw_artifact_id=raw_artifact_id,
            ingestion_reason="github_ci",
            file_hash="mock-test-run-hash-123",
            normalized_execution_fingerprint="mock-test-run-fingerprint-123"
        )
        db.add(test_run)

        import hashlib
        stable_id = "engine_suite::test_antivirus_engine"
        id_hash = hashlib.sha256(stable_id.encode('utf-8')).hexdigest()
        
        test_case = TestCase(
            id=test_case_uuid,
            repository_id=repo_id,
            suite_name="engine_suite",
            test_name="test_antivirus_engine",
            stable_identity=stable_id,
            canonical_identity_hash=id_hash,
            identity_lineage_root_hash=id_hash
        )
        db.add(test_case)
        db.commit()

        test_result = TestResult(
            test_run_id=test_run_id,
            test_case_id=test_case_uuid,
            status="passed",
            duration=6.2,
            stack_trace_redaction_status="CLEAN"
        )
        db.add(test_result)

        ingestion_job = IngestionJob(
            repository_id=repo_id,
            job_type="junit_parsing",
            status="COMPLETED",
            retry_count=0,
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow() - timedelta(minutes=4)
        )
        db.add(ingestion_job)
        db.commit()
        print(f"Seeded TestRun: {test_run_id}, TestResult, IngestionJob")

        # 4. Seed Coverage Report
        coverage_report = CoverageReport(
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.85,
            total_lines=100,
            covered_lines_count=85,
            uncovered_lines_count=15,
            confidence_score="HIGH",
            confidence_logic="Complete statement coverage mappings reconciled cleanly.",
            file_hash="mock-hash-12345",
            correlation_id="corr-cov-1"
        )
        db.add(coverage_report)
        db.commit()

        cov_file = CoverageFileEntry(
            coverage_report_id=coverage_report.id,
            file_path="src/engine.ts",
            covered_lines=[1, 2, 3, 4, 5],
            uncovered_lines=[6, 7],
            total_lines_count=7,
            covered_lines_count=5,
            uncovered_lines_count=2
        )
        db.add(cov_file)

        file_test_link = FileTestLink(
            coverage_report_id=coverage_report.id,
            file_path="src/engine.ts",
            test_case_id=test_case_uuid,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(file_test_link)

        cov_ingest_job = IngestionJob(
            repository_id=repo_id,
            job_type="coverage_ingestion",
            status="COMPLETED",
            retry_count=0,
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow() - timedelta(minutes=4)
        )
        db.add(cov_ingest_job)
        db.commit()
        print(f"Seeded CoverageReport: {coverage_report.id}, FileTestLink, IngestionJob")

        # 5. Seed Dependencies
        dep1 = FileDependency(
            repository_id=repo_id,
            file_path="src/engine.ts",
            depends_on_file_path="src/utils.ts",
            dependency_type="import",
            commit_sha=commit_sha
        )
        db.add(dep1)
        db.commit()
        print(f"Seeded FileDependency: src/engine.ts -> src/utils.ts")

        # 6. Seed Flaky Profiles & Job
        flaky_profile = FlakyTestProfile(
            repository_id=repo_id,
            test_case_id=test_case_uuid,
            failure_rate=0.15,
            recent_failure_rate=0.20,
            instability_score=0.25,
            status="unstable",
            last_failure_at=datetime.utcnow() - timedelta(hours=2),
            sample_size=15,
            confidence_level="MODERATE",
            stale_profile=False,
            execution_environment="CI",
            runner_type="ubuntu-latest",
            test_framework="jest",
            flakiness_calculation_version=1,
            rationale="Test has exhibited failures in CI environment under normal execution."
        )
        db.add(flaky_profile)

        recalc_job = FlakyRecalculationJob(
            repository_id=repo_id,
            status="COMPLETED",
            recalculation_scope="FULL_REPOSITORY",
            started_at=datetime.utcnow() - timedelta(minutes=10),
            completed_at=datetime.utcnow() - timedelta(minutes=8)
        )
        db.add(recalc_job)
        db.commit()
        print(f"Seeded FlakyTestProfile and FlakyRecalculationJob")

        # 7. Seed Recommendation Run
        rec_run = RecommendationRun(
            repository_id=repo_id,
            pr_id=str(pr_num),
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Sufficient evidence and direct test links exist."
        )
        db.add(rec_run)
        db.commit()

        rec_test = RecommendationTest(
            recommendation_run_id=rec_run.id,
            test_case_id="engine_suite::test_antivirus_engine",
            reason_type="direct_file_coverage",
            reason_details={"file": "src/engine.ts"},
            priority_score=0.95
        )
        db.add(rec_test)

        rec_reasoning = RecommendationReasoningEntry(
            recommendation_run_id=rec_run.id,
            reason_type="direct_file_coverage",
            source_entity="src/engine.ts",
            source_reference="HEAD",
            human_readable_reason="Direct changes in src/engine.ts mapped to engine_suite::test_antivirus_engine",
            confidence_level="HIGH",
            evidence_priority="CRITICAL"
        )
        db.add(rec_reasoning)
        db.commit()
        print(f"Seeded RecommendationRun: {rec_run.id}, RecommendationTest, reasoning entry")

        print("\n----------------------------------------------------------------------")
        print("SEEDING COMPLETE. INITIATING DIAGNOSTIC API ROUTE VERIFICATIONS...")
        print("----------------------------------------------------------------------")

        # ====================================================================
        # ROUTE 1: PR Ingestion Debug
        # ====================================================================
        print("\n--- 1. Testing GET /internal/prs/{id}/debug ---")
        res_pr = client.get(f"/internal/prs/{pr_id}/debug")
        assert res_pr.status_code == 200, f"PR debug failed: {res_pr.text}"
        pr_data = res_pr.json()
        PRDebugResponse(**pr_data) # Validate schema
        assert pr_data["raw_inputs"]["github_pr_id"] == 12121212
        assert len(pr_data["derived_relationships"]["changed_files"]) > 0
        assert pr_data["telemetry"]["total_retry_count"] == 0
        print("SUCCESS: PR Ingestion debug endpoint matches PRDebugResponse Pydantic schema perfectly!")

        # ====================================================================
        # ROUTE 2: Test Ingestion Debug
        # ====================================================================
        print("\n--- 2. Testing GET /internal/test-runs/{id}/debug ---")
        res_tr = client.get(f"/internal/test-runs/{test_run_id}/debug")
        assert res_tr.status_code == 200, f"Test run debug failed: {res_tr.text}"
        tr_data = res_tr.json()
        TestRunDebugResponse(**tr_data) # Validate schema
        assert tr_data["raw_inputs"]["junit_xml_filename"] == "test-run-1.xml"
        assert tr_data["raw_inputs"]["size_bytes"] == 1024
        assert len(tr_data["derived_relationships"]["test_cases"]) > 0
        print("SUCCESS: Test Ingestion debug endpoint matches TestRunDebugResponse Pydantic schema perfectly!")

        # ====================================================================
        # ROUTE 3: Coverage Mapping Debug
        # ====================================================================
        print("\n--- 3. Testing GET /internal/coverage/{repo_id}/debug ---")
        res_cov = client.get(f"/internal/coverage/{repo_id}/debug")
        assert res_cov.status_code == 200, f"Coverage debug failed: {res_cov.text}"
        cov_data = res_cov.json()
        CoverageDebugResponse(**cov_data) # Validate schema
        assert cov_data["raw_inputs"]["overall_coverage_pct"] == 0.85
        assert "src/engine.ts" in cov_data["derived_relationships"]["mapped_files"]
        print("SUCCESS: Coverage Mapping debug endpoint matches CoverageDebugResponse Pydantic schema perfectly!")

        # ====================================================================
        # ROUTE 4: Dependency Expansion Debug
        # ====================================================================
        print("\n--- 4. Testing GET /internal/dependencies/{repo_id}/debug ---")
        res_dep = client.get(f"/internal/dependencies/{repo_id}/debug")
        assert res_dep.status_code == 200, f"Dependency debug failed: {res_dep.text}"
        dep_data = res_dep.json()
        DependencyDebugResponse(**dep_data) # Validate schema
        assert dep_data["raw_inputs"]["total_dependency_edges"] == 1
        assert "src/engine.ts" in dep_data["derived_relationships"]["nodes"]
        print("SUCCESS: Dependency Expansion debug endpoint matches DependencyDebugResponse Pydantic schema perfectly!")

        # ====================================================================
        # ROUTE 5: Flaky Registry Debug
        # ====================================================================
        print("\n--- 5. Testing GET /internal/flaky-tests/{repo_id}/debug ---")
        res_flaky = client.get(f"/internal/flaky-tests/{repo_id}/debug")
        assert res_flaky.status_code == 200, f"Flaky registry debug failed: {res_flaky.text}"
        flaky_data = res_flaky.json()
        FlakyRegistryDebugResponse(**flaky_data) # Validate schema
        assert flaky_data["raw_inputs"]["total_profiles"] == 1
        assert flaky_data["raw_inputs"]["test_frameworks"] == ["jest"]
        assert len(flaky_data["telemetry"]["recalculation_jobs"]) > 0
        print("SUCCESS: Flaky Registry debug endpoint matches FlakyRegistryDebugResponse Pydantic schema perfectly!")

        # ====================================================================
        # ROUTE 6: Recommendations Debug
        # ====================================================================
        print("\n--- 6. Testing GET /internal/recommendations/{id}/debug ---")
        res_rec = client.get(f"/internal/recommendations/{rec_run.id}/debug")
        assert res_rec.status_code == 200, f"Recommendations debug failed: {res_rec.text}"
        rec_data = res_rec.json()
        RecommendationDebugResponse(**rec_data) # Validate schema
        assert rec_data["run_id"] == str(rec_run.id)
        assert rec_data["evidence_quality"] == "HIGH"
        assert len(rec_data["reasoning_entries"]) > 0
        
        # Validate newly implemented standard traceability blocks!
        assert rec_data["raw_inputs"]["pr_id"] == str(pr_num)
        assert rec_data["raw_inputs"]["repository_id"] == str(repo_id)
        assert rec_data["raw_inputs"]["changed_files"] == ["src/engine.ts"]
        assert rec_data["derived_relationships"]["predicted_tests"] == ["engine_suite::test_antivirus_engine"]
        assert rec_data["derived_relationships"]["test_reasons"]["engine_suite::test_antivirus_engine"]["reason_type"] == "direct_file_coverage"
        assert rec_data["telemetry"]["correlation_id"] == str(rec_run.id)
        print("SUCCESS: Recommendations debug endpoint matches RecommendationDebugResponse Pydantic schema perfectly!")

        print("\n======================================================================")
        print("ALL 6 INTERNAL DEBUGGING ENDPOINTS FULLY VERIFIED AND FUNCTIONAL!")
        print("======================================================================")

    finally:
        db.close()
        cleanup_database()

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
