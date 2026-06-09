import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationOutcome

logger = logging.getLogger("veriscope.recommendation_exposure_tracker")


class RecommendationExposureTracker:
    """Service to track when recommendations become visible to engineers (exposure)."""

    def __init__(self, db: Session):
        self.db = db

    def track_presented(self, run_id: uuid.UUID) -> Optional[RecommendationOutcome]:
        """Track that the recommendation run was successfully presented to engineers.

        This sets recommendation_presented_at to the current UTC timestamp only if
        it is not already set. Failed delivery must NOT trigger this tracking.
        Once set, this value is immutable (Rule 4).
        """
        outcome = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run_id
        ).first()

        if not outcome:
            logger.warning(f"Cannot track exposure presented: No RecommendationOutcome found for run {run_id}")
            return None

        # Immutability Check: presented timestamp is immutable once set (Rule 4)
        if outcome.recommendation_presented_at is not None:
            logger.info(
                f"Recommendation exposure presented already tracked for run {run_id} at "
                f"{outcome.recommendation_presented_at}. Keeping original timestamp."
            )
            return outcome

        outcome.recommendation_presented_at = datetime.utcnow()
        self.db.commit()
        logger.info(
            f"Successfully tracked recommendation exposure presented for run {run_id} at "
            f"{outcome.recommendation_presented_at}"
        )
        return outcome

    def track_acknowledged(
        self, run_id: uuid.UUID, acknowledged_at: Optional[datetime] = None
    ) -> Optional[RecommendationOutcome]:
        """Track that the recommendation run was acknowledged or interacted with by engineers.

        This is an MVP optional feature. In the future, this can be inferred from:
        - feedback clicks
        - PR interaction
        - manual acknowledgment
        """
        outcome = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run_id
        ).first()

        if not outcome:
            logger.warning(f"Cannot track acknowledgment: No RecommendationOutcome found for run {run_id}")
            return None

        # Immutability Check: acknowledgment timestamp is immutable once set
        if outcome.recommendation_acknowledged_at is not None:
            logger.info(
                f"Recommendation acknowledgment already tracked for run {run_id} at "
                f"{outcome.recommendation_acknowledged_at}. Keeping original timestamp."
            )
            return outcome

        outcome.recommendation_acknowledged_at = acknowledged_at or datetime.utcnow()
        
        # Advance status to ACKNOWLEDGED for any pre-acknowledged status
        if outcome.outcome_status in ("PENDING", "FOLLOWED", "PARTIALLY_FOLLOWED"):
            outcome.outcome_status = "ACKNOWLEDGED"

        self.db.commit()
        logger.info(
            f"Successfully tracked recommendation acknowledgment for run {run_id} at "
            f"{outcome.recommendation_acknowledged_at}"
        )
        return outcome
