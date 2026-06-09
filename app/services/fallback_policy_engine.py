from typing import List
from app.schemas.recommendation import FallbackEvidenceBundle, FallbackDecision


class FallbackPolicyEngine:
    @staticmethod
    def determine_recommendation_mode(evidence_bundle: FallbackEvidenceBundle) -> FallbackDecision:
        """
        Determine the recommendation mode, optimization allowances, fallback levels,
        expansion depths, and historical failure inclusions based on evidence metrics.
        """
        reasons = []

        # 1. Derive Quality Base
        if (
            evidence_bundle.pr_evidence_health == "INSUFFICIENT"
            or evidence_bundle.unsafe_for_optimization
            or not evidence_bundle.changed_files_availability
        ):
            evidence_quality = "UNKNOWN"
            reasons.append(
                "Evidence quality derived as UNKNOWN because optimization is explicitly unsafe, "
                "changed files are unavailable, or PR evidence health is insufficient."
            )
        else:
            # Check for HIGH evidence quality
            if (
                evidence_bundle.pr_evidence_health == "HEALTHY"
                and evidence_bundle.coverage_confidence == "HIGH"
                and evidence_bundle.dependency_graph_confidence == "HIGH"
                and evidence_bundle.flaky_profile_health == "HEALTHY"
                and evidence_bundle.evidence_consistency == "CONSISTENT"
            ):
                evidence_quality = "HIGH"
                reasons.append("Evidence quality derived as HIGH: all confidence and consistency metrics are healthy.")
            # Check for LOW evidence quality
            elif (
                evidence_bundle.coverage_confidence in ("LOW", "DEGRADED", "UNKNOWN", "MISSING")
                or evidence_bundle.dependency_graph_confidence in ("LOW", "DEGRADED", "UNKNOWN", "MISSING")
                or evidence_bundle.flaky_profile_health in ("DEGRADED", "RISKY")
                or evidence_bundle.evidence_consistency in ("DEGRADED", "INCONSISTENT")
            ):
                evidence_quality = "LOW"
                reasons.append("Evidence quality derived as LOW due to one or more degraded or low trust metrics.")
            else:
                evidence_quality = "MODERATE"
                reasons.append(
                    "Evidence quality derived as MODERATE: inputs are stable but do not meet all HIGH-level thresholds."
                )

        # 2. Evaluate Safety Overrides to LEVEL_5 (Full Regression)
        both_cov_dep_missing = (
            evidence_bundle.coverage_confidence in ("UNKNOWN", "MISSING", "None", None)
            and evidence_bundle.dependency_graph_confidence in ("UNKNOWN", "MISSING", "None", None)
        )

        is_level_5 = (
            evidence_bundle.unsafe_for_optimization
            or evidence_quality == "UNKNOWN"
            or not evidence_bundle.changed_files_availability
            or evidence_bundle.pr_evidence_health == "INSUFFICIENT"
            or both_cov_dep_missing
        )

        if is_level_5:
            reasons_l5 = []
            if evidence_bundle.unsafe_for_optimization:
                reasons_l5.append("Optimization explicitly disabled (unsafe_for_optimization=True).")
            if evidence_quality == "UNKNOWN" and not evidence_bundle.unsafe_for_optimization:
                reasons_l5.append("Overall derived evidence quality is UNKNOWN.")
            if not evidence_bundle.changed_files_availability:
                reasons_l5.append("Changed files are not available.")
            if evidence_bundle.pr_evidence_health == "INSUFFICIENT":
                reasons_l5.append("PR evidence health is INSUFFICIENT.")
            if both_cov_dep_missing:
                reasons_l5.append("Both coverage and dependency graph evidence are completely missing or unknown.")

            reasons.extend(reasons_l5)
            reasons.append("Triggered LEVEL_5 fallback: Full regression suite is required. Optimization disabled.")

            return FallbackDecision(
                recommendation_mode="FULL_REGRESSION",
                optimization_allowed=False,
                fallback_level="LEVEL_5",
                evidence_quality=evidence_quality,
                reasons=reasons,
                expansion_depth=0,
                include_historical_failures=True,
                include_critical_tests=True,
                full_regression_required=True
            )

        # 3. Map LEVEL_1 to LEVEL_4 based on quality and risk
        if evidence_quality == "HIGH":
            reasons.append("Triggered LEVEL_1 NORMAL: Direct coverage tests only. High evidence trust.")
            return FallbackDecision(
                recommendation_mode="NORMAL",
                optimization_allowed=True,
                fallback_level="LEVEL_1",
                evidence_quality="HIGH",
                reasons=reasons,
                expansion_depth=0,
                include_historical_failures=False,
                include_critical_tests=False,
                full_regression_required=False
            )
        elif evidence_quality == "MODERATE":
            reasons.append(
                "Triggered LEVEL_2 WIDENED: Direct coverage + dependency expansion (BFS depth 2). Moderate evidence trust."
            )
            return FallbackDecision(
                recommendation_mode="WIDENED",
                optimization_allowed=True,
                fallback_level="LEVEL_2",
                evidence_quality="MODERATE",
                reasons=reasons,
                expansion_depth=2,
                include_historical_failures=False,
                include_critical_tests=False,
                full_regression_required=False
            )
        else:  # LOW evidence quality
            if evidence_bundle.changed_area_risky:
                reasons.append(
                    "Triggered LEVEL_4 CRITICAL: Level 3 + critical/business tests enabled. "
                    "Evidence trust is LOW and changed area appears highly risky."
                )
                return FallbackDecision(
                    recommendation_mode="CRITICAL",
                    optimization_allowed=True,
                    fallback_level="LEVEL_4",
                    evidence_quality="LOW",
                    reasons=reasons,
                    expansion_depth=3,
                    include_historical_failures=True,
                    include_critical_tests=True,
                    full_regression_required=False
                )
            else:
                reasons.append(
                    "Triggered LEVEL_3 SAFE_FALLBACK: Level 2 + scoped historical failures + related flaky tests. "
                    "Evidence trust is LOW but changed area is not highly risky."
                )
                return FallbackDecision(
                    recommendation_mode="SAFE_FALLBACK",
                    optimization_allowed=True,
                    fallback_level="LEVEL_3",
                    evidence_quality="LOW",
                    reasons=reasons,
                    expansion_depth=3,
                    include_historical_failures=True,
                    include_critical_tests=False,
                    full_regression_required=False
                )
