/**
 * executeInputAction — single dispatcher for all 12-input CTAs.
 *
 * Every UI location passes its context here.
 * The dispatcher resolves the canonical action from the registry and
 * routes it to the correct flow (modal / navigation / mutation).
 *
 * If a flow is not yet implemented, the dispatcher shows a toast instead
 * of failing silently.
 */

import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import {
  getInputAction,
  resolveBackendAction,
  type InputId,
} from "./inputActionRegistry";

const DEV = process.env.NODE_ENV !== "production";

function log(fields: Record<string, unknown>) {
  if (DEV) {
    console.log("[INPUT_ACTION_EXECUTE]", fields);
  }
}

export interface InputActionContext {
  /** Repository ID — always required */
  repositoryId: string;
  /** Pull-request ID — required for PR-scoped inputs */
  pullRequestId?: string;
  /** Next.js app router for NAVIGATE actions */
  router: AppRouterInstance;
  /** Open the Business Requirements modal (Input 2) */
  openBusinessRequirementsModal?: () => void;
  /** Trigger a Repository Intelligence refresh mutation (Input 3) */
  runRepositoryIntelligence?: () => Promise<void>;
  /** Toast function — accepts (title, description?) */
  toast?: (title: string, opts?: { description?: string }) => void;
}

/**
 * Dispatch an action given either:
 *  - an `InputId`  (e.g. "INPUT_2"), OR
 *  - a raw backend action string (e.g. "OPEN_BUSINESS_REQUIREMENTS_MODAL")
 */
export function executeInputAction(
  inputIdOrBackendAction: string,
  ctx: InputActionContext
): void {
  // Resolve to canonical definition
  const def =
    getInputAction(inputIdOrBackendAction) ??
    resolveBackendAction(inputIdOrBackendAction);

  if (!def) {
    log({ inputId: inputIdOrBackendAction, result: "UNRECOGNISED_ACTION" });
    ctx.toast?.("Unknown action", {
      description: `No action registered for "${inputIdOrBackendAction}".`,
    });
    return;
  }

  log({
    inputId: def.inputId,
    label: def.label,
    actionType: def.actionType,
    target: def.target,
    repositoryId: ctx.repositoryId,
    pullRequestId: ctx.pullRequestId,
  });

  // Guard: action requires a PR
  if (def.requiresPullRequest && !ctx.pullRequestId) {
    ctx.toast?.("Select a pull request first", {
      description: `${def.label} requires a pull request to be selected.`,
    });
    log({ inputId: def.inputId, result: "NO_PULL_REQUEST" });
    return;
  }

  // If flow not implemented yet — show a clear message, never fail silently
  if (!def.implemented) {
    ctx.toast?.(`${def.label} — coming soon`, {
      description: def.description,
    });
    log({ inputId: def.inputId, result: "NOT_IMPLEMENTED" });
    return;
  }

  switch (def.target) {
    // ── Input 1: sync PR changes (mutation handled by parent via PR sync) ──
    case "PR_CHANGE_PACKAGE_SYNC": {
      ctx.toast?.("Sync pull request", {
        description: "Use the Sync PRs button to refresh changed files.",
      });
      log({ inputId: def.inputId, result: "REDIRECTED_TO_SYNC" });
      break;
    }

    // ── Input 2: Business Requirements modal ──
    case "BUSINESS_REQUIREMENTS_MODAL": {
      if (ctx.openBusinessRequirementsModal) {
        ctx.openBusinessRequirementsModal();
        log({ inputId: def.inputId, result: "OPENED_MODAL" });
      } else {
        ctx.toast?.("Add Requirements", {
          description:
            "The requirements modal is not available in this context.",
        });
        log({ inputId: def.inputId, result: "MODAL_NOT_MOUNTED" });
      }
      break;
    }

    // ── Input 3: Run Repository Intelligence ──
    case "PRODUCT_BEHAVIOR_MAP_MUTATION": {
      if (ctx.runRepositoryIntelligence) {
        ctx.runRepositoryIntelligence().catch(() => {
          ctx.toast?.("Intelligence refresh failed", {
            description: "Please retry or check backend connectivity.",
          });
        });
        log({ inputId: def.inputId, result: "MUTATION_TRIGGERED" });
      } else {
        ctx.toast?.("Repository Intelligence", {
          description: "Trigger a sync from the repository settings.",
        });
        log({ inputId: def.inputId, result: "MUTATION_NOT_AVAILABLE" });
      }
      break;
    }

    // ── Input 4: Test Case Import (navigate to test-history upload page) ──
    case "TEST_CASE_IMPORT_PAGE": {
      const params = new URLSearchParams({ inputType: "test-history" });
      if (ctx.pullRequestId) params.set("pullRequestId", ctx.pullRequestId);
      params.set("returnTo", "readiness");
      ctx.router.push(
        `/app/repositories/${ctx.repositoryId}/test-history?${params}`
      );
      log({ inputId: def.inputId, result: "NAVIGATED" });
      break;
    }

    // ── Input 5: AC → Test Mapping page ──
    case "AC_TEST_MAPPING_PAGE": {
      const params = new URLSearchParams();
      if (ctx.pullRequestId) params.set("pullRequestId", ctx.pullRequestId);
      params.set("returnTo", "readiness");
      ctx.router.push(
        `/app/repositories/${ctx.repositoryId}/test-history?${params}`
      );
      log({ inputId: def.inputId, result: "NAVIGATED" });
      break;
    }

    // ── Input 6: Test Results upload page ──
    case "TEST_RESULTS_UPLOAD_PAGE": {
      const params = new URLSearchParams({ inputType: "test-history" });
      if (ctx.pullRequestId) params.set("pullRequestId", ctx.pullRequestId);
      params.set("returnTo", "readiness");
      params.set("source", "input_readiness_cta");
      ctx.router.push(
        `/app/repositories/${ctx.repositoryId}/test-history?${params}`
      );
      log({ inputId: def.inputId, result: "NAVIGATED" });
      break;
    }

    // ── Input 7: Coverage upload page ──
    case "COVERAGE_UPLOAD_PAGE": {
      const params = new URLSearchParams({ inputType: "coverage" });
      if (ctx.pullRequestId) params.set("pullRequestId", ctx.pullRequestId);
      params.set("returnTo", "readiness");
      params.set("source", "input_readiness_cta");
      ctx.router.push(
        `/app/repositories/${ctx.repositoryId}/coverage?${params}`
      );
      log({ inputId: def.inputId, result: "NAVIGATED" });
      break;
    }

    // ── Input 10: Quality Gates page ──
    case "QUALITY_GATE_PAGE": {
      const params = new URLSearchParams();
      if (ctx.pullRequestId) params.set("pullRequestId", ctx.pullRequestId);
      params.set("returnTo", "readiness");
      params.set("source", "input_readiness_cta");
      ctx.router.push(
        `/app/repositories/${ctx.repositoryId}/ci-settings?${params}`
      );
      log({ inputId: def.inputId, result: "NAVIGATED" });
      break;
    }

    // ── Inputs 8-9, 11-12: not yet implemented (guard above handles this) ──
    default: {
      ctx.toast?.(`${def.label} — coming soon`, {
        description: def.description,
      });
      log({ inputId: def.inputId, target: def.target, result: "UNHANDLED_TARGET" });
    }
  }
}
