export type RequirementGroupType = "ENHANCEMENT" | "BUG_FIX" | "SECURITY" | "TECH_DEBT" | "NON_FUNCTIONAL" | "UNKNOWN";
export type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type RequirementStatus = "ACTIVE" | "NEEDS_REVIEW" | "DUPLICATE" | "REMOVED";
export type ACStatus = "ACTIVE" | "NEEDS_REVIEW" | "DUPLICATE" | "REMOVED" | "GENERATED_UNACCEPTED";
export type ACSourceType = "MANUAL" | "PR_DESCRIPTION" | "JIRA" | "AZURE_DEVOPS" | "UPLOADED_FILE" | "GENERATED";
export type PackageStatus = "READY" | "PARTIAL" | "BLOCKED" | "NEEDS_REVIEW";

export interface AcceptanceCriterionViewModel {
  id?: string;
  acNumber?: string;
  sourceNumber?: number;
  stableAcKey?: string;
  title: string;
  description?: string;
  rawText?: string;
  normalizedText?: string;
  sourceType: ACSourceType;
  status: ACStatus;
  confidence?: number;
  needsReview?: boolean;
}

export interface RequirementGroupViewModel {
  id?: string;
  groupNumber?: string;
  stableGroupKey?: string;
  title: string;
  description?: string;
  groupType: RequirementGroupType;
  businessFlow?: string;
  priority?: Priority;
  riskLevel?: Priority;
  status: RequirementStatus;
  acceptanceCriteria: AcceptanceCriterionViewModel[];
}

export interface RequirementReadinessViewModel {
  status: PackageStatus;
  groupCount: number;
  acCount: number;
  stableIdCoverage: string; // e.g., "12/12"
  duplicateCount: number;
  needsReviewCount: number;
  generatedUnacceptedCount: number;
  flatteningRisk: "LOW" | "HIGH";
  requiredFixes: string[];
}

export interface RequirementPackageViewModel {
  id?: string;
  repositoryId: string;
  pullRequestId: string;
  status: PackageStatus;
  summary?: string;
  affectedUsersOrJourneys?: string;
  riskNotes?: string;
  groups: RequirementGroupViewModel[];
  readiness: RequirementReadinessViewModel;
  // Separated business requirement sections
  businessChangeSummary?: string;
  affectedJourneys?: string[];
  invalidTestDataExamples?: string[];
  validTestDataExamples?: string[];
  securityNotes?: string[];
  integrationNotes?: string | null;
  outOfScopeNotes?: string | null;
}

export interface ParsedRequirementsResult {
  groups: RequirementGroupViewModel[];
  ungroupedACs: AcceptanceCriterionViewModel[];
  parseWarnings: string[];
}
