from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MappingSafetyDecision:
    status: str
    coverage_type: str
    requires_user_review: bool
    reason: str
    audit: Dict[str, Any]


def validate_ai_mapping_decision(
    decision: Dict[str, Any],
    deterministic_signals: Dict[str, Any],
    policy: Optional[Dict[str, float]] = None,
) -> MappingSafetyDecision:
    policy = policy or {}
    strong = float(policy.get("strong_threshold", 0.85))
    weak = float(policy.get("weak_threshold", 0.55))
    conflict = float(policy.get("conflict_threshold", 0.75))
    allowed = {
        "EVIDENCE_VERIFIED_ALIGNED",
        "METADATA_CONFLICT_SEMANTIC_MATCH",
        "PARTIAL_SUPPORT",
        "SUGGESTED",
        "NO_CANDIDATE",
    }
    recommendation = str(decision.get("status_recommendation", {}).get("status", "NO_CANDIDATE")).upper()
    semantic = decision.get("semantic_best_match") or {}
    confidence = float(semantic.get("confidence") or 0.0)
    coverage_type = str(semantic.get("coverage_type") or "none").lower()
    execution_status = str(deterministic_signals.get("execution_status") or "unknown").lower()
    declared_resolves = bool(deterministic_signals.get("declared_ref_resolves"))
    declared_matches = bool(deterministic_signals.get("declared_ref_matches_semantics"))
    conflict_detected = bool(deterministic_signals.get("conflict_detected"))
    semantic_matches_declared = bool(deterministic_signals.get("semantic_matches_declared"))
    has_better_candidate = bool(deterministic_signals.get("has_better_candidate"))
    valid_candidate_ref = bool(deterministic_signals.get("semantic_ref_in_candidates"))
    key_verified = bool(deterministic_signals.get("veriscope_key_verified"))

    if key_verified and execution_status == "passed":
        status = "VERISCOPE_KEY_VERIFIED"
        coverage_type = "full"
        review = False
        reason = "Exact veriscope_ac_key match with a passed test."
    elif recommendation not in allowed or not valid_candidate_ref:
        status = "NO_CANDIDATE"
        coverage_type = "none"
        review = True
        reason = "Semantic decision did not pass candidate-list validation."
    elif recommendation == "EVIDENCE_VERIFIED_ALIGNED":
        if execution_status == "passed" and declared_resolves and declared_matches and semantic_matches_declared and not conflict_detected and not has_better_candidate and confidence >= strong:
            status = recommendation
            coverage_type = "full"
            review = True
            reason = str(semantic.get("reason") or "Declared reference and semantic evidence align.")
        else:
            status = "SUGGESTED" if confidence >= weak else "NO_CANDIDATE"
            coverage_type = "none" if status == "NO_CANDIDATE" else coverage_type
            review = True
            reason = "Evidence-aligned recommendation did not satisfy the deterministic trust policy."
    elif recommendation == "METADATA_CONFLICT_SEMANTIC_MATCH":
        if declared_resolves and conflict_detected and not semantic_matches_declared and confidence >= conflict:
            status = recommendation
            coverage_type = "full"
            review = True
            reason = str(semantic.get("reason") or "Declared metadata conflicts with stronger semantic evidence.")
        else:
            status = "SUGGESTED" if confidence >= weak else "NO_CANDIDATE"
            coverage_type = "none" if status == "NO_CANDIDATE" else coverage_type
            review = True
            reason = "Metadata-conflict recommendation did not satisfy the routing policy."
    elif recommendation == "PARTIAL_SUPPORT" and coverage_type == "partial" and confidence >= weak:
        status = "PARTIAL_SUPPORT"
        review = True
        reason = str(semantic.get("reason") or "Evidence supports only part of the acceptance criterion.")
    elif recommendation == "SUGGESTED" and confidence >= weak:
        status = "SUGGESTED"
        review = True
        reason = str(semantic.get("reason") or "Candidate requires human review.")
    else:
        status = "NO_CANDIDATE"
        coverage_type = "none"
        review = True
        reason = str(semantic.get("reason") or "No validated candidate evidence is available.")

    return MappingSafetyDecision(
        status=status,
        coverage_type=coverage_type,
        requires_user_review=review,
        reason=reason,
        audit={
            "recommendation": recommendation,
            "confidence": confidence,
            "execution_status": execution_status,
            "deterministic_signals": deterministic_signals,
        },
    )
