import os
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.recommendation import RecommendationRun
from app.models.fragility_pattern import FragilityPattern
from app.services.risk_reasoning_builder import RiskReasoningBuilder

def run_risk_reasoning_verification():
    print("======================================================================")
    print("STARTING RISK REASONING BUILDER PLATFORM VERIFICATIONS")
    print("======================================================================\n")

    # ====================================================================
    # Test 1. Seeding Mock Objects for Example Match
    # ====================================================================
    print("--- 1. Testing Exact Example Match and Formatting ---")

    run = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        pr_id="sha_123",
        evidence_quality="MODERATE", # Coverage confidence is Moderate
        recommendation_mode="NORMAL"
    )

    snapshot = {
        "changed_files": [
            "src/auth/middleware.ts",
            "src/billing/subscriptions.ts"
        ],
        "context": {
            "file_churn": {
                "src/billing/subscriptions.ts": 4  # changed 4 times this sprint
            }
        }
    }

    # active patterns
    p1 = FragilityPattern(
        id=uuid.uuid4(),
        repository_id=run.repository_id,
        pattern_type="FILE_FAILURE_FREQUENCY",
        normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/auth/middleware.ts",
        status="ACTIVE",
        risk_level="HIGH",
        evidence_count=5,
        context={"trigger_file": "src/auth/middleware.ts"}
    )

    p2 = FragilityPattern(
        id=uuid.uuid4(),
        repository_id=run.repository_id,
        pattern_type="CO_FAILURE_PATTERN",
        normalized_pattern_key="CO_FAILURE_PATTERN:src/auth/middleware.ts->billing/subscriptions.ts",
        status="ACTIVE",
        risk_level="HIGH",
        evidence_count=3,
        context={
            "trigger_file": "src/auth/middleware.ts",
            "failure_test": "src/billing/subscriptions.ts"
        }
    )

    patterns = [p1, p2]

    res = RiskReasoningBuilder.build_risk_reasoning(run, patterns, snapshot)
    bullets = res["bullets"]
    formatted_text = res["formatted_text"]

    print("DEBUG: Generated Risk Reason Bullets:")
    for b in bullets:
        print(f"  {b}")
    print(f"\nDEBUG: Formatted Risk Reason:\n{formatted_text}\n")

    # Assert exact example match in formatting and text (adjusted to components)
    assert len(bullets) == 4
    assert bullets[0] == "auth/middleware.ts has high fragility history"
    assert bullets[1] == "billing/subscriptions.ts changed 4 times this sprint"
    assert bullets[2] == "auth + billing co-failed in 3 previous regressions"
    assert bullets[3] == "coverage confidence is Moderate"

    expected_text = (
        "Why:\n"
        "1. auth/middleware.ts has high fragility history\n"
        "2. billing/subscriptions.ts changed 4 times this sprint\n"
        "3. auth + billing co-failed in 3 previous regressions\n"
        "4. coverage confidence is Moderate"
    )
    assert formatted_text == expected_text
    print("[OK] Example matches specifications exactly!")

    # ====================================================================
    # Test 2. Bullet Prioritization and Cap strictly at 4
    # ====================================================================
    print("\n--- 2. Testing Priority Ordering and 4-Bullet Ceiling ---")

    # Let's add multiple extra patterns to trigger all priorities:
    # 1. Fragility History (FILE_FAILURE_FREQUENCY)
    # 2. Churn
    # 3. Co-failures (CO_FAILURE_PATTERN)
    # 4. Unstable Modules (UNSTABLE_MODULE)
    # 5. Low coverage
    # 6. Rollback-linked (ESCAPED_DEFECT_PATTERN)

    p_unstable = FragilityPattern(
        id=uuid.uuid4(),
        repository_id=run.repository_id,
        pattern_type="UNSTABLE_MODULE",
        normalized_pattern_key="UNSTABLE_MODULE:src/billing",
        status="ACTIVE",
        risk_level="HIGH",
        evidence_count=8,
        context={"trigger_dir": "src/billing"}
    )

    p_rollback = FragilityPattern(
        id=uuid.uuid4(),
        repository_id=run.repository_id,
        pattern_type="ESCAPED_DEFECT_PATTERN",
        normalized_pattern_key="ESCAPED_DEFECT_PATTERN:src/auth/middleware.ts",
        status="ACTIVE",
        risk_level="HIGH",
        evidence_count=6,
        context={"trigger_file": "src/auth/middleware.ts"}
    )

    all_patterns = [p1, p2, p_unstable, p_rollback]

    res_cap = RiskReasoningBuilder.build_risk_reasoning(run, all_patterns, snapshot)
    bullets_cap = res_cap["bullets"]

    print("DEBUG: Prioritized Bullets capped at 4:")
    for b in bullets_cap:
        print(f"  {b}")

    # Assert exactly 4 bullets are returned despite having 6 candidate signals
    assert len(bullets_cap) == 4
    # Assert priority order: Fragility History -> Churn -> Co-failures -> Unstable Modules
    assert "fragility history" in bullets_cap[0]
    assert "changed 4 times" in bullets_cap[1]
    assert "co-failed" in bullets_cap[2]
    assert "instability history" in bullets_cap[3] # coverage and rollback got capped!
    print("[OK] Priority sorting and strict max 4 limit validated successfully.")

    # ====================================================================
    # Test 3. Demoting CRITICAL to HIGH and Scanning Forbidden Phrasing
    # ====================================================================
    print("\n--- 3. Testing Allowed Risk Levels and Prohibited Language ---")

    # Set risk level to CRITICAL (must demote to HIGH)
    p1.risk_level = "CRITICAL"
    res_demote = RiskReasoningBuilder.build_risk_reasoning(run, [p1], snapshot)
    bullets_demote = res_demote["bullets"]
    
    print(f"DEBUG: Demoted risk level string: '{bullets_demote[0]}'")
    assert "high fragility history" in bullets_demote[0]
    assert "critical" not in bullets_demote[0]

    # Verify forbidden phrases are absent
    for b in bullets_demote:
        assert "critical" not in b.lower()
        assert "unsafe" not in b.lower()
        assert "production risk guaranteed" not in b.lower()
        assert "catastrophic" not in b.lower()

    print("[OK] Demoted CRITICAL risk level successfully to HIGH; verified zero prohibited terms.")

    # ====================================================================
    # Test 4. Pure Determinism Verification
    # ====================================================================
    print("\n--- 4. Testing Pure Determinism ---")
    res_det1 = RiskReasoningBuilder.build_risk_reasoning(run, all_patterns, snapshot)
    res_det2 = RiskReasoningBuilder.build_risk_reasoning(run, all_patterns, snapshot)
    assert res_det1 == res_det2
    print("[OK] Determinism verified: identical inputs always produce identical output.")

    print("\n=======================================================")
    print("ALL RISK REASONING BUILDER PLATFORM VERIFICATIONS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_risk_reasoning_verification()
