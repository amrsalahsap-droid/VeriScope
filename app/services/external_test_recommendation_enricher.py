"""
External Test Recommendation Enricher Service

Enriches recommendation output with external test case data.
Categorizes tests into: automated, manual to execute, suggested scenarios, automation candidates.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.models.external_test_case_detailed import ExternalTestCase
from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
from app.models.behavior_scenario import BehaviorScenario
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.pull_request import PullRequest
from app.models.behavior import Behavior


logger = logging.getLogger("veriscope.external_test_recommendation_enricher")


class RecommendationCategory(str, Enum):
    """Categories for recommendation output."""
    AUTOMATED_TEST = "AUTOMATED_TEST"
    MANUAL_TEST_TO_EXECUTE = "MANUAL_TEST_TO_EXECUTE"
    SUGGESTED_MISSING_SCENARIO = "SUGGESTED_MISSING_SCENARIO"
    AUTOMATION_CANDIDATE = "AUTOMATION_CANDIDATE"


@dataclass
class ExternalTestRecommendation:
    """External test case recommendation."""
    category: RecommendationCategory
    external_test_case_id: Optional[uuid.UUID]
    title: str
    source_tool: str  # TESTRAIL, XRAY, ZEPHYR, MANUAL_CSV
    source_url: Optional[str]
    priority: str  # BLOCKER, MUST, SHOULD, OPTIONAL
    reason: str
    linked_affected_ac: List[str]  # Linked affected acceptance criteria
    confidence: float  # 0.0 to 1.0


@dataclass
class EnrichedRecommendationOutput:
    """Enriched recommendation output with external test data."""
    automated_tests_to_run: List[Dict[str, Any]]
    managed_manual_tests_to_execute: List[ExternalTestRecommendation]
    suggested_missing_scenarios: List[Dict[str, Any]]
    automation_candidates: List[ExternalTestRecommendation]


class ExternalTestRecommendationEnricher:
    """
    Enriches recommendation output with external test case data.
    
    Rules:
    - External manual tests should not appear as automated runnable tests
    - High-priority manual cases linked to impacted AC should be recommended
    - Manual cases can reduce "missing requirement" but not "missing automation"
    - Preserve source tool/test case URL
    """
    
    def __init__(self, db: Session):
        """Initialize the enricher with database session."""
        self.db = db
    
    def enrich_recommendation(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID,
        changed_files: List[str],
        automated_test_recommendations: List[Dict[str, Any]]
    ) -> EnrichedRecommendationOutput:
        """
        Enrich recommendation output with external test case data.
        
        Args:
            repository_id: Repository ID
            pull_request_id: Pull request ID
            changed_files: List of changed files
            automated_test_recommendations: Existing automated test recommendations
            
        Returns:
            EnrichedRecommendationOutput with all categories
        """
        # Get external test cases for the repository
        external_test_cases = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == repository_id,
            ExternalTestCase.is_active == True
        ).all()
        
        # Get scenario mappings for external test cases
        external_test_case_ids = [tc.id for tc in external_test_cases]
        scenario_mappings = self.db.query(ExternalTestScenarioMapping).filter(
            ExternalTestScenarioMapping.external_test_case_id.in_(external_test_case_ids)
        ).all()
        
        # Build mapping from test case to scenarios
        test_to_scenarios = {}
        for mapping in scenario_mappings:
            if mapping.external_test_case_id not in test_to_scenarios:
                test_to_scenarios[mapping.external_test_case_id] = []
            test_to_scenarios[mapping.external_test_case_id].append(mapping)
        
        # Get impacted behaviors/scenarios from changed files
        impacted_scenarios = self._get_impacted_scenarios(repository_id, changed_files)
        
        # Categorize external test cases
        manual_tests_to_execute = []
        automation_candidates = []
        
        for test_case in external_test_cases:
            mappings = test_to_scenarios.get(test_case.id, [])
            
            # Check if test case is linked to impacted scenarios
            is_impacted = any(
                mapping.behavior_scenario_id in [s.id for s in impacted_scenarios]
                for mapping in mappings
            )
            
            # Determine category based on automation status and impact
            if test_case.automation_status == "MANUAL":
                if is_impacted:
                    recommendation = self._create_manual_test_recommendation(
                        test_case,
                        mappings,
                        impacted_scenarios
                    )
                    manual_tests_to_execute.append(recommendation)
                else:
                    # Not impacted but could be automation candidate
                    if test_case.priority in ("BLOCKER", "MUST"):
                        recommendation = self._create_automation_candidate(
                            test_case,
                            mappings,
                            reason="High-priority manual test - consider automation"
                        )
                        automation_candidates.append(recommendation)
            elif test_case.automation_status == "PARTIALLY_AUTOMATED":
                # Partially automated - recommend full automation
                if is_impacted:
                    recommendation = self._create_automation_candidate(
                        test_case,
                        mappings,
                        reason="Partially automated - recommend full automation"
                    )
                    automation_candidates.append(recommendation)
        
        # Sort by priority
        manual_tests_to_execute.sort(
            key=lambda x: self._priority_score(x.priority),
            reverse=True
        )
        automation_candidates.sort(
            key=lambda x: self._priority_score(x.priority),
            reverse=True
        )
        
        # Get suggested missing scenarios (from behavior coverage gaps)
        suggested_missing_scenarios = self._get_suggested_missing_scenarios(
            repository_id,
            impacted_scenarios,
            external_test_cases
        )
        
        return EnrichedRecommendationOutput(
            automated_tests_to_run=automated_test_recommendations,
            managed_manual_tests_to_execute=manual_tests_to_execute,
            suggested_missing_scenarios=suggested_missing_scenarios,
            automation_candidates=automation_candidates
        )
    
    def _get_impacted_scenarios(
        self,
        repository_id: uuid.UUID,
        changed_files: List[str]
    ) -> List[BehaviorScenario]:
        """
        Get behavior scenarios impacted by changed files.
        
        Args:
            repository_id: Repository ID
            changed_files: List of changed files
            
        Returns:
            List of impacted BehaviorScenario objects
        """
        # This would require behavior impact analysis
        # For now, return all active scenarios for the repository
        scenarios = self.db.query(BehaviorScenario).join(
            BehaviorScenario.behavior
        ).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
            BehaviorScenario.status == "ACTIVE"
        ).all()
        
        return scenarios
    
    def _create_manual_test_recommendation(
        self,
        test_case: ExternalTestCase,
        mappings: List[ExternalTestScenarioMapping],
        impacted_scenarios: List[BehaviorScenario]
    ) -> ExternalTestRecommendation:
        """
        Create a manual test recommendation.
        
        Args:
            test_case: ExternalTestCase
            mappings: Scenario mappings
            impacted_scenarios: Impacted scenarios
            
        Returns:
            ExternalTestRecommendation
        """
        # Get linked affected AC
        linked_affected_ac = self._get_linked_affected_ac(test_case, mappings)
        
        # Determine reason
        scenario_names = []
        for mapping in mappings:
            scenario = next((s for s in impacted_scenarios if s.id == mapping.behavior_scenario_id), None)
            if scenario:
                scenario_names.append(scenario.title)
        
        reason = f"Manual test case covers impacted scenario(s): {', '.join(scenario_names[:3])}"
        if linked_affected_ac:
            reason += f". Linked to affected AC: {', '.join(linked_affected_ac[:2])}"
        
        return ExternalTestRecommendation(
            category=RecommendationCategory.MANUAL_TEST_TO_EXECUTE,
            external_test_case_id=test_case.id,
            title=test_case.title,
            source_tool=test_case.provider,
            source_url=test_case.url,
            priority=test_case.priority or "MUST",
            reason=reason,
            linked_affected_ac=linked_affected_ac,
            confidence=0.8 if test_case.priority in ("BLOCKER", "MUST") else 0.6
        )
    
    def _create_automation_candidate(
        self,
        test_case: ExternalTestCase,
        mappings: List[ExternalTestScenarioMapping],
        reason: str
    ) -> ExternalTestRecommendation:
        """
        Create an automation candidate recommendation.
        
        Args:
            test_case: ExternalTestCase
            mappings: Scenario mappings
            reason: Reason for automation recommendation
            
        Returns:
            ExternalTestRecommendation
        """
        # Get linked affected AC
        linked_affected_ac = self._get_linked_affected_ac(test_case, mappings)
        
        return ExternalTestRecommendation(
            category=RecommendationCategory.AUTOMATION_CANDIDATE,
            external_test_case_id=test_case.id,
            title=test_case.title,
            source_tool=test_case.provider,
            source_url=test_case.url,
            priority=test_case.priority or "SHOULD",
            reason=reason,
            linked_affected_ac=linked_affected_ac,
            confidence=0.7 if test_case.priority in ("BLOCKER", "MUST") else 0.5
        )
    
    def _get_linked_affected_ac(
        self,
        test_case: ExternalTestCase,
        mappings: List[ExternalTestScenarioMapping]
    ) -> List[str]:
        """
        Get linked affected acceptance criteria.
        
        Args:
            test_case: ExternalTestCase
            mappings: Scenario mappings
            
        Returns:
            List of AC titles
        """
        # Get work item mappings for linked work items
        linked_ac = []
        
        if test_case.linked_work_item_keys:
            from app.models.external_work_item import ExternalWorkItem
            from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping
            from app.models.acceptance_criterion import AcceptanceCriterion
            
            for work_item_key in test_case.linked_work_item_keys:
                work_item = self.db.query(ExternalWorkItem).filter(
                    ExternalWorkItem.external_key == work_item_key,
                    ExternalWorkItem.repository_id == test_case.repository_id
                ).first()
                
                if work_item:
                    # Get AC linked to this work item
                    ac = self.db.query(AcceptanceCriterion).filter(
                        AcceptanceCriterion.pull_request_id == test_case.pull_request_id,
                        AcceptanceCriterion.external_work_item_id == work_item.id
                    ).first()
                    
                    if ac:
                        linked_ac.append(ac.title)
        
        return linked_ac
    
    def _get_suggested_missing_scenarios(
        self,
        repository_id: uuid.UUID,
        impacted_scenarios: List[BehaviorScenario],
        external_test_cases: List[ExternalTestCase]
    ) -> List[Dict[str, Any]]:
        """
        Get suggested missing scenarios not covered by external tests.
        
        Args:
            repository_id: Repository ID
            impacted_scenarios: Impacted scenarios
            external_test_cases: External test cases
            
        Returns:
            List of suggested scenario dictionaries
        """
        # Get scenario mappings for external test cases
        external_test_case_ids = [tc.id for tc in external_test_cases]
        scenario_mappings = self.db.query(ExternalTestScenarioMapping).filter(
            ExternalTestScenarioMapping.external_test_case_id.in_(external_test_case_ids)
        ).all()
        
        # Get covered scenario IDs
        covered_scenario_ids = set(mapping.behavior_scenario_id for mapping in scenario_mappings)
        
        # Find uncovered scenarios
        uncovered_scenarios = [
            s for s in impacted_scenarios
            if s.id not in covered_scenario_ids
        ]
        
        # Convert to suggested scenario format
        suggested = []
        for scenario in uncovered_scenarios:
            suggested.append({
                "scenario_id": str(scenario.id),
                "title": scenario.title,
                "description": scenario.description,
                "priority": scenario.priority,
                "scenario_type": scenario.scenario_type,
                "reason": "No external test case coverage - recommend test implementation"
            })
        
        return suggested
    
    def _priority_score(self, priority: str) -> int:
        """
        Convert priority string to numeric score for sorting.
        
        Args:
            priority: Priority string
            
        Returns:
            Numeric score
        """
        priority_scores = {
            "BLOCKER": 4,
            "MUST": 3,
            "SHOULD": 2,
            "OPTIONAL": 1
        }
        return priority_scores.get(priority, 2)
