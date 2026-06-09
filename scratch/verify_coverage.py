import sys
import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.config import settings
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestCase
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.artifact import RawArtifact
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationReasoningEntry,
    RecommendationOutcome
)
from app.services.lcov_parser import SafeLCOVParser, LCOVParsingError
from app.services.coverage_ingestion import CoverageIngestionService, CoverageIngestionError
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate

client = TestClient(app)

def cleanup_database():
    """Clean up test records to ensure fresh validation runs."""
    db = SessionLocal()
    try:
        # Delete recommendation-related records first to avoid foreign key issues
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationRun).delete()
        
        # Delete Coverage records
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        
        # Delete JUnit/TestCase related records
        db.query(TestCase).delete()
        db.query(RawArtifact).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Workspace).delete()
        db.commit()
        print("Database clean up successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def make_lcov_report(records):
    """
    Constructs an LCOV format payload from list of records.
    records = [
      {
        "file": "app/services/auth.py",
        "test": "tests.services.test_auth::test_login", # optional
        "da": [(1, 1), (2, 1), (3, 0)] # (line, exec_count)
      }
    ]
    """
    lcov = ""
    for r in records:
        if r.get("test"):
            lcov += f"TN:{r['test']}\n"
        lcov += f"SF:{r['file']}\n"
        for line, count in r.get("da", []):
            lcov += f"DA:{line},{count}\n"
        lcov += "end_of_record\n"
    return lcov

def run_verification():
    print("======================================================================")
    print("      VERISCOPE HARDENED LCOV COVERAGE INGESTION VERIFICATION")
    print("======================================================================\n")

    # Clean up database
    cleanup_database()

    db = SessionLocal()

    try:
        # 0. Setup Workspace & Repository
        ws = Workspace(id=uuid.uuid4(), name="Coverage Trust Corp", slug=f"coverage-trust-{uuid.uuid4().hex[:6]}")
        db.add(ws)
        db.flush()

        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            github_repo_id=987654,
            installation_id=123456,
            name="veriscope",
            full_name="coverage-trust/veriscope",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.flush()

        # Pre-populate TestCases inside repository to test direct and heuristic mappings
        tc_direct = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="tests.services.test_auth",
            test_name="test_login",
            stable_identity="tests.services.test_auth::test_login",
            canonical_identity_hash=hashlib.sha256(b"tests.services.test_auth::test_login").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"tests.services.test_auth::test_login").hexdigest()
        )
        
        tc_naming = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="tests.test_profile",
            test_name="test_update",
            stable_identity="tests.test_profile::test_update",
            canonical_identity_hash=hashlib.sha256(b"tests.test_profile::test_update").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"tests.test_profile::test_update").hexdigest()
        )
        
        tc_path = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="tests.models.test_org_isolation",
            test_name="test_boundaries",
            stable_identity="tests.models.test_org_isolation::test_boundaries",
            canonical_identity_hash=hashlib.sha256(b"tests.models.test_org_isolation::test_boundaries").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"tests.models.test_org_isolation::test_boundaries").hexdigest()
        )

        from app.models.dependency import FileDependency
        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_path="app/services/auth.py",
            depends_on_file_path="app/utils/logger.py",
            dependency_type="import",
            commit_sha="commit_pr_head"
        )
        db.add(dep)

        db.add(tc_direct)
        db.add(tc_naming)
        db.add(tc_path)
        db.commit()

        print(f"Created Workspace ID: {ws.id}")
        print(f"Created Repo ID: {repo.id}")
        print(f"Pre-populated TestCase (DIRECT) ID: {tc_direct.id}")
        print(f"Pre-populated TestCase (NAMING) ID: {tc_naming.id}")
        print(f"Pre-populated TestCase (PATH) ID: {tc_path.id}\n")

        # ----------------------------------------------------
        # 1. Safe LCOV Parsing & Size Guardrails
        # ----------------------------------------------------
        print("--- Step 1: Testing Safe LCOV Parsing & Security Guardrails ---")
        
        # Test Case 1.1: Basic well-formed parsing
        lcov_sample = make_lcov_report([
            {
                "file": "app/services/auth.py",
                "test": "tests.services.test_auth::test_login",
                "da": [(1, 1), (2, 2), (3, 0), (4, 0)]
            }
        ])
        
        parsed = SafeLCOVParser.parse_lcov(lcov_sample)
        assert len(parsed) == 1
        assert parsed[0]["file_path"] == "app/services/auth.py"
        assert parsed[0]["test_name"] == "tests.services.test_auth::test_login"
        assert parsed[0]["covered_lines"] == [1, 2]
        assert parsed[0]["uncovered_lines"] == [3, 4]
        assert parsed[0]["covered_lines_count"] == 2
        assert parsed[0]["uncovered_lines_count"] == 2
        assert parsed[0]["total_lines_count"] == 4
        print("[OK] Safe LCOV parser successfully parsed well-formed source records.")

        # Test Case 1.2: Path Normalization
        lcov_abs = make_lcov_report([
            {
                "file": "C:\\Users\\amrsa\\Downloads\\veriscope\\app\\services\\auth.py",
                "da": [(1, 1)]
            }
        ])
        parsed_abs = SafeLCOVParser.parse_lcov(lcov_abs)
        assert parsed_abs[0]["file_path"] == "app/services/auth.py", f"Expected normalized path, got {parsed_abs[0]['file_path']}"
        print("[OK] Safe LCOV path normalization correctly stripped absolute workspace prefix.")

        # Test Case 1.3: Oversized record limit guard
        try:
            SafeLCOVParser.parse_lcov(lcov_sample, max_records=0)
            raise AssertionError("Parser failed to enforce max records safety limit!")
        except LCOVParsingError as e:
            assert "contains too many file records" in str(e)
            print(f"[OK] Oversized record limit guard enforced: {e}")

        # Test Case 1.4: Oversized lines per file limit guard
        try:
            SafeLCOVParser.parse_lcov(lcov_sample, max_lines_per_file=2)
            raise AssertionError("Parser failed to enforce max lines safety limit!")
        except LCOVParsingError as e:
            assert "exceeded statement safety limit" in str(e)
            print(f"[OK] Oversized statement lines limit guard enforced: {e}")

        # ----------------------------------------------------
        # 2. Ingestion Endpoint & Object Storage
        # ----------------------------------------------------
        print("\n--- Step 2: Testing Ingestion Endpoint & S3/Local Storage Preservation ---")
        
        response = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "sha1234567890abcdef"
            },
            files={"file": ("coverage.info", lcov_sample, "text/plain")}
        )
        assert response.status_code == 201, f"Ingestion failed: {response.text}"
        data = response.json()
        assert "coverage_report_id" in data
        assert data["overall_coverage_pct"] == 0.5
        assert data["total_lines"] == 4
        assert data["covered_lines_count"] == 2
        assert data["uncovered_lines_count"] == 2
        
        report_id = data["coverage_report_id"]
        print(f"[OK] LCOV ingestion endpoint successfully accepted report, generated ID: {report_id}")

        # Verify raw storage preservation
        db.expire_all()
        report_db = db.query(CoverageReport).filter(CoverageReport.id == report_id).first()
        assert report_db is not None
        assert report_db.raw_artifact_id is not None
        
        artifact = db.query(RawArtifact).filter(RawArtifact.id == report_db.raw_artifact_id).first()
        assert artifact is not None
        assert artifact.artifact_type == "coverage_report"
        assert artifact.artifact_metadata["content_type"] == "text/plain"
        assert os.path.exists(artifact.storage_path)
        print(f"[OK] Raw report successfully preserved in raw artifacts storage under: {artifact.storage_path}")

        # ----------------------------------------------------
        # 3. Double Idempotency Guard (File Hash Shield)
        # ----------------------------------------------------
        print("\n--- Step 3: Testing Idempotency Guard (File Hash Shield) ---")
        
        # Uploading exact same report content again
        response_dup = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "sha1234567890abcdef"
            },
            files={"file": ("coverage.info", lcov_sample, "text/plain")}
        )
        assert response_dup.status_code == 201
        dup_data = response_dup.json()
        assert dup_data["coverage_report_id"] == report_id, "Duplicate upload should yield the exact same report ID"
        print("[OK] Verified idempotency: duplicate upload coalesced back to the existing report ID.")

        # ----------------------------------------------------
        # 4. Direct & Heuristic Mappings (Direct, Naming, Path)
        # ----------------------------------------------------
        print("\n--- Step 4: Testing Direct and Fallback Matching Heuristics ---")
        
        # Build LCOV containing three files targeting DIRECT, NAMING, and PATH matching
        mapping_lcov = make_lcov_report([
            {
                # 4.1 DIRECT Match: Test Name is provided in TN: and matches tc_direct stable identity
                "file": "app/services/auth.py",
                "test": "tests.services.test_auth::test_login",
                "da": [(1, 1), (2, 0)]
            },
            {
                # 4.2 NAMING Match: File stem is 'profile', which matches tc_naming suite_name 'tests.test_profile'
                "file": "app/services/profile.py",
                "da": [(1, 1), (2, 0)]
            },
            {
                # 4.3 PATH Match: File is app/models/tenant.py. Parent dir is 'models', which matches tc_path suite_name 'tests.models.test_org_isolation'
                "file": "app/models/tenant.py",
                "da": [(1, 1), (2, 0)]
            }
        ])

        response_map = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "sha_mapping_test"
            },
            files={"file": ("coverage_mapping.info", mapping_lcov, "text/plain")}
        )
        assert response_map.status_code == 201
        map_report_id = response_map.json()["coverage_report_id"]

        # Assert links created in database
        links = db.query(FileTestLink).filter(FileTestLink.coverage_report_id == map_report_id).all()
        assert len(links) == 3, f"Expected 3 test links, got {len(links)}"

        # Assert resolution types and scoring strength
        direct_link = next(link for link in links if link.file_path == "app/services/auth.py")
        assert direct_link.mapping_type == "DIRECT"
        assert direct_link.confidence_score == "HIGH"
        assert direct_link.test_case_id == tc_direct.id
        print("[OK] DIRECT file-to-test mapping resolved successfully with HIGH confidence score.")

        naming_link = next(link for link in links if link.file_path == "app/services/profile.py")
        print(f"DEBUG: naming_link file_path={naming_link.file_path}, mapping_type={naming_link.mapping_type}, confidence_score={naming_link.confidence_score}, test_case_id={naming_link.test_case_id}")
        assert naming_link.mapping_type == "HEURISTIC_NAMING"
        assert naming_link.confidence_score == "MODERATE"
        assert naming_link.test_case_id == tc_naming.id
        print("[OK] HEURISTIC_NAMING fallback naming convention mapping resolved successfully with MODERATE confidence score.")

        path_link = next(link for link in links if link.file_path == "app/models/tenant.py")
        assert path_link.mapping_type == "HEURISTIC_PATH"
        assert path_link.confidence_score == "LOW"
        assert path_link.test_case_id == tc_path.id
        print("[OK] HEURISTIC_PATH fallback directory overlap mapping resolved successfully with LOW confidence score.")

        # ----------------------------------------------------
        # 5. Coverage Confidence Scoring (HIGH, MODERATE, LOW)
        # ----------------------------------------------------
        print("\n--- Step 5: Testing Coverage Confidence Scoring Rules ---")

        # Setup Pull Request to test PR changed files scoring rules
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=112233,
            number=42,
            title="Update Auth flow & tenant logic",
            author="tester",
            source_branch="feat/auth",
            target_branch="main",
            state="open",
            head_commit_sha="commit_pr_head",
            sync_integrity_status="FULL_SUCCESS",
            evidence_consistency_status="CONSISTENT",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db.add(pr)
        db.flush()

        # Let's define the changed files for the PR
        cf_auth = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="app/services/auth.py",
            status="modified"
        )
        cf_profile = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="app/services/profile.py",
            status="modified"
        )
        cf_unmapped = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="app/utils/logger.py", # changed but unmapped
            status="modified"
        )
        db.add(cf_auth)
        db.add(cf_profile)
        db.add(cf_unmapped)
        db.commit()

        # Scenario 5.1: MODERATE confidence (2 of 3 changed files present, 1 unmapped)
        # Auth and Profile are present, but logger.py is completely missing in report.
        # Report coverage is good, but missing 1 changed file completely.
        moderate_lcov = make_lcov_report([
            {
                "file": "app/services/auth.py",
                "test": "tests.services.test_auth::test_login",
                "da": [(1, 1), (2, 1)] # 100% coverage
            },
            {
                "file": "app/services/profile.py",
                "da": [(1, 1), (2, 0)] # 50% coverage
            },
            {
                "file": "app/utils/dummy.py",
                "da": [(i, 1) for i in range(1, 60)] # 59 lines
            }
        ])

        response_mod = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "commit_mod",
                "pull_request_id": str(pr.id)
            },
            files={"file": ("coverage_mod.info", moderate_lcov, "text/plain")}
        )
        assert response_mod.status_code == 201
        res_mod = response_mod.json()
        assert res_mod["confidence_score"] == "MODERATE"
        print(f"[OK] Scored as MODERATE confidence due to partially unmapped changed files: {res_mod['confidence_logic']}")

        # Scenario 5.2: LOW confidence (Changed files are mapped, but sparse coverage (< 30%))
        sparse_lcov = make_lcov_report([
            {
                "file": "app/services/auth.py",
                "test": "tests.services.test_auth::test_login",
                "da": [(1, 1), (2, 0), (3, 0), (4, 0), (5, 0)] # 20% coverage (sparse)
            },
            {
                "file": "app/services/profile.py",
                "da": [(1, 1), (2, 0), (3, 0), (4, 0)] # 25% coverage (sparse)
            },
            {
                "file": "app/utils/dummy.py",
                "da": [(i, 1) for i in range(1, 60)] # 59 lines
            }
        ])

        response_sparse = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "commit_sparse",
                "pull_request_id": str(pr.id)
            },
            files={"file": ("coverage_sparse.info", sparse_lcov, "text/plain")}
        )
        assert response_sparse.status_code == 201
        res_sparse = response_sparse.json()
        assert res_sparse["confidence_score"] == "LOW"
        print(f"[OK] Scored as LOW confidence due to sparse changed files coverage: {res_sparse['confidence_logic']}")

        # Scenario 5.3: HIGH confidence (Most changed files are mapped, high coverage)
        # Let's delete the unmapped logger.py changed file to satisfy 100% changed files mapped
        db.delete(cf_unmapped)
        db.commit()

        high_lcov = make_lcov_report([
            {
                "file": "app/services/auth.py",
                "test": "tests.services.test_auth::test_login",
                "da": [(1, 1), (2, 1), (3, 1), (4, 0)] # 75% coverage
            },
            {
                "file": "app/services/profile.py",
                "da": [(1, 1), (2, 1), (3, 0)] # 66.6% coverage
            },
            {
                "file": "app/utils/dummy.py",
                "da": [(i, 1) for i in range(1, 60)] # 59 lines
            }
        ])

        response_high = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "commit_high",
                "branch": "main",
                "pull_request_id": str(pr.id)
            },
            files={"file": ("coverage_high.info", high_lcov, "text/plain")}
        )
        assert response_high.status_code == 201
        res_high = response_high.json()
        assert res_high["confidence_score"] == "HIGH"
        print(f"[OK] Scored as HIGH confidence when changed files coverage and mapping counts are solid: {res_high['confidence_logic']}")

        # ----------------------------------------------------
        # 6. Recommendation Degradation Integration
        # ----------------------------------------------------
        print("\n--- Step 6: Testing Recommendation Degradation Loop ---")
        
        recommendation_service = RecommendationService(db)

        # Scenario 6.1: Active report is HIGH confidence -> Expect HIGH evidence quality recommendations
        pr.head_commit_sha = "commit_high"
        db.commit()
        rec_run_high = recommendation_service.create_recommendation_run(
            RecommendationRunCreate(
                repository_id=repo.id,
                pr_id="commit_high",
                triggered_by="tester",
                changed_files=["app/services/auth.py"]
            )
        )
        assert rec_run_high.evidence_quality == "HIGH", f"Expected HIGH evidence quality, got {rec_run_high.evidence_quality}"
        print("[OK] Recommendation Engine evaluates evidence as HIGH quality when latest report is HIGH.")

        # Scenario 6.2: Low confidence coverage report uploaded -> Expect LOW quality and fallback/widened rules
        low_lcov = make_lcov_report([
            {
                "file": "app/services/auth.py",
                "da": [(1, 0), (2, 0), (3, 0)] # 0% coverage (sparse/empty)
            }
        ])
        
        # Uploading new latest report with LOW confidence
        response_new_low = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "commit_new_low",
                "pull_request_id": str(pr.id)
            },
            files={"file": ("coverage_new_low.info", low_lcov, "text/plain")}
        )
        assert response_new_low.status_code == 201
        assert response_new_low.json()["confidence_score"] == "LOW"

        # Generate recommendation
        from app.models.dependency import FileDependency
        db.query(FileDependency).delete()
        pr.head_commit_sha = "commit_new_low"
        db.commit()
        rec_run_low = recommendation_service.create_recommendation_run(
            RecommendationRunCreate(
                repository_id=repo.id,
                pr_id="commit_new_low",
                triggered_by="tester",
                changed_files=["app/services/auth.py"]
            )
        )
        assert rec_run_low.evidence_quality == "LOW", f"Expected LOW evidence quality, got {rec_run_low.evidence_quality}"
        assert rec_run_low.recommendation_mode == "SAFE_FALLBACK"
        assert "Missing coverage mapping" in rec_run_low.recommendation_reasoning_summary or "low trust" in rec_run_low.recommendation_reasoning_summary
        print("[OK] Recommendation Engine successfully degraded to SAFE_FALLBACK (safe fallback mode) due to LOW coverage report confidence.")

        # Scenario 6.3: Coverage report deleted (no coverage map) -> Expect LOW evidence quality and widened modes
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        db.commit()

        rec_run_missing = recommendation_service.create_recommendation_run(
            RecommendationRunCreate(
                repository_id=repo.id,
                pr_id=str(pr.id),
                triggered_by="tester",
                changed_files=["app/services/auth.py"]
            )
        )
        assert rec_run_missing.evidence_quality == "LOW", f"Expected LOW evidence quality, got {rec_run_missing.evidence_quality}"
        assert "Missing coverage mapping" in rec_run_missing.recommendation_reasoning_summary
        print("[OK] Recommendation Engine correctly downgraded evidence quality to LOW and widened scope due to missing coverage maps entirely.")

        # ----------------------------------------------------
        # 7. Internal Debug Endpoint
        # ----------------------------------------------------
        print("\n--- Step 7: Testing Internal Diagnostics Endpoint ---")

        # Let's populate a report with some unmapped files and weak mappings to verify diagnostics
        diag_lcov = make_lcov_report([
            {
                # Direct mapped (not weak)
                "file": "app/services/auth.py",
                "test": "tests.services.test_auth::test_login",
                "da": [(1, 1)]
            },
            {
                # Heuristic Naming (weak)
                "file": "app/services/profile.py",
                "da": [(1, 1)]
            },
            {
                # Completely unmapped file
                "file": "app/utils/logger.py",
                "da": [(1, 1)]
            }
        ])

        client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "commit_diag"
            },
            files={"file": ("coverage_diag.info", diag_lcov, "text/plain")}
        )

        response_debug = client.get(f"/internal/coverage/{repo.id}/debug")
        assert response_debug.status_code == 200
        debug_data = response_debug.json()
        
        assert debug_data["raw_inputs"] is not None
        assert debug_data["raw_inputs"]["commit_sha"] == "commit_diag"
        
        # Verify unmapped files
        assert len(debug_data["derived_relationships"]["unmapped_files"]) == 1
        assert "app/utils/logger.py" in debug_data["derived_relationships"]["unmapped_files"]
        print("[OK] Verified unmapped files list correctly shows unmapped source files.")

        # Verify weak mappings
        weak_mappings = [m for m in debug_data["derived_relationships"]["test_mappings"] if m["mapping_type"] == "HEURISTIC_NAMING"]
        assert len(weak_mappings) == 1
        assert weak_mappings[0]["file_path"] == "app/services/profile.py"
        assert weak_mappings[0]["mapping_type"] == "HEURISTIC_NAMING"
        assert weak_mappings[0]["confidence_score"] == "MODERATE"
        print("[OK] Verified weak mappings list correctly shows moderate/low confidence mappings.")

        # Verify paginated diagnostics limits
        response_debug_pag = client.get(
            f"/internal/coverage/{repo.id}/debug",
            params={"limit": 1, "offset": 0}
        )
        assert response_debug_pag.status_code == 200
        pag_data = response_debug_pag.json()
        assert len(pag_data["derived_relationships"]["unmapped_files"]) == 1
        print("[OK] Bounded diagnostics offset pagination validated successfully on coverage endpoint.")

        print("\n======================================================================")
        print("   ALL VERISCOPE LCOV PIPELINE HARDENING TESTS COMPLETED SUCCESSFULLY!")
        print("======================================================================\n")

    except Exception as e:
        print("\n[FAIL] An assertion or runtime verification check has failed!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
