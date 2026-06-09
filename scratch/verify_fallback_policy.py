import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.recommendation import FallbackEvidenceBundle
from app.services.fallback_policy_engine import FallbackPolicyEngine


def test_level_1_normal():
    print("--- Testing LEVEL_1 NORMAL Mode ---")
    bundle = FallbackEvidenceBundle(
        pr_evidence_health="HEALTHY",
        coverage_confidence="HIGH",
        dependency_graph_confidence="HIGH",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=False,
        changed_files_availability=True,
        changed_area_risky=False
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle)
    assert decision.recommendation_mode == "NORMAL"
    assert decision.optimization_allowed is True
    assert decision.fallback_level == "LEVEL_1"
    assert decision.evidence_quality == "HIGH"
    assert decision.expansion_depth == 0
    assert decision.include_historical_failures is False
    assert decision.include_critical_tests is False
    assert decision.full_regression_required is False
    print("[PASSED] Level 1 Normal successfully mapped.\n")


def test_level_2_widened():
    print("--- Testing LEVEL_2 WIDENED Mode ---")
    bundle = FallbackEvidenceBundle(
        pr_evidence_health="DEGRADED",
        coverage_confidence="MODERATE",
        dependency_graph_confidence="HIGH",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=False,
        changed_files_availability=True,
        changed_area_risky=False
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle)
    assert decision.recommendation_mode == "WIDENED"
    assert decision.optimization_allowed is True
    assert decision.fallback_level == "LEVEL_2"
    assert decision.evidence_quality == "MODERATE"
    assert decision.expansion_depth == 2
    assert decision.include_historical_failures is False
    assert decision.include_critical_tests is False
    assert decision.full_regression_required is False
    print("[PASSED] Level 2 Widened successfully mapped.\n")


def test_level_3_safe_fallback():
    print("--- Testing LEVEL_3 SAFE_FALLBACK Mode ---")
    bundle = FallbackEvidenceBundle(
        pr_evidence_health="DEGRADED",
        coverage_confidence="LOW",
        dependency_graph_confidence="HIGH",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=False,
        changed_files_availability=True,
        changed_area_risky=False
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle)
    assert decision.recommendation_mode == "SAFE_FALLBACK"
    assert decision.optimization_allowed is True
    assert decision.fallback_level == "LEVEL_3"
    assert decision.evidence_quality == "LOW"
    assert decision.expansion_depth == 3
    assert decision.include_historical_failures is True
    assert decision.include_critical_tests is False
    assert decision.full_regression_required is False
    print("[PASSED] Level 3 Safe Fallback successfully mapped.\n")


def test_level_4_critical():
    print("--- Testing LEVEL_4 CRITICAL Mode ---")
    bundle = FallbackEvidenceBundle(
        pr_evidence_health="DEGRADED",
        coverage_confidence="LOW",
        dependency_graph_confidence="HIGH",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=False,
        changed_files_availability=True,
        changed_area_risky=True
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle)
    assert decision.recommendation_mode == "CRITICAL"
    assert decision.optimization_allowed is True
    assert decision.fallback_level == "LEVEL_4"
    assert decision.evidence_quality == "LOW"
    assert decision.expansion_depth == 3
    assert decision.include_historical_failures is True
    assert decision.include_critical_tests is True
    assert decision.full_regression_required is False
    print("[PASSED] Level 4 Critical successfully mapped.\n")


def test_level_5_full_regression():
    print("--- Testing LEVEL_5 FULL_REGRESSION Override Mode ---")
    
    # 1. Unsafe for optimization override
    bundle_unsafe = FallbackEvidenceBundle(
        pr_evidence_health="HEALTHY",
        coverage_confidence="HIGH",
        dependency_graph_confidence="HIGH",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=True,
        changed_files_availability=True,
        changed_area_risky=False
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle_unsafe)
    assert decision.recommendation_mode == "FULL_REGRESSION"
    assert decision.optimization_allowed is False
    assert decision.fallback_level == "LEVEL_5"
    assert decision.evidence_quality == "UNKNOWN"
    assert decision.expansion_depth == 0
    assert decision.full_regression_required is True

    # 2. Both coverage and dependency missing override
    bundle_missing = FallbackEvidenceBundle(
        pr_evidence_health="HEALTHY",
        coverage_confidence="MISSING",
        dependency_graph_confidence="UNKNOWN",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=False,
        changed_files_availability=True,
        changed_area_risky=False
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle_missing)
    assert decision.recommendation_mode == "FULL_REGRESSION"
    assert decision.optimization_allowed is False
    assert decision.fallback_level == "LEVEL_5"
    assert decision.full_regression_required is True

    # 3. Changed files not available override
    bundle_no_files = FallbackEvidenceBundle(
        pr_evidence_health="HEALTHY",
        coverage_confidence="HIGH",
        dependency_graph_confidence="HIGH",
        flaky_profile_health="HEALTHY",
        evidence_consistency="CONSISTENT",
        unsafe_for_optimization=False,
        changed_files_availability=False,
        changed_area_risky=False
    )
    decision = FallbackPolicyEngine.determine_recommendation_mode(bundle_no_files)
    assert decision.recommendation_mode == "FULL_REGRESSION"
    assert decision.optimization_allowed is False
    assert decision.fallback_level == "LEVEL_5"
    assert decision.full_regression_required is True

    print("[PASSED] Level 5 Full Regression safety overrides successfully mapped.\n")


def main():
    print("======================================================================")
    print("STARTING FALLBACK POLICY ENGINE SERVICE INTEGRATION VERIFICATION")
    print("======================================================================\n")

    test_level_1_normal()
    test_level_2_widened()
    test_level_3_safe_fallback()
    test_level_4_critical()
    test_level_5_full_regression()

    print("ALL FALLBACK POLICY ENGINE INTEGRATION CHECKS PASSED SUCCESSFULLY!\n")


if __name__ == "__main__":
    main()
