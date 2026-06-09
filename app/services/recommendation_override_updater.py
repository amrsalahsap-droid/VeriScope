"""
RecommendationOverrideUpdater

Service for creating and managing RecommendationOverride records.

Design principles:
- Idempotent: can be called multiple times safely
- Append-only: never deletes override records
- Captures high-value learning signals (added tests)
- Captures negative learning signals (removed tests)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationOverride, RecommendationOutcome

logger = logging.getLogger("veriscope.recommendation_override_updater")


@dataclass
class OverrideCreateResult:
    """Result of creating override records."""
    created_count: int
    errors: List[str]


class RecommendationOverrideUpdater:
    """Service for creating override records from engineer actions."""
    
    @classmethod
    def record_test_added(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        test_identifier: str,
        reason: Optional[str] = None,
        source: str = "MANUAL_UI",
        created_by: Optional[str] = None,
    ) -> bool:
        """
        Record that a test was manually added by an engineer.
        
        This is a high-value learning signal - the engineer found this test
        important enough to add it to the recommendation.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            # Check if this override already exists (idempotent)
            existing = db.query(RecommendationOverride).filter(
                RecommendationOverride.recommendation_outcome_id == outcome.id,
                RecommendationOverride.test_identifier == test_identifier,
                RecommendationOverride.override_type == "TEST_ADDED"
            ).first()
            
            if existing:
                return True  # Already recorded
            
            override = RecommendationOverride(
                recommendation_outcome_id=outcome.id,
                recommendation_run_id=recommendation_run_id,
                override_type="TEST_ADDED",
                test_identifier=test_identifier,
                reason=reason,
                source=source,
                created_by=created_by
            )
            db.add(override)
            db.commit()
            return True
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to record test added: {exc}")
            return False
    
    @classmethod
    def record_test_removed(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        test_identifier: str,
        reason: Optional[str] = None,
        source: str = "MANUAL_UI",
        created_by: Optional[str] = None,
    ) -> bool:
        """
        Record that a test was manually removed by an engineer.
        
        This is a negative learning signal - the engineer found this test
        unnecessary or problematic.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            # Check if this override already exists (idempotent)
            existing = db.query(RecommendationOverride).filter(
                RecommendationOverride.recommendation_outcome_id == outcome.id,
                RecommendationOverride.test_identifier == test_identifier,
                RecommendationOverride.override_type == "TEST_REMOVED"
            ).first()
            
            if existing:
                return True  # Already recorded
            
            override = RecommendationOverride(
                recommendation_outcome_id=outcome.id,
                recommendation_run_id=recommendation_run_id,
                override_type="TEST_REMOVED",
                test_identifier=test_identifier,
                reason=reason,
                source=source,
                created_by=created_by
            )
            db.add(override)
            db.commit()
            return True
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to record test removed: {exc}")
            return False
    
    @classmethod
    def record_scenario_added(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        scenario_intent_key: str,
        reason: Optional[str] = None,
        source: str = "MANUAL_UI",
        created_by: Optional[str] = None,
    ) -> bool:
        """
        Record that a scenario was manually added by an engineer.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            # Check if this override already exists (idempotent)
            existing = db.query(RecommendationOverride).filter(
                RecommendationOverride.recommendation_outcome_id == outcome.id,
                RecommendationOverride.scenario_intent_key == scenario_intent_key,
                RecommendationOverride.override_type == "SCENARIO_ADDED"
            ).first()
            
            if existing:
                return True  # Already recorded
            
            override = RecommendationOverride(
                recommendation_outcome_id=outcome.id,
                recommendation_run_id=recommendation_run_id,
                override_type="SCENARIO_ADDED",
                scenario_intent_key=scenario_intent_key,
                reason=reason,
                source=source,
                created_by=created_by
            )
            db.add(override)
            db.commit()
            return True
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to record scenario added: {exc}")
            return False
    
    @classmethod
    def record_scenario_removed(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        scenario_intent_key: str,
        reason: Optional[str] = None,
        source: str = "MANUAL_UI",
        created_by: Optional[str] = None,
    ) -> bool:
        """
        Record that a scenario was manually removed by an engineer.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            # Check if this override already exists (idempotent)
            existing = db.query(RecommendationOverride).filter(
                RecommendationOverride.recommendation_outcome_id == outcome.id,
                RecommendationOverride.scenario_intent_key == scenario_intent_key,
                RecommendationOverride.override_type == "SCENARIO_REMOVED"
            ).first()
            
            if existing:
                return True  # Already recorded
            
            override = RecommendationOverride(
                recommendation_outcome_id=outcome.id,
                recommendation_run_id=recommendation_run_id,
                override_type="SCENARIO_REMOVED",
                scenario_intent_key=scenario_intent_key,
                reason=reason,
                source=source,
                created_by=created_by
            )
            db.add(override)
            db.commit()
            return True
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to record scenario removed: {exc}")
            return False
    
    @classmethod
    def get_overrides_for_run(
        cls,
        db: Session,
        recommendation_run_id: UUID,
    ) -> List[RecommendationOverride]:
        """
        Get all override records for a recommendation run.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return []
            
            return db.query(RecommendationOverride).filter(
                RecommendationOverride.recommendation_outcome_id == outcome.id
            ).order_by(RecommendationOverride.created_at.asc()).all()
            
        except Exception as exc:
            logger.error(f"Failed to get overrides: {exc}")
            return []
    
    @classmethod
    def get_learning_signals(
        cls,
        db: Session,
        repository_id: UUID,
        limit: int = 100,
    ) -> dict:
        """
        Get learning signals from overrides for a repository.
        
        Returns:
            {
                "added_tests": List of test identifiers frequently added
                "removed_tests": List of test identifiers frequently removed
                "added_scenarios": List of scenario intent keys frequently added
            }
        """
        try:
            from sqlalchemy import func
            
            # Get frequently added tests
            added_tests = db.query(
                RecommendationOverride.test_identifier,
                func.count(RecommendationOverride.id).label('count')
            ).join(
                RecommendationOutcome,
                RecommendationOverride.recommendation_outcome_id == RecommendationOutcome.id
            ).filter(
                RecommendationOutcome.repository_id == repository_id,
                RecommendationOverride.override_type == "TEST_ADDED"
            ).group_by(
                RecommendationOverride.test_identifier
            ).order_by(
                func.count(RecommendationOverride.id).desc()
            ).limit(limit).all()
            
            # Get frequently removed tests
            removed_tests = db.query(
                RecommendationOverride.test_identifier,
                func.count(RecommendationOverride.id).label('count')
            ).join(
                RecommendationOutcome,
                RecommendationOverride.recommendation_outcome_id == RecommendationOutcome.id
            ).filter(
                RecommendationOutcome.repository_id == repository_id,
                RecommendationOverride.override_type == "TEST_REMOVED"
            ).group_by(
                RecommendationOverride.test_identifier
            ).order_by(
                func.count(RecommendationOverride.id).desc()
            ).limit(limit).all()
            
            # Get frequently added scenarios
            added_scenarios = db.query(
                RecommendationOverride.scenario_intent_key,
                func.count(RecommendationOverride.id).label('count')
            ).join(
                RecommendationOutcome,
                RecommendationOverride.recommendation_outcome_id == RecommendationOutcome.id
            ).filter(
                RecommendationOutcome.repository_id == repository_id,
                RecommendationOverride.override_type == "SCENARIO_ADDED"
            ).group_by(
                RecommendationOverride.scenario_intent_key
            ).order_by(
                func.count(RecommendationOverride.id).desc()
            ).limit(limit).all()
            
            return {
                "added_tests": [{"test_identifier": t[0], "count": t[1]} for t in added_tests],
                "removed_tests": [{"test_identifier": t[0], "count": t[1]} for t in removed_tests],
                "added_scenarios": [{"scenario_intent_key": s[0], "count": s[1]} for s in added_scenarios],
            }
            
        except Exception as exc:
            logger.error(f"Failed to get learning signals: {exc}")
            return {"added_tests": [], "removed_tests": [], "added_scenarios": []}
