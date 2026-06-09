import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("veriscope.escaped_defect_safety_analyzer")

class EscapedDefectSafetyAnalyzer:
    """
    EscapedDefectSafetyAnalyzer
    ===========================
    Analyzes whether regression reduction correlated with escaped defects.
    Adheres strictly to safety assessment phrasing rules, avoiding causal overclaiming.
    """

    @classmethod
    def analyze_safety(
        cls,
        total_outcomes: int,
        escaped_defects_count: int,
        rollbacks_count: int,
        is_incident_lineage_complete: bool = True,
        recommendation_frequency: int = 0
    ) -> Dict[str, Any]:
        """
        Analyze safety indicators conservatively and deterministically.
        """
        # Clamp inputs
        total_outcomes = max(0, total_outcomes)
        escaped_defects_count = max(0, escaped_defects_count)
        rollbacks_count = max(0, rollbacks_count)
        recommendation_frequency = max(0, recommendation_frequency)

        # Rates
        escaped_defect_rate = escaped_defect_rate = escaped_defects_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0
        rollback_rate = rollbacks_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0

        # Disclaimers
        causal_disclaimer = (
            "Incident and rollback linkages reflect temporal correlation with recommendation runs. "
            "Direct causal relationships are not automatically assumed."
        )

        # Determine safety status and assessment
        if total_outcomes < 5 or recommendation_frequency < 5:
            safety_status = "INSUFFICIENT_DATA"
            safety_assessment = (
                f"Safety Assessment: Statistical sample size is insufficient to establish safety trends (N = {total_outcomes}). "
                "No stable baseline or conclusion can be determined from the pilot window. "
                "Rollback and defect rates are based on small sample sizes and must be treated as preliminary indicators only."
            )
        else:
            if escaped_defects_count == 0 and rollbacks_count == 0:
                safety_status = "STABLE"
                safety_assessment = (
                    "No increase in escaped defects observed during pilot window. "
                    "Rollback-linked outcomes remained stable. "
                    f"{causal_disclaimer}"
                )
            else:
                safety_status = "ATTENTION"
                safety_assessment = (
                    f"Temporal correlation analysis registered {escaped_defects_count} escaped defect{'s' if escaped_defects_count != 1 else ''} "
                    f"(defect rate: {round(escaped_defect_rate * 100, 1)}%) and {rollbacks_count} rollback-linked outcome{'s' if rollbacks_count != 1 else ''} "
                    f"(rollback rate: {round(rollback_rate * 100, 1)}%) within the evaluation period. "
                    f"{causal_disclaimer}"
                )

        # Warnings
        confidence_warning = None
        if total_outcomes < 5 or recommendation_frequency < 5:
            confidence_warning = (
                f"WARNING: Tiny dataset (N = {total_outcomes}). Statistical significance is low; safety conclusions cannot be reliably drawn."
            )

        incomplete_lineage_warning = None
        if not is_incident_lineage_complete:
            incomplete_lineage_warning = (
                "WARNING: Incomplete incident lineage detected. Production defect telemetry coverage is incomplete. "
                "Defect leakage rates may be underreported due to missing telemetry paths."
            )

        return {
            "safety_status": safety_status,
            "escaped_defect_rate": round(escaped_defect_rate, 4),
            "rollback_rate": round(rollback_rate, 4),
            "escaped_defect_rate_percent": round(escaped_defect_rate * 100, 2),
            "rollback_rate_percent": round(rollback_rate * 100, 2),
            "is_incident_lineage_complete": is_incident_lineage_complete,
            "safety_assessment": safety_assessment,
            "confidence_warning": confidence_warning,
            "incomplete_lineage_warning": incomplete_lineage_warning
        }
