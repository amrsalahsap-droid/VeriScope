import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationEngineerFeedback
)
from app.models.pull_request import PullRequest
from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

logger = logging.getLogger("veriscope.recommendation_trust_metrics_builder")

class RecommendationTrustMetricsBuilder:
    """
    RecommendationTrustMetricsBuilder
    =================================
    Measures operational developer trust metrics dynamically and deterministically.
    Adheres strictly to the rules of informational-only metrics, avoiding trust theatrics,
    fake scoring, and overclaiming behavior.
    """

    @classmethod
    def build_metrics(
        cls,
        db: Session,
        repository_ids: List[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Build developer operational trust metrics, preserving sample size, confidence limits,
        and repository segmentation.
        """
        # Return empty metrics package if no repositories enrolled
        if not repository_ids:
            return {
                "reporting_window_start": start_date.isoformat(),
                "reporting_window_end": end_date.isoformat(),
                "total_runs": 0,
                "total_outcomes": 0,
                "follow_rate": 0.0,
                "override_frequency": 0.0,
                "widening_frequency": 0.0,
                "ignored_recommendation_rate": 0.0,
                "trust_confidence_bounds": [0.0, 0.0],
                "feedback_summary": {
                    "total_feedbacks": 0,
                    "positive_feedback_rate": 0.0,
                    "distribution": {}
                },
                "recurring_adoption": {
                    "unique_authors_count": 0,
                    "unique_adopters_count": 0,
                    "unique_repeat_adopters_count": 0,
                    "recurring_adoption_rate": 0.0
                },
                "repository_segmentation": {},
                "confidence_warning": "WARNING: Empty repository scope provided."
            }

        # 1. Fetch all runs within time window and repository scope
        runs = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id.in_(repository_ids),
            RecommendationRun.created_at >= start_date,
            RecommendationRun.created_at <= end_date
        ).all()
        run_ids = [run.id for run in runs]
        runs_by_id = {run.id: run for run in runs}

        # 2. Fetch all outcomes for these runs
        outcomes = []
        if run_ids:
            outcomes = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id.in_(run_ids)
            ).all()
        outcome_ids = [outcome.id for outcome in outcomes]

        # Initialize counts
        total_runs = len(runs)
        total_outcomes = len(outcomes)
        followed_count = 0
        overridden_count = 0
        widened_count = 0
        ignored_count = 0

        # Repository-segmented stats
        repo_segmentation = {}
        for repo_id in repository_ids:
            repo_segmentation[str(repo_id)] = {
                "total_runs": 0,
                "total_outcomes": 0,
                "followed_runs": 0,
                "overridden_runs": 0,
                "widened_runs": 0,
                "ignored_runs": 0
            }

        # PR author stats to evaluate recurring adoption
        pr_ids = [run.pull_request_id for run in runs if run.pull_request_id]
        pr_authors = {}
        if pr_ids:
            prs = db.query(PullRequest).filter(PullRequest.id.in_(pr_ids)).all()
            pr_authors = {pr.id: pr.author for pr in prs if pr.author}

        author_stats = {}  # author -> {"total_outcomes": 0, "followed_outcomes": 0}

        for outcome in outcomes:
            run = runs_by_id.get(outcome.recommendation_run_id)
            if not run:
                continue

            # Identify pull request author
            author = None
            if run.pull_request_id:
                author = pr_authors.get(run.pull_request_id)
            if not author and run.pr_id:
                author = f"author_{run.pr_id}"
            if not author:
                author = "unknown_author"

            if author not in author_stats:
                author_stats[author] = {"total_outcomes": 0, "followed_outcomes": 0}

            author_stats[author]["total_outcomes"] += 1

            # Determine outcomes alignment classifications
            has_overrides = (
                len(outcome.manually_added_tests or []) > 0 or
                len(outcome.manually_removed_tests or []) > 0 or
                outcome.outcome_status == "OVERRIDDEN"
            )
            has_widening = len(outcome.manually_added_tests or []) > 0

            # Update repository segmentation
            repo_str = str(outcome.repository_id)
            if repo_str in repo_segmentation:
                repo_segmentation[repo_str]["total_outcomes"] += 1

            if has_overrides:
                overridden_count += 1
                if repo_str in repo_segmentation:
                    repo_segmentation[repo_str]["overridden_runs"] += 1
            elif outcome.outcome_status == "IGNORED":
                ignored_count += 1
                if repo_str in repo_segmentation:
                    repo_segmentation[repo_str]["ignored_runs"] += 1
            else:
                followed_count += 1
                author_stats[author]["followed_outcomes"] += 1
                if repo_str in repo_segmentation:
                    repo_segmentation[repo_str]["followed_runs"] += 1

            if has_widening:
                widened_count += 1
                if repo_str in repo_segmentation:
                    repo_segmentation[repo_str]["widened_runs"] += 1

        # Fill total runs per repository
        for run in runs:
            repo_str = str(run.repository_id)
            if repo_str in repo_segmentation:
                repo_segmentation[repo_str]["total_runs"] += 1

        # 3. Calculate rates
        follow_rate = followed_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0
        override_frequency = overridden_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0
        widening_frequency = widened_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0
        ignored_recommendation_rate = ignored_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0

        # Trust bounds via Wilson Score Interval at 90% confidence
        lower_bound, upper_bound = RecommendationIgnoreDetector.calculate_wilson_score_interval(
            followed_count,
            total_outcomes,
            confidence_level=0.90
        )

        # 4. Fetch and evaluate engineer usefulness feedbacks
        feedbacks = []
        if outcome_ids:
            feedbacks = db.query(RecommendationEngineerFeedback).filter(
                RecommendationEngineerFeedback.recommendation_outcome_id.in_(outcome_ids)
            ).all()

        total_feedbacks = len(feedbacks)
        feedback_distribution = {
            "USEFUL": 0,
            "NOT_USEFUL": 0,
            "MISSING_TESTS": 0,
            "TOO_MANY_TESTS": 0,
            "UNCLEAR_REASONING": 0
        }
        for fb in feedbacks:
            fb_type = fb.feedback_type.upper()
            if fb_type in feedback_distribution:
                feedback_distribution[fb_type] += 1
            else:
                feedback_distribution[fb_type] = feedback_distribution.get(fb_type, 0) + 1

        rating_feedbacks = feedback_distribution["USEFUL"] + feedback_distribution["NOT_USEFUL"]
        positive_feedback_rate = (
            feedback_distribution["USEFUL"] / max(rating_feedbacks, 1)
            if rating_feedbacks > 0
            else 0.0
        )

        # 5. Recurring Recommendation Adoption metrics
        unique_authors_count = len(author_stats)
        unique_adopters_count = len([a for a, s in author_stats.items() if s["followed_outcomes"] >= 1])
        unique_repeat_adopters_count = len([a for a, s in author_stats.items() if s["followed_outcomes"] >= 2])
        recurring_adoption_rate = (
            unique_repeat_adopters_count / max(unique_adopters_count, 1)
            if unique_adopters_count > 0
            else 0.0
        )

        # 6. Tiny dataset check & confidence warnings
        confidence_warning = None
        if total_outcomes < 5:
            confidence_warning = (
                f"WARNING: Tiny outcome dataset (N = {total_outcomes}). "
                "Operational trust metrics and adoption frequencies have low statistical significance. "
                "Assess indicators as preliminary observations only."
            )

        return {
            "reporting_window_start": start_date.isoformat(),
            "reporting_window_end": end_date.isoformat(),
            "total_runs": total_runs,
            "total_outcomes": total_outcomes,
            "follow_rate": round(follow_rate, 4),
            "override_frequency": round(override_frequency, 4),
            "widening_frequency": round(widening_frequency, 4),
            "ignored_recommendation_rate": round(ignored_recommendation_rate, 4),
            "trust_confidence_bounds": [round(lower_bound, 4), round(upper_bound, 4)],
            "feedback_summary": {
                "total_feedbacks": total_feedbacks,
                "positive_feedback_rate": round(positive_feedback_rate, 4),
                "distribution": feedback_distribution
            },
            "recurring_adoption": {
                "unique_authors_count": unique_authors_count,
                "unique_adopters_count": unique_adopters_count,
                "unique_repeat_adopters_count": unique_repeat_adopters_count,
                "recurring_adoption_rate": round(recurring_adoption_rate, 4)
            },
            "repository_segmentation": repo_segmentation,
            "confidence_warning": confidence_warning
        }
