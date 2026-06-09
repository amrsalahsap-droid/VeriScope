"""
Scenario Coverage Matrix API Models
====================================
Data structures for scenario coverage matrix API responses.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class RecommendationAction(Enum):
    """Recommended action for a scenario intent."""
    RUN_EXISTING_TEST = "RUN_EXISTING_TEST"
    ADD_AUTOMATED_TEST = "ADD_AUTOMATED_TEST"
    EXECUTE_MANUAL_SCENARIO = "EXECUTE_MANUAL_SCENARIO"
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    EXPAND_COVERAGE = "EXPAND_COVERAGE"
    OPTIONAL_MONITOR = "OPTIONAL_MONITOR"


@dataclass
class ExistingTestReference:
    """Reference to an existing test covering a scenario intent."""
    test_identifier: str
    test_name: str
    suite_name: Optional[str] = None
    class_name: Optional[str] = None
    last_execution_status: Optional[str] = None
    last_execution_timestamp: Optional[str] = None


@dataclass
class SuggestedScenarioReference:
    """Reference to a suggested scenario for a scenario intent."""
    scenario_id: str
    title: str
    testing_type: str
    priority: str
    automation_candidate: bool
    preconditions: List[str]
    steps: List[str]
    expected_result: str
    test_data: Dict[str, Any]


@dataclass
class ScenarioCoverageMatrixItem:
    """Single item in the scenario coverage matrix."""
    scenario_intent_key: str
    title: str
    impacted_area: str
    testing_type: str
    priority: str
    existing_tests: List[ExistingTestReference]
    suggested_scenarios: List[SuggestedScenarioReference]
    code_coverage_status: str
    current_pr_execution_status: str
    final_status: str
    recommendation_action: RecommendationAction
    evidence_reason: str
    confidence: str = "MEDIUM"
    domain: str = "general"
    feature: str = "general"
    layer: str = "api"
    case_type: str = "positive"


@dataclass
class ScenarioCoverageMatrix:
    """Complete scenario coverage matrix for a recommendation run."""
    recommendation_run_id: str
    repository_id: str
    pull_request_id: Optional[str]
    total_scenarios: int
    covered_and_verified: int
    covered_not_run: int
    partially_covered: int
    missing_automated_coverage: int
    suggest_manual_validation: int
    items: List[ScenarioCoverageMatrixItem]
    generated_at: str
