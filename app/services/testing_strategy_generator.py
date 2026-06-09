"""
TestingStrategyGenerator
========================
Recommends testing TYPES — not test cases — before the recommendation
engine selects individual tests.  Sits between ImpactProfile /
RiskAssessment and the test-case ranker.

Design principles
-----------------
- Every recommended type must carry an evidence-backed reason.
- Priority (HIGH / MEDIUM / LOW) is derived purely from signal weights,
  not editorial judgment.
- Deterministic: same inputs always produce the same strategy.
- No AI calls, no fake confidence scores, no alarmist language.

Priority Derivation
-------------------
Each testing type accumulates a priority score from two sources:

  1. change_types present in ImpactProfile — mapped to type triggers
  2. risk_categories present in ImpactProfile — mapped to type triggers
  3. risk_level from RiskAssessment — applies a global multiplier to
     REGRESSION, always ensuring baseline coverage for high-risk changes

Score thresholds:
    score >= 6  → HIGH
    score >= 3  → MEDIUM
    score >= 1  → LOW
    score == 0  → omitted (not recommended)

Testing type catalogue (from PRImpactAnalyzer):
    UNIT, API, INTEGRATION, E2E, REGRESSION, SECURITY,
    DATABASE, SMOKE, PERFORMANCE, UI
"""

from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Testing type metadata
# ---------------------------------------------------------------------------

# Human-readable label shown in the output
_TYPE_LABELS: Dict[str, str] = {
    "UNIT": "Unit",
    "API": "API",
    "INTEGRATION": "Integration",
    "E2E": "End-to-End",
    "REGRESSION": "Regression",
    "SECURITY": "Security",
    "DATABASE": "Database",
    "SMOKE": "Smoke",
    "PERFORMANCE": "Performance",
    "UI": "UI",
}

# ---------------------------------------------------------------------------
# Signal → testing type trigger table
# Entries: (signal_source, signal_value, testing_type, score_contribution, reason)
# ---------------------------------------------------------------------------
#
# score_contribution is added to the type's accumulated score each time
# a matching signal fires.  A type only appears in the output if its
# total score >= 1.
# ---------------------------------------------------------------------------

