from typing import List, Dict, Any, Optional


class BehaviorCoverageSufficiencyRules:
    """Evaluates whether an impacted business behavior is sufficiently covered for the current PR."""

    @classmethod
    def evaluate_sufficiency(
        cls,
        behavior_name: str,
        behavior_risk_level: str,          # LOW, MEDIUM, HIGH, CRITICAL
        impact_level: str,                 # LOW, MEDIUM, HIGH, CRITICAL
        scenarios: List[Dict[str, Any]],   # Output scenarios from BehaviorCoverageAnalyzer containing 'priority' and 'coverage_status'
        coverage_confidence: str,          # HIGH, MODERATE, LOW
        has_direct_code_coverage_only: bool = False,
    ) -> Dict[str, Any]:
        """Resolve precise sufficiency envelope for an impacted business behavior."""
        sufficiency = "UNKNOWN"
        reasons = []

        # Normalize inputs
        risk_level = (behavior_risk_level or "MEDIUM").upper()
        imp_level = (impact_level or "MEDIUM").upper()
        conf = (coverage_confidence or "LOW").upper()

        # Categorize scenarios by priority
        blockers = [s for s in scenarios if s["priority"] in ["BLOCKER", "MUST"]]
        optionals = [s for s in scenarios if s["priority"] in ["SHOULD", "OPTIONAL"]]

        # Find status lists
        missing_blocker_scenarios = [
            s for s in blockers 
            if s["coverage_status"] in ["MISSING_AUTOMATED_COVERAGE", "MANUAL_VALIDATION_RECOMMENDED"]
        ]
        
        covered_blocker_scenarios = [
            s for s in blockers 
            if s["coverage_status"] in ["VERIFIED_ON_CURRENT_PR", "COVERED_BY_EXISTING_TEST"]
        ]

        verified_critical_paths = [
            s for s in blockers 
            if s["coverage_status"] == "VERIFIED_ON_CURRENT_PR"
        ]

        missing_optional_scenarios = [
            s for s in optionals 
            if s["coverage_status"] in ["MISSING_AUTOMATED_COVERAGE", "MANUAL_VALIDATION_RECOMMENDED"]
        ]

        # Apply evaluation cascading rules:

        # 1. UNKNOWN Rule
        if not scenarios or conf == "LOW" and not covered_blocker_scenarios:
            sufficiency = "UNKNOWN"
            reasons.append("Behavior coverage signals are weakly inferred or insufficient scenarios are registered")

        # 2. INSUFFICIENT Rules (highest precedence of failure)
        elif len(missing_blocker_scenarios) > 0:
            sufficiency = "INSUFFICIENT"
            reasons.append(f"Any MUST/BLOCKER scenario missing automatically fails sufficiency validation ({len(missing_blocker_scenarios)} missing)")
            for ms in missing_blocker_scenarios[:2]:
                reasons.append(f"Missing MUST: '{ms['title']}'")

        elif (risk_level in ["CRITICAL", "HIGH"] or imp_level in ["CRITICAL", "HIGH"]) and not covered_blocker_scenarios:
            sufficiency = "INSUFFICIENT"
            reasons.append(f"No existing tests detected for highly impacted, critical behavior '{behavior_name}'")

        elif risk_level == "CRITICAL" and not verified_critical_paths:
            sufficiency = "INSUFFICIENT"
            reasons.append("Critical core path requires active verification on the current Pull Request build")

        # 3. PARTIAL Rules
        elif (
            len(missing_optional_scenarios) > 0 or
            (len(blockers) > 0 and len(covered_blocker_scenarios) < len(blockers)) or
            has_direct_code_coverage_only
        ):
            sufficiency = "PARTIAL"
            if len(missing_optional_scenarios) > 0:
                reasons.append(f"Core BLOCKER/MUST paths are covered, but optional validation scenarios are missing ({len(missing_optional_scenarios)} missing)")
            if has_direct_code_coverage_only:
                reasons.append("Behavior is only backed by raw file-level code coverage without explicit test mappings")

        # 4. SUFFICIENT Rules
        else:
            # Check constraints before marking SUFFICIENT:
            # - cannot call sufficient from code coverage alone
            # - low coverage confidence prevents SUFFICIENT
            if has_direct_code_coverage_only:
                sufficiency = "PARTIAL"
                reasons.append("Code coverage alone cannot prove behavior scenario coverage")
            elif conf == "LOW":
                sufficiency = "PARTIAL"
                reasons.append("Low coverage confidence prevents full SUFFICIENT state resolution")
            else:
                sufficiency = "SUFFICIENT"
                reasons.append("All core Blocker and Must scenarios are fully covered or verified with robust confidence")

        return {
            "sufficiency": sufficiency,
            "sufficiency_reason": " / ".join(reasons),
        }
