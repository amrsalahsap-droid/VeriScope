import { ScopeGroup } from "../../types/regression-scope-v2";

export interface GroupStyleConfig {
  label: string;
  textClass: string;
  bgClass: string;
  borderClass: string;
  badgeClass: string;
}

export const SCOPE_GROUP_STYLES: Record<ScopeGroup, GroupStyleConfig> = {
  [ScopeGroup.REQUIRED]: {
    label: "Required Before Release",
    textClass: "text-rose-400",
    bgClass: "bg-rose-950/20",
    borderClass: "border-rose-800/40",
    badgeClass: "text-rose-400 bg-rose-950/20 border-rose-800/40 border",
  },
  [ScopeGroup.REVIEW_NEEDED]: {
    label: "Review Needed",
    textClass: "text-purple-400",
    bgClass: "bg-purple-950/20",
    borderClass: "border-purple-800/40",
    badgeClass: "text-purple-400 bg-purple-950/20 border-purple-800/40 border",
  },
  [ScopeGroup.RECOMMENDED]: {
    label: "Recommended Regression",
    textClass: "text-amber-400",
    bgClass: "bg-amber-950/20",
    borderClass: "border-amber-800/40",
    badgeClass: "text-amber-400 bg-amber-950/20 border-amber-800/40 border",
  },
  [ScopeGroup.OPTIONAL]: {
    label: "Optional Safety Net",
    textClass: "text-zinc-400",
    bgClass: "bg-zinc-950/20",
    borderClass: "border-zinc-800/40",
    badgeClass: "text-zinc-400 bg-zinc-950/20 border-zinc-800/40 border",
  },
  [ScopeGroup.SAFE_TO_SKIP]: {
    label: "Safe To Skip",
    textClass: "text-blue-400",
    bgClass: "bg-blue-950/20",
    borderClass: "border-blue-800/40",
    badgeClass: "text-blue-400 bg-blue-950/20 border-blue-800/40 border",
  },
  [ScopeGroup.EXCLUDED_ALREADY_VERIFIED]: {
    label: "Already Verified",
    textClass: "text-emerald-400",
    bgClass: "bg-emerald-950/20",
    borderClass: "border-emerald-800/40",
    badgeClass: "text-emerald-400 bg-emerald-950/20 border-emerald-800/40 border",
  },
  [ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS]: {
    label: "Already Passed Tests",
    textClass: "text-emerald-400",
    bgClass: "bg-emerald-950/20",
    borderClass: "border-emerald-800/40",
    badgeClass: "text-emerald-400 bg-emerald-950/20 border-emerald-800/40 border",
  },
  [ScopeGroup.DEFERRED_COVERAGE_DEBT]: {
    label: "Deferred Coverage Debt",
    textClass: "text-orange-400",
    bgClass: "bg-orange-950/20",
    borderClass: "border-orange-800/40",
    badgeClass: "text-orange-400 bg-orange-950/20 border-orange-800/40 border",
  },
};
