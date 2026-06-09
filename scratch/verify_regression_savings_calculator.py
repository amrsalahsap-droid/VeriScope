import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.regression_savings_calculator import RegressionSavingsCalculator

def run_verification():
    print("======================================================================")
    print("STARTING VERISCOPE PHASE 7: REGRESSION SAVINGS CALCULATOR VERIFICATION")
    print("======================================================================\n")

    # 1. Test Duration Formatting helper
    print("--- TEST 1: Testing Duration Formatting Helper ---")
    assert RegressionSavingsCalculator.format_duration(7800.0) == "2h 10m"
    assert RegressionSavingsCalculator.format_duration(2460.0) == "41m"
    assert RegressionSavingsCalculator.format_duration(150.0) == "2m 30s"
    assert RegressionSavingsCalculator.format_duration(30.0) == "30s"
    assert RegressionSavingsCalculator.format_duration(0.0) == "0s"
    print("[PASSED] Duration formatting works perfectly for all boundary types.\n")

    # 2. Test Example Calculations (2h 10m baseline vs 41m recommended with 76 executions)
    print("--- TEST 2: Testing Core Example Calculations & ROI ---")
    res = RegressionSavingsCalculator.calculate_savings(
        full_suite_baseline_seconds=7800.0,   # 2h 10m
        recommended_runtime_seconds=2460.0,   # 41m
        recommendation_frequency=100,
        execution_frequency=76,
        excluded_runs=3,
        missing_runtime_data=2
    )

    assert res is not None
    assert res["average_full_suite_runtime"] == "2h 10m"
    assert res["average_veriscope_runtime"] == "41m"
    
    # Reduction percentage: (7800 - 2460) / 7800 = 5340 / 7800 = 68.46% (rounds to 68.5%)
    assert res["estimated_runtime_reduction"] == "68.5%"
    assert res["estimated_runtime_reduction_percent"] == 68.46

    # Engineering hours saved: (5340 seconds * 76 runs) / 3600 = 405840 / 3600 = 112.73 hours (rounds to 112.7)
    assert res["estimated_engineering_hours_saved"] == 112.7
    assert res["estimated_engineering_hours_saved_str"] == "112.7 hours"

    # Exclusions preservation
    assert res["excluded_runs_count"] == 3
    assert res["missing_runtime_data_runs_count"] == 2
    
    print("[PASSED] Deterministic savings and formatted times match example expectations!\n")

    # 3. Test Formula Transparency
    print("--- TEST 3: Testing Formula Transparency ---")
    transparency = res["formula_transparency"]
    assert transparency is not None
    assert "Full Suite Baseline" in transparency
    assert "Recommended Runtime" in transparency
    assert "Execution Frequency" in transparency
    assert "0.0 savings" in transparency
    print(f"[PASSED] Formula transparency validated successfully:\n{transparency}\n")

    # 4. Test Small Dataset Warnings
    print("--- TEST 4: Testing Dataset Size Warnings ---")
    # Low execution count
    res_low = RegressionSavingsCalculator.calculate_savings(
        full_suite_baseline_seconds=100.0,
        recommended_runtime_seconds=50.0,
        recommendation_frequency=4,
        execution_frequency=2
    )
    warning = res_low["confidence_warning"]
    assert warning is not None
    assert "WARNING: Small dataset" in warning
    assert "recommendations = 4" in warning
    assert "executions = 2" in warning
    print(f"[PASSED] Dataset size warning emitted correctly:\n{warning}\n")

    # Normal count
    res_normal = RegressionSavingsCalculator.calculate_savings(
        full_suite_baseline_seconds=100.0,
        recommended_runtime_seconds=50.0,
        recommendation_frequency=10,
        execution_frequency=5
    )
    assert res_normal["confidence_warning"] is None
    print("[PASSED] Normal dataset returns no warning flags.\n")

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 REGRESSION SAVINGS CALCULATOR TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
