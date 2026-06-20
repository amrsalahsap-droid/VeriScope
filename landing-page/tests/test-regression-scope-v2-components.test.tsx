/**
 * @jest-environment jsdom
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import {
  RegressionScopeV2Display,
  ScopeGroupDisplay,
  ExecutionPlanDisplay,
  ScopeModeSelector
} from "../components/regression-scope";
import {
  RegressionScopeV2,
  ScopeGroup,
  ScopeItemType,
  EvidenceClassification,
  RiskBand,
  ChangeImpactLevel,
  BusinessRiskLevel,
  ScopeSource
} from "../types/regression-scope-v2";

const mockRegressionScopeData: RegressionScopeV2 = {
  recommendation_run_id: "rec-run-123",
  snapshot_hash: "sha256-abc123xyz789",
  generated_at: "2026-06-13T05:00:00Z",
  scope_type: "targeted",
  source: ScopeSource.HYBRID,
  summary: "This is a mock regression scope summary describing the impact of changes.",
  execution_plan: {
    required_count: 2,
    recommended_count: 1,
    optional_count: 1,
    safe_to_skip_count: 3,
    total_executable_count: 4,
    estimated_execution_reduction: 45.5,
    confidence_level: 95.0,
    plan_summary: "Run 4 out of 7 tests, saving 45%.",
    advisory_notice: "Please ensure manual validation on staging if critical paths fail."
  },
  groups: {
    [ScopeGroup.REQUIRED]: {
      group: ScopeGroup.REQUIRED,
      count: 2,
      items: [
        {
          id: "item-uuid-req-1",
          readable_id: "AC-REQ-1",
          title: "Verify password strength validation",
          item_type: ScopeItemType.REQUIREMENT,
          group: ScopeGroup.REQUIRED,
          evidence_classification: EvidenceClassification.MISSING,
          risk_score: 9.5,
          risk_band: RiskBand.CRITICAL,
          change_impact_level: ChangeImpactLevel.DIRECT,
          business_risk_level: BusinessRiskLevel.CRITICAL,
          effective_risk_level: BusinessRiskLevel.CRITICAL,
          suggested_action: "Add automated integration test checking min length and symbols.",
          reason: "Directly touched in validation.py and auth.py",
          evidence_references: ["validation.py:L45"],
          test_references: ["test_auth_password_strength"],
          can_auto_execute: true,
          is_required_for_release: true,
          is_manual_only: false,
          diagnostics: {
            internal_requirement_id: "req-id-internal-999",
            internal_test_id: "test-id-internal-111",
            generation_rule: "rule_direct_file_mod",
            confidence_score: 0.98,
            last_updated: "2026-06-13T04:30:00Z"
          }
        },
        {
          id: "item-uuid-req-2",
          readable_id: "AC-REQ-2",
          title: "Verify lockout after 5 failed attempts",
          item_type: ScopeItemType.REQUIREMENT,
          group: ScopeGroup.REQUIRED,
          evidence_classification: EvidenceClassification.PARTIAL,
          risk_score: 8.0,
          risk_band: RiskBand.HIGH,
          change_impact_level: ChangeImpactLevel.DIRECT,
          business_risk_level: BusinessRiskLevel.HIGH,
          effective_risk_level: BusinessRiskLevel.HIGH,
          suggested_action: "Run brute_force_lockout_test",
          reason: "Security sensitive lockout controls modified",
          evidence_references: ["lockout_policy.ts"],
          test_references: ["test_lockout_mechanism"],
          can_auto_execute: true,
          is_required_for_release: true,
          is_manual_only: false,
          diagnostics: {
            internal_requirement_id: "req-id-internal-888",
            internal_test_id: "test-id-internal-222",
            generation_rule: "rule_security_critical_mod",
            confidence_score: 0.92,
            last_updated: "2026-06-13T04:30:00Z"
          }
        }
      ]
    },
    [ScopeGroup.RECOMMENDED]: {
      group: ScopeGroup.RECOMMENDED,
      count: 1,
      items: [
        {
          id: "item-uuid-rec-1",
          readable_id: "AC-REC-1",
          title: "Verify user profile details page loading",
          item_type: ScopeItemType.SCENARIO,
          group: ScopeGroup.RECOMMENDED,
          evidence_classification: EvidenceClassification.COVERED,
          risk_score: 5.5,
          risk_band: RiskBand.MEDIUM,
          change_impact_level: ChangeImpactLevel.RELATED,
          business_risk_level: BusinessRiskLevel.MEDIUM,
          effective_risk_level: BusinessRiskLevel.MEDIUM,
          suggested_action: "Execute selenium loading smoke test",
          reason: "User session variables changed, profile page might be impacted",
          evidence_references: ["profile.tsx"],
          test_references: ["smoke_test_profile"],
          can_auto_execute: true,
          is_required_for_release: false,
          is_manual_only: false
        }
      ]
    },
    [ScopeGroup.OPTIONAL]: {
      group: ScopeGroup.OPTIONAL,
      count: 1,
      items: [
        {
          id: "item-uuid-opt-1",
          readable_id: "AC-OPT-1",
          title: "Verify light/dark theme toggle styling",
          item_type: ScopeItemType.TEST,
          group: ScopeGroup.OPTIONAL,
          evidence_classification: EvidenceClassification.COVERED,
          risk_score: 2.0,
          risk_band: RiskBand.LOW,
          change_impact_level: ChangeImpactLevel.INDIRECT,
          business_risk_level: BusinessRiskLevel.LOW,
          effective_risk_level: BusinessRiskLevel.LOW,
          suggested_action: "Visual snapshot test theme-toggle",
          reason: "CSS assets updated, checking for side-effects",
          evidence_references: ["theme.css"],
          test_references: ["test_theme_toggle_renders"],
          can_auto_execute: true,
          is_required_for_release: false,
          is_manual_only: false
        }
      ]
    },
    [ScopeGroup.SAFE_TO_SKIP]: {
      group: ScopeGroup.SAFE_TO_SKIP,
      count: 1,
      items: [
        {
          id: "item-uuid-skip-1",
          readable_id: "AC-SKIP-1",
          title: "Verify export user data to CSV",
          item_type: ScopeItemType.TEST,
          group: ScopeGroup.SAFE_TO_SKIP,
          evidence_classification: EvidenceClassification.COVERED,
          risk_score: 1.0,
          risk_band: RiskBand.LOW,
          change_impact_level: ChangeImpactLevel.NONE,
          business_risk_level: BusinessRiskLevel.LOW,
          effective_risk_level: BusinessRiskLevel.LOW,
          suggested_action: "Skip execution",
          reason: "No changes detected in reporting or CSV libraries",
          evidence_references: ["csv_exporter.py"],
          test_references: ["test_csv_export"],
          can_auto_execute: false,
          is_required_for_release: false,
          is_manual_only: false
        }
      ]
    },
    [ScopeGroup.EXCLUDED_ALREADY_VERIFIED]: {
      group: ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
      count: 1,
      items: [
        {
          id: "item-uuid-ex-ver-1",
          readable_id: "AC-EX-1",
          title: "Verify API healthcheck endpoint",
          item_type: ScopeItemType.TEST,
          group: ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
          evidence_classification: EvidenceClassification.COVERED,
          risk_score: 0.5,
          risk_band: RiskBand.LOW,
          change_impact_level: ChangeImpactLevel.NONE,
          business_risk_level: BusinessRiskLevel.LOW,
          effective_risk_level: BusinessRiskLevel.LOW,
          suggested_action: "No action (already verified)",
          reason: "Passed in commit hash abc456 on dev branch",
          evidence_references: ["main.py"],
          test_references: ["test_health_endpoint"],
          can_auto_execute: true,
          is_required_for_release: false,
          is_manual_only: false
        }
      ]
    },
    [ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS]: {
      group: ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS,
      count: 1,
      items: [
        {
          id: "item-uuid-ex-pass-1",
          readable_id: "AC-EX-2",
          title: "Verify static privacy policy link redirects properly",
          item_type: ScopeItemType.MANUAL_TEST,
          group: ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS,
          evidence_classification: EvidenceClassification.COVERED,
          risk_score: 0.2,
          risk_band: RiskBand.LOW,
          change_impact_level: ChangeImpactLevel.NONE,
          business_risk_level: BusinessRiskLevel.LOW,
          effective_risk_level: BusinessRiskLevel.LOW,
          suggested_action: "No action (already passed tests)",
          reason: "Covered by automated end-to-end suite passing on prod branch 1 hour ago",
          evidence_references: ["privacy_policy.html"],
          test_references: ["e2e_test_footer_links"],
          can_auto_execute: false,
          is_required_for_release: false,
          is_manual_only: true
        }
      ]
    }
  },
  exclusions: {
    already_verified_count: 1,
    already_passed_tests_count: 1,
    already_verified_items: [],
    already_passed_test_items: []
  },
  optimization_metrics: {
    current_regression_size: 7,
    optimized_required_count: 2,
    optimized_recommended_count: 1,
    optimized_optional_count: 1,
    safe_to_skip_count: 3,
    optimization_percentage: 42.8,
    execution_reduction: 45.5,
    coverage_confidence: 95.0
  },
  governance: {
    risk_reviews_count: 0,
    overridden_count: 0,
    needs_discussion_count: 0,
    release_decision_required: true,
    release_decision_status: "pending"
  },
  diagnostics: {
    generation_timestamp: "2026-06-13T05:00:00Z",
    generation_duration_ms: 120,
    rules_applied: ["Rule1: DirectChanges", "Rule2: RiskPropagation", "Rule3: HistoryDeduplication"],
    warnings: ["Some tests do not have linked requirements"],
    errors: ["A critical diagnostic error occurred"]
  }
};

describe("RegressionScopeV2 Components", () => {
  // Test 1
  it("RegressionScopeV2Display renders summary and execution plan", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    // Check summary description
    expect(screen.getByText("This is a mock regression scope summary describing the impact of changes.")).toBeInTheDocument();
    
    // Check execution plan header/details
    expect(screen.getByText("Execution Plan")).toBeInTheDocument();
    expect(screen.getByText("Run 4 out of 7 tests, saving 45%.")).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("46%")).toBeInTheDocument(); // estimated_execution_reduction (45.5 rounded)
  });

  // Test 2
  it("renders Required Before Release section", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.getByText("Required Before Release")).toBeInTheDocument();
    expect(screen.getByText("AC-REQ-1")).toBeInTheDocument();
    expect(screen.getByText("Verify password strength validation")).toBeInTheDocument();
    expect(screen.getByText("AC-REQ-2")).toBeInTheDocument();
    expect(screen.getByText("Verify lockout after 5 failed attempts")).toBeInTheDocument();
  });

  // Test 3
  it("renders Recommended Regression section", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.getByText("Recommended Regression")).toBeInTheDocument();
    expect(screen.getByText("AC-REC-1")).toBeInTheDocument();
    expect(screen.getByText("Verify user profile details page loading")).toBeInTheDocument();
  });

  // Test 4
  it("renders Optional Safety Net section", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.getByText("Optional Safety Net")).toBeInTheDocument();
    expect(screen.getByText("AC-OPT-1")).toBeInTheDocument();
    expect(screen.getByText("Verify light/dark theme toggle styling")).toBeInTheDocument();
  });

  // Test 5
  it("Safe To Skip group is hidden/collapsed by default", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.queryByText("Safe To Skip")).not.toBeInTheDocument();
    expect(screen.queryByText("AC-SKIP-1")).not.toBeInTheDocument();
  });

  // Test 6
  it("Safe To Skip group is visible when showSafeToSkip=true", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} showSafeToSkip={true} />);
    
    expect(screen.getByText("Safe To Skip")).toBeInTheDocument();
    expect(screen.getByText("AC-SKIP-1")).toBeInTheDocument();
    expect(screen.getByText("Verify export user data to CSV")).toBeInTheDocument();
  });

  // Test 7
  it("Exclusions groups (Already Verified and Already Passed Tests) are hidden by default", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.queryByText("Already Verified")).not.toBeInTheDocument();
    expect(screen.queryByText("Already Passed Tests")).not.toBeInTheDocument();
  });

  // Test 8
  it("Exclusions groups are visible in auditMode=true or showExclusions=true", () => {
    const { rerender } = render(<RegressionScopeV2Display scope={mockRegressionScopeData} showExclusions={true} />);
    expect(screen.getByText("Already Verified")).toBeInTheDocument();
    expect(screen.getByText("Already Passed Tests")).toBeInTheDocument();
    expect(screen.getByText("AC-EX-1")).toBeInTheDocument();
    expect(screen.getByText("AC-EX-2")).toBeInTheDocument();

    rerender(<RegressionScopeV2Display scope={mockRegressionScopeData} auditMode={true} />);
    expect(screen.getByText("Already Verified")).toBeInTheDocument();
    expect(screen.getByText("Already Passed Tests")).toBeInTheDocument();
  });

  // Test 9
  it("Diagnostics information is hidden in normal mode", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.queryByText("Diagnostics Audit")).not.toBeInTheDocument();
    expect(screen.queryByText("Rule1: DirectChanges")).not.toBeInTheDocument();
    expect(screen.queryByText("A critical diagnostic error occurred")).not.toBeInTheDocument();
  });

  // Test 10
  it("Diagnostics information is visible in auditMode=true", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} auditMode={true} />);
    
    expect(screen.getByText("Diagnostics Audit")).toBeInTheDocument();
    expect(screen.getByText("Rule1: DirectChanges")).toBeInTheDocument();
    expect(screen.getByText("A critical diagnostic error occurred")).toBeInTheDocument();
  });

  // Test 11
  it("Internal IDs (UUIDs, internal hashes, internal requirement IDs) are hidden in normal mode", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} />);
    
    expect(screen.queryByText("item-uuid-req-1")).not.toBeInTheDocument();
    expect(screen.queryByText("req-id-internal-999")).not.toBeInTheDocument();
    expect(screen.queryByText("test-id-internal-111")).not.toBeInTheDocument();
  });

  // Test 12
  it("Internal IDs are visible in auditMode=true", () => {
    render(<RegressionScopeV2Display scope={mockRegressionScopeData} auditMode={true} />);
    
    // Check for ID strings in the rendered audit fields
    expect(screen.getByText(/item-uuid-req-1/)).toBeInTheDocument();
    expect(screen.getByText(/req-id-internal-999/)).toBeInTheDocument();
    expect(screen.getByText(/test-id-internal-111/)).toBeInTheDocument();
  });

  // Test 13
  it("Compact mode renders without errors", () => {
    const { container } = render(<RegressionScopeV2Display scope={mockRegressionScopeData} compact={true} />);
    
    // In compact mode, we shouldn't render the top layout's header or summary description
    expect(screen.queryByText("This is a mock regression scope summary describing the impact of changes.")).not.toBeInTheDocument();
    // But execution plan and groups should render
    expect(screen.getByText("Required Before Release")).toBeInTheDocument();
    expect(container).toBeInTheDocument();
  });

  // Test 14
  it("Empty groups display the correct empty fallback state message", () => {
    const emptyData: RegressionScopeV2 = {
      ...mockRegressionScopeData,
      groups: {
        [ScopeGroup.REQUIRED]: {
          group: ScopeGroup.REQUIRED,
          count: 0,
          items: []
        }
      }
    };
    render(<RegressionScopeV2Display scope={emptyData} />);
    
    expect(screen.getByText("No required tasks for this release.")).toBeInTheDocument();
  });

  // Test 15
  it("ScopeModeSelector triggers the onChange callback correctly", () => {
    const onChangeMock = jest.fn();
    render(<ScopeModeSelector value="targeted" onChange={onChangeMock} />);
    
    const riskBasedBtn = screen.getByText("Risk-Based Mode");
    fireEvent.click(riskBasedBtn);
    
    expect(onChangeMock).toHaveBeenCalledTimes(1);
    expect(onChangeMock).toHaveBeenCalledWith("risk_based");
  });
});
