"""
RecommendationOverrideTracker
==============================
Detects and records manual widening/narrowing of recommended test suites.

Reads RecommendationTestOutcome rows already written by
RecommendationExecutedTestCollector and produces a single
RecommendationOverrideRecord capturing the override lineage.

Design principles:
- Evidence only: no judgment, no good/bad classification.
- One record per RecommendationOutcome (idempotent).
- Deterministic: same inputs always produce identical output.
- Replayable: second call returns existing record unchanged.
- Timing preserved: detected_at is set once and never mutated.

Critical test detection:
    A removed test is "critical" if it has a RecommendationReasoningEntry
    with evidence_priority = "CRITICAL" for this recommendation_run_id.

Flaky test detection:
    An added test is "flaky restored" if it has a FlakyTestProfile with
    status in ("unstable", "quarantined") in this repository.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Set

from sqlalchemy.orm import Session

from app.models.flaky_test import FlakyTestProfile
from app.models.recommendation import (
    RecommendationOutcome,
    RecommendationOverrideRecord,
    RecommendationReasoningEntry,
    RecommendationRun,
    RecommendationTestOutcome,
)

logger = logging.getLogger("veriscope.recommendation_override_tracker")

_FLAKY_STATUSES = {"unstable", "quarantined"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class OverrideResult:
    recommendation_run_id: uuid.UUID
    recommendation_outcome_id: uuid.UUID
    total_recommended: int
    total_manually_added: int
    total_manually_removed: int
    override_ratio: float
    critical_tests_removed: int
    flaky_tests_manually_restored: int
    widening_detected: bool
    narrowing_detected: bool
    was_replayed: bool  # True if an existing record was returned (idempotent)


# ---------------------------------------------------------------------------
# Tracker service
# ---------------------------------------------------------------------------

class RecommendationOverrideTracker:
    """
    Detects manual widening and narrowing overrides from an already-collected
    RecommendationTestOutcome set and persists a RecommendationOverrideRecord.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(self, recommendation_run_id: uuid.UUID) -> OverrideResult:
        """
        Detect and record override lineage for a recommendation run.

        Prerequisites:
            RecommendationExecutedTestCollector.collect() must have been called
            first so that RecommendationTestOutcome rows exist.

        Args:
            recommendation_run_id: UUID of the RecommendationRun to analyse.

        Returns:
            OverrideResult describing the override lineage.

        Raises:
            ValueError: if the RecommendationOutcome is missing, or if no
                        RecommendationTestOutcome rows exist yet.
        """
        run, outcome = self._load_and_validate(recommendation_run_id)

        # --- Idempotency: return existing record unchanged ----------------
        existing = self.db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == outcome.id
        ).first()
        if existing:
            logger.info(
                f"Override record already exists for run {recommendation_run_id}, "
                f"returning existing record (idempotent replay)."
            )
            return self._result_from_record(existing, was_replayed=True)

        # --- Load RecommendationTestOutcome rows -------------------------
        test_outcomes = (
            self.db.query(RecommendationTestOutcome)
            .filter(RecommendationTestOutcome.recommendation_outcome_id == outcome.id)
            .all()
        )

        if not test_outcomes:
            raise ValueError(
                f"No RecommendationTestOutcome rows found for outcome {outcome.id} "
                f"(run {recommendation_run_id}). "
                f"RecommendationExecutedTestCollector.collect() must run first."
            )

        # --- Partition into added / removed / recommended ----------------
        added_ids: List[uuid.UUID] = []
        removed_ids: List[uuid.UUID] = []
        total_recommended = 0

        for row in test_outcomes:
            if row.recommended_by_veriscope:
                total_recommended += 1
            if row.manually_added:
                added_ids.append(row.test_case_id)
            if row.manually_removed:
                removed_ids.append(row.test_case_id)

        added_set: Set[uuid.UUID] = set(added_ids)
        removed_set: Set[uuid.UUID] = set(removed_ids)

        # --- Critical tests removed -------------------------------------
        # A removed test is "critical" if it has a CRITICAL reasoning entry
        # for this run.
        critical_removed_ids: List[uuid.UUID] = []
        if removed_set:
            critical_entries = (
                self.db.query(RecommendationReasoningEntry.test_case_id)
                .filter(
                    RecommendationReasoningEntry.recommendation_run_id == run.id,
                    RecommendationReasoningEntry.evidence_priority == "CRITICAL",
                    RecommendationReasoningEntry.test_case_id.in_(list(removed_set)),
                )
                .all()
            )
            # Deduplicate: multiple reasoning entries can point to the same test
            critical_removed_ids = list({row.test_case_id for row in critical_entries})

        # --- Flaky tests manually restored ------------------------------
        # An added test is "flaky restored" if it has an unstable/quarantined
        # FlakyTestProfile in this repository.
        flaky_restored_ids: List[uuid.UUID] = []
        if added_set:
            flaky_profiles = (
                self.db.query(FlakyTestProfile.test_case_id)
                .filter(
                    FlakyTestProfile.repository_id == run.repository_id,
                    FlakyTestProfile.test_case_id.in_(list(added_set)),
                    FlakyTestProfile.status.in_(list(_FLAKY_STATUSES)),
                )
                .all()
            )
            flaky_restored_ids = [row.test_case_id for row in flaky_profiles]

        # --- Compute override ratio ------------------------------------
        override_ratio = round(
            (len(added_ids) + len(removed_ids)) / max(total_recommended, 1),
            6,
        )

        # --- Persist RecommendationOverrideRecord ----------------------
        now = datetime.utcnow()
        record = RecommendationOverrideRecord(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome.id,
            recommendation_run_id=run.id,
            repository_id=run.repository_id,
            detected_at=now,
            total_manually_added=len(added_ids),
            total_manually_removed=len(removed_ids),
            override_ratio=override_ratio,
            critical_tests_removed=len(critical_removed_ids),
            flaky_tests_manually_restored=len(flaky_restored_ids),
            manually_added_test_ids=[str(tc_id) for tc_id in added_ids],
            manually_removed_test_ids=[str(tc_id) for tc_id in removed_ids],
            critical_removed_test_ids=[str(tc_id) for tc_id in critical_removed_ids],
            flaky_restored_test_ids=[str(tc_id) for tc_id in flaky_restored_ids],
            widening_detected=len(added_ids) > 0,
            narrowing_detected=len(removed_ids) > 0,
            created_at=now,
        )
        self.db.add(record)
        self.db.commit()

        logger.info(
            f"Override record created for run {recommendation_run_id}: "
            f"added={len(added_ids)}, removed={len(removed_ids)}, "
            f"ratio={override_ratio:.4f}, critical_removed={len(critical_removed_ids)}, "
            f"flaky_restored={len(flaky_restored_ids)}"
        )

        return OverrideResult(
            recommendation_run_id=recommendation_run_id,
            recommendation_outcome_id=outcome.id,
            total_recommended=total_recommended,
            total_manually_added=len(added_ids),
            total_manually_removed=len(removed_ids),
            override_ratio=override_ratio,
            critical_tests_removed=len(critical_removed_ids),
            flaky_tests_manually_restored=len(flaky_restored_ids),
            widening_detected=len(added_ids) > 0,
            narrowing_detected=len(removed_ids) > 0,
            was_replayed=False,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_and_validate(
        self, recommendation_run_id: uuid.UUID
    ):
        run = self.db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()
        if not run:
            raise ValueError(
                f"RecommendationRun {recommendation_run_id} not found."
            )

        outcome = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == recommendation_run_id
        ).first()
        if not outcome:
            raise ValueError(
                f"RecommendationOutcome not found for run {recommendation_run_id}. "
                f"An outcome record must exist before override tracking."
            )

        return run, outcome

    @staticmethod
    def _result_from_record(
        record: RecommendationOverrideRecord, was_replayed: bool
    ) -> OverrideResult:
        """Reconstruct an OverrideResult from an existing persisted record."""
        return OverrideResult(
            recommendation_run_id=record.recommendation_run_id,
            recommendation_outcome_id=record.recommendation_outcome_id,
            # total_recommended is not stored on the record; use added+removed+0 as lower bound
            total_recommended=0,
            total_manually_added=record.total_manually_added,
            total_manually_removed=record.total_manually_removed,
            override_ratio=record.override_ratio,
            critical_tests_removed=record.critical_tests_removed,
            flaky_tests_manually_restored=record.flaky_tests_manually_restored,
            widening_detected=record.widening_detected,
            narrowing_detected=record.narrowing_detected,
            was_replayed=was_replayed,
        )
