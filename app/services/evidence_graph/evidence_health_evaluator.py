from typing import Tuple, Dict, Any
from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy

class EvidenceHealthEvaluator:
    @staticmethod
    def determine_health(
        metrics: Dict[str, Any],
        policy: EvidenceQualityPolicy
    ) -> Tuple[str, bool]:
        """Determines health status and can_render_recommendation flag.
        
        Returns:
            Tuple of (health_status_str, can_render_recommendation_bool)
        """
        # Rule 0: If has stale inputs
        if metrics.get("has_stale_inputs", False):
            return "STALE_INPUTS", True

        # Rule 1: If no AC source
        if metrics.get("has_no_ac_source", False):
            return "INSUFFICIENT_INPUT", False

        # Rule 2: If AC extraction returns 0
        if metrics.get("total_parent_requirements", 0) == 0 or metrics.get("is_ac_extraction_empty", False):
            return "INSUFFICIENT_INPUT", False

        # Rule 3: If graph invariant fails
        if metrics.get("invariant_failed", False):
            return "INTERNAL_EVIDENCE_MODEL_INCONSISTENT", False

        # Rule 4: If current PR tests failed
        # metrics["failed_count"] represents requirements classified as failed (e.g. they map to a failed execution)
        # also check if counts had failed tests uploaded in execution nodes
        if metrics.get("failed_count", 0) > 0 or metrics.get("raw_failed_tests_count", 0) > 0:
            return "BLOCKED_BY_FAILED_TESTS", True

        # Rule 5: If required tests were skipped
        if metrics.get("skipped_count", 0) > 0 or metrics.get("raw_skipped_tests_count", 0) > 0:
            return "BLOCKED_BY_SKIPPED_REQUIRED_TESTS", True

        # Rule 6: If policy thresholds for Ready are not met because verified coverage is low or unmapped requirements are high
        # Policy rules check:
        # Check verified coverage ratio:
        total = metrics.get("total_parent_requirements", 0)
        verified_ratio = metrics.get("verified_ratio", 1.0)
        unmapped_ratio = metrics.get("unmapped_ratio", 0.0)
        not_mapped_count = metrics.get("not_mapped_traceability_risk_count", 0)
        missing_ratio = metrics.get("missing_ratio", 0.0)

        # Ratio rules are typically checked only if total is >= minimum_parent_requirements_for_ratio_rules
        check_ratios = total >= policy.minimum_parent_requirements_for_ratio_rules

        verified_coverage_low = False
        if check_ratios and verified_ratio < policy.min_verified_ratio_for_ready:
            verified_coverage_low = True

        not_mapped_high = False
        if check_ratios and unmapped_ratio > policy.max_not_mapped_ratio_for_ready:
            not_mapped_high = True
        if not_mapped_count > policy.max_not_mapped_count_for_ready:
            not_mapped_high = True

        # Only return NEEDS_TRACEABILITY_REVIEW if there are actual unmapped requirements
        if not_mapped_high and not_mapped_count > 0:
            return "NEEDS_TRACEABILITY_REVIEW", True
        
        # If verified coverage is low but no unmapped requirements, this is a coverage gap issue
        if verified_coverage_low:
            return "VALIDATION_PASSED_COVERAGE_INCOMPLETE", True

        # Rule 7: If current PR tests passed but some requirements are missing, partial, or required-not-run
        has_partial = metrics.get("partial_coverage_count", 0) > 0
        has_missing = metrics.get("missing_automated_coverage_count", 0) > 0
        has_required_not_run = metrics.get("required_not_run_count", 0) > 0

        # Check policy allowance
        partial_disallowed = has_partial and not policy.allow_ready_with_partial_coverage
        required_not_run_disallowed = has_required_not_run and not policy.allow_ready_with_required_not_run

        if has_missing or partial_disallowed or required_not_run_disallowed:
            return "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE", True

        # Rule 8: If all policy conditions for Ready are met
        return "READY", True
