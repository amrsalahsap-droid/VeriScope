"""
OutcomeExecutionCollector Service

Maps uploaded/current JUnit TestRun to a recommendation outcome.

This service:
1. Loads recommended tests for a recommendation run
2. Loads actual TestResults from a TestRun
3. Matches tests by test_identifier/stable_identity
4. Marks recommended tests with execution status (PASSED, FAILED, SKIPPED, NOT_RUN)
5. Identifies extra executed tests not recommended
6. Creates RecommendationOverride rows for extra tests
7. Updates RecommendationOutcome status (ACCEPTED, PARTIALLY_ACCEPTED, IGNORED)
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.test_result import TestRun, TestResult, TestCase
from app.models.recommendation import (
    RecommendationRun,
    RecommendedTest,
    RecommendationOutcome,
    RecommendationTestOutcome,
    RecommendationOverride,
)
from app.services.recommendation_test_outcome_updater import RecommendationTestOutcomeUpdater
from app.services.recommendation_override_updater import RecommendationOverrideUpdater

logger = logging.getLogger(__name__)


class OutcomeExecutionCollector:
    """
    Maps JUnit TestRun results to recommendation outcomes.
    
    Handles:
    - Test matching by stable_identity/test_identifier
    - Execution status mapping
    - Override creation for extra tests
    - Outcome status determination
    """

    def __init__(self, db: Session):
        self.db = db
        self.test_outcome_updater = RecommendationTestOutcomeUpdater(db)
        self.override_updater = RecommendationOverrideUpdater(db)

    def collect_execution_outcomes(
        self,
        recommendation_run_id: str,
        test_run_id: str,
    ) -> Dict:
        """
        Map TestRun results to recommendation outcomes.
        
        Args:
            recommendation_run_id: UUID of the recommendation run
            test_run_id: UUID of the test run to map
            
        Returns:
            Dict with collection results:
            - matched_tests: count of tests matched
            - unmatched_recommended: count of recommended tests not executed
            - extra_executed: count of executed tests not recommended
            - outcome_status: final outcome status
            - is_current_pr: whether test run matches current PR
        """
        # Load recommendation run
        rec_run = self.db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()
        
        if not rec_run:
            raise ValueError(f"Recommendation run {recommendation_run_id} not found")
        
        # Load test run
        test_run = self.db.query(TestRun).filter(
            TestRun.id == test_run_id
        ).first()
        
        if not test_run:
            raise ValueError(f"Test run {test_run_id} not found")
        
        # Verify same repository
        if test_run.repository_id != rec_run.repository_id:
            raise ValueError(
                f"Test run repository {test_run.repository_id} does not match "
                f"recommendation run repository {rec_run.repository_id}"
            )
        
        # Check if this is current PR execution
        is_current_pr = self._is_current_pr_execution(rec_run, test_run)
        
        logger.info(
            f"Collecting execution outcomes: recommendation_run={recommendation_run_id}, "
            f"test_run={test_run_id}, is_current_pr={is_current_pr}"
        )
        
        # Load recommended tests
        recommended_tests = self.db.query(RecommendedTest).filter(
            RecommendedTest.recommendation_run_id == recommendation_run_id
        ).all()
        
        # Load test results with test cases
        test_results = self.db.query(TestResult).join(TestCase).filter(
            TestResult.test_run_id == test_run_id
        ).all()
        
        # Build lookup maps
        recommended_map = {rt.test_identifier: rt for rt in recommended_tests}
        executed_map = {tr.test_case.stable_identity: tr for tr in test_results}
        
        # Match and update outcomes
        matched_count = 0
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        not_run_count = 0
        
        for test_identifier, recommended_test in recommended_map.items():
            test_result = executed_map.get(test_identifier)
            
            if test_result:
                # Test was executed
                execution_status = self._map_junit_status(test_result.status)
                matched_count += 1
                
                if execution_status == "PASSED":
                    passed_count += 1
                elif execution_status == "FAILED":
                    failed_count += 1
                elif execution_status == "SKIPPED":
                    skipped_count += 1
                
                # Update test outcome
                self.test_outcome_updater.update_test_outcome(
                    recommendation_run_id=recommendation_run_id,
                    recommended_test_id=recommended_test.id,
                    execution_status=execution_status,
                    actual_test_result_id=str(test_result.id),
                    actual_test_run_id=str(test_run_id),
                    duration_seconds=test_result.duration,
                    failure_message=test_result.failure_message,
                )
            else:
                # Test was not executed
                not_run_count += 1
                
                # Update test outcome as NOT_RUN
                self.test_outcome_updater.update_test_outcome(
                    recommendation_run_id=recommendation_run_id,
                    recommended_test_id=recommended_test.id,
                    execution_status="NOT_RUN",
                )
        
        # Identify extra executed tests (not recommended)
        extra_executed = set(executed_map.keys()) - set(recommended_map.keys())
        extra_count = len(extra_executed)
        
        # Create overrides for extra tests
        for test_identifier in extra_executed:
            test_result = executed_map[test_identifier]
            
            # Only create override if this is current PR execution
            if is_current_pr:
                self.override_updater.record_test_added(
                    recommendation_run_id=recommendation_run_id,
                    test_identifier=test_identifier,
                    reason="Test executed but not recommended",
                    source="OUTCOME_EXECUTION_COLLECTOR",
                )
                logger.info(f"Created TEST_ADDED override for extra test: {test_identifier}")
            else:
                logger.info(
                    f"Skipping override for extra test (historical execution): {test_identifier}"
                )
        
        # Determine outcome status
        outcome_status = self._determine_outcome_status(
            matched_count=matched_count,
            total_recommended=len(recommended_tests),
            extra_count=extra_count,
            is_current_pr=is_current_pr,
        )
        
        # Update recommendation outcome
        self._update_recommendation_outcome(
            recommendation_run_id=recommendation_run_id,
            outcome_status=outcome_status,
        )
        
        logger.info(
            f"Execution collection complete: matched={matched_count}, "
            f"passed={passed_count}, failed={failed_count}, skipped={skipped_count}, "
            f"not_run={not_run_count}, extra={extra_count}, "
            f"outcome_status={outcome_status}"
        )
        
        return {
            "matched_tests": matched_count,
            "passed_tests": passed_count,
            "failed_tests": failed_count,
            "skipped_tests": skipped_count,
            "not_run_tests": not_run_count,
            "extra_executed": extra_count,
            "unmatched_recommended": len(recommended_tests) - matched_count,
            "outcome_status": outcome_status,
            "is_current_pr": is_current_pr,
        }

    def _is_current_pr_execution(
        self,
        rec_run: RecommendationRun,
        test_run: TestRun,
    ) -> bool:
        """
        Determine if test run is for current PR.
        
        Current PR/head SHA match is strongest signal.
        """
        # If recommendation run has a PR, check if test run matches
        if rec_run.pull_request_id:
            if test_run.pull_request_id == rec_run.pull_request_id:
                return True
        
        # Check commit SHA match
        if rec_run.commit_sha and test_run.commit_sha:
            if rec_run.commit_sha == test_run.commit_sha:
                return True
        
        # If no clear match, assume historical
        return False

    def _map_junit_status(self, junit_status: str) -> str:
        """
        Map JUnit status to RecommendationTestOutcome execution_status.
        
        JUnit statuses: passed, failed, skipped, error
        Outcome statuses: PASSED, FAILED, SKIPPED, NOT_RUN
        """
        status_map = {
            "passed": "PASSED",
            "failed": "FAILED",
            "skipped": "SKIPPED",
            "error": "FAILED",  # Treat error as failure
        }
        
        return status_map.get(junit_status.lower(), "FAILED")

    def _determine_outcome_status(
        self,
        matched_count: int,
        total_recommended: int,
        extra_count: int,
        is_current_pr: bool,
    ) -> str:
        """
        Determine final outcome status.
        
        Rules:
        - ACCEPTED: All recommended tests executed, no extra tests
        - PARTIALLY_ACCEPTED: Some recommended tests executed, or extra tests present
        - IGNORED: No tests executed (historical or ignored)
        """
        if not is_current_pr:
            # Historical execution - don't change outcome status
            return "SHOWN"
        
        if total_recommended == 0:
            # No tests were recommended
            return "IGNORED"
        
        if matched_count == 0:
            # No recommended tests were executed
            return "IGNORED"
        
        if matched_count == total_recommended and extra_count == 0:
            # All recommended tests executed, no extras
            return "ACCEPTED"
        
        # Partial match or extra tests
        return "PARTIALLY_ACCEPTED"

    def _update_recommendation_outcome(
        self,
        recommendation_run_id: str,
        outcome_status: str,
    ):
        """
        Update RecommendationOutcome status.
        """
        outcome = self.db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == recommendation_run_id
        ).first()
        
        if outcome:
            outcome.outcome_status = outcome_status
            outcome.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Updated outcome status to {outcome_status}")
        else:
            logger.warning(f"No outcome found for recommendation run {recommendation_run_id}")
