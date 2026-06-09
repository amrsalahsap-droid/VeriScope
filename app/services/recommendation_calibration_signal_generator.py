import uuid
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationOutcome, RecommendationRun

logger = logging.getLogger(__name__)

class RecommendationCalibrationSignalGenerator:
    """
    RecommendationCalibrationSignalGenerator
    ========================================
    Generates rich, informational calibration inputs at the repository level without
    modifying recommendation engine behavior (preventing automatic learning loops).
    
    Features:
    - Time-window normalization
    - Wilson score confidence intervals (95%)
    - Bayesian beta-prior smoothing for tiny repositories (total < min_recommendations)
    - Detailed metrics: follow rate, override rate, defect rate, rollback rate,
      widening/narrowing frequencies, flaky restores, and human feedback distributions.
    """

    @classmethod
    def calculate_wilson_interval(cls, successes: int, total: int, z: float = 1.95996) -> Dict[str, float]:
        """
        Compute the 95% Wilson Score interval for a binomial proportion.
        """
        if total == 0:
            return {"lower": 0.0, "estimate": 0.0, "upper": 0.0}
        
        p = successes / total
        denom = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denom
        spread = z * math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2))) / denom
        
        lower = max(0.0, center - spread)
        upper = min(1.0, center + spread)
        
        return {
            "lower": round(lower, 4),
            "estimate": round(p, 4),
            "upper": round(upper, 4)
        }

    @classmethod
    def get_smoothed_rate(cls, successes: int, total: int, alpha: float = 2.0, beta: float = 2.0) -> float:
        """
        Compute Bayesian-smoothed proportion using a Beta(alpha, beta) prior.
        Highly effective at preventing extreme swings for small sample sizes.
        """
        return round((successes + alpha) / (total + alpha + beta), 4)

    @classmethod
    def generate_signals(
        cls,
        db: Session,
        repository_id: uuid.UUID,
        window_days: Optional[int] = None,
        min_recommendations: int = 5
    ) -> Dict[str, Any]:
        """
        Generate informational calibration signals for a given repository.
        
        Args:
            db: SQLAlchemy Session.
            repository_id: UUID of the target repository.
            window_days: Optional sliding time window in days.
            min_recommendations: Threshold below which a repository is treated as "tiny"
                                 and has its rate estimates smoothed conservatively.
                                 
        Returns:
            Dict containing aggregated signals, raw counts, and confidence bounds.
        """
        # 1. Fetch chronological outcomes for the repository within the time window
        query = db.query(RecommendationOutcome).join(
            RecommendationRun, RecommendationOutcome.recommendation_run_id == RecommendationRun.id
        ).filter(RecommendationRun.repository_id == repository_id)

        if window_days is not None:
            cutoff = datetime.utcnow() - timedelta(days=window_days)
            query = query.filter(RecommendationOutcome.created_at >= cutoff)

        outcomes = query.order_by(RecommendationOutcome.created_at.asc()).all()
        total_count = len(outcomes)

        # Initialize raw counters
        followed_count = 0
        override_count = 0
        defect_count = 0
        rollback_count = 0
        widening_count = 0
        narrowing_count = 0
        flaky_restore_count = 0
        usefulness_feedback_count = 0

        # Loop through outcomes to extract signals
        for outcome in outcomes:
            # A. Follow Rate
            if outcome.outcome_status == "FOLLOWED" or outcome.was_followed_legacy is True:
                followed_count += 1

            # B. Override Rate
            has_overrides = (
                outcome.outcome_status == "OVERRIDDEN" or
                len(outcome.manually_added_tests or []) > 0 or
                len(outcome.manually_removed_tests or []) > 0 or
                outcome.was_followed_legacy is False
            )
            if has_overrides:
                override_count += 1

            # C. Escaped Defect Rate
            has_defect = (
                outcome.outcome_status == "ESCAPED_DEFECT_LINKED" or
                outcome.escaped_defect_detected is True or
                outcome.escaped_defect_legacy is True
            )
            if has_defect:
                defect_count += 1

            # D. Rollback Rate
            has_rollback = (
                outcome.outcome_status == "ROLLBACK_LINKED" or
                outcome.rollback_occurred is True
            )
            if has_rollback:
                rollback_count += 1

            # E. Widening Frequency (Dev added custom tests)
            if len(outcome.manually_added_tests or []) > 0 or (outcome.override_record and outcome.override_record.widening_detected):
                widening_count += 1

            # F. Narrowing Frequency (Dev removed recommended tests)
            if len(outcome.manually_removed_tests or []) > 0 or (outcome.override_record and outcome.override_record.narrowing_detected):
                narrowing_count += 1

            # G. Flaky Restore Frequency (Manually restored flaky tests)
            if outcome.override_record and outcome.override_record.flaky_tests_manually_restored > 0:
                flaky_restore_count += 1

            # H. Usefulness Feedback (USEFUL human alignment capture)
            has_useful_feedback = False
            if outcome.feedback_state == "USEFUL":
                has_useful_feedback = True
            elif outcome.feedbacks:
                has_useful_feedback = any(fb.feedback_type == "USEFUL" for fb in outcome.feedbacks)
            elif outcome.feedback_legacy and "useful" in outcome.feedback_legacy.lower() and "not" not in outcome.feedback_legacy.lower():
                has_useful_feedback = True
            
            if has_useful_feedback:
                usefulness_feedback_count += 1

        is_tiny_repository = total_count < min_recommendations

        # Compile final smoothed estimates and Wilson intervals for each signal
        signals_def = [
            ("recommendation_follow_rate", followed_count),
            ("override_rate", override_count),
            ("escaped_defect_rate", defect_count),
            ("rollback_rate", rollback_count),
            ("widening_frequency", widening_count),
            ("narrowing_frequency", narrowing_count),
            ("flaky_restore_frequency", flaky_restore_count),
            ("recommendation_usefulness_feedback", usefulness_feedback_count)
        ]

        metrics = {}
        for name, successes in signals_def:
            raw_rate = round(successes / total_count, 4) if total_count > 0 else 0.0
            smoothed_rate = cls.get_smoothed_rate(successes, total_count)
            wilson = cls.calculate_wilson_interval(successes, total_count)

            # Apply conservative normalization for tiny repositories
            final_estimate = smoothed_rate if is_tiny_repository else raw_rate

            metrics[name] = {
                "raw_rate": raw_rate,
                "smoothed_rate": smoothed_rate,
                "confidence_interval": wilson,
                "final_calibrated_estimate": final_estimate
            }

        report = {
            "repository_id": str(repository_id),
            "window_days": window_days,
            "total_outcomes_analyzed": total_count,
            "is_tiny_repository_normalization_applied": is_tiny_repository,
            "min_recommendations_threshold": min_recommendations,
            "generated_at": datetime.utcnow().isoformat(),
            "signals": metrics,
            "raw_counts": {
                "followed_count": followed_count,
                "override_count": override_count,
                "defect_count": defect_count,
                "rollback_count": rollback_count,
                "widening_count": widening_count,
                "narrowing_count": narrowing_count,
                "flaky_restore_count": flaky_restore_count,
                "usefulness_feedback_count": usefulness_feedback_count
            },
            "advisory_statement": (
                "Informational calibration signals generated for auditing. "
                "No active recommendation engine modification performed (auto-learning loop disabled)."
            )
        }

        logger.info(
            f"Generated informational calibration signals for repository {repository_id} "
            f"(Tiny-repo normalization: {is_tiny_repository}, outcomes count: {total_count})."
        )

        return report
