"""
Scenario Coverage Matrix Builder
================================
Builds scenario coverage matrix from database records for API responses.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.api.models.scenario_coverage_matrix import (
    ScenarioCoverageMatrix,
    ScenarioCoverageMatrixItem,
    ExistingTestReference,
    SuggestedScenarioReference,
    RecommendationAction
)
from app.models.recommendation import ScenarioIntent, RecommendationRun, SuggestedTestScenario, RecommendationTest
from app.models.test_result import TestCase
from app.services.scenario_coverage_resolver import FinalCoverageStatus


class ScenarioCoverageMatrixBuilder:
    """
    Builds scenario coverage matrix from database records.
    
    Combines scenario intents, coverage statuses, existing tests, and suggested scenarios
    into a unified matrix for API responses.
    """
    
    @classmethod
    def determine_recommendation_action(
        cls,
        final_status: str,
        priority: str,
        automation_candidate: bool,
        has_existing_test: bool,
        current_pr_execution_status: str
    ) -> RecommendationAction:
        """
        Determine the recommended action for a scenario intent.
        
        Args:
            final_status: Final coverage status from ScenarioCoverageResolver
            priority: Priority level (MUST, SHOULD, OPTIONAL)
            automation_candidate: Whether the scenario can be automated
            has_existing_test: Whether an existing test covers this intent
            current_pr_execution_status: Current PR execution status
        
        Returns:
            RecommendationAction
        """
        # ALREADY_VERIFIED: already covered and verified
        if final_status == FinalCoverageStatus.COVERED_AND_VERIFIED.value:
            return RecommendationAction.ALREADY_VERIFIED
        
        # RUN_EXISTING_TEST: existing test exists but not run on PR
        if final_status == FinalCoverageStatus.COVERED_NOT_RUN.value and has_existing_test:
            return RecommendationAction.RUN_EXISTING_TEST
        
        # EXPAND_COVERAGE: partial coverage, expand existing test
        if final_status == FinalCoverageStatus.PARTIALLY_COVERED.value:
            return RecommendationAction.EXPAND_COVERAGE
        
        # EXECUTE_MANUAL_SCENARIO: weak evidence, manual validation needed
        if final_status == FinalCoverageStatus.SUGGEST_MANUAL_VALIDATION.value:
            return RecommendationAction.EXECUTE_MANUAL_SCENARIO
        
        # OPTIONAL_MONITOR: low priority scenarios
        if priority == "OPTIONAL":
            return RecommendationAction.OPTIONAL_MONITOR
        
        # ADD_AUTOMATED_TEST: default for missing automated coverage
        if automation_candidate:
            return RecommendationAction.ADD_AUTOMATED_TEST
        else:
            return RecommendationAction.EXECUTE_MANUAL_SCENARIO
    
    @classmethod
    def build_existing_test_references(
        cls,
        scenario_intent: ScenarioIntent,
        existing_test_coverages: List[Any],
        test_cases: List[TestCase]
    ) -> List[ExistingTestReference]:
        """
        Build existing test references for a scenario intent.
        
        Args:
            scenario_intent: The scenario intent
            existing_test_coverages: List of ExistingTestScenarioCoverage objects
            test_cases: List of TestCase records
        
        Returns:
            List of ExistingTestReference objects
        """
        references = []
        canonical_key = scenario_intent.canonical_key
        
        # Find matching coverages
        for coverage in existing_test_coverages:
            if coverage.scenario_intent_key == canonical_key:
                # Find corresponding test case
                test_case = None
                for tc in test_cases:
                    if tc.stable_identity == coverage.test_identifier:
                        test_case = tc
                        break
                
                references.append(ExistingTestReference(
                    test_identifier=coverage.test_identifier,
                    test_name=test_case.test_name if test_case else coverage.test_identifier,
                    suite_name=test_case.suite_name if test_case else None,
                    class_name=test_case.suite_name if test_case else None,
                    last_execution_status=None,  # Could be enhanced with execution data
                    last_execution_timestamp=None  # Could be enhanced with execution data
                ))
        
        return references
    
    @classmethod
    def build_suggested_scenario_references(
        cls,
        scenario_intent: ScenarioIntent,
        suggested_scenarios: List[SuggestedTestScenario]
    ) -> List[SuggestedScenarioReference]:
        """
        Build suggested scenario references for a scenario intent.
        
        Args:
            scenario_intent: The scenario intent
            suggested_scenarios: List of SuggestedTestScenario records
        
        Returns:
            List of SuggestedScenarioReference objects
        """
        references = []
        intent_id = scenario_intent.id
        
        for scenario in suggested_scenarios:
            if scenario.scenario_intent_id == intent_id:
                references.append(SuggestedScenarioReference(
                    scenario_id=str(scenario.id),
                    title=scenario.title,
                    testing_type=scenario.testing_type,
                    priority=scenario.priority,
                    automation_candidate=scenario.automation_candidate,
                    preconditions=scenario.preconditions or [],
                    steps=scenario.steps or [],
                    expected_result=scenario.expected_result,
                    test_data=scenario.test_data or {}
                ))
        
        return references
    
    @classmethod
    def build_matrix_item(
        cls,
        scenario_intent: ScenarioIntent,
        coverage_status: Optional[Any],
        existing_test_coverages: List[Any],
        suggested_scenarios: List[SuggestedTestScenario],
        test_cases: List[TestCase]
    ) -> ScenarioCoverageMatrixItem:
        """
        Build a single matrix item for a scenario intent.
        
        Args:
            scenario_intent: The scenario intent
            coverage_status: ScenarioCoverageStatus object
            existing_test_coverages: List of ExistingTestScenarioCoverage objects
            suggested_scenarios: List of SuggestedTestScenario records
            test_cases: List of TestCase records
        
        Returns:
            ScenarioCoverageMatrixItem
        """
        # Extract coverage status information
        code_coverage_status = "NONE"
        current_pr_execution_status = "NOT_RUN"
        final_status = "MISSING_AUTOMATED_COVERAGE"
        confidence = "MEDIUM"
        
        if coverage_status:
            code_coverage_status = coverage_status.code_coverage_status.value
            current_pr_execution_status = coverage_status.current_pr_execution_status.value
            final_status = coverage_status.final_status.value
            confidence = coverage_status.confidence
        
        # Build existing test references
        existing_tests = cls.build_existing_test_references(
            scenario_intent=scenario_intent,
            existing_test_coverages=existing_test_coverages,
            test_cases=test_cases
        )
        
        # Build suggested scenario references
        suggested_scenario_refs = cls.build_suggested_scenario_references(
            scenario_intent=scenario_intent,
            suggested_scenarios=suggested_scenarios
        )
        
        # Determine priority from scenario intent
        priority = scenario_intent.priority
        
        # Determine recommendation action
        has_existing_test = len(existing_tests) > 0
        automation_candidate = True  # Default, could be enhanced from suggested scenarios
        if suggested_scenario_refs:
            automation_candidate = suggested_scenario_refs[0].automation_candidate
        
        recommendation_action = cls.determine_recommendation_action(
            final_status=final_status,
            priority=priority,
            automation_candidate=automation_candidate,
            has_existing_test=has_existing_test,
            current_pr_execution_status=current_pr_execution_status
        )
        
        # Build evidence reason
        evidence_reason = cls._build_evidence_reason(
            final_status=final_status,
            code_coverage_status=code_coverage_status,
            current_pr_execution_status=current_pr_execution_status,
            has_existing_test=has_existing_test,
            confidence=confidence
        )
        
        return ScenarioCoverageMatrixItem(
            scenario_intent_key=scenario_intent.canonical_key,
            title=scenario_intent.title,
            impacted_area=f"{scenario_intent.domain}.{scenario_intent.feature}",
            testing_type=scenario_intent.layer,
            priority=priority,
            existing_tests=existing_tests,
            suggested_scenarios=suggested_scenario_refs,
            code_coverage_status=code_coverage_status,
            current_pr_execution_status=current_pr_execution_status,
            final_status=final_status,
            recommendation_action=recommendation_action,
            evidence_reason=evidence_reason,
            confidence=confidence,
            domain=scenario_intent.domain,
            feature=scenario_intent.feature,
            layer=scenario_intent.layer,
            case_type=scenario_intent.case_type
        )
    
    @classmethod
    def _build_evidence_reason(
        cls,
        final_status: str,
        code_coverage_status: str,
        current_pr_execution_status: str,
        has_existing_test: bool,
        confidence: str
    ) -> str:
        """
        Build evidence reason string for the matrix item.
        
        Args:
            final_status: Final coverage status
            code_coverage_status: Code coverage status
            current_pr_execution_status: Current PR execution status
            has_existing_test: Whether existing test exists
            confidence: Confidence level
        
        Returns:
            Evidence reason string
        """
        parts = []
        
        if has_existing_test:
            parts.append("Existing automated test detected")
        else:
            parts.append("No existing automated test")
        
        if code_coverage_status != "NONE":
            parts.append(f"Code coverage: {code_coverage_status}")
        
        if current_pr_execution_status != "NOT_RUN":
            parts.append(f"Current PR execution: {current_pr_execution_status}")
        
        parts.append(f"Confidence: {confidence}")
        
        return ". ".join(parts) + "."
    
    @classmethod
    def build_matrix(
        cls,
        db: Session,
        recommendation_run_id: str
    ) -> ScenarioCoverageMatrix:
        """
        Build complete scenario coverage matrix for a recommendation run.
        
        Args:
            db: Database session
            recommendation_run_id: The recommendation run ID
        
        Returns:
            ScenarioCoverageMatrix
        """
        # Fetch recommendation run
        run = db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()
        
        if not run:
            raise ValueError(f"Recommendation run {recommendation_run_id} not found")
        
        # Fetch scenario intents for this run
        scenario_intents = db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == recommendation_run_id
        ).all()
        
        # Fetch suggested scenarios for this run
        suggested_scenarios = db.query(SuggestedTestScenario).filter(
            SuggestedTestScenario.recommendation_run_id == recommendation_run_id
        ).all()
        
        # Fetch recommendation tests for this run
        recommendation_tests = db.query(RecommendationTest).filter(
            RecommendationTest.recommendation_run_id == recommendation_run_id
        ).all()
        
        # Fetch test cases for the repository
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == run.repository_id
        ).all()
        
        # Map existing test coverages (simplified - could be enhanced with actual coverage data)
        existing_test_coverages = []
        for rec_test in recommendation_tests:
            if rec_test.scenario_intent_id:
                intent = db.query(ScenarioIntent).filter(
                    ScenarioIntent.id == rec_test.scenario_intent_id
                ).first()
                if intent:
                    # Create a simple coverage object
                    class SimpleCoverage:
                        def __init__(self, key, test_id):
                            self.scenario_intent_key = key
                            self.test_identifier = test_id
                            self.confidence = "HIGH"
                    
                    existing_test_coverages.append(
                        SimpleCoverage(intent.canonical_key, rec_test.test_case_id)
                    )
        
        # Build matrix items
        items = []
        status_counts = {
            "COVERED_AND_VERIFIED": 0,
            "COVERED_NOT_RUN": 0,
            "PARTIALLY_COVERED": 0,
            "MISSING_AUTOMATED_COVERAGE": 0,
            "SUGGEST_MANUAL_VALIDATION": 0
        }
        
        for intent in scenario_intents:
            # Find coverage status (simplified - could be enhanced with actual resolver)
            coverage_status = None  # Would come from ScenarioCoverageResolver
            
            item = cls.build_matrix_item(
                scenario_intent=intent,
                coverage_status=coverage_status,
                existing_test_coverages=existing_test_coverages,
                suggested_scenarios=suggested_scenarios,
                test_cases=test_cases
            )
            items.append(item)
            
            # Count statuses
            if item.final_status in status_counts:
                status_counts[item.final_status] += 1
        
        return ScenarioCoverageMatrix(
            recommendation_run_id=str(recommendation_run_id),
            repository_id=str(run.repository_id),
            pull_request_id=str(run.pull_request_id) if run.pull_request_id else None,
            total_scenarios=len(items),
            covered_and_verified=status_counts["COVERED_AND_VERIFIED"],
            covered_not_run=status_counts["COVERED_NOT_RUN"],
            partially_covered=status_counts["PARTIALLY_COVERED"],
            missing_automated_coverage=status_counts["MISSING_AUTOMATED_COVERAGE"],
            suggest_manual_validation=status_counts["SUGGEST_MANUAL_VALIDATION"],
            items=items,
            generated_at=datetime.utcnow().isoformat()
        )