_TRIGGERS: List[Tuple[str, str, str, int, str]] = [
    # ---- AUTH_CHANGE -------------------------------------------------------
    ("change_type", "AUTH_CHANGE", "SECURITY",     6, "Authentication logic was modified"),
    ("change_type", "AUTH_CHANGE", "INTEGRATION",  3, "Auth changes cross service boundaries"),
    ("change_type", "AUTH_CHANGE", "REGRESSION",   3, "Auth regressions break user flows silently"),
    ("change_type", "AUTH_CHANGE", "SMOKE",        2, "Core login path must be verified post-change"),

    # ---- API_CHANGE --------------------------------------------------------
    ("change_type", "API_CHANGE",  "API",          6, "API surface was modified"),
    ("change_type", "API_CHANGE",  "INTEGRATION",  3, "API changes affect downstream consumers"),
    ("change_type", "API_CHANGE",  "REGRESSION",   2, "API contract changes break existing callers"),

    # ---- DATABASE_CHANGE ---------------------------------------------------
    ("change_type", "DATABASE_CHANGE", "DATABASE", 6, "Database schema or model was changed"),
    ("change_type", "DATABASE_CHANGE", "INTEGRATION", 3, "Schema changes impact service integration"),
    ("change_type", "DATABASE_CHANGE", "REGRESSION",  2, "Data model changes carry regression risk"),

    # ---- DEPENDENCY_CHANGE -------------------------------------------------
    ("change_type", "DEPENDENCY_CHANGE", "INTEGRATION", 4, "Updated dependency may change integration behaviour"),
    ("change_type", "DEPENDENCY_CHANGE", "REGRESSION",  3, "Dependency updates carry regression risk"),
    ("change_type", "DEPENDENCY_CHANGE", "UNIT",         2, "Unit tests catch dependency interface breaks"),

    # ---- VALIDATION_CHANGE -------------------------------------------------
    ("change_type", "VALIDATION_CHANGE", "UNIT",        4, "Validation rules are unit-testable in isolation"),
    ("change_type", "VALIDATION_CHANGE", "INTEGRATION", 2, "Validation interacts with upstream input paths"),
    ("change_type", "VALIDATION_CHANGE", "REGRESSION",  1, "Validation changes can silently loosen constraints"),

    # ---- CONFIG_CHANGE -----------------------------------------------------
    ("change_type", "CONFIG_CHANGE", "SMOKE",       4, "Configuration changes must not break startup"),
    ("change_type", "CONFIG_CHANGE", "INTEGRATION", 2, "Config affects service-to-service behaviour"),

    # ---- WORKFLOW_CHANGE ---------------------------------------------------
    ("change_type", "WORKFLOW_CHANGE", "SMOKE",       3, "Pipeline configuration changes must not break CI"),
    ("change_type", "WORKFLOW_CHANGE", "REGRESSION",  2, "Workflow changes can silently skip test stages"),

    # ---- UI_CHANGE ---------------------------------------------------------
    ("change_type", "UI_CHANGE", "UI",          6, "Frontend component was modified"),
    ("change_type", "UI_CHANGE", "E2E",         3, "UI changes must be verified in a real browser flow"),
    ("change_type", "UI_CHANGE", "REGRESSION",  2, "UI changes frequently cause visual regression"),

    # ---- TEST_CHANGE -------------------------------------------------------
    ("change_type", "TEST_CHANGE", "REGRESSION", 1, "Test suite modifications must not degrade coverage"),

    # ---- risk_category: AUTH -----------------------------------------------
    ("risk_category", "AUTH",        "SECURITY",     6, "AUTH risk area requires security-layer verification"),
    ("risk_category", "AUTH",        "SMOKE",        3, "Auth failure blocks all users — smoke gate required"),
    ("risk_category", "AUTH",        "REGRESSION",   3, "Auth regressions are high-severity user-facing defects"),

    # ---- risk_category: SECURITY -------------------------------------------
    ("risk_category", "SECURITY",    "SECURITY",     6, "SECURITY risk area mandates security testing"),
    ("risk_category", "SECURITY",    "REGRESSION",   2, "Security changes carry silent regression risk"),

    # ---- risk_category: PAYMENTS -------------------------------------------
    ("risk_category", "PAYMENTS",    "E2E",          6, "Payment flows require end-to-end transaction testing"),
    ("risk_category", "PAYMENTS",    "SMOKE",        4, "Payment critical path must pass smoke checks"),
    ("risk_category", "PAYMENTS",    "INTEGRATION",  3, "Billing systems integrate with multiple services"),
    ("risk_category", "PAYMENTS",    "REGRESSION",   3, "Payment regressions have direct financial impact"),

    # ---- risk_category: DATA_INTEGRITY -------------------------------------
    ("risk_category", "DATA_INTEGRITY", "DATABASE",     6, "Data integrity risk requires database-layer testing"),
    ("risk_category", "DATA_INTEGRITY", "INTEGRATION",  3, "Data integrity spans service and persistence layers"),
    ("risk_category", "DATA_INTEGRITY", "REGRESSION",   2, "Data corruption regressions are hard to detect"),

    # ---- risk_category: PERMISSIONS ----------------------------------------
    ("risk_category", "PERMISSIONS", "SECURITY",     5, "Permission logic changes must be security-tested"),
    ("risk_category", "PERMISSIONS", "INTEGRATION",  3, "Permissions are enforced across service boundaries"),
    ("risk_category", "PERMISSIONS", "REGRESSION",   2, "Permission regressions grant or deny access silently"),

    # ---- risk_category: USER_REGISTRATION ----------------------------------
    ("risk_category", "USER_REGISTRATION", "INTEGRATION", 4, "Registration flows cross auth, email, and DB layers"),
    ("risk_category", "USER_REGISTRATION", "E2E",          3, "Registration is a user-critical flow requiring E2E coverage"),
    ("risk_category", "USER_REGISTRATION", "REGRESSION",   2, "Registration regressions prevent new user onboarding"),

    # ---- risk_category: NOTIFICATIONS --------------------------------------
    ("risk_category", "NOTIFICATIONS", "INTEGRATION", 3, "Notification delivery spans multiple service calls"),
    ("risk_category", "NOTIFICATIONS", "REGRESSION",  1, "Notification regressions silently fail user communication"),

    # ---- risk_category: WORKFLOW -------------------------------------------
    ("risk_category", "WORKFLOW", "SMOKE",       3, "Workflow changes must not break the CI pipeline"),
    ("risk_category", "WORKFLOW", "REGRESSION",  1, "Workflow regressions silently skip verification stages"),
]

# Risk-level global boosts applied to REGRESSION (always recommended as baseline)
_RISK_LEVEL_REGRESSION_BOOST: Dict[str, int] = {
    "LOW":      1,
    "MODERATE": 2,
    "HIGH":     4,
    "CRITICAL": 6,
}

# Baseline UNIT boost — always recommend unit tests when any code changed
_BASELINE_UNIT_BOOST = 2

# Score thresholds
_HIGH_THRESHOLD   = 6
_MEDIUM_THRESHOLD = 3
_LOW_THRESHOLD    = 1


def _priority_from_score(score: int) -> str:
    if score >= _HIGH_THRESHOLD:
        return "HIGH"
    if score >= _MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


