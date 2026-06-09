import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTest,
)

logger = logging.getLogger("veriscope.pilot_metrics_aggregator")

class PilotMetricsAggregator:
    """
    PilotMetricsAggregator
    =====================
    Generates deterministic, lineage-backed operational metrics for pilots.
    Applies strict data exclusion and dataset confidence rules.
    """

    @classmethod
    def aggregate_metrics(
        cls,
        db: Session,
        repository_ids: List[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Query and aggregate pilot metrics over the specified window and repository scope.
        """
        if not repository_ids:
            return {
                "reporting_window_start": start_date.isoformat(),
                "reporting_window_end": end_date.isoformat(),
                "repository_ids": [],
                "aggregation_version": 1,
                "total_prs_analyzed": 0,
                "total_recommendation_runs": 0,
                "total_recommended_tests": 0,
                "total_executed_tests": 0,
                "total_full_suite_runtime_seconds": 0.0,
                "total_recommended_runtime_seconds": 0.0,
                "override_frequency": 0.0,
                "ignored_recommendation_rate": 0.0,
                "rollback_linked_outcomes": 0,
                "escaped_defect_linked_outcomes": 0,
                "excluded_data_counts": {
                    "missing_full_suite_runtime": 0,
                    "missing_recommended_runtime": 0,
                    "missing_pull_request": 0,
                    "missing_outcome": 0
                },
                "confidence_warning": "WARNING: Empty repository scope provided."
            }

        # Query all recommendation runs in the time window and repository scope
        runs = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id.in_(repository_ids),
            RecommendationRun.created_at >= start_date,
            RecommendationRun.created_at <= end_date
        ).all()

        run_ids = [run.id for run in runs]

        # Fetch outcomes associated with these runs
        outcomes = []
        if run_ids:
            outcomes = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id.in_(run_ids)
            ).all()

        outcome_by_run = {o.recommendation_run_id: o for o in outcomes}

        # Initialize counters
        pr_set = set()
        total_recommended_tests = 0
        total_executed_tests = 0
        total_full_suite_runtime_seconds = 0.0
        total_recommended_runtime_seconds = 0.0
        overridden_count = 0
        ignored_count = 0
        rollback_linked_outcomes = 0
        escaped_defect_linked_outcomes = 0
        total_outcomes = 0

        # Exclusions tracking
        missing_full_suite_runtime = 0
        missing_recommended_runtime = 0
        missing_pull_request = 0
        missing_outcome = 0

        for run in runs:
            # 1. PR Lineage aggregation
            if run.pull_request_id:
                pr_set.add(str(run.pull_request_id))
            elif run.pr_id and run.pr_id.strip() not in ("", "N/A", "unknown", "legacy_hash"):
                pr_set.add(run.pr_id)
            else:
                missing_pull_request += 1

            # 2. Recommended tests summation
            total_recommended_tests += len(run.tests)

            # 3. Full-suite equivalent runtime aggregation (strict null check)
            if run.full_suite_runtime_seconds is not None:
                total_full_suite_runtime_seconds += run.full_suite_runtime_seconds
            else:
                missing_full_suite_runtime += 1

            # 4. Recommended runtime aggregation (strict null check)
            if run.estimated_runtime_seconds is not None:
                total_recommended_runtime_seconds += run.estimated_runtime_seconds
            else:
                missing_recommended_runtime += 1

            # 5. Outcome metrics
            outcome = outcome_by_run.get(run.id)
            if not outcome:
                missing_outcome += 1
                continue

            total_outcomes += 1

            # Sum of executed tests (uses dynamic ORM property)
            total_executed_tests += len(outcome.executed_tests)

            # Check for developer overrides
            has_overrides = (
                len(outcome.manually_added_tests or []) > 0 or
                len(outcome.manually_removed_tests or []) > 0 or
                outcome.outcome_status == "OVERRIDDEN"
            )
            if has_overrides:
                overridden_count += 1

            # Check for ignores
            if outcome.outcome_status == "IGNORED":
                ignored_count += 1

            # Incidents & Rollbacks
            if outcome.rollback_occurred:
                rollback_linked_outcomes += 1
            if outcome.escaped_defect_detected:
                escaped_defect_linked_outcomes += 1

        # Ratios
        override_frequency = overridden_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0
        ignored_recommendation_rate = ignored_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0

        # Confidence warning for tiny datasets
        confidence_warning = None
        if len(runs) < 5 or total_outcomes < 5:
            confidence_warning = (
                f"WARNING: Tiny dataset (runs = {len(runs)}, outcomes = {total_outcomes}). "
                "Statistical metrics like override frequency and ignore rate have low reliability due to small sample size."
            )

        return {
            "reporting_window_start": start_date.isoformat(),
            "reporting_window_end": end_date.isoformat(),
            "repository_ids": [str(r) for r in repository_ids],
            "aggregation_version": 1,
            "total_prs_analyzed": len(pr_set),
            "total_recommendation_runs": len(runs),
            "total_recommended_tests": total_recommended_tests,
            "total_executed_tests": total_executed_tests,
            "total_full_suite_runtime_seconds": round(total_full_suite_runtime_seconds, 2),
            "total_recommended_runtime_seconds": round(total_recommended_runtime_seconds, 2),
            "override_frequency": round(override_frequency, 3),
            "ignored_recommendation_rate": round(ignored_recommendation_rate, 3),
            "rollback_linked_outcomes": rollback_linked_outcomes,
            "escaped_defect_linked_outcomes": escaped_defect_linked_outcomes,
            "excluded_data_counts": {
                "missing_full_suite_runtime": missing_full_suite_runtime,
                "missing_recommended_runtime": missing_recommended_runtime,
                "missing_pull_request": missing_pull_request,
                "missing_outcome": missing_outcome
            },
            "confidence_warning": confidence_warning
        }
