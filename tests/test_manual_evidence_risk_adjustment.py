"""
Manual Evidence Risk Adjustment Service Tests (Phase 6.4)

Tests for the manual evidence risk adjustment engine that allows manual evidence
to influence risk assessment while preserving automated evidence truth.
"""

import pytest
from app.services.manual_evidence_risk_adjustment_service import (
    ManualEvidenceRiskAdjustmentService,
    ManualSupportStatus
)
from app.schemas.regression_scope_v2 import RiskBand


class TestManualEvidenceRiskAdjustmentService:
    """Test suite for ManualEvidenceRiskAdjustmentService."""

    def test_passed_reduces_one_band_critical_to_high(self):
        """Test that PASSED reduces CRITICAL to HIGH."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED"
        )
        assert result["residual_risk_band"] == "HIGH"
        assert result["adjustment_delta"] == -1
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_REDUCED_RISK"
        assert "reduced" in result["adjustment_reason"].lower()

    def test_passed_reduces_one_band_high_to_medium(self):
        """Test that PASSED reduces HIGH to MEDIUM."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="PASSED"
        )
        assert result["residual_risk_band"] == "MEDIUM"
        assert result["adjustment_delta"] == -1
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_REDUCED_RISK"

    def test_passed_reduces_one_band_medium_to_low(self):
        """Test that PASSED reduces MEDIUM to LOW."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.MEDIUM,
            manual_support_status="PASSED"
        )
        assert result["residual_risk_band"] == "LOW"
        assert result["adjustment_delta"] == -1
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_REDUCED_RISK"

    def test_passed_no_change_when_already_low(self):
        """Test that PASSED does not change when already at LOW."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.LOW,
            manual_support_status="PASSED"
        )
        assert result["residual_risk_band"] == "LOW"
        assert result["adjustment_delta"] == 0
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_REDUCED_RISK"

    def test_failed_increases_one_band_low_to_medium(self):
        """Test that FAILED increases LOW to MEDIUM."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.LOW,
            manual_support_status="FAILED"
        )
        assert result["residual_risk_band"] == "MEDIUM"
        assert result["adjustment_delta"] == 1
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_FAILED"
        assert "elevated" in result["adjustment_reason"].lower()

    def test_failed_increases_one_band_medium_to_high(self):
        """Test that FAILED increases MEDIUM to HIGH."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.MEDIUM,
            manual_support_status="FAILED"
        )
        assert result["residual_risk_band"] == "HIGH"
        assert result["adjustment_delta"] == 1
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_FAILED"

    def test_failed_increases_one_band_high_to_critical(self):
        """Test that FAILED increases HIGH to CRITICAL."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="FAILED"
        )
        assert result["residual_risk_band"] == "CRITICAL"
        assert result["adjustment_delta"] == 1
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_FAILED"

    def test_failed_no_change_when_already_critical(self):
        """Test that FAILED does not change when already at CRITICAL."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="FAILED"
        )
        assert result["residual_risk_band"] == "CRITICAL"
        assert result["adjustment_delta"] == 0
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_FAILED"

    def test_blocked_no_change(self):
        """Test that BLOCKED does not change risk band."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="BLOCKED"
        )
        assert result["residual_risk_band"] == "HIGH"
        assert result["adjustment_delta"] == 0
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_BLOCKED"
        assert "blocked" in result["adjustment_reason"].lower()

    def test_skipped_no_change(self):
        """Test that SKIPPED does not change risk band."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="SKIPPED"
        )
        assert result["residual_risk_band"] == "HIGH"
        assert result["adjustment_delta"] == 0
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_NOT_EXECUTED"

    def test_not_executed_no_change(self):
        """Test that NOT_EXECUTED does not change risk band."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="NOT_EXECUTED"
        )
        assert result["residual_risk_band"] == "HIGH"
        assert result["adjustment_delta"] == 0
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_NOT_EXECUTED"

    def test_unknown_status_no_change(self):
        """Test that unknown status does not change risk band."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="UNKNOWN_STATUS"
        )
        assert result["residual_risk_band"] == "HIGH"
        assert result["adjustment_delta"] == 0
        # Unknown status falls back to NOT_EXECUTED
        assert result["diagnostic_code"] == "MANUAL_EVIDENCE_NOT_EXECUTED"

    def test_case_insensitive_status(self):
        """Test that manual support status is case-insensitive."""
        result_lower = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="passed"
        )
        result_upper = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="PASSED"
        )
        assert result_lower["residual_risk_band"] == result_upper["residual_risk_band"]
        assert result_lower["adjustment_delta"] == result_upper["adjustment_delta"]

    def test_deterministic_behavior(self):
        """Test that the service produces deterministic results."""
        result1 = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="PASSED"
        )
        result2 = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="PASSED"
        )
        assert result1 == result2

    def test_all_risk_bands_with_passed(self):
        """Test PASSED adjustment across all risk bands."""
        expected_results = {
            RiskBand.CRITICAL: ("HIGH", -1),
            RiskBand.HIGH: ("MEDIUM", -1),
            RiskBand.MEDIUM: ("LOW", -1),
            RiskBand.LOW: ("LOW", 0),
        }

        for risk_band, (expected_residual, expected_delta) in expected_results.items():
            result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=risk_band,
                manual_support_status="PASSED"
            )
            assert result["residual_risk_band"] == expected_residual
            assert result["adjustment_delta"] == expected_delta

    def test_all_risk_bands_with_failed(self):
        """Test FAILED adjustment across all risk bands."""
        expected_results = {
            RiskBand.CRITICAL: ("CRITICAL", 0),
            RiskBand.HIGH: ("CRITICAL", 1),
            RiskBand.MEDIUM: ("HIGH", 1),
            RiskBand.LOW: ("MEDIUM", 1),
        }

        for risk_band, (expected_residual, expected_delta) in expected_results.items():
            result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=risk_band,
                manual_support_status="FAILED"
            )
            assert result["residual_risk_band"] == expected_residual
            assert result["adjustment_delta"] == expected_delta

    def test_all_risk_bands_with_blocked(self):
        """Test BLOCKED adjustment across all risk bands (no change)."""
        for risk_band in [RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.MEDIUM, RiskBand.LOW]:
            result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=risk_band,
                manual_support_status="BLOCKED"
            )
            assert result["residual_risk_band"] == risk_band.value
            assert result["adjustment_delta"] == 0

    def test_all_risk_bands_with_skipped(self):
        """Test SKIPPED adjustment across all risk bands (no change)."""
        for risk_band in [RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.MEDIUM, RiskBand.LOW]:
            result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=risk_band,
                manual_support_status="SKIPPED"
            )
            assert result["residual_risk_band"] == risk_band.value
            assert result["adjustment_delta"] == 0

    def test_all_risk_bands_with_not_executed(self):
        """Test NOT_EXECUTED adjustment across all risk bands (no change)."""
        for risk_band in [RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.MEDIUM, RiskBand.LOW]:
            result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=risk_band,
                manual_support_status="NOT_EXECUTED"
            )
            assert result["residual_risk_band"] == risk_band.value
            assert result["adjustment_delta"] == 0

    def test_adjustment_reason_content(self):
        """Test that adjustment reasons are descriptive."""
        result_passed = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="PASSED"
        )
        assert "manual validation" in result_passed["adjustment_reason"].lower()
        assert "passed" in result_passed["adjustment_reason"].lower()

        result_failed = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="FAILED"
        )
        assert "manual validation" in result_failed["adjustment_reason"].lower()
        assert "failed" in result_failed["adjustment_reason"].lower()

        result_blocked = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="BLOCKED"
        )
        assert "blocked" in result_blocked["adjustment_reason"].lower()

    def test_diagnostic_codes(self):
        """Test that correct diagnostic codes are generated."""
        diagnostic_codes = {
            "PASSED": "MANUAL_EVIDENCE_REDUCED_RISK",
            "FAILED": "MANUAL_EVIDENCE_FAILED",
            "BLOCKED": "MANUAL_EVIDENCE_BLOCKED",
            "SKIPPED": "MANUAL_EVIDENCE_NOT_EXECUTED",
            "NOT_EXECUTED": "MANUAL_EVIDENCE_NOT_EXECUTED",
        }

        for status, expected_code in diagnostic_codes.items():
            result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=RiskBand.HIGH,
                manual_support_status=status
            )
            assert result["diagnostic_code"] == expected_code