class TestingStrategyGenerator:
    """
    Generates a TestingStrategy from an ImpactProfile and a RiskAssessment.

    The strategy is a priority-ordered list of testing types, each annotated
    with a concise factual reason.  It deliberately does NOT name specific
    test cases — that is the job of the recommendation engine downstream.

    Usage
    -----
    ::

        impact_profile = PRImpactAnalyzer.analyze_pr_impact(...)
        risk = RiskIntelligenceEngine.assess_without_persist(impact_profile)
        strategy = TestingStrategyGenerator.generate(impact_profile, risk)

        for entry in strategy["types"]:
            print(entry["priority"], entry["type"], "—", entry["reason"])
    """

    @classmethod
    def generate(
        cls,
        impact_profile: Dict[str, Any],
        risk_assessment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a TestingStrategy.

        Parameters
        ----------
        impact_profile:
            Output of PRImpactAnalyzer.analyze_pr_impact() or the
            impact_profile column of a RiskAssessment ORM instance.
        risk_assessment:
            Plain dict with keys: risk_level, risk_areas, risk_reasons.
            (Use RiskIntelligenceEngine.assess_without_persist() or pass
            the ORM instance fields directly.)

        Returns
        -------
        Dict with keys:
            types        — ordered list of TestingTypeEntry dicts
            summary      — one-sentence plain-text summary
            risk_level   — echoed from the RiskAssessment for convenience
        """
        change_types   = set(impact_profile.get("change_types", []))
        risk_categories = set(impact_profile.get("risk_categories", []))
        risk_level     = (risk_assessment.get("risk_level") or "LOW").upper()

        # Accumulate scores and reasons per testing type
        scores:  Dict[str, int]        = {}
        reasons: Dict[str, List[str]]  = {}

        for (src, signal, t_type, score, reason) in _TRIGGERS:
            if src == "change_type"   and signal in change_types:
                scores[t_type]  = scores.get(t_type, 0) + score
                reasons.setdefault(t_type, [])
                if reason not in reasons[t_type]:
                    reasons[t_type].append(reason)

            elif src == "risk_category" and signal in risk_categories:
                scores[t_type]  = scores.get(t_type, 0) + score
                reasons.setdefault(t_type, [])
                if reason not in reasons[t_type]:
                    reasons[t_type].append(reason)

        # Apply global regression boost from risk level
        reg_boost = _RISK_LEVEL_REGRESSION_BOOST.get(risk_level, 1)
        scores["REGRESSION"] = scores.get("REGRESSION", 0) + reg_boost
        reasons.setdefault("REGRESSION", [])
        if f"Risk level is {risk_level.title()} — regression baseline required" not in reasons["REGRESSION"]:
            reasons["REGRESSION"].insert(
                0, f"Risk level is {risk_level.title()} — regression baseline required"
            )

        # Apply baseline unit boost if any actual code changed
        if change_types - {"TEST_CHANGE"}:
            scores["UNIT"] = scores.get("UNIT", 0) + _BASELINE_UNIT_BOOST
            reasons.setdefault("UNIT", [])
            if "Changed files require unit-level verification" not in reasons["UNIT"]:
                reasons["UNIT"].insert(0, "Changed files require unit-level verification")

        # Build result entries — omit types with score == 0
        entries: List[Dict[str, Any]] = []
        for t_type, score in scores.items():
            if score < _LOW_THRESHOLD:
                continue
            priority = _priority_from_score(score)
            # Best single reason: first reason (already ordered by insertion = priority order)
            primary_reason = reasons[t_type][0] if reasons[t_type] else ""
            entries.append({
                "type":     t_type,
                "label":    _TYPE_LABELS.get(t_type, t_type.title()),
                "priority": priority,
                "score":    score,
                "reason":   primary_reason,
                "all_reasons": reasons[t_type],
            })

        # Sort: HIGH first, then MEDIUM, then LOW; within each tier by score desc then type name
        _priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        entries.sort(key=lambda e: (_priority_order[e["priority"]], -e["score"], e["type"]))

        # Build summary sentence
        high_types  = [e["label"] for e in entries if e["priority"] == "HIGH"]
        total_types = len(entries)
        if high_types:
            summary = (
                f"{total_types} testing type(s) recommended. "
                f"High-priority: {', '.join(high_types)}."
            )
        elif entries:
            summary = f"{total_types} testing type(s) recommended at MEDIUM or LOW priority."
        else:
            summary = "No specific testing types triggered. Standard regression is advised."

        return {
            "types":      entries,
            "summary":    summary,
            "risk_level": risk_level,
        }

    @classmethod
    def format_for_display(cls, strategy: Dict[str, Any]) -> str:
        """
        Render a TestingStrategy as a human-readable text block.

        Example output
        --------------
        Recommended Testing Types

        HIGH PRIORITY
        - Security — Authentication logic was modified
        - Integration — Auth changes cross service boundaries
        - Regression — Risk level is High — regression baseline required

        MEDIUM PRIORITY
        - API — API surface was modified

        LOW PRIORITY
        - Performance — Changed files require unit-level verification
        """
        lines = ["Recommended Testing Types", ""]

        current_priority = None
        for entry in strategy["types"]:
            p = entry["priority"]
            if p != current_priority:
                if current_priority is not None:
                    lines.append("")
                lines.append(f"{p} PRIORITY")
                current_priority = p
            lines.append(f"- {entry['label']} — {entry['reason']}")

        lines.append("")
        lines.append(strategy["summary"])
        return "\n".join(lines)
