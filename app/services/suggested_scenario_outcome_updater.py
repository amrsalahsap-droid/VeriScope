"""
SuggestedScenarioOutcomeUpdater

Service for idempotently updating SuggestedScenarioOutcome records
when engineers make decisions or convert scenarios to tests.

Design principles:
- Idempotent: can be called multiple times safely
- Append-safe: never deletes historical data
- Tracks engineer decisions on missing scenarios
- Links automated tests created from scenarios
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import SuggestedScenarioOutcome, RecommendationOutcome

logger = logging.getLogger("veriscope.suggested_scenario_outcome_updater")


@dataclass
class ScenarioOutcomeUpdateResult:
    """Result of updating scenario outcomes."""
    updated_count: int
    errors: List[str]


class SuggestedScenarioOutcomeUpdater:
    """Service for updating scenario outcomes with engineer decisions and test links."""
    
    @classmethod
    def update_engineer_decision(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        suggested_scenario_id: UUID,
        engineer_decision: str,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Update engineer decision for a specific suggested scenario.
        
        engineer_decision: ACCEPTED, DISMISSED, MARKED_IMPORTANT, NOT_DECIDED
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            scenario_outcome = db.query(SuggestedScenarioOutcome).filter(
                SuggestedScenarioOutcome.recommendation_outcome_id == outcome.id,
                SuggestedScenarioOutcome.suggested_scenario_id == suggested_scenario_id
            ).first()
            
            if scenario_outcome:
                scenario_outcome.engineer_decision = engineer_decision
                if comment is not None:
                    scenario_outcome.comment = comment
                db.commit()
                return True
            
            return False
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to update engineer decision: {exc}")
            return False
    
    @classmethod
    def link_to_test(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        suggested_scenario_id: UUID,
        test_identifier: str,
    ) -> bool:
        """
        Link a suggested scenario to an automated test that was created from it.
        
        This should be called when an engineer creates an automated test
        based on a suggested scenario.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            scenario_outcome = db.query(SuggestedScenarioOutcome).filter(
                SuggestedScenarioOutcome.recommendation_outcome_id == outcome.id,
                SuggestedScenarioOutcome.suggested_scenario_id == suggested_scenario_id
            ).first()
            
            if scenario_outcome:
                scenario_outcome.converted_to_test = True
                scenario_outcome.linked_test_identifier = test_identifier
                scenario_outcome.engineer_decision = "ACCEPTED"
                db.commit()
                return True
            
            return False
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to link scenario to test: {exc}")
            return False
    
    @classmethod
    def update_execution_status(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        suggested_scenario_id: UUID,
        execution_status: str,
    ) -> bool:
        """
        Update execution status for a scenario that was executed manually.
        
        execution_status: NOT_EXECUTED, PASSED, FAILED, BLOCKED, UNKNOWN
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            scenario_outcome = db.query(SuggestedScenarioOutcome).filter(
                SuggestedScenarioOutcome.recommendation_outcome_id == outcome.id,
                SuggestedScenarioOutcome.suggested_scenario_id == suggested_scenario_id
            ).first()
            
            if scenario_outcome:
                scenario_outcome.execution_status = execution_status
                db.commit()
                return True
            
            return False
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to update execution status: {exc}")
            return False
    
    @classmethod
    def get_scenario_outcomes(
        cls,
        db: Session,
        recommendation_run_id: UUID,
    ) -> List[SuggestedScenarioOutcome]:
        """
        Get all scenario outcomes for a recommendation run.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return []
            
            return db.query(SuggestedScenarioOutcome).filter(
                SuggestedScenarioOutcome.recommendation_outcome_id == outcome.id
            ).all()
            
        except Exception as exc:
            logger.error(f"Failed to get scenario outcomes: {exc}")
            return []
    
    @classmethod
    def get_accepted_scenarios(
        cls,
        db: Session,
        repository_id: UUID,
        limit: int = 50,
    ) -> List[SuggestedScenarioOutcome]:
        """
        Get accepted scenarios for a repository, ordered by recency.
        
        This is useful for learning which scenarios engineers care about
        and should be prioritized in future recommendations.
        """
        try:
            return db.query(SuggestedScenarioOutcome).join(
                RecommendationOutcome,
                SuggestedScenarioOutcome.recommendation_outcome_id == RecommendationOutcome.id
            ).filter(
                RecommendationOutcome.repository_id == repository_id,
                SuggestedScenarioOutcome.engineer_decision.in_(["ACCEPTED", "MARKED_IMPORTANT"])
            ).order_by(
                SuggestedScenarioOutcome.created_at.desc()
            ).limit(limit).all()
            
        except Exception as exc:
            logger.error(f"Failed to get accepted scenarios: {exc}")
            return []
