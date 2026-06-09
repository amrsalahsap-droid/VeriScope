"""
RecommendationTestOutcomeUpdater

Service for idempotently updating RecommendationTestOutcome records
when execution results become available.

Design principles:
- Idempotent: can be called multiple times safely
- Append-safe: never deletes historical data
- Distinguishes recommended-but-not-run from removed
- Skipped in CI means selected but skipped, not missing
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationTestOutcome, RecommendationOutcome
from app.models.test_result import TestResult, TestRun

logger = logging.getLogger("veriscope.recommendation_test_outcome_updater")


@dataclass
class TestOutcomeUpdateResult:
    """Result of updating test outcomes."""
    updated_count: int
    created_count: int
    skipped_count: int
    errors: List[str]


class RecommendationTestOutcomeUpdater:
    """Service for updating test outcomes with execution results."""
    
    @classmethod
    def update_from_test_run(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        test_run_id: UUID,
    ) -> TestOutcomeUpdateResult:
        """
        Update test outcomes from a TestRun.
        
        This is idempotent - can be called multiple times safely.
        It will update existing outcomes or create new ones for tests
        that were executed but not in the original recommendation.
        """
        result = TestOutcomeUpdateResult(
            updated_count=0,
            created_count=0,
            skipped_count=0,
            errors=[]
        )
        
        try:
            # Get the recommendation outcome
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                result.errors.append(f"No RecommendationOutcome found for run {recommendation_run_id}")
                return result
            
            # Get test results from the test run
            test_results = db.query(TestResult).filter(
                TestResult.test_run_id == test_run_id
            ).all()
            
            for test_result in test_results:
                if not test_result.test_case:
                    result.skipped_count += 1
                    continue
                
                test_identifier = test_result.test_case.stable_identity
                
                # Find or create test outcome
                test_outcome = db.query(RecommendationTestOutcome).filter(
                    RecommendationTestOutcome.recommendation_outcome_id == outcome.id,
                    RecommendationTestOutcome.test_identifier == test_identifier
                ).first()
                
                # Map test result status to execution_status
                execution_status = cls._map_execution_status(test_result.status)
                
                if test_outcome:
                    # Update existing outcome (idempotent)
                    test_outcome.execution_status = execution_status
                    test_outcome.actual_test_result_id = test_result.id
                    test_outcome.actual_test_run_id = test_run_id
                    test_outcome.duration_seconds = test_result.duration
                    if test_result.status == "failed":
                        test_outcome.failure_message = "Test failed"
                    result.updated_count += 1
                else:
                    # Create new outcome for test that ran but wasn't recommended
                    test_outcome = RecommendationTestOutcome(
                        recommendation_outcome_id=outcome.id,
                        recommendation_run_id=recommendation_run_id,
                        test_identifier=test_identifier,
                        recommendation_action="RUN_EXISTING_TEST",
                        execution_status=execution_status,
                        engineer_decision="KEPT",  # Manually added/kept
                        actual_test_result_id=test_result.id,
                        actual_test_run_id=test_run_id,
                        duration_seconds=test_result.duration,
                        failure_message="Test failed" if test_result.status == "failed" else None
                    )
                    db.add(test_outcome)
                    result.created_count += 1
            
            db.commit()
            logger.info(f"Updated test outcomes for run {recommendation_run_id}: {result}")
            
        except Exception as exc:
            db.rollback()
            msg = f"Failed to update test outcomes: {exc}"
            logger.error(msg)
            result.errors.append(msg)
        
        return result
    
    @classmethod
    def update_engineer_decision(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        test_identifier: str,
        engineer_decision: str,
    ) -> bool:
        """
        Update engineer decision for a specific test.
        
        engineer_decision: KEPT, REMOVED, NOT_DECIDED
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            test_outcome = db.query(RecommendationTestOutcome).filter(
                RecommendationTestOutcome.recommendation_outcome_id == outcome.id,
                RecommendationTestOutcome.test_identifier == test_identifier
            ).first()
            
            if test_outcome:
                test_outcome.engineer_decision = engineer_decision
                db.commit()
                return True
            
            return False
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to update engineer decision: {exc}")
            return False
    
    @classmethod
    def update_recommendation_action(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        test_identifier: str,
        recommendation_action: str,
    ) -> bool:
        """
        Update recommendation action for a specific test.
        
        recommendation_action: RUN_EXISTING_TEST, SKIP, OPTIONAL_MONITOR
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                return False
            
            test_outcome = db.query(RecommendationTestOutcome).filter(
                RecommendationTestOutcome.recommendation_outcome_id == outcome.id,
                RecommendationTestOutcome.test_identifier == test_identifier
            ).first()
            
            if test_outcome:
                test_outcome.recommendation_action = recommendation_action
                db.commit()
                return True
            
            return False
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to update recommendation action: {exc}")
            return False
    
    @staticmethod
    def _map_execution_status(test_result_status: str) -> str:
        """Map TestResult status to RecommendationTestOutcome execution_status."""
        status_map = {
            "passed": "PASSED",
            "failed": "FAILED",
            "skipped": "SKIPPED",
            "error": "FAILED",
            "quarantined": "SKIPPED",
        }
        return status_map.get(test_result_status.lower(), "UNKNOWN")
