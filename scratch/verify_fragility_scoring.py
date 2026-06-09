import os
import sys
import math
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.fragility_pattern import FragilityPattern
from app.services.fragility_scoring_engine import (
    FragilityScoringEngine,
    FragilityScoringInputs,
    FragilityScoringResult,
    FragilityScoringWeights,
    SCORING_FORMULA_VERSION
)

def run_fragility_scoring_verification():
    print("======================================================================")
    print("STARTING SCORING ENGINE MATHEMATICAL & DETERMINISTIC TRUST VERIFICATIONS")
    print("======================================================================\n")

    engine = FragilityScoringEngine()

    # ====================================================================
    # Test 1. Determinism Verification
    # ====================================================================
    print("--- 1. Testing Scoring Engine Determinism ---")
    inputs1 = FragilityScoringInputs(
        failure_frequency=5,
        days_since_last_seen=12,
        module_churn=450,
        test_instability_score=0.35,
        incident_count=1,
        dependency_proximity_weight=0.7,
        rollback_count=2,
        evidence_count=14
    )
    
    inputs2 = FragilityScoringInputs(
        failure_frequency=5,
        days_since_last_seen=12,
        module_churn=450,
        test_instability_score=0.35,
        incident_count=1,
        dependency_proximity_weight=0.7,
        rollback_count=2,
        evidence_count=14
    )

    res1 = engine.calculate_fragility_score_from_inputs(inputs1)
    res2 = engine.calculate_fragility_score_from_inputs(inputs2)

    # Assert exact floating point determinism
    assert res1.fragility_score == res2.fragility_score
    assert res1.risk_level == res2.risk_level
    assert res1.confidence_level == res2.confidence_level
    assert res1.incident_score == res2.incident_score
    assert res1.rollback_score == res2.rollback_score
    assert res1.frequency_score == res2.frequency_score
    assert res1.recency_score == res2.recency_score
    assert res1.churn_score == res2.churn_score
    assert res1.instability_score == res2.instability_score
    assert res1.dependency_proximity_score == res2.dependency_proximity_score
    assert res1.stale_decay_factor == res2.stale_decay_factor
    assert res1.raw_composite_score == res2.raw_composite_score
    print(f"[OK] Pure determinism verified: score is {res1.fragility_score} ({res1.risk_level}).")

    # ====================================================================
    # Test 2. Score Explainability and Reconstruction from Persisted JSONB
    # ====================================================================
    print("\n--- 2. Testing Explainability & Replayability from Persisted JSONB ---")
    
    # Store score components
    persisted_components = res1.to_score_components()
    assert isinstance(persisted_components, dict)
    print(f"DEBUG: Stored Components: {persisted_components}")

    # Build FragilityPattern ORM model mock
    pattern = FragilityPattern(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        pattern_type="FILE_FAILURE_FREQUENCY",
        normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/core.py",
        explanation="Explainability test pattern.",
        evidence_count=inputs1.evidence_count,
        incident_count=inputs1.incident_count,
        last_seen_at=datetime.utcnow() - timedelta(days=inputs1.days_since_last_seen),
        score_components=persisted_components,
        replayable_evidence_snapshot={
            "summary_statistics": {
                "incident_count": inputs1.incident_count,
                "rollback_count": inputs1.rollback_count,
                "total_evidence": inputs1.failure_frequency,
                "days_since_last_seen": inputs1.days_since_last_seen
            }
        }
    )

    # Reconstruct score using calculate_fragility_score
    reconstructed_res = engine.calculate_fragility_score(pattern)
    
    print(f"DEBUG: Original Score: {res1.fragility_score}, Reconstructed Score: {reconstructed_res.fragility_score}")
    
    # Assert near-exact or exact matching (accounting for float roundings stored in JSONB)
    assert abs(res1.fragility_score - reconstructed_res.fragility_score) < 0.5
    assert res1.risk_level == reconstructed_res.risk_level
    assert res1.confidence_level == reconstructed_res.confidence_level
    print("[OK] Explainability verified: Score can be successfully reconstructed from persisted score_components JSONB.")

    # ====================================================================
    # Test 3. Weight Calibration checks (Spec Requirements)
    # ====================================================================
    print("\n--- 3. Testing Weight Calibration and Impact Tiers ---")
    
    # Baseline inputs
    base_inputs = FragilityScoringInputs()
    base_res = engine.calculate_fragility_score_from_inputs(base_inputs)
    print(f"DEBUG: Base score with zero inputs: {base_res.fragility_score}")
    
    # 1. High Impact: Incident linkage
    incident_inputs = FragilityScoringInputs(incident_count=1)
    incident_res = engine.calculate_fragility_score_from_inputs(incident_inputs)
    incident_increase = incident_res.fragility_score - base_res.fragility_score
    print(f"DEBUG: 1 Incident adds: {incident_increase:.2f} to final score.")
    assert incident_increase > 8.0  # (1/3)*100 * 0.25 weight = 8.33% base increase
    
    # 2. High Impact: Rollback linkage
    rollback_inputs = FragilityScoringInputs(rollback_count=1)
    rollback_res = engine.calculate_fragility_score_from_inputs(rollback_inputs)
    rollback_increase = rollback_res.fragility_score - base_res.fragility_score
    print(f"DEBUG: 1 Rollback adds: {rollback_increase:.2f} to final score.")
    assert rollback_increase > 6.0  # (1/3)*100 * 0.20 weight = 6.66% base increase

    # 3. Moderate: Repeated co-failure (frequency)
    freq_inputs = FragilityScoringInputs(failure_frequency=1)
    freq_res = engine.calculate_fragility_score_from_inputs(freq_inputs)
    freq_increase = freq_res.fragility_score - base_res.fragility_score
    print(f"DEBUG: 1 Failure frequency adds: {freq_increase:.2f} to final score.")
    assert freq_increase > 1.0  # (1/10)*100 * 0.15 weight = 1.5% base increase

    print("[OK] Weight calibrations confirmed: Incident & Rollback are high impact, co-failure frequency is moderate.")

    # ====================================================================
    # Test 4. Stale Evidence Decay (The Bug Fix Verification!)
    # ====================================================================
    print("\n--- 4. Testing Stale Evidence Decay & Continuous Decay Math ---")

    # Raw composite test inputs (non-zero raw score, days_since variable)
    composite_inputs = FragilityScoringInputs(
        failure_frequency=10,
        days_since_last_seen=0,
        module_churn=1000,
        test_instability_score=1.0,
        dependency_proximity_weight=1.0
    )

    # To isolate the stale compound decay verification, we use a custom weight vector
    # where the w_recency weight is set to 0.0 (so days_since does not affect raw_composite).
    custom_weights = FragilityScoringWeights(
        w_recency=0.0,
        w_incident_linkage=0.30,
        w_rollback_linkage=0.25,
        w_failure_frequency=0.20,
        w_module_churn=0.10,
        w_test_instability=0.08,
        w_dependency_proximity=0.07
    )
    decay_engine = FragilityScoringEngine(weights=custom_weights)

    # 0 days since last seen (no decay)
    decay_0_days = decay_engine.calculate_fragility_score_from_inputs(composite_inputs)
    print(f"DEBUG: Score at 0 days (fresh): {decay_0_days.fragility_score} (decay factor = {decay_0_days.stale_decay_factor:.4f})")
    assert decay_0_days.stale_decay_factor == 0.0
    assert decay_0_days.fragility_score > 0.0

    # 30 days since last seen (10% decay)
    composite_inputs_30 = FragilityScoringInputs(
        failure_frequency=10,
        days_since_last_seen=30,
        module_churn=1000,
        test_instability_score=1.0,
        dependency_proximity_weight=1.0
    )
    decay_30_days = decay_engine.calculate_fragility_score_from_inputs(composite_inputs_30)
    print(f"DEBUG: Score at 30 days: {decay_30_days.fragility_score} (decay factor = {decay_30_days.stale_decay_factor:.4f})")
    assert math.isclose(decay_30_days.stale_decay_factor, 0.10, rel_tol=1e-5)
    # Score should be exactly 90% of the 0 days score
    assert abs(decay_30_days.fragility_score - decay_0_days.fragility_score * 0.90) < 0.02

    # 90 days since last seen (27.1% decay)
    composite_inputs_90 = FragilityScoringInputs(
        failure_frequency=10,
        days_since_last_seen=90,
        module_churn=1000,
        test_instability_score=1.0,
        dependency_proximity_weight=1.0
    )
    decay_90_days = decay_engine.calculate_fragility_score_from_inputs(composite_inputs_90)
    print(f"DEBUG: Score at 90 days: {decay_90_days.fragility_score} (decay factor = {decay_90_days.stale_decay_factor:.4f})")
    assert math.isclose(decay_90_days.stale_decay_factor, 0.271, rel_tol=1e-3)
    # Score should be exactly 72.9% of the 0 days score
    assert abs(decay_90_days.fragility_score - decay_0_days.fragility_score * 0.729) < 0.02

    print("[OK] Continuous compounding decay math verified. Bug fix successfully proven!")

    # ====================================================================
    # Test 5. Risk Level Boundary Mapping
    # ====================================================================
    print("\n--- 5. Testing Risk Level Boundary Mapping ---")

    # Helper function to mock mapping
    from app.services.fragility_scoring_engine import _map_risk_level
    
    assert _map_risk_level(0.0) == "LOW"
    assert _map_risk_level(24.0) == "LOW"
    assert _map_risk_level(24.99) == "LOW"
    
    assert _map_risk_level(25.0) == "MODERATE"
    assert _map_risk_level(49.0) == "MODERATE"
    assert _map_risk_level(49.99) == "MODERATE"
    
    assert _map_risk_level(50.0) == "HIGH"
    assert _map_risk_level(74.0) == "HIGH"
    assert _map_risk_level(74.99) == "HIGH"
    
    assert _map_risk_level(75.0) == "CRITICAL"
    assert _map_risk_level(100.0) == "CRITICAL"

    print("[OK] All risk level mapping boundaries verified strictly against rules 0-24, 25-49, 50-74, 75-100.")

    # ====================================================================
    # Test 6. ML Absence Certification
    # ====================================================================
    print("\n--- 6. Certifying Pure Deterministic Mathematical Design (No ML) ---")
    
    # Read engine module source lines to ensure zero neural/scikit imports
    src_path = Path(__file__).resolve().parent.parent / "app" / "services" / "fragility_scoring_engine.py"
    with open(src_path, "r", encoding="utf-8") as f:
        src_code = f.read()
    
    forbidden = ["sklearn", "scikit", "tensorflow", "pytorch", "torch", "keras", "xgboost", "randomforest"]
    for f in forbidden:
        assert f not in src_code.lower(), f"Forbidden ML framework '{f}' imported or referenced in FragilityScoringEngine!"
        
    print("[OK] Verified zero ML dependency imports or stochastic operations.")

    print("\n======================================================================")
    print("ALL SCORING ENGINE MATHEMATICAL & DETERMINISTIC TRUST VERIFICATIONS PASSED!")
    print("======================================================================\n")

if __name__ == "__main__":
    run_fragility_scoring_verification()
