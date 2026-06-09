import os
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.recommendation import RecommendationRun, RecommendationTest
from app.services.recommendation_explanation_builder import RecommendationExplanationBuilder

def run_explanation_builder_verification():
    print("======================================================================")
    print("STARTING RECOMMENDATION EXPLANATION BUILDER VERIFICATIONS")
    print("======================================================================\n")

    # ====================================================================
    # Test 1. Determinism Verification
    # ====================================================================
    print("--- 1. Testing Determinism ---")
    
    # Mock recommendation runs with exactly the same inputs
    run1 = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        pr_id="sha_123",
        triggered_by="manual",
        evidence_quality="HIGH",
        engine_version="v1.0",
        recommendation_mode="NORMAL",
        skipped_count=805,
        estimated_runtime_seconds=1080.0, # 18 min
        full_suite_runtime_seconds=8040.0  # 2h 14m
    )
    
    # Mock tests relationship
    run1.tests = [RecommendationTest(id=uuid.uuid4()) for _ in range(42)]
    
    run2 = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        pr_id="sha_456",
        triggered_by="manual",
        evidence_quality="HIGH",
        engine_version="v1.0",
        recommendation_mode="NORMAL",
        skipped_count=805,
        estimated_runtime_seconds=1080.0,
        full_suite_runtime_seconds=8040.0
    )
    run2.tests = [RecommendationTest(id=uuid.uuid4()) for _ in range(42)]
    
    res1 = RecommendationExplanationBuilder.build_recommendation_summary(run1)
    res2 = RecommendationExplanationBuilder.build_recommendation_summary(run2)
    
    assert res1 == res2
    print("[OK] Deterministic output matches identically for identical inputs.")

    # ====================================================================
    # Test 2. Duration Formatting Verification
    # ====================================================================
    print("\n--- 2. Testing Duration Formatting ---")
    
    # < 60 minutes
    assert RecommendationExplanationBuilder.format_duration(1080.0) == "18 min"
    assert RecommendationExplanationBuilder.format_duration(30.0) == "1 min"
    assert RecommendationExplanationBuilder.format_duration(0.0) == "0 min"
    assert RecommendationExplanationBuilder.format_duration(3599.0) == "1h 0m"  # Rounded to 60, but wait:
    # 60 min is >= 60 min, so let's check:
    # 3599.0 seconds -> 60 minutes -> 1h 0m
    print(f"DEBUG: 3599s -> {RecommendationExplanationBuilder.format_duration(3599.0)}")
    assert RecommendationExplanationBuilder.format_duration(3599.0) == "1h 0m"
    
    # >= 60 minutes
    assert RecommendationExplanationBuilder.format_duration(3600.0) == "1h 0m"
    assert RecommendationExplanationBuilder.format_duration(8040.0) == "2h 14m"
    assert RecommendationExplanationBuilder.format_duration(7200.0) == "2h 0m"
    print("[OK] Exact duration formatting matched: '< 60m' prints as 'X min', '>= 60m' prints as 'Yh Zm'.")

    # ====================================================================
    # Test 3. Coverage Confidence Mapping
    # ====================================================================
    print("\n--- 3. Testing Coverage Confidence Boundaries ---")
    
    # Allowed boundary checks
    for q in ["HIGH", "MODERATE", "LOW"]:
        run1.evidence_quality = q
        res = RecommendationExplanationBuilder.build_recommendation_summary(run1)
        assert res["coverage_confidence"] == q
        
    # Check invalid mappings fallback cleanly to LOW (no crash)
    for invalid in ["UNKNOWN", "STALE", None]:
        run1.evidence_quality = invalid
        res = RecommendationExplanationBuilder.build_recommendation_summary(run1)
        assert res["coverage_confidence"] == "LOW"
        
    print("[OK] Coverage confidence mapped strictly to HIGH / MODERATE / LOW with graceful fallbacks.")

    # ====================================================================
    # Test 4. Output Formatting & Avoid Fake Precision
    # ====================================================================
    print("\n--- 4. Checking Formatting & Prohibited Phrasing ---")
    
    run1.evidence_quality = "HIGH"
    res = RecommendationExplanationBuilder.build_recommendation_summary(run1)
    
    lines = res["summary_lines"]
    print("DEBUG: Generated Summary Lines:")
    for line in lines:
        print(f"  {line}")
        
    assert lines[0] == "Recommended Regression Suite"
    assert lines[1] == "Run 42 tests out of 847"
    assert lines[2] == "Estimated runtime: 18 min vs 2h 14m full suite"
    
    # Ensure no float values are present in key outputs to avoid fake precision
    assert isinstance(res["recommended_tests_count"], int)
    assert isinstance(res["total_tests_count"], int)
    assert isinstance(res["estimated_runtime_minutes"], int)
    assert isinstance(res["full_suite_runtime_minutes"], int)
    
    # Scan for prohibited patterns in the summary lines
    for line in lines:
        assert "%" not in line, "Avoid exposing raw percentage metrics!"
        assert "probability" not in line.lower(), "Avoid probabilistic release claims!"
        assert "likely" not in line.lower(), "Avoid probabilistic claims!"
        assert "exaggerated" not in line.lower(), "Avoid exaggerated optimization claims!"
        
    print("[OK] Summary layout matches specification example exactly; no fake precision or prohibited language present.")

    # ====================================================================
    # Test 5. Graceful Missing Full Suite Fallback
    # ====================================================================
    print("\n--- 5. Checking Missing Full Suite Graceful Fallback ---")
    run1.full_suite_runtime_seconds = None
    res = RecommendationExplanationBuilder.build_recommendation_summary(run1)
    lines = res["summary_lines"]
    print("DEBUG: Fallback Summary Lines:")
    for line in lines:
        print(f"  {line}")
    assert "Estimated runtime: 18 min vs 3h 0m full suite" in lines[2]
    print("[OK] Missing full suite runtime cleanly handled with a deterministic 10x fallback comparison.")

    print("\n=======================================================")
    print("ALL RECOMMENDATION EXPLANATION BUILDER VERIFICATIONS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_explanation_builder_verification()
