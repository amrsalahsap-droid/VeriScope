"""
Quality Gate Service

Maps Veriscope state to CI/CD quality gate results.
"""
from typing import Optional
from app.models.pipeline_run import QualityGateStatus
from app.models.release_decision import ReleaseDecision


class QualityGateService:
    """Service for mapping Veriscope state to CI quality gates."""
    
    @staticmethod
    def compute_quality_gate(
        release_decision: Optional[ReleaseDecision],
        recommendation_health: Optional[str],
        required_before_release_count: int = 0,
        has_blocking_failed_tests: bool = False,
        recommendation_generation_failed: bool = False
    ) -> QualityGateStatus:
        """
        Compute quality gate status from Veriscope state.
        
        Rules:
        - Release Decision: Verified/Approved → PASSED
        - Release Decision: Partially Verified with required items → PARTIAL
        - Blocking failed tests or critical validation failure → FAILED
        - Recommendation generation failed → BLOCKED
        - Unknown/still running → UNKNOWN
        
        Important: Recommendation Health: Ready alone must NOT make CI pass.
        CI pass must depend on release readiness/quality gate.
        """
        # Generation failure blocks everything
        if recommendation_generation_failed:
            return QualityGateStatus.BLOCKED
        
        # Blocking test failures
        if has_blocking_failed_tests:
            return QualityGateStatus.FAILED
        
        # If we have a release decision, use it
        if release_decision:
            decision_status = release_decision.decision_status
            
            # Approved or verified → PASSED
            if decision_status in ["APPROVED", "VERIFIED"]:
                return QualityGateStatus.PASSED
            
            # Conditionally approved with required items → PARTIAL
            if decision_status in ["PARTIALLY_VERIFIED", "CONDITIONALLY_APPROVED"]:
                # If required items remain, it's PARTIAL
                if required_before_release_count > 0:
                    return QualityGateStatus.PARTIAL
                # If no required items but still conditionally approved, treat as PASSED
                return QualityGateStatus.PASSED
            
            # Rejected → FAILED
            if decision_status == "REJECTED":
                return QualityGateStatus.FAILED
            
            # Pending/other → UNKNOWN
            return QualityGateStatus.UNKNOWN
        
        # No release decision yet
        # Check if required items exist
        if required_before_release_count > 0:
            return QualityGateStatus.PARTIAL
        
        # No release decision, no required items
        # Recommendation Health alone does NOT determine quality gate
        # Return UNKNOWN until release decision is made
        return QualityGateStatus.UNKNOWN
    
    @staticmethod
    def get_summary_text(quality_gate: QualityGateStatus, required_count: int = 0) -> str:
        """Get human-readable summary for quality gate."""
        if quality_gate == QualityGateStatus.PASSED:
            return "All release checks passed. Ready for deployment."
        elif quality_gate == QualityGateStatus.PARTIAL:
            if required_count > 0:
                return f"Core tests passed, but {required_count} critical requirements still require review."
            return "Core tests passed, but some release checks remain incomplete."
        elif quality_gate == QualityGateStatus.FAILED:
            return "Release blocked by failed tests or validation failures."
        elif quality_gate == QualityGateStatus.BLOCKED:
            return "Recommendation generation failed. Cannot determine quality gate."
        else:
            return "Quality gate status unknown. Recommendation may still be running."
