/**
 * @jest-environment jsdom
 *
 * Manual Evidence Risk Adjustment Tests (Phase 6.4)
 *
 * Tests for the manual evidence risk adjustment display in the frontend.
 * Verifies that residual risk, manual contribution status, and adjustment
 * indicators are displayed correctly.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ScopeGroupDisplay } from "../components/regression-scope/ScopeGroupDisplay";
import { ScopeGroup, ScopeItemType, RiskBand, EvidenceClassification, ChangeImpactLevel, BusinessRiskLevel } from "../types/regression-scope-v2";

describe("Manual Evidence Risk Adjustment", () => {
  const mockItemWithRiskAdjustment = {
    id: "req-1",
    readable_id: "AC-17",
    source_ac_number: 17,
    title: "Verify password reset email",
    item_type: ScopeItemType.REQUIREMENT,
    group: ScopeGroup.REQUIRED,
    evidence_classification: EvidenceClassification.MISSING,
    risk_score: 9.5,
    risk_band: RiskBand.MEDIUM,
    change_impact_level: ChangeImpactLevel.DIRECT,
    business_risk_level: BusinessRiskLevel.HIGH,
    effective_risk_level: BusinessRiskLevel.HIGH,
    suggested_action: "Execute manual test before release",
    reason: "Mapped to AC-17, which is missing automated coverage and has high risk.",
    evidence_references: [],
    test_references: ["test-1"],
    can_auto_execute: false,
    execution_status: "NOT_EXECUTED",
    estimated_effort: "10 min (manual_test_default)",
    is_required_for_release: true,
    is_manual_only: false,
    provider: undefined,
    external_id: undefined,
    diagnostics: undefined,
    // Phase 6.4: Manual evidence risk adjustment fields
    manual_contribution_status: "PASSED",
    generated_risk_band: "HIGH",
    residual_risk_band: "MEDIUM",
    risk_adjustment_reason: "Manual validation passed and reduced residual risk by one band.",
    risk_adjustment_delta: -1,
  };

  const mockItemWithFailedManual = {
    ...mockItemWithRiskAdjustment,
    id: "req-2",
    readable_id: "AC-18",
    source_ac_number: 18,
    manual_contribution_status: "FAILED",
    generated_risk_band: "MEDIUM",
    residual_risk_band: "HIGH",
    risk_adjustment_reason: "Manual validation failed and elevated residual risk by one band.",
    risk_adjustment_delta: 1,
    risk_band: RiskBand.HIGH,
  };

  const mockItemWithNoManualEvidence = {
    ...mockItemWithRiskAdjustment,
    id: "req-3",
    readable_id: "AC-19",
    source_ac_number: 19,
    manual_contribution_status: undefined,
    generated_risk_band: undefined,
    residual_risk_band: undefined,
    risk_adjustment_reason: undefined,
    risk_adjustment_delta: undefined,
  };

  test("displays manual contribution status badge", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithRiskAdjustment]}
      />
    );

    expect(screen.getByText(/Manual: PASSED/)).toBeInTheDocument();
  });

  test("displays reduced risk indicator for PASSED manual evidence", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithRiskAdjustment]}
      />
    );

    expect(screen.getByText(/↓ 1 band/)).toBeInTheDocument();
  });

  test("displays elevated risk indicator for FAILED manual evidence", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithFailedManual]}
      />
    );

    expect(screen.getByText(/↑ 1 band/)).toBeInTheDocument();
  });

  test("displays manual contribution status for FAILED", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithFailedManual]}
      />
    );

    expect(screen.getByText(/Manual: FAILED/)).toBeInTheDocument();
  });

  test("does not display risk adjustment indicators when no manual evidence", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithNoManualEvidence]}
      />
    );

    expect(screen.queryByText(/Manual:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/↓ 1 band/)).not.toBeInTheDocument();
    expect(screen.queryByText(/↑ 1 band/)).not.toBeInTheDocument();
  });

  test("displays residual risk band correctly", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithRiskAdjustment]}
      />
    );

    // The displayed risk band should be the residual risk band (MEDIUM)
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();
  });

  test("residual risk band differs from generated risk band when adjusted", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithRiskAdjustment]}
      />
    );

    // Generated risk was HIGH, residual risk is MEDIUM
    // The displayed badge should show MEDIUM (residual)
    const riskBadges = screen.getAllByText("MEDIUM");
    expect(riskBadges.length).toBeGreaterThan(0);
  });

  test("displays manual contribution status for BLOCKED", () => {
    const mockBlocked = {
      ...mockItemWithRiskAdjustment,
      manual_contribution_status: "BLOCKED",
      generated_risk_band: "HIGH",
      residual_risk_band: "HIGH",
      risk_adjustment_reason: "Manual validation blocked; no risk adjustment.",
      risk_adjustment_delta: 0,
      risk_band: RiskBand.HIGH,
    };

    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockBlocked]}
      />
    );

    expect(screen.getByText(/Manual: BLOCKED/)).toBeInTheDocument();
    // No adjustment indicator when delta is 0
    expect(screen.queryByText(/↓ 1 band/)).not.toBeInTheDocument();
    expect(screen.queryByText(/↑ 1 band/)).not.toBeInTheDocument();
  });

  test("displays manual contribution status for SKIPPED", () => {
    const mockSkipped = {
      ...mockItemWithRiskAdjustment,
      manual_contribution_status: "SKIPPED",
      generated_risk_band: "HIGH",
      residual_risk_band: "HIGH",
      risk_adjustment_reason: "Manual validation skipped; no risk adjustment.",
      risk_adjustment_delta: 0,
      risk_band: RiskBand.HIGH,
    };

    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockSkipped]}
      />
    );

    expect(screen.getByText(/Manual: SKIPPED/)).toBeInTheDocument();
  });

  test("displays manual contribution status for NOT_EXECUTED", () => {
    const mockNotExecuted = {
      ...mockItemWithRiskAdjustment,
      manual_contribution_status: "NOT_EXECUTED",
      generated_risk_band: "HIGH",
      residual_risk_band: "HIGH",
      risk_adjustment_reason: "Manual validation not executed; no risk adjustment.",
      risk_adjustment_delta: 0,
      risk_band: RiskBand.HIGH,
    };

    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockNotExecuted]}
      />
    );

    expect(screen.getByText(/Manual: NOT_EXECUTED/)).toBeInTheDocument();
  });

  test("handles multiple items with different manual contributions", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithRiskAdjustment, mockItemWithFailedManual, mockItemWithNoManualEvidence]}
      />
    );

    expect(screen.getByText(/Manual: PASSED/)).toBeInTheDocument();
    expect(screen.getByText(/Manual: FAILED/)).toBeInTheDocument();
    expect(screen.getByText(/↓ 1 band/)).toBeInTheDocument();
    expect(screen.getByText(/↑ 1 band/)).toBeInTheDocument();
  });

  test("risk adjustment indicator has correct color for reduced risk", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithRiskAdjustment]}
      />
    );

    const reducedIndicator = screen.getByText(/↓ 1 band/);
    expect(reducedIndicator).toBeInTheDocument();
    // The indicator itself should have green styling for reduced risk
    expect(reducedIndicator).toHaveClass("bg-green-500/10");
  });

  test("risk adjustment indicator has correct color for elevated risk", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockItemWithFailedManual]}
      />
    );

    const elevatedIndicator = screen.getByText(/↑ 1 band/);
    expect(elevatedIndicator).toBeInTheDocument();
    // The indicator itself should have red styling for elevated risk
    expect(elevatedIndicator).toHaveClass("bg-red-500/10");
  });
});
