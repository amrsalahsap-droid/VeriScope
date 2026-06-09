"""
External Requirement Coverage Resolver Service

Determines whether acceptance criteria/business requirements are covered by:
- automated tests
- external/manual test cases
- suggested scenarios
- current PR execution
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
from app.models.behavior_scenario import BehaviorScenario
from app.models.test_result import TestRun, TestResult
from app.models.pull_request import PullRequest


logger = logging.getLogger("veriscope.external_requirement_coverage_resolver")


class CoverageStatus(str, Enum):
    """Coverage status for acceptance criteria."""
    AUTOMATED_COVERAGE = "AUTOMATED_COVERAGE"
    MANUAL_TEST_COVERAGE = "MANUAL_TEST_COVERAGE"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    MISSING_COVERAGE = "MISSING_COVERAGE"
    VERIFIED_ON_CURRENT_PR = "VERIFIED_ON_CURRENT_PR"
    UNKNOWN = "UNKNOWN"


@dataclass
class RequirementCoverageStatus:
    """Coverage status for an acceptance criterion."""
    acceptance_criterion_id: uuid.UUID
    automated_tests: List[str]  # Test identifiers
    external_test_cases: List[str]  # External test case titles
    suggested_scenarios: List[str]  # Scenario titles
    coverage_status: CoverageStatus
    confidence: float  # 0.0 to 1.0
    recommended_action: str  # Human-readable recommended action


class ExternalRequirementCoverageResolver:
    """
    Resolves coverage status for acceptance criteria.
    
    Rules:
    - Manual test case coverage ≠ automation coverage
    - Historical automated test ≠ current PR verified
    - AC can be covered manually but still recommended for automation if high-risk
    - Do not mark verified unless execution evidence exists
    """
    
    def __init__(self, db: Session):
        """Initialize the resolver with database session."""
        self.db = db
    
    def resolve_coverage(
        self,
        acceptance_criterion: AcceptanceCriterion,
        repository_id: uuid.UUID,
        current_pr_id: Optional[uuid.UUID] = None
    ) -> RequirementCoverageStatus:
        """
        Resolve coverage status for an acceptance criterion.
        
        Args:
            acceptance_criterion: AcceptanceCriterion to resolve coverage for
            repository_id: Repository ID
            current_pr_id: Optional current PR ID for verification check
            
        Returns:
            RequirementCoverageStatus with coverage information
        """
        # Check for current PR verification
        if current_pr_id:
            verified = self._check_current_pr_verification(
                acceptance_criterion,
                current_pr_id
            )
            if verified:
                return RequirementCoverageStatus(
                    acceptance_criterion_id=acceptance_criterion.id,
                    automated_tests=[],
                    external_test_cases=[],
                    suggested_scenarios=[],
                    coverage_status=CoverageStatus.VERIFIED_ON_CURRENT_PR,
                    confidence=1.0,
                    recommended_action="Verified on current PR execution"
                )
        
        # Check for automated test coverage
        automated_tests = self._check_automated_coverage(
            acceptance_criterion,
            repository_id
        )
        
        # Check for external/manual test case coverage
        external_test_cases = self._check_external_test_coverage(
            acceptance_criterion,
            repository_id
        )
        
        # Check for suggested scenario coverage
        suggested_scenarios = self._check_suggested_scenario_coverage(
            acceptance_criterion,
            repository_id
        )
        
        # Determine coverage status
        coverage_status, confidence = self._determine_coverage_status(
            automated_tests,
            external_test_cases,
            suggested_scenarios
        )
        
        # Determine recommended action
        recommended_action = self._determine_recommended_action(
            coverage_status,
            automated_tests,
            external_test_cases,
            suggested_scenarios
        )
        
        return RequirementCoverageStatus(
            acceptance_criterion_id=acceptance_criterion.id,
            automated_tests=automated_tests,
            external_test_cases=external_test_cases,
            suggested_scenarios=suggested_scenarios,
            coverage_status=coverage_status,
            confidence=confidence,
            recommended_action=recommended_action
        )
    
    def _check_current_pr_verification(
        self,
        acceptance_criterion: AcceptanceCriterion,
        pr_id: uuid.UUID
    ) -> bool:
        """
        Check if AC is verified on current PR execution.
        
        Args:
            acceptance_criterion: AcceptanceCriterion
            pr_id: Pull request ID
            
        Returns:
            True if verified on current PR, False otherwise
        """
        # Get test runs for this PR
        test_runs = self.db.query(TestRun).filter(
            TestRun.pull_request_id == pr_id
        ).all()
        
        if not test_runs:
            return False
        
        # Check if any test results cover this AC
        # This would require linking test results to AC - for now, return False
        # In a full implementation, we would check test names/descriptions against AC text
        return False
    
    def _check_automated_coverage(
        self,
        acceptance_criterion: AcceptanceCriterion,
        repository_id: uuid.UUID
    ) -> List[str]:
        """
        Check for automated test coverage.
        
        Args:
            acceptance_criterion: AcceptanceCriterion
            repository_id: Repository ID
            
        Returns:
            List of automated test identifiers covering this AC
        """
        # Get test runs for the repository
        test_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id
        ).all()
        
        if not test_runs:
            return []
        
        # Check test results for coverage
        # This would require linking test results to AC - for now, return empty list
        # In a full implementation, we would:
        # 1. Get test results from test runs
        # 2. Match test names/descriptions to AC text
        # 3. Return matching test identifiers
        return []
    
    def _check_external_test_coverage(
        self,
        acceptance_criterion: AcceptanceCriterion,
        repository_id: uuid.UUID
    ) -> List[str]:
        """
        Check for external/manual test case coverage.
        
        Args:
            acceptance_criterion: AcceptanceCriterion
            repository_id: Repository ID
            
        Returns:
            List of external test case titles covering this AC
        """
        # Get external test cases for the repository
        external_test_cases = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == repository_id,
            ExternalTestCase.is_active == True
        ).all()
        
        if not external_test_cases:
            return []
        
        # Match test cases to AC
        # Use text matching to find test cases that cover this AC
        ac_text = self._prepare_ac_text(acceptance_criterion)
        
        matching_test_cases = []
        for test_case in external_test_cases:
            test_text = self._prepare_test_case_text(test_case)
            
            # Simple text overlap check
            if self._has_text_overlap(ac_text, test_text):
                matching_test_cases.append(test_case.title)
        
        return matching_test_cases
    
    def _check_suggested_scenario_coverage(
        self,
        acceptance_criterion: AcceptanceCriterion,
        repository_id: uuid.UUID
    ) -> List[str]:
        """
        Check for suggested scenario coverage.
        
        Args:
            acceptance_criterion: AcceptanceCriterion
            repository_id: Repository ID
            
        Returns:
            List of suggested scenario titles covering this AC
        """
        # Get behavior scenarios for the repository
        scenarios = self.db.query(BehaviorScenario).join(
            BehaviorScenario.behavior
        ).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
            BehaviorScenario.status == "ACTIVE"
        ).all()
        
        if not scenarios:
            return []
        
        # Match scenarios to AC
        ac_text = self._prepare_ac_text(acceptance_criterion)
        
        matching_scenarios = []
        for scenario in scenarios:
            scenario_text = self._prepare_scenario_text(scenario)
            
            # Simple text overlap check
            if self._has_text_overlap(ac_text, scenario_text):
                matching_scenarios.append(scenario.title)
        
        return matching_scenarios
    
    def _determine_coverage_status(
        self,
        automated_tests: List[str],
        external_test_cases: List[str],
        suggested_scenarios: List[str]
    ) -> tuple[CoverageStatus, float]:
        """
        Determine coverage status based on available coverage.
        
        Args:
            automated_tests: List of automated test identifiers
            external_test_cases: List of external test case titles
            suggested_scenarios: List of suggested scenario titles
            
        Returns:
            Tuple of (CoverageStatus, confidence)
        """
        has_automated = len(automated_tests) > 0
        has_manual = len(external_test_cases) > 0
        has_suggested = len(suggested_scenarios) > 0
        
        if has_automated and has_manual:
            return CoverageStatus.PARTIAL_COVERAGE, 0.8
        elif has_automated:
            return CoverageStatus.AUTOMATED_COVERAGE, 0.9
        elif has_manual:
            return CoverageStatus.MANUAL_TEST_COVERAGE, 0.7
        elif has_suggested:
            return CoverageStatus.PARTIAL_COVERAGE, 0.5
        else:
            return CoverageStatus.MISSING_COVERAGE, 0.0
    
    def _determine_recommended_action(
        self,
        coverage_status: CoverageStatus,
        automated_tests: List[str],
        external_test_cases: List[str],
        suggested_scenarios: List[str]
    ) -> str:
        """
        Determine recommended action based on coverage status.
        
        Args:
            coverage_status: Coverage status
            automated_tests: List of automated test identifiers
            external_test_cases: List of external test case titles
            suggested_scenarios: List of suggested scenario titles
            
        Returns:
            Human-readable recommended action
        """
        if coverage_status == CoverageStatus.VERIFIED_ON_CURRENT_PR:
            return "No action needed - verified on current PR"
        
        elif coverage_status == CoverageStatus.AUTOMATED_COVERAGE:
            return "Automated coverage exists - review for relevance"
        
        elif coverage_status == CoverageStatus.MANUAL_TEST_COVERAGE:
            return "Manual test coverage exists - consider automation for high-risk scenarios"
        
        elif coverage_status == CoverageStatus.PARTIAL_COVERAGE:
            if automated_tests and external_test_cases:
                return "Both automated and manual coverage exists - review for gaps"
            elif automated_tests and suggested_scenarios:
                return "Automated coverage exists with suggested scenarios - review for completeness"
            elif external_test_cases and suggested_scenarios:
                return "Manual coverage exists with suggested scenarios - consider automation"
            else:
                return "Partial coverage exists - review for gaps"
        
        elif coverage_status == CoverageStatus.MISSING_COVERAGE:
            if suggested_scenarios:
                return f"No coverage - consider implementing: {', '.join(suggested_scenarios[:3])}"
            else:
                return "No coverage - recommend test implementation"
        
        else:
            return "Review coverage status"
    
    def _prepare_ac_text(self, acceptance_criterion: AcceptanceCriterion) -> str:
        """
        Prepare acceptance criterion text for matching.
        
        Args:
            acceptance_criterion: AcceptanceCriterion
            
        Returns:
            Normalized text string
        """
        parts = []
        
        if acceptance_criterion.title:
            parts.append(acceptance_criterion.title.lower())
        
        if acceptance_criterion.description:
            parts.append(acceptance_criterion.description.lower())
        
        return ' '.join(parts)
    
    def _prepare_test_case_text(self, test_case: ExternalTestCase) -> str:
        """
        Prepare test case text for matching.
        
        Args:
            test_case: ExternalTestCase
            
        Returns:
            Normalized text string
        """
        parts = []
        
        if test_case.title:
            parts.append(test_case.title.lower())
        
        if test_case.description:
            parts.append(test_case.description.lower())
        
        # Add step text
        if test_case.steps:
            for step in test_case.steps:
                if isinstance(step, dict):
                    step_text = step.get('step', '')
                    expected_text = step.get('expected', '')
                    if step_text:
                        parts.append(step_text.lower())
                    if expected_text:
                        parts.append(expected_text.lower())
        
        return ' '.join(parts)
    
    def _prepare_scenario_text(self, scenario: BehaviorScenario) -> str:
        """
        Prepare scenario text for matching.
        
        Args:
            scenario: BehaviorScenario
            
        Returns:
            Normalized text string
        """
        parts = []
        
        if scenario.title:
            parts.append(scenario.title.lower())
        
        if scenario.description:
            parts.append(scenario.description.lower())
        
        return ' '.join(parts)
    
    def _has_text_overlap(self, text1: str, text2: str) -> bool:
        """
        Check if two texts have overlapping terms.
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            True if texts have overlapping terms, False otherwise
        """
        import re
        
        # Extract terms from both texts
        terms1 = set(re.findall(r'\b[a-z]{3,}\b', text1.lower()))
        terms2 = set(re.findall(r'\b[a-z]{3,}\b', text2.lower()))
        
        # Filter out common stop words
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'this',
            'that', 'with', 'they', 'from', 'will', 'more', 'when', 'what',
            'about', 'which', 'their', 'there', 'would', 'could', 'should'
        }
        
        terms1 = terms1 - stop_words
        terms2 = terms2 - stop_words
        
        # Check for overlap
        overlap = terms1 & terms2
        
        return len(overlap) > 0
