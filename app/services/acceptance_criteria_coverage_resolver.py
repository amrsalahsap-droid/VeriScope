"""Acceptance Criteria Coverage Resolver service.

Determines whether each acceptance criterion is covered by existing tests,
suggested scenarios, or missing.
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from app.schemas.acceptance_criteria import AcceptanceCriteriaCoverageStatus, AcceptanceCriteriaCoverageReport
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase, TestResult
from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage
from app.models.recommendation import SuggestedTestScenario
from app.models.test_coverage_link import TestCoverageLink
from app.models.business_behavior_mapping import BusinessBehaviorMapping


class AcceptanceCriteriaCoverageResolver:
    """Resolves coverage status for acceptance criteria."""
    
    # Coverage status constants
    COVERED_BY_EXISTING_TEST = "COVERED_BY_EXISTING_TEST"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    MISSING_TEST_COVERAGE = "MISSING_TEST_COVERAGE"
    VERIFIED_ON_CURRENT_PR = "VERIFIED_ON_CURRENT_PR"
    MANUAL_VALIDATION_REQUIRED = "MANUAL_VALIDATION_REQUIRED"
    UNKNOWN = "UNKNOWN"
    
    # Execution status constants
    EXECUTED = "EXECUTED"
    NOT_EXECUTED = "NOT_EXECUTED"
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the resolver with optional database session."""
        self.db = db
    
    def resolve_coverage(
        self,
        acceptance_criteria: List[AcceptanceCriterion],
        existing_tests: List[TestCase],
        behavior_scenario_coverages: List[BehaviorScenarioCoverage],
        suggested_scenarios: List[SuggestedTestScenario],
        test_coverage_links: List[TestCoverageLink],
        business_behavior_mappings: List[BusinessBehaviorMapping],
        current_pr_test_runs: Optional[List[TestResult]] = None,
        repository_id: Optional[str] = None
    ) -> AcceptanceCriteriaCoverageReport:
        """Resolve coverage status for all acceptance criteria.
        
        Rules:
        - historical JUnit ≠ verified on current PR
        - code coverage alone does not prove AC coverage
        - scenario match can make PARTIALLY_COVERED
        - missing AC must generate suggested scenario
        """
        coverage_statuses = []
        
        # Build lookup maps
        ac_map = {str(ac.id): ac for ac in acceptance_criteria}
        test_map = {str(t.id): t for t in existing_tests}
        scenario_coverage_map = {str(sc.behavior_scenario_id): sc for sc in behavior_scenario_coverages if sc.behavior_scenario_id}
        
        # Build AC to behavior mapping
        ac_to_behavior = {}
        ac_to_scenario = {}
        for mapping in business_behavior_mappings:
            if mapping.acceptance_criterion_id:
                ac_id = str(mapping.acceptance_criterion_id)
                ac_to_behavior[ac_id] = str(mapping.behavior_id)
                if mapping.behavior_scenario_id:
                    ac_to_scenario[ac_id] = str(mapping.behavior_scenario_id)
        
        # Build test to scenario mapping from coverage links
        test_to_scenarios = {}
        for link in test_coverage_links:
            test_id = str(link.test_case_id)
            if test_id not in test_to_scenarios:
                test_to_scenarios[test_id] = []
            if link.scenario_intent_id:
                test_to_scenarios[test_id].append(str(link.scenario_intent_id))
        
        # Build current PR execution map
        current_pr_execution = {}
        if current_pr_test_runs:
            for run in current_pr_test_runs:
                test_id = str(run.test_case_id)
                current_pr_execution[test_id] = run.status
        
        for ac in acceptance_criteria:
            ac_id = str(ac.id)
            status = self._resolve_single_ac_coverage(
                ac=ac,
                ac_id=ac_id,
                ac_to_behavior=ac_to_behavior,
                ac_to_scenario=ac_to_scenario,
                scenario_coverage_map=scenario_coverage_map,
                test_to_scenarios=test_to_scenarios,
                current_pr_execution=current_pr_execution,
                suggested_scenarios=suggested_scenarios,
                repository_id=repository_id
            )
            coverage_statuses.append(status)
        
        # Generate report
        return self._generate_report(coverage_statuses)
    
    def _resolve_single_ac_coverage(
        self,
        ac: AcceptanceCriterion,
        ac_id: str,
        ac_to_behavior: Dict[str, str],
        ac_to_scenario: Dict[str, str],
        scenario_coverage_map: Dict[str, BehaviorScenarioCoverage],
        test_to_scenarios: Dict[str, List[str]],
        current_pr_execution: Dict[str, str],
        suggested_scenarios: List[SuggestedTestScenario],
        repository_id: Optional[str]
    ) -> AcceptanceCriteriaCoverageStatus:
        """Resolve coverage status for a single acceptance criterion."""
        
        # Check if AC has a mapped scenario
        scenario_id = ac_to_scenario.get(ac_id)
        
        if scenario_id:
            # Check scenario coverage
            scenario_coverage = scenario_coverage_map.get(scenario_id)
            
            if scenario_coverage:
                # Check if scenario has existing tests
                existing_test_ids = scenario_coverage.test_mappings.get("test_ids", [])
                
                if existing_test_ids:
                    # Check if any test executed on current PR
                    executed_on_pr = False
                    for test_id in existing_test_ids:
                        if str(test_id) in current_pr_execution:
                            executed_on_pr = True
                            break
                    
                    if executed_on_pr:
                        return AcceptanceCriteriaCoverageStatus(
                            acceptance_criterion_id=ac_id,
                            coverage_status=self.VERIFIED_ON_CURRENT_PR,
                            existing_tests=existing_test_ids,
                            suggested_scenarios=[],
                            current_pr_execution_status=self.EXECUTED,
                            confidence=0.9,
                            reason="Scenario verified on current PR through existing test execution"
                        )
                    else:
                        return AcceptanceCriteriaCoverageStatus(
                            acceptance_criterion_id=ac_id,
                            coverage_status=self.COVERED_BY_EXISTING_TEST,
                            existing_tests=existing_test_ids,
                            suggested_scenarios=[],
                            current_pr_execution_status=self.NOT_EXECUTED,
                            confidence=0.8,
                            reason="Scenario covered by existing tests but not executed on current PR"
                        )
                else:
                    # No existing tests, check for partial coverage
                    if scenario_coverage.coverage_status in ["PARTIALLY_COVERED", "COVERED_BY_EXISTING_TEST"]:
                        return AcceptanceCriteriaCoverageStatus(
                            acceptance_criterion_id=ac_id,
                            coverage_status=self.PARTIALLY_COVERED,
                            existing_tests=[],
                            suggested_scenarios=[],
                            current_pr_execution_status=self.NOT_EXECUTED,
                            confidence=0.6,
                            reason="Scenario has partial coverage but no direct test match"
                        )
        
        # No scenario match or no coverage - check for suggested scenarios
        suggested_for_ac = [str(s.id) for s in suggested_scenarios if hasattr(s, 'acceptance_criterion_id') and str(s.acceptance_criterion_id) == ac_id]
        
        if suggested_for_ac:
            return AcceptanceCriteriaCoverageStatus(
                acceptance_criterion_id=ac_id,
                coverage_status=self.MISSING_TEST_COVERAGE,
                existing_tests=[],
                suggested_scenarios=suggested_for_ac,
                current_pr_execution_status=self.NOT_EXECUTED,
                confidence=0.7,
                reason="No existing test coverage, suggested scenarios available"
            )
        
        # No coverage at all
        return AcceptanceCriteriaCoverageStatus(
            acceptance_criterion_id=ac_id,
            coverage_status=self.MISSING_TEST_COVERAGE,
            existing_tests=[],
            suggested_scenarios=[],
            current_pr_execution_status=self.NOT_EXECUTED,
            confidence=0.5,
            reason="No test coverage found for this acceptance criterion"
        )
    
    def _generate_report(self, coverage_statuses: List[AcceptanceCriteriaCoverageStatus]) -> AcceptanceCriteriaCoverageReport:
        """Generate coverage report from statuses."""
        
        total = len(coverage_statuses)
        covered_by_existing_test = sum(1 for s in coverage_statuses if s.coverage_status == self.COVERED_BY_EXISTING_TEST)
        partially_covered = sum(1 for s in coverage_statuses if s.coverage_status == self.PARTIALLY_COVERED)
        missing_test_coverage = sum(1 for s in coverage_statuses if s.coverage_status == self.MISSING_TEST_COVERAGE)
        verified_on_current_pr = sum(1 for s in coverage_statuses if s.coverage_status == self.VERIFIED_ON_CURRENT_PR)
        manual_validation_required = sum(1 for s in coverage_statuses if s.coverage_status == self.MANUAL_VALIDATION_REQUIRED)
        unknown = sum(1 for s in coverage_statuses if s.coverage_status == self.UNKNOWN)
        
        return AcceptanceCriteriaCoverageReport(
            total_criteria=total,
            covered_by_existing_test=covered_by_existing_test,
            partially_covered=partially_covered,
            missing_test_coverage=missing_test_coverage,
            verified_on_current_pr=verified_on_current_pr,
            manual_validation_required=manual_validation_required,
            unknown=unknown,
            coverage_statuses=coverage_statuses
        )
