"""
RecommendationReasoningEngine
==============================
Generates plain-English explanations for a recommendation run.

Produces:
  - executive_summary: ≤4 bullets answering "Why these tests?"
  - per_test_explanations: one sentence per recommended test

Rules:
  - No AI wording ("AI determined", "model predicts", "confidence score")
  - No fake certainty ("safe to ship", "guaranteed", "100% coverage")
  - No fabricated percentages
  - Every bullet must be grounded in a real signal from the run
  - Max 4 executive bullets, deduplicated, ordered by signal strength
  - Per-test explanations derived from RecommendationReasoningEntry records
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry
from app.models.test_result import TestCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shorten(path: str, max_parts: int = 3) -> str:
    """Return the last N path components for readability."""
    if not path:
        return ""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    return "/".join(parts[-max_parts:]) if len(parts) > max_parts else "/".join(parts)


def _domain_from_path(path: str) -> str:
    """Infer a human-readable domain label from a file path."""
    p = path.lower().replace("\\", "/")
    if any(k in p for k in ("auth", "login", "session", "token", "password", "credential")):
        return "authentication"
    if any(k in p for k in ("billing", "payment", "invoice", "subscription", "charge")):
        return "billing"
    if any(k in p for k in ("security", "permission", "access", "role", "acl", "policy")):
        return "security"
    if any(k in p for k in ("api", "router", "route", "endpoint", "handler", "controller")):
        return "API layer"
    if any(k in p for k in ("model", "schema", "entity", "orm", "migration", "db", "database")):
        return "data model"
    if any(k in p for k in ("test", "spec", "fixture")):
        return "test infrastructure"
    if any(k in p for k in ("util", "helper", "common", "shared", "lib")):
        return "shared utilities"
    if any(k in p for k in ("config", "setting", "env")):
        return "configuration"
    # Fall back to the parent directory name
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if len(parts) >= 2:
        return parts[-2].replace("_", " ").replace("-", " ")
    return parts[0].replace("_", " ").replace("-", " ") if parts else "codebase"


def _clean(text: str) -> str:
    """Strip forbidden phrases and normalise whitespace."""
    forbidden = [
        r"\bAI\b", r"\bmodel\b", r"\bpredicts?\b", r"\bconfidence score\b",
        r"\bsafe to ship\b", r"\bguaranteed\b", r"\b100%\b",
        r"\bneural\b", r"\bLLM\b", r"\bGPT\b",
    ]
    for pat in forbidden:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RecommendationReasoningEngine:
    """
    Derives human-readable explanations from a persisted RecommendationRun.

    Usage:
        engine = RecommendationReasoningEngine(db)
        result = engine.explain(run)
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def explain(self, run: RecommendationRun) -> Dict[str, Any]:
        """
        Return a structured explanation dict:
        {
            "executive_summary": ["bullet 1", "bullet 2", ...],   # ≤4 items
            "per_test_explanations": {
                "TestSuite::test_name": "one sentence reason",
                ...
            },
            "recommendation_mode": "NORMAL",
            "evidence_quality": "MODERATE",
        }
        """
        changed_files = self._changed_files(run)
        reasoning_entries = run.reasoning_entries or []
        tests = run.tests or []

        executive = self._build_executive_summary(run, changed_files, reasoning_entries)
        per_test = self._build_per_test_explanations(tests, reasoning_entries)

        return {
            "executive_summary": executive,
            "per_test_explanations": per_test,
            "recommendation_mode": run.recommendation_mode or "NORMAL",
            "evidence_quality": run.evidence_quality or "UNKNOWN",
        }

    # ------------------------------------------------------------------
    # Executive summary (≤4 bullets)
    # ------------------------------------------------------------------

    def _build_executive_summary(
        self,
        run: RecommendationRun,
        changed_files: List[str],
        entries: List[RecommendationReasoningEntry],
    ) -> List[str]:
        bullets: List[str] = []
        seen: set = set()

        def add(b: str) -> None:
            b = _clean(b.strip())
            if b and b not in seen and len(bullets) < 4:
                seen.add(b)
                bullets.append(b)

        # --- Bullet 1: What changed ---
        if changed_files:
            domains = list(dict.fromkeys(_domain_from_path(f) for f in changed_files))
            if len(changed_files) == 1:
                add(f"PR modifies {_shorten(changed_files[0])}.")
            elif len(domains) == 1:
                add(f"PR modifies {len(changed_files)} files in the {domains[0]} area.")
            else:
                domain_str = ", ".join(domains[:3])
                add(f"PR touches {len(changed_files)} files across {domain_str}.")

        # --- Bullet 2: Domain affected ---
        if changed_files:
            primary_domain = _domain_from_path(changed_files[0])
            if primary_domain not in ("codebase", "shared utilities"):
                add(f"The {primary_domain} domain is affected by this change.")

        # --- Bullet 3: Historical failure signal ---
        fragility_entries = [
            e for e in entries
            if e.reason_type in ("historical_fragility", "scoped_historical_failure")
        ]
        if fragility_entries:
            # Pick the entry with the most evidence
            best = max(
                fragility_entries,
                key=lambda e: (e.reasoning_metadata or {}).get("evidence_count", 0)
                if e.reasoning_metadata else 0,
                default=fragility_entries[0],
            )
            meta = best.reasoning_metadata or {}
            evidence_count = meta.get("evidence_count")
            if evidence_count and int(evidence_count) > 0:
                add(
                    f"Similar changes previously caused {evidence_count} "
                    f"regression failure{'s' if int(evidence_count) != 1 else ''}."
                )
            else:
                add("Similar changes have caused failures in previous runs.")

        # --- Bullet 4: Coverage / fallback signal ---
        mode = run.recommendation_mode or "NORMAL"
        quality = (run.evidence_quality or "UNKNOWN").upper()

        if mode == "FULL_REGRESSION":
            add(
                "Coverage evidence is insufficient — the full test suite is recommended for safety."
            )
        elif mode == "SAFE_FALLBACK":
            add(
                "Coverage confidence is low; conservative test selection is applied."
            )
        elif mode == "WIDENED":
            add(
                "Dependency expansion is active — tests covering related modules are included."
            )
        elif quality == "LOW":
            add(
                "Coverage confidence is low, so a broader set of tests is included."
            )
        elif quality == "MODERATE":
            add(
                "Coverage mapping is partial; tests are selected from direct and adjacent modules."
            )

        # Fallback if nothing was added
        if not bullets:
            add("Tests are selected based on the files changed in this pull request.")

        return bullets

    # ------------------------------------------------------------------
    # Per-test explanations
    # ------------------------------------------------------------------

    def _build_per_test_explanations(
        self,
        tests: List[Any],
        entries: List[RecommendationReasoningEntry],
    ) -> Dict[str, str]:
        """
        Return {stable_identity: one_sentence_reason} for each recommended test.
        Derived from RecommendationReasoningEntry records; falls back to reason_type
        on the RecommendationTest if no entry exists.
        """
        # Build a lookup: stable_identity -> best reasoning entry
        entry_by_identity: Dict[str, RecommendationReasoningEntry] = {}
        for e in entries:
            if e.test_case_id is None:
                continue
            # Resolve stable_identity from test_case_id
            tc = self.db.query(TestCase).filter(TestCase.id == e.test_case_id).first()
            identity = tc.stable_identity if tc else str(e.test_case_id)
            if identity not in entry_by_identity:
                entry_by_identity[identity] = e
            else:
                # Prefer higher-priority entry
                priority_order = {"CRITICAL": 0, "IMPORTANT": 1, "SUPPORTING": 2}
                existing_p = priority_order.get(entry_by_identity[identity].evidence_priority, 3)
                new_p = priority_order.get(e.evidence_priority, 3)
                if new_p < existing_p:
                    entry_by_identity[identity] = e

        result: Dict[str, str] = {}
        for test in tests:
            identity = test.test_case_id  # stable_identity string stored on RecommendationTest
            entry = entry_by_identity.get(identity)

            if entry and entry.human_readable_reason:
                sentence = _clean(entry.human_readable_reason)
            else:
                sentence = _reason_from_type(test.reason_type, test.reason_details or {})

            result[identity] = sentence

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _changed_files(self, run: RecommendationRun) -> List[str]:
        """Recover changed files from the input snapshot or PR relationship."""
        # Try input snapshot first (most reliable)
        if run.input_snapshot and run.input_snapshot.changed_files:
            raw = run.input_snapshot.changed_files
            if isinstance(raw, list):
                # May be list of strings or list of dicts with "file_path"
                files = []
                for item in raw:
                    if isinstance(item, str):
                        files.append(item)
                    elif isinstance(item, dict):
                        fp = item.get("file_path") or item.get("filename")
                        if fp:
                            files.append(fp)
                if files:
                    return files

        # Fall back to PR changed files
        if run.pull_request and run.pull_request.changed_files:
            return [f.file_path for f in run.pull_request.changed_files]

        return []

    @classmethod
    def generate_explanation(cls, signals: Dict[str, Any]) -> List[str]:
        """Produce at most 4 factual bullet points from the active signals dict.
        Order: highest-value signals first.
        """
        _SIGNAL_PRIORITY = [
            "domain_match",
            "escaped_defect_learning",
            "manual_override_history",
            "pattern_memory",
            "coverage_link",
            "knowledge_graph",
            "architectural_impact",
            "indirect_dependency_impact",
            "module_match",
            "token_similarity",
            "historical_failure",
            "module_risk",
            "runtime_cost",
        ]

        _SIGNAL_LABELS = {
            "escaped_defect_learning": "Escaped defect gap: This test previously missed defect coverage in the changed file area.",
            "manual_override_history": "Manual override history: Engineers repeatedly added this test manually for the changed files.",
            "pattern_memory": "Pattern memory match: This test has historically proved useful when similar file change patterns occurred.",
            "coverage_link": "Direct code coverage: Coverage report confirms this test executes lines in the changed file.",
            "knowledge_graph": "Knowledge graph link: Execution traces correlate this test to the modified path.",
            "architectural_impact": "Architectural impact: This test covers services or domains transitively impacted by the changes.",
            "module_match": "Module match: Changed files belong to the same module/folder as this test suite.",
            "token_similarity": "Token similarity: Changed files overlap in name or function with this test case.",
            "historical_failure": "Recent execution failure: This test has failed recently in the last 30 days.",
            "module_risk": "Module risk profile: Changed file lies in a directory path with elevated defect history.",
            "runtime_cost": "Low runtime cost: This test executes quickly and has a low runtime cost.",
        }

        bullets = []
        for name in _SIGNAL_PRIORITY:
            val = signals.get(name)
            if not val:
                continue

            if name == "domain_match":
                domain_name = signals.get("domain_name") or "active"
                label = f"Domain match: Test and changed files both reside in the '{domain_name}' business domain."
                if label not in bullets:
                    bullets.append(label)
                continue

            if name == "indirect_dependency_impact":
                trace_str = signals.get("dependency_impact_trace")
                if trace_str:
                    label = f"Indirect dependency risk: This test covers components with indirect exposure to {trace_str}."
                else:
                    label = "Indirect dependency risk: This test covers components with indirect exposure to modified services/routes."
                if label not in bullets:
                    bullets.append(label)
                continue

            if name == "runtime_cost":
                try:
                    cost_val = int(val)
                except (ValueError, TypeError):
                    continue
                if cost_val < -5:
                    continue

            label = _SIGNAL_LABELS.get(name)
            if label and label not in bullets:
                bullets.append(label)
            if len(bullets) == 4:
                break

        return bullets

    @classmethod
    def format_explanation(cls, signals: Dict[str, Any]) -> str:
        """Build bulleted string from active signals."""
        bullets = cls.generate_explanation(signals)
        if not bullets:
            return "Selected based on pipeline fallback optimization rules."
        return "\n".join(f"- {b}" for b in bullets)



# ---------------------------------------------------------------------------
# Reason-type → sentence fallback
# ---------------------------------------------------------------------------

_REASON_TYPE_TEMPLATES: Dict[str, str] = {
    "direct_file_coverage":
        "This test directly covers a file changed in the pull request.",
    "path_heuristic_fallback":
        "This test matches the changed file by naming convention.",
    "dependency_expansion":
        "This test covers a module that depends on a changed file.",
    "historical_fragility":
        "This test has failed in previous runs when similar files were changed.",
    "scoped_historical_failure":
        "This test failed in a recent run that touched the same area.",
    "full_regression_fallback":
        "Full regression is active; this test is included for safety.",
    "flaky_test_warning":
        "This test has shown instability and is included for monitoring.",
}


def _reason_from_type(reason_type: str, details: Dict[str, Any]) -> str:
    """Generate a fallback sentence from reason_type and details dict."""
    template = _REASON_TYPE_TEMPLATES.get(reason_type)
    if template:
        # Enrich with details where available
        source = details.get("source_file_path") or details.get("referenced_by") or details.get("file")
        if source and "{source}" in template:
            template = template.replace("{source}", _shorten(source))
        return template

    # Generic fallback
    return f"Included based on {reason_type.replace('_', ' ')} signal."
