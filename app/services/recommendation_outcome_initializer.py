"""
RecommendationOutcomeInitializer

Service for automatically creating outcome records after recommendation generation.

Design principles:
- Idempotent: can be called multiple times safely
- Safe on repeated recommendation generation
- No duplicate outcome rows
- Consolidates all outcome creation logic
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationOutcome,
    RecommendationTestOutcome,
    SuggestedScenarioOutcome,
    RecommendedTest,
    SuggestedTestScenario,
    ScenarioIntent,
)

logger = logging.getLogger("veriscope.recommendation_outcome_initializer")


@dataclass
class InitializationResult:
    """Result of outcome initialization."""
    outcome_created: bool
    test_outcomes_created: int
    scenario_outcomes_created: int
    test_outcomes_skipped: int
    scenario_outcomes_skipped: int
    errors: List[str]


class RecommendationOutcomeInitializer:
    """Service for initializing outcome records after recommendation generation."""
    
    @classmethod
    def initialize_outcomes(
        cls,
        db: Session,
        recommendation_run_id: UUID,
        repository_id: UUID,
        workspace_id: Optional[UUID] = None,
    ) -> InitializationResult:
        """
        Initialize all outcome records for a recommendation run.
        
        This is idempotent - can be called multiple times safely.
        It will:
        1. Create RecommendationOutcome if it doesn't exist
        2. Create RecommendationTestOutcome for each RecommendedTest
        3. Create SuggestedScenarioOutcome for each SuggestedTestScenario
        
        Returns:
            InitializationResult with counts of created/skipped records
        """
        result = InitializationResult(
            outcome_created=False,
            test_outcomes_created=0,
            scenario_outcomes_created=0,
            test_outcomes_skipped=0,
            scenario_outcomes_skipped=0,
            errors=[]
        )
        
        try:
            # Step 1: Create or get RecommendationOutcome
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                outcome = RecommendationOutcome(
                    recommendation_run_id=recommendation_run_id,
                    repository_id=repository_id,
                    workspace_id=workspace_id,
                    recommendation_snapshot_hash=str(recommendation_run_id),
                    outcome_status="SHOWN",
                    user_feedback="NOT_REVIEWED",
                    escaped_defect_detected=False,
                    rollback_occurred=False
                )
                db.add(outcome)
                db.flush()  # Get the outcome ID
                result.outcome_created = True
                logger.info(f"Created RecommendationOutcome for run {recommendation_run_id}")
            else:
                logger.info(f"RecommendationOutcome already exists for run {recommendation_run_id}")
            
            # Step 2: Create RecommendationTestOutcome for each RecommendedTest
            recommended_tests = db.query(RecommendedTest).filter(
                RecommendedTest.recommendation_run_id == recommendation_run_id
            ).all()
            
            for recommended_test in recommended_tests:
                existing_test_outcome = db.query(RecommendationTestOutcome).filter(
                    RecommendationTestOutcome.recommendation_run_id == recommendation_run_id,
                    RecommendationTestOutcome.test_identifier == recommended_test.test_identifier
                ).first()
                
                if not existing_test_outcome:
                    test_outcome = RecommendationTestOutcome(
                        recommendation_outcome_id=outcome.id,
                        recommendation_run_id=recommendation_run_id,
                        recommended_test_id=recommended_test.id,
                        test_identifier=recommended_test.test_identifier,
                        recommendation_action="RUN_EXISTING_TEST",
                        execution_status="NOT_RUN",
                        engineer_decision="NOT_DECIDED"
                    )
                    db.add(test_outcome)
                    result.test_outcomes_created += 1
                else:
                    # Update the recommendation_outcome_id if it was None
                    if existing_test_outcome.recommendation_outcome_id is None:
                        existing_test_outcome.recommendation_outcome_id = outcome.id
                    result.test_outcomes_skipped += 1
            
            # Step 3: Create SuggestedScenarioOutcome for each SuggestedTestScenario
            suggested_scenarios = db.query(SuggestedTestScenario).filter(
                SuggestedTestScenario.recommendation_run_id == recommendation_run_id
            ).all()
            
            for scenario in suggested_scenarios:
                existing_scenario_outcome = db.query(SuggestedScenarioOutcome).filter(
                    SuggestedScenarioOutcome.recommendation_run_id == recommendation_run_id,
                    SuggestedScenarioOutcome.suggested_scenario_id == scenario.id
                ).first()
                
                if not existing_scenario_outcome:
                    # Get scenario_intent_key from scenario_intent if available
                    scenario_intent_key = None
                    if scenario.scenario_intent_id:
                        intent = db.query(ScenarioIntent).filter(
                            ScenarioIntent.id == scenario.scenario_intent_id
                        ).first()
                        if intent:
                            scenario_intent_key = intent.canonical_key
                    
                    scenario_outcome = SuggestedScenarioOutcome(
                        recommendation_outcome_id=outcome.id,
                        recommendation_run_id=recommendation_run_id,
                        suggested_scenario_id=scenario.id,
                        scenario_intent_key=scenario_intent_key or f"scenario_{scenario.id}",
                        engineer_decision="NOT_DECIDED",
                        execution_status="NOT_EXECUTED",
                        converted_to_test=False
                    )
                    db.add(scenario_outcome)
                    result.scenario_outcomes_created += 1
                else:
                    # Update the recommendation_outcome_id if it was None
                    if existing_scenario_outcome.recommendation_outcome_id is None:
                        existing_scenario_outcome.recommendation_outcome_id = outcome.id
                    result.scenario_outcomes_skipped += 1
            
            db.commit()
            logger.info(
                f"Initialized outcomes for run {recommendation_run_id}: "
                f"outcome_created={result.outcome_created}, "
                f"test_outcomes={result.test_outcomes_created}/{result.test_outcomes_created + result.test_outcomes_skipped}, "
                f"scenario_outcomes={result.scenario_outcomes_created}/{result.scenario_outcomes_created + result.scenario_outcomes_skipped}"
            )
            
        except Exception as exc:
            db.rollback()
            msg = f"Failed to initialize outcomes for run {recommendation_run_id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
        
        return result
    
    @classmethod
    def ensure_outcome_exists(
        cls,
        db: Session,
        recommendation_run_id: UUID,
    ) -> Optional[RecommendationOutcome]:
        """
        Ensure a RecommendationOutcome exists for a run.
        
        This is a lightweight check that only creates the outcome record
        without creating test/scenario outcomes. Useful for cases where
        you just need the outcome record to exist.
        """
        try:
            outcome = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id == recommendation_run_id
            ).first()
            
            if not outcome:
                from app.models.recommendation import RecommendationRun
                run = db.query(RecommendationRun).filter(
                    RecommendationRun.id == recommendation_run_id
                ).first()
                
                if run:
                    outcome = RecommendationOutcome(
                        recommendation_run_id=recommendation_run_id,
                        repository_id=run.repository_id,
                        workspace_id=run.workspace_id,
                        recommendation_snapshot_hash=str(recommendation_run_id),
                        outcome_status="SHOWN",
                        user_feedback="NOT_REVIEWED",
                        escaped_defect_detected=False,
                        rollback_occurred=False
                    )
                    db.add(outcome)
                    db.commit()
                    logger.info(f"Created RecommendationOutcome for run {recommendation_run_id}")
            
            return outcome
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to ensure outcome exists: {exc}")
            return None
