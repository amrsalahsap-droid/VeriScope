import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.pilot_executive_summary_renderer import PilotExecutiveSummaryRenderer

def run_verification():
    print("======================================================================")
    print("STARTING VERISCOPE PHASE 7: PILOT EXECUTIVE SUMMARY RENDERER VERIFICATION")
    print("======================================================================\n")

    # 1. Test explicit keyword arguments rendering
    print("--- TEST 1: Rendering from Explicit Keyword Arguments ---")
    summary1 = PilotExecutiveSummaryRenderer.render(
        prs_analyzed=86,
        average_full_regression_runtime="2h 10m",
        average_veriscope_recommended_runtime="41m",
        estimated_time_saved="112 engineering hours/month",
        escaped_defects="No increase observed during pilot window",
        most_fragile_modules=["auth", "billing", "notification pipeline"]
    )

    expected1 = (
        "PRs analyzed: 86\n\n"
        "Average full regression runtime:\n"
        "2h 10m\n\n"
        "Average Veriscope recommended runtime:\n"
        "41m\n\n"
        "Estimated time saved:\n"
        "112 engineering hours/month\n\n"
        "Escaped defects:\n"
        "No increase observed during pilot window\n\n"
        "Most fragile modules:\n"
        "- auth\n"
        "- billing\n"
        "- notification pipeline"
    )

    print("Rendered Output:")
    print("----------------------------------------")
    print(summary1)
    print("----------------------------------------")
    
    assert summary1 == expected1, "Explicit kwargs rendering does not match expected output format."
    print("[PASSED] Explicit arguments rendered perfectly.\n")


    # 2. Test rendering from structured json_payload
    print("--- TEST 2: Ingesting & Rendering from structured JSON payload ---")
    report_payload = {
        "pilot_summary": {
            "organization_name": "Acme Corp",
            "pilot_name": "Developer Velocity Pilot",
            "pricing_model": "FIXED_MONTHLY",
            "monthly_price_usd": 500.0,
            "pilot_status": "ACTIVE",
            "total_prs_analyzed": 94,
            "enrolled_repositories": ["acme/core-service"]
        },
        "regression_efficiency": {
            "average_full_suite_runtime": "1h 45m",
            "average_veriscope_runtime": "32m",
            "estimated_engineering_hours_saved": 85.5,
            "estimated_engineering_hours_saved_str": "85.5 hours"
        },
        "fragility_intelligence": {
            "most_fragile_modules": [
                {"title": "UNSTABLE_MODULE:auth", "fragility_score": 92.5},
                {"title": "UNSTABLE_MODULE:database", "fragility_score": 88.0}
            ]
        },
        "escaped_defect_safety": {
            "safety_status": "STABLE",
            "escaped_defect_rate_percent": 0.0
        }
    }

    summary2 = PilotExecutiveSummaryRenderer.render(report_payload)

    expected2 = (
        "PRs analyzed: 94\n\n"
        "Average full regression runtime:\n"
        "1h 45m\n\n"
        "Average Veriscope recommended runtime:\n"
        "32m\n\n"
        "Estimated time saved:\n"
        "85.5 engineering hours/month\n\n"
        "Escaped defects:\n"
        "No increase observed during pilot window\n\n"
        "Most fragile modules:\n"
        "- auth\n"
        "- database"
    )

    print("Rendered Output:")
    print("----------------------------------------")
    print(summary2)
    print("----------------------------------------")

    assert summary2 == expected2, "JSON payload ingestion rendering does not match expected output format."
    print("[PASSED] Structured JSON payload ingested and rendered perfectly.\n")


    # 3. Test empty/fallback constraints
    print("--- TEST 3: Testing Fallbacks with Missing Data ---")
    summary3 = PilotExecutiveSummaryRenderer.render({})
    
    # Assert fallbacks are used and no crashes occur
    assert "PRs analyzed: 0" in summary3
    assert "Average full regression runtime:\n0s" in summary3
    assert "Average Veriscope recommended runtime:\n0s" in summary3
    assert "Estimated time saved:\n0 engineering hours" in summary3
    assert "Escaped defects:\nNo increase observed during pilot window" in summary3
    assert "Most fragile modules:\n- None registered" in summary3
    
    # Assert emojiless and no marketing hype
    assert "🔥" not in summary3
    assert "🚀" not in summary3
    assert "revolutionary" not in summary3.lower()

    print("[PASSED] Fallbacks and safety/emojiless formatting rules strictly enforced.\n")

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT EXECUTIVE SUMMARY RENDERER TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
