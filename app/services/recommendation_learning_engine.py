"""
app/services/recommendation_learning_engine.py
================================================

RecommendationLearningEngine
=============================
Orchestrates all learning signals from a finalised ``RecommendationOutcome``
into incremental ``PatternLearning`` records.

Design principles
-----------------
* **Engineer behavior outweighs heuristics.**
  Signal strength hierarchy (highest → lowest):
    1. ESCAPED_DEFECT  — production escape, base strength 0.80
    2. MANUAL_OVERRIDE — engineer explicitly added a test, base strength 0.60
    3. FOLLOWED        — recommendation was accepted and executed, base 0.40
    4. HEURISTIC       — path/naming match only, base 0.20

* **Learning is incremental.**
  Each call to ``learn()`` upserts ``PatternLearning`` rows — it never
  replaces or deletes existing records.  ``strength`` and ``confidence``
  grow monotonically; ``usage_count`` increments by 1 per observation.

* **No destructive updates.**
  Existing ``PatternLearning`` rows are only updated via additive increments.
  Historical ``RecommendationOutcome``, ``RecommendationRun``, and reasoning
  entries are never touched.

* **Non-blocking.**
  ``learn()`` always returns a ``LearningEngineResult``; it never propagates
  exceptions to the caller.  All failures land in ``result.errors``.

Pattern key format
------------------
Pattern keys are normalised strings of the form ``"<signal>:<value>"``:

  ``"file_change:app/services/auth.py"``   — a specific file was changed
  ``"domain:authentication"``              — a domain label was inferred
  ``"defect_escape:app/services/auth.py"`` — a defect escaped via this file
  ``"manual_add:app/services/auth.py"``    — engineer added a test for this file

This keeps patterns human-readable and queryable without a separate taxonomy.

Strength formula
----------------
  new_strength = min(base + (usage_count × step), 1.0)

  Source         base   step
  ESCAPED_DEFECT 0.80   0.05
  MANUAL_OVERRIDE 0.60  0.10
  FOLLOWED        0.40  0.05
  HEURISTIC       0.20  0.02

Confidence formula
------------------
  confidence = min(usage_count / CONFIDENCE_SATURATION, 1.0)
  CONFIDENCE_SATURATION = 10  (10 observations → full confidence)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern_learning import PatternLearning
from app.models.pull_request import PullRequestChangedFile
from app.models.recommendation import RecommendationOutcome

logger = logging.getLogger("veriscope.learning_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Source signal hierarchy
_SOURCES = {
    "ESCAPED_DEFECT":  {"base": 0.80, "step": 0.05},
    "MANUAL_OVERRIDE": {"base": 0.60, "step": 0.10},
    "FOLLOWED":        {"base": 0.40, "step": 0.05},
    "HEURISTIC":       {"base": 0.20, "step": 0.02},
}

# Number of observations at which confidence saturates at 1.0
_CONFIDENCE_SATURATION = 10

# File extensions to skip when building file-change patterns
_SKIP_EXTENSIONS = frozenset({
    ".md", ".rst", ".txt", ".yml", ".yaml", ".json", ".toml",
    ".lock", ".cfg", ".ini", ".png", ".jpg", ".svg", ".ico",
})

# Domain inference keywords → label
_DOMAIN_KEYWORDS: List[Tuple[str, str]] = [
    (("auth", "login", "session", "token", "password", "credential"), "authentication"),
    (("billing", "payment", "invoice", "subscription", "charge"),     "billing"),
    (("security", "permission", "access", "role", "acl", "policy"),   "security"),
    (("api", "router", "route", "endpoint", "handler", "controller"), "api"),
    (("model", "schema", "entity", "orm", "migration", "db"),         "data_model"),
    (("util", "helper", "common", "shared", "lib"),                   "utilities"),
    (("config", "setting", "env"),                                     "configuration"),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class LearningEngineResult:
    """Structured summary of a single learning pass.

    Attributes
    ----------
    patterns_upserted:
        Total ``PatternLearning`` rows created or updated.
    signals_processed:
        Number of (pattern_key, test_identifier, source) triples processed.
    errors:
        Non-fatal error messages.
    """
    patterns_upserted: int = 0
    signals_processed: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RecommendationLearningEngine:
    """Orchestrates incremental learning from a finalised RecommendationOutcome.

    Usage::

        engine = RecommendationLearningEngine(db)
        result = engine.learn(outcome, workspace_id=workspace_id)
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def learn(
        self,
        outcome: RecommendationOutcome,
        *,
        workspace_id: UUID,
        observed_at: Optional[datetime] = None,
    ) -> LearningEngineResult:
        """Learn from all signals on a finalised outcome.

        Parameters
        ----------
        outcome:
            The ``RecommendationOutcome`` to process.  Should be committed
            so that all relationships are accessible.
        workspace_id:
            Workspace that owns the repository.
        observed_at:
            Timestamp to record.  Defaults to now.

        Returns
        -------
        LearningEngineResult
            Always returns; never raises.
        """
        if outcome.pull_request_id is None:
            return LearningEngineResult()

        result = LearningEngineResult()
        now = observed_at or datetime.utcnow()

        try:
            signals = self._collect_signals(outcome)
        except Exception as exc:
            msg = f"RecommendationLearningEngine: failed to collect signals for outcome {outcome.id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            result.signals_processed = 0
            return result

        if not signals:
            logger.debug(
                "RecommendationLearningEngine: no signals for outcome %s — no-op.",
                outcome.id,
            )
            return result

        for (pattern_key, test_identifier, source) in signals:
            result.signals_processed += 1
            try:
                upserted = self._upsert(
                    repository_id=outcome.repository_id,
                    pattern_key=pattern_key,
                    test_identifier=test_identifier,
                    source=source,
                    outcome_id=outcome.id,
                    now=now,
                    result=result,
                )
                if upserted:
                    result.patterns_upserted += 1
            except Exception as exc:
                msg = (
                    f"RecommendationLearningEngine: upsert failed for "
                    f"pattern={pattern_key!r} test={test_identifier!r} "
                    f"source={source!r} outcome={outcome.id}: {exc}"
                )
                logger.warning(msg)
                result.errors.append(msg)

        try:
            self.db.commit()
        except Exception as exc:
            msg = f"RecommendationLearningEngine: commit failed for outcome {outcome.id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            self.db.rollback()

        logger.info(
            "RecommendationLearningEngine: outcome=%s signals=%d upserted=%d errors=%d",
            outcome.id,
            result.signals_processed,
            result.patterns_upserted,
            len(result.errors),
        )
        return result

    # ------------------------------------------------------------------
    # Signal collection
    # ------------------------------------------------------------------

    def _collect_signals(
        self,
        outcome: RecommendationOutcome,
    ) -> List[Tuple[str, str, str]]:
        """
        Collect (pattern_key, test_identifier, source) triples from the outcome.

        Signal priority order (highest first):
          1. ESCAPED_DEFECT  — missed tests on defect/rollback outcomes
          2. MANUAL_OVERRIDE — tests the engineer explicitly added
          3. FOLLOWED        — recommended tests that were actually executed
          4. HEURISTIC       — recommended tests that were NOT executed
             (weaker signal — engineer chose not to run them)
        """
        signals: List[Tuple[str, str, str]] = []
        seen: Set[Tuple[str, str, str]] = set()

        def add(pattern_key: str, test_id: str, source: str) -> None:
            key = (pattern_key, test_id, source)
            if key not in seen:
                seen.add(key)
                signals.append(key)

        # Resolve changed files for this PR
        changed_files = self._changed_files(outcome)
        source_files = [
            f for f in changed_files
            if not any(f.endswith(ext) for ext in _SKIP_EXTENSIONS)
        ]

        # Infer domain labels from changed files
        domains = list(dict.fromkeys(self._infer_domain(f) for f in source_files))

        # Read test sets
        recommended = list(outcome.recommended_tests or [])
        executed    = list(outcome.executed_tests or [])
        added       = list(outcome.manually_added_tests or [])
        removed     = list(outcome.manually_removed_tests or [])

        executed_set    = set(executed)
        recommended_set = set(recommended)
        added_set       = set(added)

        is_escape   = bool(outcome.escaped_defect_detected)
        is_rollback = bool(outcome.rollback_occurred)

        # ── Signal 1: ESCAPED_DEFECT ──────────────────────────────────────
        # Missed tests (recommended but not executed) on defect/rollback outcomes.
        # These are the highest-value signal: the gap that let the defect through.
        if is_escape or is_rollback:
            missed = recommended_set - executed_set
            for test_id in sorted(missed):
                for file_path in source_files:
                    add(f"defect_escape:{file_path}", test_id, "ESCAPED_DEFECT")
                for domain in domains:
                    add(f"domain:{domain}", test_id, "ESCAPED_DEFECT")

        # ── Signal 2: MANUAL_OVERRIDE ─────────────────────────────────────
        # Tests the engineer explicitly added beyond the recommendation.
        # Strong signal: engineer knows something the heuristics don't.
        for test_id in sorted(added_set):
            for file_path in source_files:
                add(f"manual_add:{file_path}", test_id, "MANUAL_OVERRIDE")
                add(f"file_change:{file_path}", test_id, "MANUAL_OVERRIDE")
            for domain in domains:
                add(f"domain:{domain}", test_id, "MANUAL_OVERRIDE")

        # ── Signal 3: FOLLOWED ────────────────────────────────────────────
        # Recommended tests that were actually executed (recommendation accepted).
        # Moderate signal: confirms the recommendation was useful.
        followed_tests = recommended_set & executed_set
        for test_id in sorted(followed_tests):
            for file_path in source_files:
                add(f"file_change:{file_path}", test_id, "FOLLOWED")
            for domain in domains:
                add(f"domain:{domain}", test_id, "FOLLOWED")

        # ── Signal 4: HEURISTIC ───────────────────────────────────────────
        # Recommended tests that were NOT executed (engineer chose to skip).
        # Weak signal: the recommendation existed but wasn't followed.
        # Only emit if the outcome was not a full ignore (some tests were run).
        if executed_set and recommended_set:
            not_executed = recommended_set - executed_set - added_set
            for test_id in sorted(not_executed):
                for file_path in source_files:
                    add(f"file_change:{file_path}", test_id, "HEURISTIC")

        return signals

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def _upsert(
        self,
        *,
        repository_id: UUID,
        pattern_key: str,
        test_identifier: str,
        source: str,
        outcome_id: UUID,
        now: datetime,
        result: "LearningEngineResult",
    ) -> bool:
        """Create or incrementally update a PatternLearning row.

        Returns True if a row was created or updated.
        """
        if source not in _SOURCES:
            msg = (
                f"RecommendationLearningEngine: unknown source {source!r} for "
                f"pattern={pattern_key!r} test={test_identifier!r} — skipping"
            )
            logger.warning(msg)
            result.errors.append(msg)
            return False

        existing = (
            self.db.query(PatternLearning)
            .filter(
                PatternLearning.repository_id == repository_id,
                PatternLearning.pattern_key == pattern_key,
                PatternLearning.test_identifier == test_identifier,
                PatternLearning.source == source,
            )
            .first()
        )

        cfg = _SOURCES.get(source, _SOURCES["HEURISTIC"])

        if existing:
            # Incremental update — never decrease strength or confidence
            new_usage = existing.usage_count + 1
            new_strength = min(cfg["base"] + (new_usage - 1) * cfg["step"], 1.0)
            new_confidence = min(new_usage / _CONFIDENCE_SATURATION, 1.0)

            existing.strength       = max(existing.strength, new_strength)
            existing.confidence     = max(existing.confidence, new_confidence)
            existing.usage_count    = new_usage
            existing.last_outcome_id = outcome_id
            existing.last_seen_at   = now
            existing.updated_at     = now
            self.db.add(existing)
        else:
            # First observation
            initial_strength    = cfg["base"]
            initial_confidence  = min(1 / _CONFIDENCE_SATURATION, 1.0)

            row = PatternLearning(
                repository_id    = repository_id,
                pattern_key      = pattern_key,
                test_identifier  = test_identifier,
                source           = source,
                strength         = initial_strength,
                confidence       = initial_confidence,
                usage_count      = 1,
                last_outcome_id  = outcome_id,
                context          = {},
                first_seen_at    = now,
                last_seen_at     = now,
                created_at       = now,
                updated_at       = now,
            )
            self.db.add(row)

        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _changed_files(self, outcome: RecommendationOutcome) -> List[str]:
        """Resolve changed files from the PR linked to this outcome."""
        if not outcome.pull_request_id:
            return []
        try:
            rows = (
                self.db.query(PullRequestChangedFile)
                .filter(
                    PullRequestChangedFile.pull_request_id == outcome.pull_request_id,
                    PullRequestChangedFile.status != "removed",
                )
                .all()
            )
            return [r.file_path.replace("\\", "/") for r in rows]
        except Exception as exc:
            logger.warning(
                "RecommendationLearningEngine: failed to load changed files "
                "for PR %s: %s",
                outcome.pull_request_id,
                exc,
            )
            return []

    @staticmethod
    def _infer_domain(file_path: str) -> str:
        """Infer a domain label from a file path."""
        p = file_path.lower().replace("\\", "/")
        for keywords, label in _DOMAIN_KEYWORDS:
            if any(k in p for k in keywords):
                return label
        # Fall back to parent directory name
        parts = [x for x in p.split("/") if x]
        if len(parts) >= 2:
            return parts[-2].replace("_", " ").replace("-", " ")
        return "general"

    # ------------------------------------------------------------------
    # Query helpers (for use by recommendation engine)
    # ------------------------------------------------------------------

    def get_learned_tests(
        self,
        repository_id: UUID,
        pattern_keys: List[str],
        min_strength: float = 0.40,
        min_confidence: float = 0.10,
        sources: Optional[List[str]] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """
        Return learned (test_identifier, strength, confidence, source) tuples
        for the given pattern keys, ordered by strength descending.

        Parameters
        ----------
        repository_id:
            Repository to query.
        pattern_keys:
            List of pattern keys to match (e.g. ``["file_change:app/auth.py"]``).
        min_strength:
            Minimum strength threshold (default 0.40 = FOLLOWED base).
        min_confidence:
            Minimum confidence threshold.
        sources:
            Optional filter by source list.  None = all sources.
        limit:
            Maximum rows to return.

        Returns
        -------
        List of dicts with keys: test_identifier, pattern_key, source,
        strength, confidence, usage_count.
        """
        if not pattern_keys:
            return []

        query = (
            self.db.query(PatternLearning)
            .filter(
                PatternLearning.repository_id == repository_id,
                PatternLearning.pattern_key.in_(pattern_keys),
                PatternLearning.strength >= min_strength,
                PatternLearning.confidence >= min_confidence,
            )
        )
        if sources:
            query = query.filter(PatternLearning.source.in_(sources))

        rows = (
            query
            .order_by(PatternLearning.strength.desc(), PatternLearning.usage_count.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "test_identifier": r.test_identifier,
                "pattern_key":     r.pattern_key,
                "source":          r.source,
                "strength":        round(r.strength, 4),
                "confidence":      round(r.confidence, 4),
                "usage_count":     r.usage_count,
            }
            for r in rows
        ]
