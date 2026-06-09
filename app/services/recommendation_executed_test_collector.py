"""
RecommendationExecutedTestCollector
====================================
Tracks which tests actually executed after a recommendation was generated,
by joining RecommendationRun → RecommendationTest against TestRun → TestResult.

Design principles:
- Explicit pairing only: caller supplies both recommendation_run_id and test_run_id.
- Append-only: existing RecommendationTestOutcome rows are never mutated.
- No intent inference: flags describe what happened, not why.
- Deterministic: same inputs always produce the same output rows.
- Replayable: idempotent — second call with same inputs is a no-op.

Matching strategy (Rule 2):
  1. Primary  — RecommendationTest.test_case_id (String) parsed as UUID,
                matched to TestResult.test_case_id (UUID FK).
  2. Fallback — RecommendationTest.test_case_id compared as a plain string
                against TestCase.stable_identity for tests that don't resolve
                to a UUID in the TestCase table.

execution_presence_status values:
  EXECUTED        — test ran and produced a non-skipped result.
  PRESENT_SKIPPED — test was present in the TestRun as explicitly skipped
                    (actually_executed=True, manually_removed=False).
  ABSENT          — recommended test was completely absent from the TestRun
                    (manually_removed=True).
  UNKNOWN         — presence state could not be determined.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationOutcome,
    RecommendationRun,
    RecommendationTest,
    RecommendationTestOutcome,
)
from app.models.repository import Repository
from app.models.test_result import TestCase, TestResult, TestRun

logger = logging.getLogger("veriscope.recommendation_executed_test_collector")

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CollectionResult:
    recommendation_run_id: uuid.UUID
    test_run_id: uuid.UUID
    recommendation_outcome_id: uuid.UUID
    total_recommended: int
    total_executed: int
    recommended_and_executed: int
    recommended_present_skipped: int   # recommended, present as skipped in TestRun
    recommended_absent: int            # recommended, absent entirely from TestRun
    non_recommended_executed: int      # widening: executed but not recommended
    outcome_rows_written: int
    outcome_rows_skipped: int          # idempotency: rows already present, not rewritten
    classification: str                # trusted / widened / narrowed / overridden / ignored
    replayable: bool = True


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

_EXECUTION_RESULT_MAP: Dict[str, str] = {
    "passed": "PASSED",
    "failed": "FAILED",
    "skipped": "SKIPPED",
    "error": "FAILED",
    "quarantined": "QUARANTINED",
}

def _map_execution_result(status: str) -> str:
    return _EXECUTION_RESULT_MAP.get(status.lower(), "UNKNOWN")


def _derive_presence_status(execution_result: str, test_absent: bool) -> str:
    """Derive execution_presence_status from result and absence flag."""
    if test_absent:
        return "ABSENT"
    if execution_result == "SKIPPED":
        return "PRESENT_SKIPPED"
    if execution_result in ("PASSED", "FAILED", "QUARANTINED"):
        return "EXECUTED"
    return "UNKNOWN"


def _classify_outcome(
    recommended_set: Set[uuid.UUID],
    executed_set: Set[uuid.UUID],
) -> str:
    """
    Determine the high-level classification of how the recommendation was followed.
    Mirrors RecommendationOutcome.classification property semantics but operates on
    resolved UUID sets for determinism.
    """
    from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

    if not recommended_set:
        return "trusted" if not executed_set else "widened"
    if recommended_set == executed_set:
        return "trusted"
    if RecommendationIgnoreDetector.detect(recommended_set, executed_set)["status"] == "IGNORED":
        return "ignored"
    if recommended_set.issubset(executed_set):
        return "widened"
    if executed_set.issubset(recommended_set):
        return "narrowed"
    return "overridden"


# ---------------------------------------------------------------------------
# Collector service
# ---------------------------------------------------------------------------

class RecommendationExecutedTestCollector:
    """
    Matches CI TestRun results back to a RecommendationRun and persists
    granular RecommendationTestOutcome rows capturing what was and wasn't run.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(
        self,
        recommendation_run_id: uuid.UUID,
        test_run_id: uuid.UUID,
    ) -> CollectionResult:
        """
        Produce RecommendationTestOutcome rows linking a recommendation to its CI results.

        Args:
            recommendation_run_id: UUID of the RecommendationRun to evaluate.
            test_run_id:           UUID of the TestRun that followed.

        Returns:
            CollectionResult describing the mapping produced.

        Raises:
            ValueError: if the RecommendationRun, TestRun, or RecommendationOutcome
                        cannot be found, or if there is a repository mismatch.
        """
        run, test_run, outcome = self._load_and_validate(
            recommendation_run_id, test_run_id
        )

        # --- Build recommended set (test_case_id as UUID, with fallback) ------
        rec_tests = (
            self.db.query(RecommendationTest)
            .filter(RecommendationTest.recommendation_run_id == run.id)
            .all()
        )

        # Resolve each RecommendationTest.test_case_id (String) to a TestCase UUID
        # and collect the recommendation reason per resolved UUID.
        recommended_map: Dict[uuid.UUID, str] = {}   # test_case_id → reason_type
        unresolved_by_identity: Dict[str, str] = {}  # stable_identity → reason_type

        for rec_test in rec_tests:
            resolved_id = self._resolve_test_case_id(
                rec_test.test_case_id, run.repository_id
            )
            if resolved_id is not None:
                recommended_map[resolved_id] = rec_test.reason_type
            else:
                # Keep as unresolved string for fallback identity matching
                unresolved_by_identity[rec_test.test_case_id] = rec_test.reason_type

        recommended_set: Set[uuid.UUID] = set(recommended_map.keys())

        # --- Build executed map from TestResults ------------------------------
        test_results = (
            self.db.query(TestResult)
            .filter(TestResult.test_run_id == test_run.id)
            .all()
        )

        # executed_map: test_case_id → (raw_status, duration)
        executed_map: Dict[uuid.UUID, Tuple[str, Optional[float]]] = {}
        for tr in test_results:
            executed_map[tr.test_case_id] = (tr.status, tr.duration)

        # Attempt fallback matching for any unresolved recommendation strings
        # by comparing against TestCase.stable_identity within this repository.
        if unresolved_by_identity:
            matched = self._fallback_identity_match(
                unresolved_by_identity, run.repository_id, executed_map
            )
            recommended_map.update(matched)
            recommended_set = set(recommended_map.keys())

        # --- Build the executed set of non-skipped tests (for classification) --
        actually_run_set: Set[uuid.UUID] = {
            tc_id
            for tc_id, (status, _) in executed_map.items()
            if status.lower() != "skipped"
        }

        classification = _classify_outcome(recommended_set, actually_run_set)

        # Check if the TestRun has already been collected for this outcome (idempotency check / CI replay protection)
        from app.models.recommendation import RecommendationOutcomeEvidence
        existing_evidence = self.db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "TEST_RUN",
            RecommendationOutcomeEvidence.source_reference_id == str(test_run_id)
        ).first()
        if existing_evidence:
            logger.info(f"TestRun {test_run_id} already collected for outcome {outcome.id}. Returning existing result.")
            outcome_rows_count = self.db.query(RecommendationTestOutcome).filter(
                RecommendationTestOutcome.recommendation_outcome_id == outcome.id
            ).count()
            return CollectionResult(
                recommendation_run_id=recommendation_run_id,
                test_run_id=test_run_id,
                recommendation_outcome_id=outcome.id,
                total_recommended=len(recommended_set),
                total_executed=len(executed_map),
                recommended_and_executed=len(recommended_set & set(executed_map.keys())),
                recommended_present_skipped=sum(
                    1 for tc_id in recommended_set
                    if tc_id in executed_map and executed_map[tc_id][0].lower() == "skipped"
                ),
                recommended_absent=len(recommended_set - set(executed_map.keys())),
                non_recommended_executed=len(set(executed_map.keys()) - recommended_set),
                outcome_rows_written=0,
                outcome_rows_skipped=outcome_rows_count,
                classification=classification,
                replayable=True,
            )

        # --- Fetch existing outcome rows to enforce idempotency ---------------
        existing_rows: Set[uuid.UUID] = {
            row.test_case_id
            for row in self.db.query(RecommendationTestOutcome.test_case_id).filter(
                RecommendationTestOutcome.recommendation_outcome_id == outcome.id
            ).all()
        }

        # --- Produce outcome rows ---------------------------------------------
        rows_written = 0
        rows_skipped = 0
        now = datetime.utcnow()

        # 1. Process every test that appeared in the recommendation
        for tc_id, reason_type in recommended_map.items():
            if tc_id in existing_rows:
                rows_skipped += 1
                continue

            if tc_id in executed_map:
                raw_status, duration = executed_map[tc_id]
                exec_result = _map_execution_result(raw_status)
                is_skipped = raw_status.lower() == "skipped"
                presence = _derive_presence_status(exec_result, test_absent=False)
                row = RecommendationTestOutcome(
                    id=uuid.uuid4(),
                    recommendation_outcome_id=outcome.id,
                    test_case_id=tc_id,
                    recommendation_reason=reason_type,
                    recommended_by_veriscope=True,
                    actually_executed=True,       # present in TestRun (even if skipped)
                    manually_added=False,
                    manually_removed=False,
                    execution_result=exec_result,
                    execution_presence_status=presence,
                    execution_duration_seconds=duration,
                    created_at=now,
                )
            else:
                # Completely absent from the TestRun
                row = RecommendationTestOutcome(
                    id=uuid.uuid4(),
                    recommendation_outcome_id=outcome.id,
                    test_case_id=tc_id,
                    recommendation_reason=reason_type,
                    recommended_by_veriscope=True,
                    actually_executed=False,
                    manually_added=False,
                    manually_removed=True,
                    execution_result=None,
                    execution_presence_status="ABSENT",
                    execution_duration_seconds=None,
                    created_at=now,
                )

            self.db.add(row)
            rows_written += 1

        # 2. Process tests executed that were NOT recommended (widening)
        for tc_id, (raw_status, duration) in executed_map.items():
            if tc_id in recommended_set:
                continue  # already handled above
            if tc_id in existing_rows:
                rows_skipped += 1
                continue

            exec_result = _map_execution_result(raw_status)
            presence = _derive_presence_status(exec_result, test_absent=False)
            row = RecommendationTestOutcome(
                id=uuid.uuid4(),
                recommendation_outcome_id=outcome.id,
                test_case_id=tc_id,
                recommendation_reason=None,
                recommended_by_veriscope=False,
                actually_executed=True,
                manually_added=True,
                manually_removed=False,
                execution_result=exec_result,
                execution_presence_status=presence,
                execution_duration_seconds=duration,
                created_at=now,
            )
            self.db.add(row)
            rows_written += 1

        self.db.commit()

        # Capture append-only snapshot evidence for auditing integrity (Rule 3 & Rule 4)
        from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity
        RecommendationOutcomeEvidenceIntegrity.record_evidence(
            db=self.db,
            outcome_id=outcome.id,
            evidence_type="TEST_RUN",
            source_reference_id=str(test_run_id),
            payload={
                "test_run_id": str(test_run_id),
                "executed_tests": outcome.executed_tests,
                "manually_added_tests": outcome.manually_added_tests,
                "manually_removed_tests": outcome.manually_removed_tests,
                "was_followed": outcome.was_followed,
                "override_reason": outcome.override_reason
            }
        )

        # --- Learn from manual overrides — expand the knowledge graph --------
        # Fetch workspace_id via the Repository so the learner can upsert links.
        # This is wrapped so any failure never prevents collect() from returning.
        try:
            from app.services.manual_override_learner import ManualOverrideLearner
            _repo_row = self.db.query(Repository).filter(
                Repository.id == run.repository_id
            ).first()
            if _repo_row and outcome.manually_added_tests:
                _learn_result = ManualOverrideLearner.learn_from_outcome(
                    db=self.db,
                    outcome=outcome,
                    workspace_id=_repo_row.workspace_id,
                    observed_at=now,
                )
                if not _learn_result.success:
                    logger.warning(
                        "ManualOverrideLearner errors for outcome %s: %s",
                        outcome.id,
                        _learn_result.errors,
                    )
        except Exception as _learn_exc:
            logger.error(
                "ManualOverrideLearner raised an unexpected exception for outcome %s: %s",
                outcome.id,
                _learn_exc,
            )

        # --- Compute summary counts ------------------------------------------
        recommended_and_executed = len(recommended_set & set(executed_map.keys()))
        recommended_skipped_count = sum(
            1 for tc_id in recommended_set
            if tc_id in executed_map and executed_map[tc_id][0].lower() == "skipped"
        )
        recommended_absent = len(recommended_set - set(executed_map.keys()))
        non_recommended_executed = len(set(executed_map.keys()) - recommended_set)

        logger.info(
            f"Collected execution mapping for run {recommendation_run_id}: "
            f"recommended={len(recommended_set)}, executed={len(executed_map)}, "
            f"classification={classification}, rows_written={rows_written}, "
            f"rows_skipped={rows_skipped}"
        )

        return CollectionResult(
            recommendation_run_id=recommendation_run_id,
            test_run_id=test_run_id,
            recommendation_outcome_id=outcome.id,
            total_recommended=len(recommended_set),
            total_executed=len(executed_map),
            recommended_and_executed=recommended_and_executed,
            recommended_present_skipped=recommended_skipped_count,
            recommended_absent=recommended_absent,
            non_recommended_executed=non_recommended_executed,
            outcome_rows_written=rows_written,
            outcome_rows_skipped=rows_skipped,
            classification=classification,
            replayable=True,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_and_validate(
        self,
        recommendation_run_id: uuid.UUID,
        test_run_id: uuid.UUID,
    ) -> Tuple[RecommendationRun, TestRun, RecommendationOutcome]:
        """Load and validate both runs and their shared outcome."""
        run = self.db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()
        if not run:
            raise ValueError(
                f"RecommendationRun {recommendation_run_id} not found."
            )

        test_run = self.db.query(TestRun).filter(TestRun.id == test_run_id).first()
        if not test_run:
            raise ValueError(f"TestRun {test_run_id} not found.")

        # Cross-repository safety guard
        if test_run.repository_id != run.repository_id:
            raise ValueError(
                f"Repository mismatch: RecommendationRun belongs to repo "
                f"{run.repository_id} but TestRun belongs to repo "
                f"{test_run.repository_id}. Cross-repo pairing is not allowed."
            )

        outcome = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == recommendation_run_id
        ).first()
        if not outcome:
            raise ValueError(
                f"RecommendationOutcome not found for run {recommendation_run_id}. "
                f"Cannot collect execution mapping without an outcome record."
            )

        return run, test_run, outcome

    def _resolve_test_case_id(
        self, raw_id: str, repository_id: uuid.UUID
    ) -> Optional[uuid.UUID]:
        """
        Attempt to parse raw_id as a UUID and verify it exists as a TestCase.
        Returns None if it cannot be resolved as a UUID FK.
        """
        try:
            parsed = uuid.UUID(raw_id)
        except (ValueError, AttributeError):
            return None

        exists = (
            self.db.query(TestCase.id)
            .filter(
                TestCase.id == parsed,
                TestCase.repository_id == repository_id,
            )
            .first()
        )
        return parsed if exists else None

    def _fallback_identity_match(
        self,
        unresolved_by_identity: Dict[str, str],  # stable_identity → reason_type
        repository_id: uuid.UUID,
        executed_map: Dict[uuid.UUID, Tuple[str, Optional[float]]],
    ) -> Dict[uuid.UUID, str]:
        """
        For test_case_ids that couldn't be resolved as UUIDs, attempt to match
        them against TestCase.stable_identity strings within the repository.

        Only resolves cases where the stable_identity uniquely identifies a
        TestCase that also appears in the executed_map — no speculative matches.
        """
        resolved: Dict[uuid.UUID, str] = {}

        # Build a lookup: stable_identity → TestCase.id for tests in executed_map
        if not executed_map:
            return resolved

        cases = (
            self.db.query(TestCase.id, TestCase.stable_identity)
            .filter(
                TestCase.repository_id == repository_id,
                TestCase.id.in_(list(executed_map.keys())),
            )
            .all()
        )
        identity_to_uuid: Dict[str, uuid.UUID] = {
            row.stable_identity: row.id for row in cases
        }

        for stable_id, reason_type in unresolved_by_identity.items():
            matched_uuid = identity_to_uuid.get(stable_id)
            if matched_uuid is not None:
                resolved[matched_uuid] = reason_type
                logger.debug(
                    f"Fallback identity match: '{stable_id}' → {matched_uuid}"
                )
            else:
                logger.warning(
                    f"Could not resolve RecommendationTest identifier '{stable_id}' "
                    f"via fallback stable_identity match. Skipping."
                )

        return resolved
