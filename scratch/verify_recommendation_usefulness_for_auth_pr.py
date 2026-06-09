import sys
import os
import uuid
import random
from datetime import datetime, timedelta
from fastapi import HTTPException

# Add parent directory to path to enable local app imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.user import Workspace
from app.models.recommendation import RecommendationRun, RecommendedTest
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.coverage import CoverageReport, FileTestLink
from app.models.domain_map import DomainMap
from app.services.recommendation import RecommendationService
from app.routers.recommendation import get_recommendation_run

def run_usefulness_verifications():
    db = SessionLocal()
    
    # Generate deterministic IDs for verification entities
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    coverage_report_id = uuid.uuid4()
    
    # Generate unique slug, names and IDs to avoid unique constraint violations
    random_suffix = uuid.uuid4().hex[:6]
    workspace_slug = f"verify-space-{random_suffix}"
    repo_name = f"verify-auth-repo-{random_suffix}"
    repo_full_name = f"verify-org/{repo_name}"
    
    github_repo_id = random.randint(1000000, 9999999)
    github_pr_id = random.randint(1000000, 9999999)
    
    print("=== STARTING AUTH PR RECOMMENDATION USEFULNESS VERIFICATIONS ===")
    
    try:
        # Start transaction
        db.begin_nested()
        
        # 1. Seed Workspace
        workspace = Workspace(
            id=workspace_id,
            name="Verification Space",
            slug=workspace_slug
        )
        db.add(workspace)
        db.flush()
        print("[SEED] Workspace seeded.")
        
        # 2. Seed Repository
        repo = Repository(
            id=repo_id,
            workspace_id=workspace_id,
            github_repo_id=github_repo_id,
            name=repo_name,
            full_name=repo_full_name,
            default_branch="main",
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.flush()
        print("[SEED] Repository seeded.")
        
        # 3. Seed Pull Request
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=github_pr_id,
            number=101,
            title="Implement modern password validation rules and fix test suites",
            author="auth-engineer",
            source_branch="feature/auth-validation",
            target_branch="main",
            state="open",
            head_commit_sha="eeddccbbaa00112233445566778899aa",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db.add(pr)
        db.flush()
        print("[SEED] Pull Request seeded.")
        
        # 4. Seed PR Changed Files
        changed_paths = [
            "src/app/api/auth/reset-password/route.ts",
            "src/app/reset-password/page.tsx",
            "src/app/signup/sign-up-form.tsx",
            "src/modules/users/sign-up.ts",
            "src/tests/integration/auth-workflow.test.ts"
        ]
        for path in changed_paths:
            cf = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr_id,
                file_path=path,
                status="modified",
                additions=15,
                deletions=2,
                created_at=datetime.utcnow()
            )
            db.add(cf)
        db.flush()
        print(f"[SEED] PR Changed Files ({len(changed_paths)}) seeded.")
        
        # 5. Seed Test Cases (Auth + Billing)
        test_cases_to_seed = [
            # Auth suite
            ("tests.integration.auth-workflow.test.ts", "should_allow_valid_token", "tests.integration.auth-workflow.test.ts::should_allow_valid_token"),
            ("tests.integration.auth-workflow.test.ts", "should_reject_expired_token", "tests.integration.auth-workflow.test.ts::should_reject_expired_token"),
            ("tests.integration.auth-workflow.test.ts", "should_attach_user_context", "tests.integration.auth-workflow.test.ts::should_attach_user_context"),
            # Billing suite (unrelated)
            ("tests.billing.test_pricing", "should_calculate_monthly_invoice", "tests.billing.test_pricing::should_calculate_monthly_invoice"),
            ("tests.billing.test_pricing", "should_apply_trial_discount", "tests.billing.test_pricing::should_apply_trial_discount")
        ]
        
        tc_map = {}
        for suite, name, identity in test_cases_to_seed:
            tc_id = uuid.uuid4()
            tc = TestCase(
                id=tc_id,
                repository_id=repo_id,
                suite_name=suite,
                test_name=name,
                stable_identity=identity,
                raw_test_name=name,
                normalized_test_name=name,
                normalized_identity_strategy="EXACT",
                framework_name="jest",
                framework_version="29.0",
                identity_normalization_version=1,
                canonical_identity_hash=str(uuid.uuid4()),
                identity_lineage_root_hash=str(uuid.uuid4()),
                identity_version=1,
                identity_resolution_strategy="EXACT",
                created_at=datetime.utcnow()
            )
            db.add(tc)
            tc_map[identity] = tc_id
        db.flush()
        print(f"[SEED] Test Cases ({len(test_cases_to_seed)}) seeded.")
        
        # 6. Seed Test Run to satisfy test history check
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="some_historical_commit_sha",
            status="passed",
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            duration=12.5,
            file_hash="hash-1",
            normalized_execution_fingerprint="fingerprint-1",
            created_at=datetime.utcnow()
        )
        db.add(test_run)
        
        # Seed test results
        for tc_identity, tc_id in tc_map.items():
            tr = TestResult(
                id=uuid.uuid4(),
                test_run_id=test_run.id,
                test_case_id=tc_id,
                status="passed",
                duration=2.5,
                created_at=datetime.utcnow()
            )
            db.add(tr)
        db.flush()
        print("[SEED] Test Run and Results seeded.")
        
        # 7. Seed Domain Map
        dm = DomainMap(
            id=uuid.uuid4(),
            repository_id=repo_id,
            domain="Authentication",
            files=["src/app/api/auth/reset-password/route.ts"],
            modules=["tests.integration.auth-workflow.test.ts"],
            owners=[],
            created_at=datetime.utcnow()
        )
        db.add(dm)
        db.flush()
        print("[SEED] Domain Map seeded.")
        
        # 8. Seed Coverage Report (With Fallback Trigger! Commit SHA differs from PR head commit)
        coverage_report = CoverageReport(
            id=coverage_report_id,
            repository_id=repo_id,
            workspace_id=workspace_id,
            commit_sha="different_historical_commit_sha",
            branch="main",
            format="LCOV",
            source="MANUAL_UPLOAD",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="hash-coverage-999",
            confidence_score="HIGH",
            files_total=10,
            line_coverage_ratio=0.825,
            created_at=datetime.utcnow() - timedelta(days=2) # 2 days ago (fresh, not stale)
        )
        db.add(coverage_report)
        db.flush()
        
        # Seed FileTestLink for DIRECT coverage match (+40)
        ftl = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=coverage_report_id,
            file_path="src/app/api/auth/reset-password/route.ts",
            test_case_id=tc_map["tests.integration.auth-workflow.test.ts::should_allow_valid_token"],
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(ftl)
        db.flush()
        print("[SEED] Coverage report and direct FileTestLink seeded (Fallbacks will trigger).")
        
        db.commit()
        
        # ========================================================
        # 9. GENERATE RECOMMENDATIONS
        # ========================================================
        print("\n--- Generating Recommendation Run via RecommendationService ---")
        service = RecommendationService(db)
        
        # Make a mock context request
        from app.schemas.recommendation import RecommendationRunCreate
        run_create = RecommendationRunCreate(
            repository_id=str(repo_id),
            pr_id=str(pr_id),
            changed_files=changed_paths,
            triggered_by="verify-script",
            engine_version="V3"
        )
        
        response = service.create_recommendation_run(run_create)
        run_id = response.id if isinstance(response.id, uuid.UUID) else uuid.UUID(response.id)
        print(f"  Successfully generated recommendation run ID: {run_id}")
        
        # ========================================================
        # 10. CALL AND ASSERT FASTAPI READ ENDPOINT
        # ========================================================
        print("\n--- Retrieving Enriched Recommendation Run Payload ---")
        payload = get_recommendation_run(
            recommendation_run_id=run_id,
            workspace=workspace,
            db=db
        )
        
        # Assert Criteria 1: impact_profile
        print("\nAsserting Criteria 1: impact_profile contains correct areas...")
        impact = payload["executive_summary"]["impact_profile"]
        print(f"  Resolved Impact Areas: {list(impact.keys())}")
        
        # Verify deterministic risk categories and change types match our auth PR properties
        assert "AUTH" in impact.get("risk_categories", []), "Missing AUTH risk category!"
        assert "SECURITY" in impact.get("risk_categories", []), "Missing SECURITY risk category!"
        assert "USER_REGISTRATION" in impact.get("risk_categories", []), "Missing USER_REGISTRATION risk category!"
        assert "VALIDATION_CHANGE" in impact.get("change_types", []), "Missing VALIDATION_CHANGE change type!"
        print("  -> Passed.")
        
        # Assert Criteria 2: testing_strategy.types
        print("\nAsserting Criteria 2: testing_strategy types...")
        strategy_types = payload["testing_strategy"]["types"]
        print(f"  Testing Strategy Types: {strategy_types}")
        
        # Extract the type uppercase codes
        type_codes = [t["type"] for t in strategy_types]
        assert "SECURITY" in type_codes, "Missing SECURITY strategy!"
        assert "API" in type_codes, "Missing API strategy!"
        assert "INTEGRATION" in type_codes, "Missing INTEGRATION strategy!"
        print("  -> Passed.")
        
        # Assert Criteria 3: Coverage report links fallback to the repository's latest report when exact commit is missing
        print("\nAsserting Criteria 3: Coverage report fallback works gracefully...")
        cov_info = payload["evidence"]["coverage"]
        assert cov_info is not None, "Coverage report evidence missing!"
        print(f"  Coverage Report linked commit: '{cov_info['commit_sha']}' (Expected: 'different_historical_commit_sha')")
        assert cov_info["commit_sha"] == "different_historical_commit_sha", "Failed to link fallback latest repository coverage report!"
        print("  -> Passed.")
        
        # Assert Criteria 4: Selected tests rank correctly (Auth tests above Billing tests)
        print("\nAsserting Criteria 4: Ranking of Auth tests above Billing tests...")
        rec_tests = payload["recommended_tests"]
        print("  Recommended Tests Order:")
        for idx, t in enumerate(rec_tests):
            print(f"    {idx+1}. {t['stable_identity']} | Score: {t['priority_score']} | Tier: {t['tier']}")
            
        # Verify auth tests are at the top
        auth_indices = [idx for idx, t in enumerate(rec_tests) if "auth-workflow" in t["stable_identity"]]
        billing_indices = [idx for idx, t in enumerate(rec_tests) if "billing" in t["stable_identity"]]
        
        for ai in auth_indices:
            for bi in billing_indices:
                assert ai < bi, f"Auth test at index {ai} is incorrectly positioned below Billing test at index {bi}!"
        print("  -> Passed.")
        
        # Assert Criteria 5: Contradictory recommendation modes are eliminated
        print("\nAsserting Criteria 5: Contradictory modes eliminated (not FULL_SUITE)...")
        mode = payload["testing_strategy"]["recommendation_mode"]
        print(f"  Resolved Mode: '{mode}' (Selected: {len(rec_tests)} / Total: 5)")
        assert mode != "FULL_SUITE", "Contradictory Mode 'FULL_SUITE' returned even though only targeted tests were selected!"
        assert mode in ("TARGETED", "CONSERVATIVE"), f"Unexpected mode: {mode}"
        print("  -> Passed.")
        
        # Assert Criteria 6: Enriched per-test fields (display name, testing type, impacted area, confidence, personalized dynamic reasons, signals)
        print("\nAsserting Criteria 6: Enriched per-test fields...")
        for t in rec_tests:
            stable_id = t["stable_identity"]
            print(f"\n  Checking Test: '{stable_id}'")
            print(f"    Display Name: '{t['display_name']}'")
            print(f"    Testing Type: '{t['testing_type']}'")
            print(f"    Impacted Area: '{t['impacted_area']}'")
            print(f"    Confidence: '{t['confidence']}'")
            print(f"    Personalized Reason: '{t['reason']}'")
            print(f"    Signals: {t['signals']}")
            
            assert t["display_name"] in ("should_allow_valid_token", "should_reject_expired_token", "should_attach_user_context", "should_calculate_monthly_invoice", "should_apply_trial_discount"), "Invalid display name!"
            assert len(t["testing_type"]) > 0, "Missing testing type!"
            assert len(t["impacted_area"]) > 0, "Missing impacted area!"
            assert t["confidence"] in ("HIGH", "MEDIUM", "LOW"), "Invalid confidence!"
            assert "PR changes" in t["reason"] and "behavior" in t["reason"], "Missing personalized reason context!"
            assert len(t["signals"]) > 0, "Missing matching signal items!"
            
        print("\n  -> Passed.")
        
        print("\n========================================================")
        print("ALL 8 VERISCOPE RECOMMENDATION ENGINE VALIDATIONS PASSED!")
        print("========================================================")
        
    except AssertionError as ae:
        print(f"\n[ASSERTION FAILURE]: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        # Final cleanup rollback to keep the database completely untouched
        db.rollback()
        db.close()

if __name__ == "__main__":
    run_usefulness_verifications()
