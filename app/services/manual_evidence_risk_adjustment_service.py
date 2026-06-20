"""
Manual Evidence Risk Adjustment Service (Phase 6.4, Phase 6.5)

This service allows manual evidence to influence risk assessment while preserving
automated evidence truth. Manual evidence becomes a risk signal, not a coverage signal.

Phase 6.5: Risk adjustment is gated by governance status. Only APPROVED manual evidence
may adjust residual risk. All other governance states (PENDING_REVIEW, REJECTED, CHALLENGED,
EXPIRED) result in no risk adjustment.

Non-Negotiable Invariants:
- Manual evidence MUST NOT change Covered count
- Manual evidence MUST NOT change Partial count
- Manual evidence MUST NOT change Missing count
- Manual evidence MUST NOT change Traceability count
- Manual evidence MUST NOT change Health status
- Manual evidence MUST NOT change Ready status
- Manual evidence MUST NOT change Release Decision
- Manual evidence MUST NOT change Risk Review decisions
- Manual evidence MUST NOT change Automated Evidence buckets
- Manual evidence MUST NOT change Evidence Graph coverage classification
"""

from enum import Enum
from typing import Optional, Tuple
from app.schemas.regression_scope_v2 import RiskBand


class ManualSupportStatus(str, Enum):
    """Manual evidence execution status."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    NOT_EXECUTED = "NOT_EXECUTED"


class ManualEvidenceRiskAdjustmentService:
    """Service for adjusting risk bands based on manual evidence."""

    # Risk band order from lowest to highest
    _RISK_BAND_ORDER = [
        RiskBand.LOW,
        RiskBand.MEDIUM,
        RiskBand.HIGH,
        RiskBand.CRITICAL,
    ]

    @staticmethod
    def _get_risk_band_index(risk_band: RiskBand) -> int:
        """Get the index of a risk band in the order."""
        return ManualEvidenceRiskAdjustmentService._RISK_BAND_ORDER.index(risk_band)

    @staticmethod
    def _adjust_risk_band(
        generated_risk_band: RiskBand,
        manual_support_status: ManualSupportStatus
    ) -> Tuple[RiskBand, str, int, str]:
        """
        Adjust risk band based on manual evidence.

        Returns:
            Tuple of (residual_risk_band, adjustment_reason, adjustment_delta, diagnostic_code)
        """
        if manual_support_status == ManualSupportStatus.PASSED:
            # PASSED reduces risk by one band
            current_index = ManualEvidenceRiskAdjustmentService._get_risk_band_index(generated_risk_band)
            if current_index > 0:
                new_index = current_index - 1
                residual_risk_band = ManualEvidenceRiskAdjustmentService._RISK_BAND_ORDER[new_index]
                return (
                    residual_risk_band,
                    "Manual validation passed and reduced residual risk by one band.",
                    -1,
                    "MANUAL_EVIDENCE_REDUCED_RISK"
                )
            else:
                # Already at LOW, cannot reduce further
                return (
                    generated_risk_band,
                    "Manual validation passed but risk already at LOW.",
                    0,
                    "MANUAL_EVIDENCE_REDUCED_RISK"
                )

        elif manual_support_status == ManualSupportStatus.FAILED:
            # FAILED increases risk by one band
            current_index = ManualEvidenceRiskAdjustmentService._get_risk_band_index(generated_risk_band)
            if current_index < len(ManualEvidenceRiskAdjustmentService._RISK_BAND_ORDER) - 1:
                new_index = current_index + 1
                residual_risk_band = ManualEvidenceRiskAdjustmentService._RISK_BAND_ORDER[new_index]
                return (
                    residual_risk_band,
                    "Manual validation failed and elevated residual risk by one band.",
                    1,
                    "MANUAL_EVIDENCE_FAILED"
                )
            else:
                # Already at CRITICAL, cannot increase further
                return (
                    generated_risk_band,
                    "Manual validation failed but risk already at CRITICAL.",
                    0,
                    "MANUAL_EVIDENCE_FAILED"
                )

        elif manual_support_status == ManualSupportStatus.BLOCKED:
            # BLOCKED - no change
            return (
                generated_risk_band,
                "Manual validation blocked; no risk adjustment.",
                0,
                "MANUAL_EVIDENCE_BLOCKED"
            )

        elif manual_support_status == ManualSupportStatus.SKIPPED:
            # SKIPPED - no change
            return (
                generated_risk_band,
                "Manual validation skipped; no risk adjustment.",
                0,
                "MANUAL_EVIDENCE_NOT_EXECUTED"
            )

        elif manual_support_status == ManualSupportStatus.NOT_EXECUTED:
            # NOT_EXECUTED - no change
            return (
                generated_risk_band,
                "Manual validation not executed; no risk adjustment.",
                0,
                "MANUAL_EVIDENCE_NOT_EXECUTED"
            )

        else:
            # Unknown status - no change
            return (
                generated_risk_band,
                f"Unknown manual support status: {manual_support_status}; no risk adjustment.",
                0,
                "MANUAL_EVIDENCE_UNKNOWN_STATUS"
            )

    @staticmethod
    def adjust_risk(
        generated_risk_band: RiskBand,
        manual_support_status: str,
        governance_status: Optional[str] = None
    ) -> dict:
        """
        Adjust risk band based on manual evidence.

        Phase 6.5: Risk adjustment is gated by governance status. Only APPROVED
        manual evidence may adjust residual risk. All other governance states
        result in no risk adjustment.

        Args:
            generated_risk_band: The risk band generated from automated evidence
            manual_support_status: The manual evidence execution status
            governance_status: The governance status of the manual evidence (APPROVED, PENDING_REVIEW, REJECTED, CHALLENGED, EXPIRED)

        Returns:
            Dictionary containing:
                - residual_risk_band: The adjusted risk band
                - adjustment_reason: Human-readable explanation of the adjustment
                - adjustment_delta: The number of bands adjusted (-1, 0, or +1)
                - diagnostic_code: Diagnostic code for logging
        """
        # Phase 6.5: Check governance status
        if governance_status != "APPROVED":
            # Governance blocks risk adjustment
            if governance_status == "PENDING_REVIEW":
                return {
                    "residual_risk_band": generated_risk_band.value,
                    "adjustment_reason": "Manual execution awaiting governance approval.",
                    "adjustment_delta": 0,
                    "diagnostic_code": "MANUAL_EVIDENCE_GOVERNANCE_PENDING",
                }
            elif governance_status == "REJECTED":
                return {
                    "residual_risk_band": generated_risk_band.value,
                    "adjustment_reason": "Rejected manual evidence ignored.",
                    "adjustment_delta": 0,
                    "diagnostic_code": "MANUAL_EVIDENCE_GOVERNANCE_REJECTED",
                }
            elif governance_status == "CHALLENGED":
                return {
                    "residual_risk_band": generated_risk_band.value,
                    "adjustment_reason": "Challenged manual evidence temporarily untrusted.",
                    "adjustment_delta": 0,
                    "diagnostic_code": "MANUAL_EVIDENCE_GOVERNANCE_CHALLENGED",
                }
            elif governance_status == "EXPIRED":
                return {
                    "residual_risk_band": generated_risk_band.value,
                    "adjustment_reason": "Expired manual evidence no longer trusted.",
                    "adjustment_delta": 0,
                    "diagnostic_code": "MANUAL_EVIDENCE_GOVERNANCE_EXPIRED",
                }
            else:
                # Unknown or no governance status - treat as pending
                return {
                    "residual_risk_band": generated_risk_band.value,
                    "adjustment_reason": "Manual execution awaiting governance approval.",
                    "adjustment_delta": 0,
                    "diagnostic_code": "MANUAL_EVIDENCE_GOVERNANCE_PENDING",
                }

        # Convert string to enum
        try:
            manual_status_enum = ManualSupportStatus(manual_support_status.upper())
        except (ValueError, AttributeError):
            manual_status_enum = ManualSupportStatus.NOT_EXECUTED

        residual_risk_band, adjustment_reason, adjustment_delta, diagnostic_code = \
            ManualEvidenceRiskAdjustmentService._adjust_risk_band(
                generated_risk_band,
                manual_status_enum
            )

        return {
            "residual_risk_band": residual_risk_band.value,
            "adjustment_reason": adjustment_reason,
            "adjustment_delta": adjustment_delta,
            "diagnostic_code": diagnostic_code,
        }
