import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern_memory import PatternMemory
from app.models.pull_request import PullRequestChangedFile
from app.models.recommendation import RecommendationOutcome

logger = logging.getLogger("veriscope.learning_engine_v2")


@dataclass
class LearningEngineV2Result:
    """Structured summary of a single LearningEngineV2 learning pass."""
    patterns_upserted: int = 0
    signals_processed: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class LearningEngineV2:
    """Incremental learning engine v2.

    Learns from engineer behavior, recommended tests, executed tests,
    added/removed tests, defects, and rollbacks, and stores them in PatternMemory.
    """

    @classmethod
    def learn(
        cls,
        db: Session,
        *,
        outcome: RecommendationOutcome,
        workspace_id: UUID,
        observed_at: Optional[datetime] = None,
    ) -> LearningEngineV2Result:
        """Learn from all sets on a finalised RecommendationOutcome.

        Updates the PatternMemory table.
        """
        result = LearningEngineV2Result()
        if outcome.pull_request_id is None:
            return result

        now = observed_at or datetime.utcnow()

        try:
            # 1. Fetch changed files
            changed_files = (
                db.query(PullRequestChangedFile)
                .filter(
                    PullRequestChangedFile.pull_request_id == outcome.pull_request_id,
                    PullRequestChangedFile.status != "removed",
                )
                .all()
            )
            file_paths = [cf.file_path.replace("\\", "/") for cf in changed_files]
            if not file_paths:
                return result

            # 2. Extract test sets
            recommended = list(outcome.recommended_tests or [])
            executed = list(outcome.executed_tests or [])
            added = list(outcome.manually_added_tests or [])
            removed = list(outcome.manually_removed_tests or [])

            recommended_set = set(recommended)
            executed_set = set(executed)
            added_set = set(added)
            removed_set = set(removed)

            all_tests = recommended_set | executed_set | added_set | removed_set
            if not all_tests:
                return result

            is_escape = bool(outcome.escaped_defect_detected)
            is_rollback = bool(outcome.rollback_occurred)

            # 3. Process signals for each (file_path, test_id) combination
            for f in file_paths:
                for t in all_tests:
                    # Determine signal type, base, and step
                    signal_type = None
                    base = 0.0
                    step = 0.0
                    is_positive = True

                    if t in added_set:
                        signal_type = "MANUAL_ADD"
                        base = 0.80
                        step = 0.10
                    elif t in removed_set:
                        signal_type = "REMOVED"
                        is_positive = False
                    elif t in recommended_set and t in executed_set:
                        signal_type = "FOLLOWED"
                        base = 0.50
                        step = 0.05
                    elif t in recommended_set and t not in executed_set and (is_escape or is_rollback):
                        signal_type = "DEFECT_ESCAPE"
                        base = 0.90
                        step = 0.05
                    elif t in recommended_set and t not in executed_set:
                        signal_type = "SKIPPED"
                        base = 0.20
                        step = 0.02

                    if not signal_type:
                        continue

                    result.signals_processed += 1

                    # Look up existing pattern memory record using key fields
                    existing = (
                        db.query(PatternMemory)
                        .filter(
                            PatternMemory.repository_id == outcome.repository_id,
                            PatternMemory.pattern_key == f"file_change:{f}",
                            PatternMemory.test_identifier == t,
                        )
                        .first()
                    )

                    if existing:
                        if is_positive:
                            new_usage = existing.usage_count + 1
                            new_conf = min(base + (new_usage - 1) * step, 1.0)
                            existing.confidence = max(float(existing.confidence), new_conf)
                            existing.usage_count = new_usage
                        else:
                            # Apply negative penalty (REMOVED) directly to confidence
                            existing.confidence = max(0.0, float(existing.confidence) - 0.30)
                        existing.updated_at = now
                        db.add(existing)
                    else:
                        if is_positive:
                            row = PatternMemory(
                                workspace_id=workspace_id,
                                repository_id=outcome.repository_id,
                                pattern_key=f"file_change:{f}",
                                changed_file_pattern=f,
                                recommended_test=t,
                                test_identifier=t,
                                confidence=base,
                                usage_count=1,
                                created_at=now,
                                updated_at=now,
                            )
                        else:
                            row = PatternMemory(
                                workspace_id=workspace_id,
                                repository_id=outcome.repository_id,
                                pattern_key=f"file_change:{f}",
                                changed_file_pattern=f,
                                recommended_test=t,
                                test_identifier=t,
                                confidence=0.0,
                                usage_count=0,
                                created_at=now,
                                updated_at=now,
                            )
                        db.add(row)

                    result.patterns_upserted += 1

        except Exception as exc:
            msg = f"LearningEngineV2: failed to learn from outcome {outcome.id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)

        return result
