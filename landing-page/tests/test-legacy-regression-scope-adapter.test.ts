import { legacyRegressionScopeToV2 } from "../lib/adapters/legacyRegressionScopeToV2";
import { ScopeGroup, ScopeItemType } from "../types/regression-scope-v2";

describe("Legacy Regression Scope Adapter Tests", () => {
  const mockLegacyScope = {
    id: "legacy-scope-id",
    recommendation_run_id: "run-123",
    created_at: "2026-06-13T05:00:00Z",
    scope_type: "targeted",
    health_at_creation: "READY_WITH_GAPS",
    summary: "This is a summary of the legacy regression scope",
    source_evidence_graph_snapshot: {
      recommendation_run_id: "run-123",
      snapshot_hash: "sha256-abc123xyz789",
      generated_at: "2026-06-13T05:00:00Z"
    },
    required_items: [
      {
        id: "item-req-1",
        readable_id: "AC-REQ-1",
        title: "Legacy Required Requirement",
        item_type: "REQUIRED_MISSING_COVERAGE",
        classification: "MISSING",
        suggested_action: "Add integration tests",
        flow: "flow-1",
        businessContext: {
          riskLevel: "CRITICAL",
          priority: "MUST"
        }
      }
    ],
    review_items: [
      {
        id: "item-rev-1",
        readable_id: "AC-REV-1",
        title: "Legacy Review Item",
        item_type: "REVIEW_PARTIAL_SUPPORT",
        classification: "PARTIAL",
        businessRiskReview: {
          reviewStatus: "NEEDS_DISCUSSION",
          originalRiskLevel: "HIGH",
          effectiveRiskLevel: "MEDIUM"
        }
      }
    ],
    optional_safety_net_items: [
      {
        id: "item-opt-1",
        title: "Legacy Optional Item",
        item_type: "TEST"
      }
    ],
    excluded_already_verified_requirements: [
      {
        id: "item-ver-1",
        title: "Legacy Verified Item",
        item_type: "EXCLUDED_ALREADY_VERIFIED"
      }
    ],
    excluded_already_passed_tests: [
      {
        id: "item-pass-1",
        title: "Legacy Passed Test",
        item_type: "EXCLUDED_ALREADY_PASSED",
        test_id: "test-id-pass"
      }
    ],
    generation_rules_applied: ["rule1", "rule2"],
    diagnostics: ["error1", "error2"]
  };

  it("converts required_items to REQUIRED group", () => {
    const v2 = legacyRegressionScopeToV2(mockLegacyScope);
    expect(v2.groups[ScopeGroup.REQUIRED].count).toBe(1);
    const item = v2.groups[ScopeGroup.REQUIRED].items[0];
    expect(item.id).toBe("item-req-1");
    expect(item.readable_id).toBe("AC-REQ-1");
    expect(item.title).toBe("Legacy Required Requirement");
    expect(item.item_type).toBe(ScopeItemType.REQUIREMENT);
    expect(item.group).toBe(ScopeGroup.REQUIRED);
    expect(item.risk_band).toBe("CRITICAL");
    expect(item.business_risk_level).toBe("CRITICAL");
  });

  it("converts review_items to RECOMMENDED group", () => {
    const v2 = legacyRegressionScopeToV2(mockLegacyScope);
    expect(v2.groups[ScopeGroup.RECOMMENDED].count).toBe(1);
    const item = v2.groups[ScopeGroup.RECOMMENDED].items[0];
    expect(item.id).toBe("item-rev-1");
    expect(item.item_type).toBe(ScopeItemType.REQUIREMENT);
    expect(item.group).toBe(ScopeGroup.RECOMMENDED);
    expect(item.business_risk_level).toBe("HIGH");
    expect(item.effective_risk_level).toBe("MEDIUM");
  });

  it("converts optional_safety_net_items to OPTIONAL group", () => {
    const v2 = legacyRegressionScopeToV2(mockLegacyScope);
    expect(v2.groups[ScopeGroup.OPTIONAL].count).toBe(1);
    const item = v2.groups[ScopeGroup.OPTIONAL].items[0];
    expect(item.id).toBe("item-opt-1");
    expect(item.item_type).toBe(ScopeItemType.TEST);
  });

  it("converts excluded_already_verified_requirements to EXCLUDED_ALREADY_VERIFIED group", () => {
    const v2 = legacyRegressionScopeToV2(mockLegacyScope);
    expect(v2.exclusions.already_verified_count).toBe(1);
    expect(v2.exclusions.already_verified_items[0].id).toBe("item-ver-1");
    expect(v2.exclusions.already_verified_items[0].group).toBe(ScopeGroup.EXCLUDED_ALREADY_VERIFIED);
  });

  it("converts excluded_already_passed_tests to EXCLUDED_ALREADY_PASSED_TESTS group", () => {
    const v2 = legacyRegressionScopeToV2(mockLegacyScope);
    expect(v2.exclusions.already_passed_tests_count).toBe(1);
    const item = v2.exclusions.already_passed_test_items[0];
    expect(item.id).toBe("item-pass-1");
    expect(item.group).toBe(ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS);
    expect(item.test_references).toEqual(["test-id-pass"]);
  });

  it("preserves snapshot reference, summary and diagnostics", () => {
    const v2 = legacyRegressionScopeToV2(mockLegacyScope);
    expect(v2.recommendation_run_id).toBe("run-123");
    expect(v2.snapshot_hash).toBe("sha256-abc123xyz789");
    expect(v2.summary).toBe("This is a summary of the legacy regression scope");
    expect(v2.diagnostics.rules_applied).toEqual(["rule1", "rule2"]);
    expect(v2.diagnostics.errors).toEqual(["error1", "error2"]);
  });

  it("safely handles empty/missing fields", () => {
    const emptyLegacy = {
      id: "empty-id",
      recommendation_run_id: "run-empty",
      created_at: "2026-06-13T05:00:00Z"
    };
    const v2 = legacyRegressionScopeToV2(emptyLegacy);
    expect(v2.recommendation_run_id).toBe("run-empty");
    expect(v2.snapshot_hash).toBe("");
    expect(v2.groups[ScopeGroup.REQUIRED].items).toEqual([]);
    expect(v2.exclusions.already_verified_items).toEqual([]);
  });
});
