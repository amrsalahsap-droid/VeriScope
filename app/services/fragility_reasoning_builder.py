import logging
from typing import Dict, Any, List
from app.models.fragility_pattern import FragilityPattern

logger = logging.getLogger(__name__)

class FragilityReasoningBuilder:
    """
    Generates deterministic, human-readable, evidence-backed, and non-speculative
    fragility explanations for FragilityPattern records.
    """

    @staticmethod
    def build_explanation(pattern: FragilityPattern) -> str:
        """
        Generates a concise, evidence-backed, deterministic explanation string
        for the given FragilityPattern. Caps explanation length at exactly 500 chars.
        
        Guarantees zero use of prohibited phrases ("AI believes", "likely risky").
        """
        if not pattern:
            return ""

        # ---- Context extraction
        ctx = pattern.context or {}
        snap = pattern.replayable_evidence_snapshot or {}
        stats = snap.get("summary_statistics", {})

        # ---- Outcome statistics extraction (aligned with scoring engine)
        incident_count = int(
            pattern.incident_count
            or stats.get("incident_count", 0)
            or stats.get("incident_runs_count", 0)
            or 0
        )
        rollback_count = int(
            stats.get("rollback_count", 0)
            or stats.get("rollback_recs_count", 0)
            or 0
        )
        failure_count = int(
            stats.get("total_evidence", 0)
            or pattern.evidence_count
            or pattern.related_failure_count
            or 0
        )
        window_days = int(
            stats.get("evidence_window_days", 90)  # default to 90 days
        )

        # ---- Formatting outcomes deterministically (active voice, no speculative words)
        outcome_parts: List[str] = []
        if failure_count > 0:
            outcome_parts.append(f"{failure_count} failed execution{'s' if failure_count != 1 else ''}")
        if rollback_count > 0:
            outcome_parts.append(f"{rollback_count} rollback-linked regression{'s' if rollback_count != 1 else ''}")
        if incident_count > 0:
            outcome_parts.append(f"{incident_count} production incident{'s' if incident_count != 1 else ''}")

        if not outcome_parts:
            # Fallback if no counts are resolved
            outcome_parts.append("failures")

        if len(outcome_parts) == 1:
            outcomes_str = outcome_parts[0]
        elif len(outcome_parts) == 2:
            outcomes_str = f"{outcome_parts[0]} and {outcome_parts[1]}"
        else:
            outcomes_str = f"{outcome_parts[0]}, {outcome_parts[1]}, and {outcome_parts[2]}"

        # ---- Helper extractions for templates
        trigger_file = ctx.get("trigger_file") or pattern.normalized_pattern_key.split(":")[-1]
        trigger_files = ctx.get("trigger_files", [])
        trigger_dir = ctx.get("trigger_dir") or "src"
        trigger_neighborhood = ctx.get("trigger_neighborhood") or "src"
        dependency_file = ctx.get("dependency_file") or "unknown_service.py"
        failure_test = ctx.get("failure_test") or "unknown_test"
        suite_name = ctx.get("suite_name") or "unknown_suite"

        explanation = ""
        pt = pattern.pattern_type

        # ---- Pattern-specific deterministic templates
        if pt == "FILE_FAILURE_FREQUENCY":
            explanation = (
                f"Changes involving {trigger_file} preceded {outcomes_str} "
                f"in the last {window_days} days."
            )
        elif pt == "CO_FAILURE_PATTERN":
            explanation = (
                f"Changes involving {trigger_file} co-failed with downstream test {failure_test} "
                f"across {outcomes_str} in the last {window_days} days."
            )
        elif pt == "DEPENDENCY_PROXIMITY":
            explanation = (
                f"Changes involving {trigger_file} expanded into neighbor {dependency_file} "
                f"before {outcomes_str} in the last {window_days} days."
            )
        elif pt == "ESCAPED_DEFECT_PATTERN":
            explanation = (
                f"Changes involving {trigger_file} linked to {outcomes_str} "
                f"in the last {window_days} days."
            )
        elif pt == "TEST_CLUSTER_FAILURE":
            explanation = (
                f"Changes involving directory prefix {trigger_neighborhood} preceded test suite {suite_name} "
                f"failing across {outcomes_str} in the last {window_days} days."
            )
        elif pt == "RISKY_COMBINATION":
            # format trigger files list clearly
            files_str = ", ".join(trigger_files) if trigger_files else trigger_file
            explanation = (
                f"Changes involving multiple files {files_str} co-failed with downstream test {failure_test} "
                f"across {outcomes_str} in the last {window_days} days."
            )
        elif pt == "UNSTABLE_MODULE":
            explanation = (
                f"Changes inside directory prefix {trigger_dir}/ preceded {outcomes_str} "
                f"inside this module prefix in the last {window_days} days."
            )
        elif pt == "ROLLBACK_INVOLVEMENT":
            explanation = (
                f"Changes involving {trigger_file} linked to {outcomes_str} "
                f"in the last {window_days} days."
            )
        else:
            # Safe generic fallback
            explanation = (
                f"Changes involving {pattern.normalized_pattern_key} preceded {outcomes_str} "
                f"in the last {window_days} days."
            )

        # ---- Strictly bounded at 500 characters
        if len(explanation) > 500:
            logger.warning(f"Exceeded 500 characters limit. Truncating explanation for pattern {pattern.id}.")
            explanation = explanation[:497] + "..."

        return explanation
