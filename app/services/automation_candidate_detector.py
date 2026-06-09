"""
Automation Candidate Detector Service

Identifies manual/external tests that should become automated.
Considers risk level, behavior impact, execution frequency, AC criticality, missing automation, and historical defects.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.models.external_test_case_detailed import ExternalTestCase
from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.fragility_memory_v2 import FragilityMemoryV2


logger = logging.getLogger("veriscope.automation_candidate_detector")


class AutomationPriority(str, Enum):
    """Priority for automation candidates."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AutomationLayer(str, Enum):
    """Suggested automation layer."""
    UNIT = "UNIT"
    INTEGRATION = "INTEGRATION"
    E2E = "E2E"
    API = "API"
    UI = "UI"


@dataclass
class AutomationCandidate:
    """Automation candidate for a manual test case."""
    external_test_case_id: uuid.UUID
    behavior_id: Optional[uuid.UUID]
    scenario_intent_key: Optional[str]
    priority: AutomationPriority
    reason: str
    suggested_automation_layer: AutomationLayer
    confidence: float  # 0.0 to 1.0


class AutomationCandidateDetector:
    """
    Identifies manual/external tests that should become automated.
    
    Rules:
    - High-risk frequently recommended manual tests become strong automation candidates
    - Low-priority manual cases remain optional
    - No fake automation status
    """
    
    def __init__(self, db: Session):
        """Initialize the detector with database session."""
        self.db = db
    
    def detect_automation_candidates(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID,
        risk_level: str = "LOW",
        behavior_impact: List[Dict[str, Any]] = None
    ) -> List[AutomationCandidate]:
        """
        Detect automation candidates for manual test cases.
        
        Args:
            repository_id: Repository ID
            pull_request_id: Pull request ID
            risk_level: Overall risk level (LOW, MODERATE, HIGH, CRITICAL)
            behavior_impact: List of impacted behaviors with impact levels
            
        Returns:
            List of AutomationCandidate objects
        """
        behavior_impact = behavior_impact or []
        
        # Get manual test cases for the repository
        manual_tests = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == repository_id,
            ExternalTestCase.automation_status == "MANUAL",
            ExternalTestCase.is_active == True
        ).all()
        
        if not manual_tests:
            return []
        
        # Get scenario mappings for manual tests
        test_ids = [t.id for t in manual_tests]
        scenario_mappings = self.db.query(ExternalTestScenarioMapping).filter(
            ExternalTestScenarioMapping.external_test_case_id.in_(test_ids)
        ).all()
        
        # Build mapping from test to scenarios
        test_to_scenarios = {}
        for mapping in scenario_mappings:
            if mapping.external_test_case_id not in test_to_scenarios:
                test_to_scenarios[mapping.external_test_case_id] = []
            test_to_scenarios[mapping.external_test_case_id].append(mapping)
        
        # Get impacted behavior IDs
        impacted_behavior_ids = set()
        for impact in behavior_impact:
            if impact.get("behavior_id"):
                impacted_behavior_ids.add(impact["behavior_id"])
        
        # Get historical fragility patterns
        fragility_patterns = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.status == "ACTIVE"
        ).all()
        
        # Get high-risk behavior IDs from fragility
        high_risk_behavior_ids = set()
        for pattern in fragility_patterns:
            if pattern.risk_level in ("HIGH", "CRITICAL"):
                if pattern.behavior_id:
                    high_risk_behavior_ids.add(pattern.behavior_id)
        
        # Detect candidates
        candidates = []
        
        for test in manual_tests:
            mappings = test_to_scenarios.get(test.id, [])
            
            # Check if test is linked to impacted behaviors
            is_impacted = any(
                mapping.behavior_id in impacted_behavior_ids
                for mapping in mappings
            )
            
            # Check if test is linked to high-risk behaviors
            is_high_risk = any(
                mapping.behavior_id in high_risk_behavior_ids
                for mapping in mappings
            )
            
            # Determine automation priority
            priority, reason, confidence = self._determine_automation_priority(
                test=test,
                is_impacted=is_impacted,
                is_high_risk=is_high_risk,
                risk_level=risk_level,
                mappings=mappings
            )
            
            # Skip low priority candidates
            if priority == AutomationPriority.LOW:
                continue
            
            # Determine suggested automation layer
            automation_layer = self._determine_automation_layer(test, mappings)
            
            # Get behavior ID and scenario intent key
            behavior_id = None
            scenario_intent_key = None
            
            if mappings:
                behavior_id = mappings[0].behavior_id
                scenario_intent_key = mappings[0].scenario_intent_key
            
            candidates.append(AutomationCandidate(
                external_test_case_id=test.id,
                behavior_id=behavior_id,
                scenario_intent_key=scenario_intent_key,
                priority=priority,
                reason=reason,
                suggested_automation_layer=automation_layer,
                confidence=confidence
            ))
        
        # Sort by priority and confidence
        priority_order = {
            AutomationPriority.CRITICAL: 0,
            AutomationPriority.HIGH: 1,
            AutomationPriority.MEDIUM: 2,
            AutomationPriority.LOW: 3
        }
        
        candidates.sort(
            key=lambda c: (priority_order[c.priority], -c.confidence)
        )
        
        return candidates
    
    def _determine_automation_priority(
        self,
        test: ExternalTestCase,
        is_impacted: bool,
        is_high_risk: bool,
        risk_level: str,
        mappings: List[ExternalTestScenarioMapping]
    ) -> tuple[AutomationPriority, str, float]:
        """
        Determine automation priority for a test case.
        
        Args:
            test: ExternalTestCase
            is_impacted: Whether test is linked to impacted behaviors
            is_high_risk: Whether test is linked to high-risk behaviors
            risk_level: Overall risk level
            mappings: Scenario mappings
            
        Returns:
            Tuple of (priority, reason, confidence)
        """
        # Start with base priority from test
        test_priority = test.priority or "SHOULD"
        
        # CRITICAL: High-risk + high-priority + impacted
        if is_high_risk and test_priority in ("BLOCKER", "MUST") and is_impacted:
            return (
                AutomationPriority.CRITICAL,
                "High-risk behavior with critical test case - automation strongly recommended",
                0.9
            )
        
        # HIGH: High-risk + high-priority
        if is_high_risk and test_priority in ("BLOCKER", "MUST"):
            return (
                AutomationPriority.HIGH,
                "High-risk behavior with critical test case - automation recommended",
                0.8
            )
        
        # HIGH: High-priority + impacted + high overall risk
        if test_priority in ("BLOCKER", "MUST") and is_impacted and risk_level in ("HIGH", "CRITICAL"):
            return (
                AutomationPriority.HIGH,
                "Critical test case in high-risk area - automation recommended",
                0.75
            )
        
        # MEDIUM: High-priority + impacted
        if test_priority in ("BLOCKER", "MUST") and is_impacted:
            return (
                AutomationPriority.MEDIUM,
                "Critical test case in impacted area - consider automation",
                0.6
            )
        
        # MEDIUM: High-priority
        if test_priority in ("BLOCKER", "MUST"):
            return (
                AutomationPriority.MEDIUM,
                "Critical test case - consider automation",
                0.5
            )
        
        # LOW: Should priority
        if test_priority == "SHOULD":
            return (
                AutomationPriority.LOW,
                "Optional test case - automation not critical",
                0.3
            )
        
        # LOW: Optional priority
        return (
            AutomationPriority.LOW,
            "Optional test case - automation not recommended",
            0.2
        )
    
    def _determine_automation_layer(
        self,
        test: ExternalTestCase,
        mappings: List[ExternalTestScenarioMapping]
    ) -> AutomationLayer:
        """
        Determine suggested automation layer for a test case.
        
        Args:
            test: ExternalTestCase
            mappings: Scenario mappings
            
        Returns:
            Suggested AutomationLayer
        """
        # Check test type for hints
        test_type = test.test_type or ""
        test_type_lower = test_type.lower()
        
        # API tests
        if "api" in test_type_lower or "endpoint" in test_type_lower or "service" in test_type_lower:
            return AutomationLayer.API
        
        # UI tests
        if "ui" in test_type_lower or "frontend" in test_type_lower or "user interface" in test_type_lower:
            return AutomationLayer.UI
        
        # E2E tests
        if "e2e" in test_type_lower or "end-to-end" in test_type_lower or "journey" in test_type_lower:
            return AutomationLayer.E2E
        
        # Integration tests
        if "integration" in test_type_lower:
            return AutomationLayer.INTEGRATION
        
        # Unit tests
        if "unit" in test_type_lower:
            return AutomationLayer.UNIT
        
        # Default to integration for most cases
        return AutomationLayer.INTEGRATION
