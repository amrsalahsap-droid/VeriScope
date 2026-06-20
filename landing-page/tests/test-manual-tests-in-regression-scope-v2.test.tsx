/**
 * @jest-environment jsdom
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ScopeGroupDisplay } from "../components/regression-scope";
import {
  ScopeGroup,
  ScopeItemType,
  EvidenceClassification,
  RiskBand,
  ChangeImpactLevel,
  BusinessRiskLevel
} from "../types/regression-scope-v2";

describe("Manual Tests in RegressionScopeV2", () => {
  const mockManualItem = {
    id: "manual-test-1",
    readable_id: "MT-MT-12",
    source_ac_number: 12,
    title: "Verify password reset email",
    item_type: ScopeItemType.MANUAL_TEST,
    group: ScopeGroup.REQUIRED,
    evidence_classification: EvidenceClassification.MISSING,
    risk_score: 9.5,
    risk_band: RiskBand.CRITICAL,
    change_impact_level: ChangeImpactLevel.DIRECT,
    business_risk_level: BusinessRiskLevel.CRITICAL,
    effective_risk_level: BusinessRiskLevel.CRITICAL,
    suggested_action: "Execute manual test before release",
    reason: "Mapped to AC-12, which is missing automated coverage and has critical risk.",
    evidence_references: [],
    test_references: ["MT-MT-12 (MANUAL_CSV:MT-12)"],
    can_auto_execute: false,
    execution_status: "NOT_EXECUTED",
    estimated_effort: "10 min (manual_test_default)",
    is_required_for_release: true,
    is_manual_only: true,
    provider: "MANUAL_CSV",
    external_id: "MT-12",
    diagnostics: undefined
  };

  const mockManualItemWithExecution = {
    ...mockManualItem,
    id: "manual-test-2",
    readable_id: "MT-MT-3",
    source_ac_number: 3,
    title: "Login smoke check",
    group: ScopeGroup.SAFE_TO_SKIP,
    execution_status: "PASSED",
    provider: "TESTRAIL",
    external_id: "MT-3"
  };

  test("renders Manual Test badge for MANUAL_TEST items", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockManualItem]}
      />
    );

    expect(screen.getByText("Manual Test")).toBeInTheDocument();
  });

  test("displays execution status for manual items", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockManualItem]}
      />
    );

    expect(screen.getByText("NOT_EXECUTED")).toBeInTheDocument();
  });

  test("displays estimated effort for manual items", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockManualItem]}
      />
    );

    expect(screen.getByText(/Effort: 10 min \(manual_test_default\)/)).toBeInTheDocument();
  });

  test("displays provider and external ID for manual items", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockManualItem]}
      />
    );

    expect(screen.getByText(/Provider: MANUAL_CSV/)).toBeInTheDocument();
    expect(screen.getByText("MT-12")).toBeInTheDocument();
  });

  test("displays PASSED status for executed manual tests", () => {
    render(
      <ScopeGroupDisplay
        title="Safe to Skip"
        description="Items that can be safely skipped"
        group={ScopeGroup.SAFE_TO_SKIP}
        items={[mockManualItemWithExecution]}
      />
    );

    expect(screen.getByText("PASSED")).toBeInTheDocument();
  });

  test("displays provider TESTRAIL for TestRail manual tests", () => {
    render(
      <ScopeGroupDisplay
        title="Safe to Skip"
        description="Items that can be safely skipped"
        group={ScopeGroup.SAFE_TO_SKIP}
        items={[mockManualItemWithExecution]}
      />
    );

    expect(screen.getByText(/Provider: TESTRAIL/)).toBeInTheDocument();
  });

  test("does not render Manual Test badge for REQUIREMENT items", () => {
    const mockRequirementItem = {
      ...mockManualItem,
      item_type: ScopeItemType.REQUIREMENT,
      is_manual_only: false,
      provider: undefined,
      external_id: undefined
    };

    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockRequirementItem]}
      />
    );

    expect(screen.queryByText("Manual Test")).not.toBeInTheDocument();
  });

  test("displays multiple manual items correctly", () => {
    render(
      <ScopeGroupDisplay
        title="Required"
        description="Critical items that must be executed"
        group={ScopeGroup.REQUIRED}
        items={[mockManualItem, mockManualItemWithExecution]}
      />
    );

    expect(screen.getAllByText("Manual Test")).toHaveLength(2);
  });
});
