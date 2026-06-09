import os
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.services.skipped_reasoning_service import SkippedReasoningService
from app.schemas.recommendation import SkippedSummary

def run_verification():
    print("======================================================================")
    print("STARTING SKIPPED REASONING SERVICE DIRECT UNIT TESTS")
    print("======================================================================\n")

    db = SessionLocal()
    repo_id = uuid.uuid4()

    try:
        # Test Case 1: High Evidence Quality with Skips
        print("--- Test 1: High Evidence Quality ---")
        recommended = ["test_a", "test_b"]
        all_tests = ["test_f", "test_e", "test_b", "test_a", "test_c", "test_d"]
        
        summary = SkippedReasoningService.build_skipped_summary(
            db=db,
            repository_id=repo_id,
            recommended_test_ids=recommended,
            all_test_ids=all_tests,
            evidence_quality="HIGH",
            max_examples=3
        )
        
        assert summary.skipped_count == 4, f"Expected 4 skipped tests, got {summary.skipped_count}"
        # top_skipped_examples should be sorted alphabetically: "test_c", "test_d", "test_e"
        assert summary.top_skipped_examples == ["test_c", "test_d", "test_e"], f"Expected sorted top 3 examples, got {summary.top_skipped_examples}"
        assert "Safe to skip under high trust evidence quality." in summary.skipped_reason_summary
        print("[PASSED] High evidence quality assertions passed!")

        # Test Case 2: Moderate Evidence Quality
        print("\n--- Test 2: Moderate Evidence Quality ---")
        summary_mod = SkippedReasoningService.build_skipped_summary(
            db=db,
            repository_id=repo_id,
            recommended_test_ids=recommended,
            all_test_ids=all_tests,
            evidence_quality="MODERATE",
            max_examples=3
        )
        assert summary_mod.skipped_count == 4
        assert "Not selected by current evidence" in summary_mod.skipped_reason_summary
        assert "No direct or dependency mapping found" in summary_mod.skipped_reason_summary
        assert "moderate trust" in summary_mod.skipped_reason_summary
        assert "Safe to skip" not in summary_mod.skipped_reason_summary
        print("[PASSED] Moderate evidence quality assertions passed!")

        # Test Case 3: Low/Unknown Evidence Quality
        print("\n--- Test 3: Low/Unknown Evidence Quality ---")
        for eq in ["LOW", "UNKNOWN", "OTHER_STUFF"]:
            summary_low = SkippedReasoningService.build_skipped_summary(
                db=db,
                repository_id=repo_id,
                recommended_test_ids=recommended,
                all_test_ids=all_tests,
                evidence_quality=eq,
                max_examples=3
            )
            assert summary_low.skipped_count == 4
            assert "Not selected by current evidence" in summary_low.skipped_reason_summary
            assert "No direct or dependency mapping found" in summary_low.skipped_reason_summary
            assert "Caution: Skipped under low or unknown trust evidence quality" in summary_low.skipped_reason_summary
            assert "Safe to skip" not in summary_low.skipped_reason_summary
        print("[PASSED] Low/Unknown evidence quality assertions passed!")

        # Test Case 4: No Tests Skipped
        print("\n--- Test 4: No Tests Skipped ---")
        summary_none = SkippedReasoningService.build_skipped_summary(
            db=db,
            repository_id=repo_id,
            recommended_test_ids=recommended,
            all_test_ids=recommended,
            evidence_quality="HIGH",
            max_examples=3
        )
        assert summary_none.skipped_count == 0
        assert summary_none.top_skipped_examples == []
        assert summary_none.skipped_reason_summary == "No tests were skipped."
        print("[PASSED] No tests skipped assertions passed!")

        # Test Case 5: Custom Max Examples Limit
        print("\n--- Test 5: Custom Max Examples Limit ---")
        summary_limit = SkippedReasoningService.build_skipped_summary(
            db=db,
            repository_id=repo_id,
            recommended_test_ids=recommended,
            all_test_ids=all_tests,
            evidence_quality="HIGH",
            max_examples=2
        )
        assert summary_limit.skipped_count == 4
        assert summary_limit.top_skipped_examples == ["test_c", "test_d"]
        print("[PASSED] Custom max examples limit assertions passed!")

        # Test Case 6: Schema Parsing/Validation
        print("\n--- Test 6: Schema Parsing/Validation ---")
        # Validate dump and reload via Pydantic model
        data = summary.model_dump()
        parsed = SkippedSummary(**data)
        assert parsed.skipped_count == summary.skipped_count
        assert parsed.skipped_reason_summary == summary.skipped_reason_summary
        assert parsed.top_skipped_examples == summary.top_skipped_examples
        print("[PASSED] Pydantic schema validation passed!")

        print("\n======================================================================")
        print("ALL SKIPPED REASONING SERVICE UNIT TESTS PASSED SUCCESSFULLY!")
        print("======================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
