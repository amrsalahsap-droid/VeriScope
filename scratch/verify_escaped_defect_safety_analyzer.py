import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.escaped_defect_safety_analyzer import EscapedDefectSafetyAnalyzer

def run_verification():
    print("======================================================================")
    print("STARTING VERISCOPE PHASE 7: ESCAPED DEFECT SAFETY ANALYZER VERIFICATION")
    print("======================================================================\n")

    # Scenario 1: Stable, Complete Lineage
    print("--- TEST 1: Testing Stable, Complete Lineage Scenario ---")
    res1 = EscapedDefectSafetyAnalyzer.analyze_safety(
        total_outcomes=10,
        escaped_defects_count=0,
        rollbacks_count=0,
        is_incident_lineage_complete=True,
        recommendation_frequency=10
    )
    assert res1["safety_status"] == "STABLE"
    assert "No increase in escaped defects observed during pilot window." in res1["safety_assessment"]
    assert "Rollback-linked outcomes remained stable." in res1["safety_assessment"]
    assert "Incident and rollback linkages reflect temporal correlation" in res1["safety_assessment"]
    # NEVER claim "prevented incidents"
    assert "prevented" not in res1["safety_assessment"].lower()
    assert res1["confidence_warning"] is None
    assert res1["incomplete_lineage_warning"] is None
    print("[PASSED] Stable complete lineage safety assessment looks clean and objective.\n")

    # Scenario 2: Low Volume (Tiny Dataset)
    print("--- TEST 2: Testing Low Volume / Tiny Dataset Scenario ---")
    res2 = EscapedDefectSafetyAnalyzer.analyze_safety(
        total_outcomes=4,
        escaped_defects_count=0,
        rollbacks_count=0,
        is_incident_lineage_complete=True,
        recommendation_frequency=4
    )
    assert res2["safety_status"] == "INSUFFICIENT_DATA"
    assert "insufficient to establish safety trends" in res2["safety_assessment"]
    assert res2["confidence_warning"] is not None
    assert "WARNING: Tiny dataset" in res2["confidence_warning"]
    assert res2["incomplete_lineage_warning"] is None
    print(f"[PASSED] Correctly handled tiny dataset with status INSUFFICIENT_DATA:\n{res2['safety_assessment']}\n")

    # Scenario 3: Incomplete Telemetry Lineage
    print("--- TEST 3: Testing Incomplete Telemetry Lineage Scenario ---")
    res3 = EscapedDefectSafetyAnalyzer.analyze_safety(
        total_outcomes=12,
        escaped_defects_count=0,
        rollbacks_count=0,
        is_incident_lineage_complete=False,
        recommendation_frequency=12
    )
    assert res3["safety_status"] == "STABLE"
    assert res3["confidence_warning"] is None
    assert res3["incomplete_lineage_warning"] is not None
    assert "Incomplete incident lineage detected" in res3["incomplete_lineage_warning"]
    print(f"[PASSED] Incomplete lineage warning successfully returned:\n{res3['incomplete_lineage_warning']}\n")

    # Scenario 4: Defects / Rollbacks Present (Attention status)
    print("--- TEST 4: Testing Attention Status with Active Failures ---")
    res4 = EscapedDefectSafetyAnalyzer.analyze_safety(
        total_outcomes=10,
        escaped_defects_count=1,
        rollbacks_count=2,
        is_incident_lineage_complete=True,
        recommendation_frequency=10
    )
    assert res4["safety_status"] == "ATTENTION"
    assert res4["escaped_defect_rate_percent"] == 10.0
    assert res4["rollback_rate_percent"] == 20.0
    assert "temporal correlation analysis registered 1 escaped defect" in res4["safety_assessment"].lower()
    assert "2 rollback-linked outcomes" in res4["safety_assessment"]
    # Verify disclaimer is attached
    assert "direct causal relationships are not automatically assumed" in res4["safety_assessment"].lower()
    assert "prevented" not in res4["safety_assessment"].lower()
    print(f"[PASSED] Attention status correctly formatted with rates and disclaimers:\n{res4['safety_assessment']}\n")

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 ESCAPED DEFECT SAFETY ANALYZER TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
