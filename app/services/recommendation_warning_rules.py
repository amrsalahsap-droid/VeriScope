"""
recommendation_warning_rules.py
────────────────────────────────
Generates operationally useful warnings from a recommendation run.

Design rules
────────────
- Warnings describe observable conditions, not predicted outcomes.
- No alarmist language: "unsafe", "catastrophic", "guaranteed", "outage".
- No statistical fake precision: no percentages, no probabilities.
- Each warning is at most one line (single sentence).
- At most MAX_WARNINGS warnings per run (prevents noise accumulation).
- All warnings are deterministic given the same inputs.
- Warnings are ordered from most to least operationally significant.
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry

logger = logging.getLogger("veriscope.recommendation_warning_rules")

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

MAX_WARNINGS: int = 5
"""Hard ceiling on warnings emitted per run.  Prevents wall-of-text comments."""

_FORBIDDEN: List[str] = [
    "unsafe to merge",
    "high probability of outage",
    "production failure likely",
    "catastrophic",
    "guaranteed",
    "certified safe",
    "approved",
]

# Thresholds for flaky-influence detection
_FLAKY_ENTRY_THRESHOLD: int = 2
"""Minimum number of flaky reasoning entries before a flaky warning fires."""

# Threshold for sparse historical evidence
_MIN_RECOMMENDED_TESTS_FOR_HISTORY: int = 3
"""If fewer tests were recommended, history is considered sparse."""

_MIN_HISTORY_WINDOW_DAYS: int = 14
"""Runs whose history window is shorter than this are flagged as sparse."""


# ─────────────────────────────────────────────────────────────
# Warning dataclass
# ─────────────────────────────────────────────────────────────

class WarningSeverity(str, Enum):
    """Relative priority used to sort and cap warnings, not exposed to users."""
    HIGH   = "HIGH"    # emitted first
    MEDIUM = "MEDIUM"
    LOW    = "LOW"     # emitted last


@dataclass(order=False)
class RecommendationWarning:
    code: str          # machine-readable identifier, e.g. "LOW_COVERAGE_CONFIDENCE"
    message: str       # human-readable, one sentence, non-alarmist
    severity: WarningSeverity = WarningSeverity.MEDIUM

    def __post_init__(self):
        self._validate_message()

    def _validate_message(self):
        msg_lower = self.message.lower()
        for phrase in _FORBIDDEN:
            if phrase in msg_lower:
                logger.error(
                    f"[RecommendationWarningRules] Forbidden phrase '{phrase}' "
                    f"found in warning '{self.code}'. Stripping."
                )
                self.message = re.sub(re.escape(phrase), "[removed]", self.message, flags=re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────

def _shorten_path(path: str) -> str:
    """Return at most the last two path components for concise display."""
    if not path:
        return ""
    parts = path.split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else path


# ─────────────────────────────────────────────────────────────
# Warning rules
# ─────────────────────────────────────────────────────────────

class RecommendationWarningRules:
    """
    Evaluates a RecommendationRun against a fixed set of operational warning
    rules and returns a deterministically ordered, capped list of warnings.

    Usage
    ─────
    snapshot  = run.input_snapshot          # RecommendationInputSnapshot or None
    patterns  = [...]                       # List[FragilityPattern], may be empty

    result = RecommendationWarningRules.evaluate(
        run=run,
        fragility_patterns=patterns,
    )

    # result.warnings  → List[RecommendationWarning]
    # result.codes     → List[str]
    # result.messages  → List[str]   (ready for PR comment insertion)
    """

    @classmethod
    def evaluate(
        cls,
        run: RecommendationRun,
        fragility_patterns: Optional[List[Any]] = None,
    ) -> "WarningResult":
        """
        Evaluate all warning rules against `run` and return a WarningResult.

        Parameters
        ──────────
        run                 RecommendationRun to evaluate.
        fragility_patterns  Active FragilityPattern objects for the repository.
                            Pass an empty list (or None) when unavailable.
        """
        patterns = fragility_patterns or []
        snapshot = getattr(run, "input_snapshot", None)
        reasoning = getattr(run, "reasoning_entries", []) or []

        collected: List[RecommendationWarning] = []

        # Evaluate in declared priority order
        collected += cls._rule_low_coverage_confidence(run)
        collected += cls._rule_unstable_dependency_neighborhood(patterns, snapshot)
        collected += cls._rule_repeated_rollback_fragility(patterns, snapshot)
        collected += cls._rule_high_flaky_influence(reasoning)
        collected += cls._rule_sparse_historical_evidence(run, snapshot)

        # Deduplicate by code (first occurrence wins)
        seen_codes: set = set()
        unique: List[RecommendationWarning] = []
        for w in collected:
            if w.code not in seen_codes:
                unique.append(w)
                seen_codes.add(w.code)

        # Sort: HIGH → MEDIUM → LOW, preserving insertion order within tier
        _order = {WarningSeverity.HIGH: 0, WarningSeverity.MEDIUM: 1, WarningSeverity.LOW: 2}
        unique.sort(key=lambda w: _order[w.severity])

        # Cap at MAX_WARNINGS
        final = unique[:MAX_WARNINGS]

        return WarningResult(warnings=final)

    # ──────────────────────────────────────────────────────────
    # Rule 1: Low coverage confidence
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _rule_low_coverage_confidence(
        cls, run: RecommendationRun
    ) -> List[RecommendationWarning]:
        """Fire when coverage evidence quality is LOW or missing."""
        quality = (run.evidence_quality or "UNKNOWN").upper()

        if quality == "LOW":
            return [RecommendationWarning(
                code="LOW_COVERAGE_CONFIDENCE",
                message="Coverage confidence is limited; some changed files lack mapped coverage data.",
                severity=WarningSeverity.HIGH,
            )]

        if quality in ("MISSING", "UNKNOWN"):
            return [RecommendationWarning(
                code="MISSING_COVERAGE_DATA",
                message="Coverage data is unavailable for this repository. Regression scope was widened accordingly.",
                severity=WarningSeverity.HIGH,
            )]

        if quality == "MODERATE":
            return [RecommendationWarning(
                code="MODERATE_COVERAGE_CONFIDENCE",
                message="Coverage confidence is partial. Dependency-expanded tests supplement direct mappings.",
                severity=WarningSeverity.MEDIUM,
            )]

        return []

    # ──────────────────────────────────────────────────────────
    # Rule 2: Unstable dependency neighborhood
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _rule_unstable_dependency_neighborhood(
        cls,
        patterns: List[Any],
        snapshot: Optional[Any],
    ) -> List[RecommendationWarning]:
        """
        Fire when active DEPENDENCY_PROXIMITY or UNSTABLE_MODULE fragility
        patterns overlap with the changed files in the snapshot.
        """
        changed_files: List[str] = []
        if snapshot:
            changed_files = list(getattr(snapshot, "changed_files", None) or [])

        unstable_dirs: List[str] = []
        for pat in patterns:
            pat_type = getattr(pat, "pattern_type", "")
            pat_status = getattr(pat, "status", "")
            if pat_type in ("DEPENDENCY_PROXIMITY", "UNSTABLE_MODULE") and pat_status == "ACTIVE":
                ctx = getattr(pat, "context", {}) or {}
                trigger = ctx.get("trigger_file") or ctx.get("trigger_dir") or ""
                if not trigger:
                    continue
                # Emit if trigger file is in changed_files, or if no changed_files
                # were provided (conservative fallback)
                if not changed_files or any(
                    trigger.startswith(cf.rsplit("/", 1)[0]) or cf.startswith(trigger)
                    for cf in changed_files
                ):
                    label = _shorten_path(trigger)
                    if label and label not in unstable_dirs:
                        unstable_dirs.append(label)

        if unstable_dirs:
            # Limit to 2 paths for conciseness
            paths_str = " and ".join(unstable_dirs[:2])
            return [RecommendationWarning(
                code="UNSTABLE_DEPENDENCY_NEIGHBORHOOD",
                message=(
                    f"Dependency neighborhood instability detected in {paths_str}. "
                    f"Expanded test scope applied."
                ),
                severity=WarningSeverity.HIGH,
            )]

        return []

    # ──────────────────────────────────────────────────────────
    # Rule 3: Repeated rollback-linked fragility
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _rule_repeated_rollback_fragility(
        cls,
        patterns: List[Any],
        snapshot: Optional[Any],
    ) -> List[RecommendationWarning]:
        """
        Fire when active ESCAPED_DEFECT_PATTERN or ROLLBACK_INVOLVEMENT
        patterns touch any changed file in the snapshot.
        """
        changed_files: List[str] = []
        if snapshot:
            changed_files = list(getattr(snapshot, "changed_files", None) or [])

        rollback_paths: List[tuple] = []  # (evidence_count, display_path)
        for pat in patterns:
            pat_type = getattr(pat, "pattern_type", "")
            pat_status = getattr(pat, "status", "")
            if pat_type in ("ESCAPED_DEFECT_PATTERN", "ROLLBACK_INVOLVEMENT") and pat_status == "ACTIVE":
                ctx = getattr(pat, "context", {}) or {}
                trigger = ctx.get("trigger_file", "")
                if not trigger:
                    continue
                if not changed_files or trigger in changed_files:
                    count = getattr(pat, "evidence_count", 1)
                    rollback_paths.append((count, _shorten_path(trigger)))

        if rollback_paths:
            rollback_paths.sort(key=lambda x: x[0], reverse=True)
            top_path = rollback_paths[0][1]
            return [RecommendationWarning(
                code="ROLLBACK_LINKED_FRAGILITY",
                message=(
                    f"Historical fragility detected in {top_path} with prior rollback-linked regressions. "
                    f"Integration tests were prioritised."
                ),
                severity=WarningSeverity.HIGH,
            )]

        return []

    # ──────────────────────────────────────────────────────────
    # Rule 4: High flaky-test influence
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _rule_high_flaky_influence(
        cls, reasoning: List[RecommendationReasoningEntry]
    ) -> List[RecommendationWarning]:
        """
        Fire when several reasoning entries are driven by flaky-test profiles,
        indicating the recommendation was materially shaped by flakiness data.
        """
        flaky_count = sum(
            1 for entry in reasoning
            if getattr(entry, "reason_type", "") == "flaky_adjustments"
            or "flaky" in (getattr(entry, "human_readable_reason", "") or "").lower()
        )

        if flaky_count >= _FLAKY_ENTRY_THRESHOLD:
            return [RecommendationWarning(
                code="HIGH_FLAKY_INFLUENCE",
                message=(
                    f"Flaky test profiles influenced the priority ordering of {flaky_count} "
                    f"recommended tests. Results may vary across consecutive runs."
                ),
                severity=WarningSeverity.MEDIUM,
            )]

        return []

    # ──────────────────────────────────────────────────────────
    # Rule 5: Sparse historical evidence
    # ──────────────────────────────────────────────────────────

    @classmethod
    def _rule_sparse_historical_evidence(
        cls,
        run: RecommendationRun,
        snapshot: Optional[Any],
    ) -> List[RecommendationWarning]:
        """
        Fire when:
        - The test history window is shorter than _MIN_HISTORY_WINDOW_DAYS, OR
        - Very few tests were recommended (below _MIN_RECOMMENDED_TESTS_FOR_HISTORY)
          AND the recommendation_mode is SAFE_FALLBACK or FULL_REGRESSION
          (indicating confidence was already degraded).

        Does NOT fire if the run has HIGH coverage confidence and NORMAL mode —
        that combination already implies sufficient evidence.
        """
        quality = (run.evidence_quality or "UNKNOWN").upper()
        mode = (run.recommendation_mode or "NORMAL").upper()

        # Skip: already have strong evidence
        if quality == "HIGH" and mode == "NORMAL":
            return []

        # Check history window length
        window_start = getattr(run, "test_history_window_start", None)
        window_end   = getattr(run, "test_history_window_end", None)

        if window_start and window_end:
            window_days = (window_end - window_start).days
            if window_days < _MIN_HISTORY_WINDOW_DAYS:
                return [RecommendationWarning(
                    code="SPARSE_HISTORICAL_EVIDENCE",
                    message=(
                        f"Test history window covers only {window_days} day(s). "
                        f"Regression prioritisation has limited historical signal."
                    ),
                    severity=WarningSeverity.MEDIUM,
                )]

        # Check for coverage of recently added files (no history at all)
        changed_files: List[str] = []
        if snapshot:
            changed_files = list(getattr(snapshot, "changed_files", None) or [])
        historical_failures_used: List[Any] = []
        if snapshot:
            historical_failures_used = list(
                getattr(snapshot, "historical_failures_used", None) or []
            )

        if changed_files and not historical_failures_used:
            return [RecommendationWarning(
                code="NO_HISTORICAL_FAILURE_SIGNAL",
                message=(
                    "Coverage confidence is limited for recently added or infrequently tested files. "
                    "No historical failure signal was available."
                ),
                severity=WarningSeverity.LOW,
            )]

        return []


# ─────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────

@dataclass
class WarningResult:
    warnings: List[RecommendationWarning] = field(default_factory=list)

    @property
    def codes(self) -> List[str]:
        return [w.code for w in self.warnings]

    @property
    def messages(self) -> List[str]:
        return [w.message for w in self.warnings]

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "warning_count": len(self.warnings),
            "warnings": [
                {"code": w.code, "message": w.message, "severity": w.severity.value}
                for w in self.warnings
            ],
        }
