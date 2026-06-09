"""
recommendation_action_generator.py
─────────────────────────────────────
Generates a single, concise, actionable next-step sentence for a PR comment.

Design rules
────────────
- Exactly one output sentence. Never a list, never a paragraph.
- Action is derived from evidence, not from templates applied blindly.
- Signals are evaluated in strict priority order (highest-signal wins).
- Sentence is deterministic: identical inputs always produce identical output.
- No AI prose. No playbooks. No hyperbole. No fake statistics.

Priority decision table (first matching rule wins)
────────────────────────────────────────────────────
1. ROLLBACK_INVOLVEMENT or ESCAPED_DEFECT_PATTERN touching a changed file
   → rollback-sensitive flow review + integration tests
2. CO_FAILURE_PATTERN touching two or more changed components
   → named integration tests for the co-failing pair
3. FILE_FAILURE_FREQUENCY pattern on a changed file (HIGH risk)
   → integration tests focused on the fragile file's area
4. Warning code ROLLBACK_LINKED_FRAGILITY present
   → rollback-sensitive flow review
5. Warning code UNSTABLE_DEPENDENCY_NEIGHBORHOOD present
   → smoke validation on the affected dependency area
6. Warning code HIGH_FLAKY_INFLUENCE present
   → manual verification before merge (flaky tests may mask regressions)
7. coverage_confidence == LOW or MISSING
   → smoke validation covering recently changed files
8. coverage_confidence == MODERATE
   → run the recommended suite and verify critical paths manually
9. recommendation_mode == SAFE_FALLBACK or FULL_REGRESSION
   → full regression suite before merge
10. Default (HIGH confidence, NORMAL mode, no strong signal)
    → run the recommended regression suite before merge

Allowed action types
─────────────────────
- integration tests
- smoke validation
- auth validation
- rollback-sensitive flow review
- manual verification
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.models.recommendation import RecommendationRun

logger = logging.getLogger("veriscope.recommendation_action_generator")

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

_ROLLBACK_TYPES = frozenset({"ROLLBACK_INVOLVEMENT", "ESCAPED_DEFECT_PATTERN"})
_COFAIL_TYPE = "CO_FAILURE_PATTERN"
_FREQ_TYPE = "FILE_FAILURE_FREQUENCY"
_AUTH_KEYWORDS = frozenset({"auth", "login", "session", "token", "oauth", "jwt", "permission", "access"})
_BILLING_KEYWORDS = frozenset({"billing", "payment", "invoice", "subscription", "charge", "pricing"})

# Forbidden phrases enforced at generation time
_FORBIDDEN = [
    "unsafe to merge",
    "high probability of outage",
    "production failure",
    "catastrophic",
    "guaranteed",
    "will fail",
    "do not merge",
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _shorten_path(path: str) -> str:
    """Return at most the last two path components."""
    if not path:
        return ""
    parts = path.split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else path


def _component_label(path: str) -> str:
    """Extract the parent folder name as a component label."""
    if not path:
        return "affected"
    parts = path.replace("\\", "/").split("/")
    # Strip extension from last part, return parent folder if possible
    return parts[-2] if len(parts) >= 2 else parts[0].split(".")[0]


def _detect_domain(paths: List[str]) -> str:
    """
    Infer a domain label (e.g. 'auth', 'billing') from file paths.
    Returns empty string if no known domain is detected.
    """
    combined = " ".join(paths).lower()
    if any(kw in combined for kw in _AUTH_KEYWORDS):
        return "auth"
    if any(kw in combined for kw in _BILLING_KEYWORDS):
        return "billing"
    return ""


def _active(pat: Any) -> bool:
    return getattr(pat, "status", "") == "ACTIVE"


def _validate_sentence(sentence: str) -> str:
    """Strip forbidden phrases from the generated sentence defensively."""
    lower = sentence.lower()
    for phrase in _FORBIDDEN:
        if phrase in lower:
            logger.error(
                f"[RecommendationActionGenerator] Forbidden phrase '{phrase}' "
                f"found in generated action. Replacing with safe fallback."
            )
            return "Run the recommended regression suite before merging."
    return sentence


# ─────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────

@dataclass
class ActionResult:
    sentence: str           # the single action sentence for the PR comment
    action_type: str        # machine-readable label for the chosen action type
    signal_source: str      # which rule fired (for logging / auditability)

    def as_dict(self) -> Dict[str, str]:
        return {
            "sentence": self.sentence,
            "action_type": self.action_type,
            "signal_source": self.signal_source,
        }


# ─────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────

class RecommendationActionGenerator:
    """
    Generates a single actionable sentence derived from:
    - Active fragility patterns
    - Warning codes from RecommendationWarningRules
    - Coverage confidence (evidence_quality)
    - Recommendation mode

    Usage
    ─────
    result = RecommendationActionGenerator.generate(
        run=run,
        fragility_patterns=patterns,     # List[FragilityPattern], may be []
        warning_codes=warning_codes,     # List[str], from WarningResult.codes
        changed_files=changed_files,     # List[str], from input_snapshot
    )
    print(result.sentence)
    # -> "Run auth-billing integration tests before merge."
    """

    @classmethod
    def generate(
        cls,
        run: RecommendationRun,
        fragility_patterns: Optional[List[Any]] = None,
        warning_codes: Optional[List[str]] = None,
        changed_files: Optional[List[str]] = None,
    ) -> ActionResult:
        """
        Evaluate all signals in priority order and return the first matching action.

        All parameters are optional to allow graceful degradation when upstream
        data is unavailable.
        """
        patterns = fragility_patterns or []
        codes = set(warning_codes or [])
        files = changed_files or cls._extract_changed_files(run)
        quality = (getattr(run, "evidence_quality", None) or "UNKNOWN").upper()
        mode = (getattr(run, "recommendation_mode", None) or "NORMAL").upper()

        active_patterns = [p for p in patterns if _active(p)]

        # ── Priority 1: Rollback-linked patterns on changed files ──────────
        result = cls._rule_rollback_linked(active_patterns, files)
        if result:
            return result

        # ── Priority 2: Co-failure patterns on changed components ──────────
        result = cls._rule_cofailure_pair(active_patterns, files)
        if result:
            return result

        # ── Priority 3: High-risk file failure frequency ───────────────────
        result = cls._rule_high_frequency_fragility(active_patterns, files)
        if result:
            return result

        # ── Priority 4–6: Warning-code–derived actions ─────────────────────
        result = cls._rule_from_warning_codes(codes, files)
        if result:
            return result

        # ── Priority 7: Low / missing coverage ────────────────────────────
        if quality in ("LOW", "MISSING", "UNKNOWN"):
            domain = _detect_domain(files)
            area = f"{domain} " if domain else ""
            return ActionResult(
                sentence=f"Run smoke validation covering {area}recently changed files before merging.",
                action_type="smoke_validation",
                signal_source="LOW_COVERAGE_CONFIDENCE",
            )

        # ── Priority 8: Moderate coverage ─────────────────────────────────
        if quality == "MODERATE":
            return ActionResult(
                sentence="Run the recommended suite and verify critical paths manually before merging.",
                action_type="manual_verification",
                signal_source="MODERATE_COVERAGE_CONFIDENCE",
            )

        # ── Priority 9: Degraded recommendation mode ───────────────────────
        if mode in ("SAFE_FALLBACK", "FULL_REGRESSION"):
            return ActionResult(
                sentence="Run the full regression suite before merging.",
                action_type="full_regression",
                signal_source=f"RECOMMENDATION_MODE:{mode}",
            )

        # ── Priority 10: Default ───────────────────────────────────────────
        return ActionResult(
            sentence="Run the recommended regression suite before merging.",
            action_type="regression_suite",
            signal_source="DEFAULT",
        )

    # ──────────────────────────────────────────────────────────
    # Rule implementations
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _rule_rollback_linked(
        cls, patterns: List[Any], files: List[str]
    ) -> Optional[ActionResult]:
        """
        Fire when ROLLBACK_INVOLVEMENT or ESCAPED_DEFECT_PATTERN touches a changed file.
        Chooses between 'rollback-sensitive flow review' and 'integration tests'
        based on detected auth/billing domains.
        """
        triggered: List[str] = []
        for pat in patterns:
            if getattr(pat, "pattern_type", "") not in _ROLLBACK_TYPES:
                continue
            ctx = getattr(pat, "context", {}) or {}
            trigger = ctx.get("trigger_file", "")
            if not trigger:
                continue
            if not files or trigger in files:
                triggered.append(trigger)

        if not triggered:
            return None

        # Determine domain from the triggering files + changed files
        all_paths = triggered + files
        domain = _detect_domain(all_paths)

        if domain == "auth":
            return ActionResult(
                sentence="Review auth flow changes and run rollback-sensitive integration tests before merging.",
                action_type="auth_validation",
                signal_source="ROLLBACK_INVOLVEMENT:auth",
            )
        if domain == "billing":
            return ActionResult(
                sentence="Review billing flow changes and run rollback-sensitive integration tests before merging.",
                action_type="rollback_flow_review",
                signal_source="ROLLBACK_INVOLVEMENT:billing",
            )

        top = _shorten_path(triggered[0])
        return ActionResult(
            sentence=f"Review rollback-sensitive flows in {top} and run integration tests before merging.",
            action_type="rollback_flow_review",
            signal_source="ROLLBACK_INVOLVEMENT",
        )

    @classmethod
    def _rule_cofailure_pair(
        cls, patterns: List[Any], files: List[str]
    ) -> Optional[ActionResult]:
        """
        Fire when a CO_FAILURE_PATTERN names two components that can be
        identified as distinct (auth+billing, etc.).  Produces a named
        integration test recommendation.
        """
        for pat in patterns:
            if getattr(pat, "pattern_type", "") != _COFAIL_TYPE:
                continue
            ctx = getattr(pat, "context", {}) or {}
            trigger_file = ctx.get("trigger_file", "")
            related = ctx.get("failure_test") or (ctx.get("related_tests") or [""])[0]

            if not trigger_file or not related:
                continue

            # Only act if trigger_file is in the changed set (or no changed files given)
            if files and trigger_file not in files:
                continue

            comp1 = _component_label(trigger_file)
            comp2 = _component_label(related)

            # Name the integration area
            pair_paths = [trigger_file, related]
            domain = _detect_domain(pair_paths)

            if domain and comp1 != comp2:
                return ActionResult(
                    sentence=f"Run {comp1}-{comp2} integration tests before merging.",
                    action_type="integration_tests",
                    signal_source=f"CO_FAILURE_PATTERN:{comp1}+{comp2}",
                )
            if comp1 != comp2:
                return ActionResult(
                    sentence=f"Run integration tests covering {comp1} and {comp2} before merging.",
                    action_type="integration_tests",
                    signal_source=f"CO_FAILURE_PATTERN:{comp1}+{comp2}",
                )
            return ActionResult(
                sentence=f"Run integration tests for the {comp1} module before merging.",
                action_type="integration_tests",
                signal_source=f"CO_FAILURE_PATTERN:{comp1}",
            )

        return None

    @classmethod
    def _rule_high_frequency_fragility(
        cls, patterns: List[Any], files: List[str]
    ) -> Optional[ActionResult]:
        """
        Fire when a HIGH-risk FILE_FAILURE_FREQUENCY pattern touches a changed file.
        """
        candidates: List[tuple] = []  # (evidence_count, path)
        for pat in patterns:
            if getattr(pat, "pattern_type", "") != _FREQ_TYPE:
                continue
            if (getattr(pat, "risk_level", "") or "").upper() not in ("HIGH", "CRITICAL"):
                continue
            ctx = getattr(pat, "context", {}) or {}
            trigger = ctx.get("trigger_file", "")
            if not trigger:
                continue
            if not files or trigger in files:
                count = getattr(pat, "evidence_count", 0)
                candidates.append((count, trigger))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_path = candidates[0][1]
        domain = _detect_domain([top_path] + files)
        area = f"{domain} " if domain else ""
        short = _shorten_path(top_path)

        return ActionResult(
            sentence=f"Run {area}integration tests covering {short} before merging.",
            action_type="integration_tests",
            signal_source=f"FILE_FAILURE_FREQUENCY:{short}",
        )

    @classmethod
    def _rule_from_warning_codes(
        cls, codes: set, files: List[str]
    ) -> Optional[ActionResult]:
        """
        Map warning codes to actions, in priority order.

        Priority:
        4. ROLLBACK_LINKED_FRAGILITY  → rollback-sensitive flow review
        5. UNSTABLE_DEPENDENCY_NEIGHBORHOOD → smoke validation
        6. HIGH_FLAKY_INFLUENCE       → manual verification
        """
        if "ROLLBACK_LINKED_FRAGILITY" in codes:
            domain = _detect_domain(files)
            area = f"{domain} " if domain else ""
            return ActionResult(
                sentence=f"Review {area}rollback-sensitive flows and run integration tests before merging.",
                action_type="rollback_flow_review",
                signal_source="WARNING:ROLLBACK_LINKED_FRAGILITY",
            )

        if "UNSTABLE_DEPENDENCY_NEIGHBORHOOD" in codes:
            domain = _detect_domain(files)
            area = f"{domain} dependency " if domain else "dependency "
            return ActionResult(
                sentence=f"Run smoke validation on the {area}neighborhood before merging.",
                action_type="smoke_validation",
                signal_source="WARNING:UNSTABLE_DEPENDENCY_NEIGHBORHOOD",
            )

        if "HIGH_FLAKY_INFLUENCE" in codes:
            return ActionResult(
                sentence="Verify test results manually before merging; flaky test influence may affect reliability.",
                action_type="manual_verification",
                signal_source="WARNING:HIGH_FLAKY_INFLUENCE",
            )

        return None

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _extract_changed_files(cls, run: RecommendationRun) -> List[str]:
        """Pull changed files from input_snapshot if available."""
        snapshot = getattr(run, "input_snapshot", None)
        if snapshot:
            return list(getattr(snapshot, "changed_files", None) or [])
        return []
