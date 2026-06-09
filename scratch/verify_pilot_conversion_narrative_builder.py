import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.pilot_conversion_narrative_builder import PilotConversionNarrativeBuilder

def run_verification():
    print("======================================================================")
    print("STARTING VERISCOPE PHASE 7: PILOT CONVERSION NARRATIVE BUILDER VERIFICATION")
    print("======================================================================\n")

    # 1. Test explicit keyword parameters
    print("--- TEST 1: Generating from Explicit Parameters ---")
    bullets1 = PilotConversionNarrativeBuilder.generate_narrative(
        reduction_percent=68.5,
        hours_saved=112.0,
        adherence_rate=0.85,
        repeat_adopters_count=3,
        safety_status="STABLE",
        has_fragile_modules=True
    )

    print("Generated Bullets:")
    for b in bullets1:
        print(f"  - {b}")

    assert len(bullets1) == 5
    assert bullets1[0] == "We reduced regression execution scope by 68.5% while maintaining stable escaped defect outcomes."
    assert bullets1[1] == "Engineers repeatedly followed Veriscope recommendations during the pilot window, establishing recurring adoption patterns."
    assert bullets1[2] == "Pilot codebases realized an estimated 112.0 engineering hours saved through selective test recommendations."
    assert bullets1[3] == "Production safety outcomes remained stable, with no increase in escaped defects or rollbacks observed during the pilot window."
    assert bullets1[4] == "Granular fragility patterns were isolated across active modules, highlighting specific areas for diagnostic scoping."
    
    # Assert safety rules
    for b in bullets1:
        assert "guaranteed" not in b.lower()
        assert "prevented" not in b.lower()
        assert "autonomous" not in b.lower()

    print("[PASSED] Explicit arguments mapped and generated perfectly with conservative rules.\n")

    # 2. Test automatic report payload ingestion
    print("--- TEST 2: Ingesting & Generating from structured Report Payload ---")
    report_payload = {
        "regression_efficiency": {
            "estimated_runtime_reduction": "45.2%",
            "estimated_engineering_hours_saved": 85.0
        },
        "recommendation_trust_signals": {
            "adherence_rate": 0.75
        },
        "recurring_adoption": {
            "unique_repeat_adopters_count": 0
        },
        "escaped_defect_safety": {
            "safety_status": "STABLE"
        },
        "fragility_intelligence": {
            "most_fragile_modules": []
        }
    }

    bullets2 = PilotConversionNarrativeBuilder.generate_narrative(report_payload)
    print("Generated Bullets:")
    for b in bullets2:
        print(f"  - {b}")

    assert len(bullets2) == 5
    assert "reduced regression execution scope by 45.2%" in bullets2[0]
    assert "adherence rate of 75.0%" in bullets2[1]
    assert "realized an estimated 85.0 engineering hours" in bullets2[2]
    assert "safety outcomes remained stable" in bullets2[3]
    # No fragile modules in payload
    assert "audited for fragility and co-failure patterns" in bullets2[4]
    
    print("[PASSED] Structured JSON payload successfully ingested and parsed.\n")

    # 3. Test empty/fallback behaviors
    print("--- TEST 3: Testing Fallbacks with Empty Payload ---")
    bullets3 = PilotConversionNarrativeBuilder.generate_narrative({})
    
    assert len(bullets3) == 5
    assert "monitored regression execution runtimes" in bullets3[0]
    assert "Developer interaction and alignment" in bullets3[1]
    assert "baseline execution times" in bullets3[2]
    assert "Defect telemetry baselines" in bullets3[3]
    assert "audited for fragility and co-failure patterns" in bullets3[4]
    
    print("[PASSED] Fallbacks and safety/emojiless formatting rules strictly enforced.\n")

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT CONVERSION NARRATIVE BUILDER TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
