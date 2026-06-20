"""
Risk Scoring Service for Phase 3.0

Deterministic risk scoring engine that prioritizes requirements, gaps, and regression scope candidates
without modifying evidence truth, coverage buckets, readiness decisions, or traceability results.

The engine operates strictly as a derived layer above the existing Evidence Graph.
"""

from typing import Dict, Any, Optional, List
from enum import Enum


class RiskBand(Enum):
    """Risk band classifications."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CoverageStatus(Enum):
    """Coverage status for risk calculation."""
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"


class RequirementCriticality(Enum):
    """Requirement criticality levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BusinessRisk(Enum):
    """Business risk levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RequirementType(Enum):
    """Requirement types."""
    FUNCTIONAL = "FUNCTIONAL"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    COMPLIANCE = "COMPLIANCE"
    USER_EXPERIENCE = "USER_EXPERIENCE"


class RiskScoringService:
    """Deterministic risk scoring engine for requirements and gaps."""

    # Weighting constants for risk score calculation
    BUSINESS_RISK_WEIGHTS = {
        BusinessRisk.CRITICAL: 40,
        BusinessRisk.HIGH: 30,
        BusinessRisk.MEDIUM: 20,
        BusinessRisk.LOW: 10,
    }

    COVERAGE_GAP_WEIGHTS = {
        CoverageStatus.MISSING: 35,
        CoverageStatus.PARTIAL: 20,
        CoverageStatus.FAILED: 25,
        CoverageStatus.SKIPPED: 15,
        CoverageStatus.NOT_RUN: 10,
        CoverageStatus.VERIFIED: 0,
    }

    CRITICALITY_WEIGHTS = {
        RequirementCriticality.CRITICAL: 25,
        RequirementCriticality.HIGH: 15,
        RequirementCriticality.MEDIUM: 10,
        RequirementCriticality.LOW: 5,
    }

    REQUIREMENT_TYPE_MULTIPLIERS = {
        RequirementType.SECURITY: 1.3,
        RequirementType.COMPLIANCE: 1.2,
        RequirementType.FUNCTIONAL: 1.0,
        RequirementType.PERFORMANCE: 1.1,
        RequirementType.USER_EXPERIENCE: 0.9,
    }

    # Risk band thresholds
    RISK_BAND_THRESHOLDS = {
        RiskBand.CRITICAL: 80,
        RiskBand.HIGH: 60,
        RiskBand.MEDIUM: 40,
        RiskBand.LOW: 0,
    }

    @staticmethod
    def calculate_requirement_risk_score(
        business_risk: str,
        coverage_status: str,
        criticality: str,
        requirement_type: str,
        risk_review_adjustment: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate risk score for a requirement.

        Args:
            business_risk: Business risk level (CRITICAL, HIGH, MEDIUM, LOW)
            coverage_status: Coverage status (VERIFIED, PARTIAL, MISSING, FAILED, SKIPPED, NOT_RUN)
            criticality: Requirement criticality (CRITICAL, HIGH, MEDIUM, LOW)
            requirement_type: Requirement type (FUNCTIONAL, SECURITY, PERFORMANCE, COMPLIANCE, USER_EXPERIENCE)
            risk_review_adjustment: Optional manual adjustment from risk review (-20 to +20)

        Returns:
            Dict with riskScore, riskScoreReason, riskBand
        """
        # Parse enums
        try:
            business_risk_enum = BusinessRisk(business_risk.upper())
            coverage_status_enum = CoverageStatus(coverage_status.upper())
            criticality_enum = RequirementCriticality(criticality.upper())
            requirement_type_enum = RequirementType(requirement_type.upper())
        except (ValueError, AttributeError) as e:
            # Default to lowest risk if invalid input
            return {
                "riskScore": 0,
                "riskScoreReason": "Invalid input parameters - defaulting to low risk",
                "riskBand": RiskBand.LOW.value
            }

        # Calculate base score
        base_score = (
            RiskScoringService.BUSINESS_RISK_WEIGHTS.get(business_risk_enum, 10) +
            RiskScoringService.COVERAGE_GAP_WEIGHTS.get(coverage_status_enum, 0) +
            RiskScoringService.CRITICALITY_WEIGHTS.get(criticality_enum, 5)
        )

        # Apply requirement type multiplier
        type_multiplier = RiskScoringService.REQUIREMENT_TYPE_MULTIPLIERS.get(
            requirement_type_enum, 1.0
        )
        adjusted_score = base_score * type_multiplier

        # Apply risk review adjustment if provided
        if risk_review_adjustment is not None:
            adjusted_score += risk_review_adjustment

        # Clamp to 0-100 range
        final_score = max(0, min(100, int(adjusted_score)))

        # Determine risk band
        risk_band = RiskScoringService._determine_risk_band(final_score)

        # Generate reason
        reason_parts = [
            f"Business Risk: {business_risk} ({RiskScoringService.BUSINESS_RISK_WEIGHTS.get(business_risk_enum, 10)})",
            f"Coverage: {coverage_status} ({RiskScoringService.COVERAGE_GAP_WEIGHTS.get(coverage_status_enum, 0)})",
            f"Criticality: {criticality} ({RiskScoringService.CRITICALITY_WEIGHTS.get(criticality_enum, 5)})",
            f"Type: {requirement_type} (x{type_multiplier})"
        ]

        if risk_review_adjustment is not None:
            reason_parts.append(f"Review Adjustment: {risk_review_adjustment:+d}")

        reason = " + ".join(reason_parts)

        return {
            "riskScore": final_score,
            "riskScoreReason": reason,
            "riskBand": risk_band.value
        }

    @staticmethod
    def calculate_gap_risk_score(
        business_risk: str,
        criticality: str,
        requirement_type: str,
        gap_severity: str = "HIGH"
    ) -> Dict[str, Any]:
        """
        Calculate risk score for a coverage gap.

        Args:
            business_risk: Business risk level
            criticality: Requirement criticality
            requirement_type: Requirement type
            gap_severity: Gap severity (HIGH, MEDIUM, LOW)

        Returns:
            Dict with riskScore, riskScoreReason, riskBand
        """
        # Gaps are always MISSING coverage
        return RiskScoringService.calculate_requirement_risk_score(
            business_risk=business_risk,
            coverage_status="MISSING",
            criticality=criticality,
            requirement_type=requirement_type
        )

    @staticmethod
    def _determine_risk_band(score: int) -> RiskBand:
        """Determine risk band from score."""
        if score >= RiskScoringService.RISK_BAND_THRESHOLDS[RiskBand.CRITICAL]:
            return RiskBand.CRITICAL
        elif score >= RiskScoringService.RISK_BAND_THRESHOLDS[RiskBand.HIGH]:
            return RiskBand.HIGH
        elif score >= RiskScoringService.RISK_BAND_THRESHOLDS[RiskBand.MEDIUM]:
            return RiskBand.MEDIUM
        else:
            return RiskBand.LOW

    @staticmethod
    def batch_calculate_risk_scores(
        requirements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate risk scores for multiple requirements.

        Args:
            requirements: List of requirement dicts with business_risk, coverage_status,
                         criticality, requirement_type, and optional risk_review_adjustment

        Returns:
            List of risk score results
        """
        results = []
        for req in requirements:
            risk_result = RiskScoringService.calculate_requirement_risk_score(
                business_risk=req.get("business_risk", "LOW"),
                coverage_status=req.get("coverage_status", "VERIFIED"),
                criticality=req.get("criticality", "LOW"),
                requirement_type=req.get("requirement_type", "FUNCTIONAL"),
                risk_review_adjustment=req.get("risk_review_adjustment")
            )
            results.append({
                "requirement_id": req.get("id"),
                **risk_result
            })
        return results

    @staticmethod
    def get_risk_explanation(risk_score: int, risk_band: str) -> str:
        """
        Get human-readable explanation of risk score.

        Args:
            risk_score: Calculated risk score
            risk_band: Risk band classification

        Returns:
            Human-readable explanation
        """
        if risk_band == RiskBand.CRITICAL.value:
            return f"Critical risk ({risk_score}/100): Immediate attention required. Missing coverage for critical business requirement."
        elif risk_band == RiskBand.HIGH.value:
            return f"High risk ({risk_score}/100): Significant gap in coverage. Prioritize for regression testing."
        elif risk_band == RiskBand.MEDIUM.value:
            return f"Medium risk ({risk_score}/100): Moderate coverage gap. Consider for regression scope."
        else:
            return f"Low risk ({risk_score}/100): Adequate coverage or low business impact. Optional for regression."
