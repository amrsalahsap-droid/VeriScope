"""
External Test Case Scenario Mapper Service

Maps external test cases (TestRail, Xray, Zephyr, CSV) to Veriscope Behavior Scenarios and Scenario Intents.
Uses test title, steps, and linked work items for mapping.
"""

import re
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.external_test_case_detailed import ExternalTestCase
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping


logger = logging.getLogger("veriscope.external_test_scenario_mapper")


@dataclass
class ScenarioMappingResult:
    """Result of external test case to scenario mapping."""
    behavior_id: Optional[uuid.UUID]
    behavior_scenario_id: Optional[uuid.UUID]
    scenario_intent_key: Optional[str]
    confidence: float
    matched_terms: List[str]
    reason: str


class ExternalTestCaseScenarioMapper:
    """
    Maps external test cases to behavior scenarios and scenario intents.
    
    Key distinction:
    - External test cases are manual/managed test assets, not executed tests
    - They can cover scenarios but are not executed
    - This mapping is separate from automated test coverage mapping
    
    Rules:
    - Test title + steps + linked work item used for mapping
    - Manual cases can cover scenarios but are not executed
    - Confidence must be explainable via matched terms
    - Do not duplicate existing automated test mapping
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE_MIN = 0.8
    MEDIUM_CONFIDENCE_MIN = 0.5
    LOW_CONFIDENCE_MIN = 0.2
    
    def __init__(self, db: Session):
        """Initialize the mapper with database session."""
        self.db = db
    
    def map_test_case(
        self,
        test_case: ExternalTestCase,
        repository_id: uuid.UUID
    ) -> ScenarioMappingResult:
        """
        Map an external test case to behavior scenarios.
        
        Args:
            test_case: ExternalTestCase to map
            repository_id: Repository ID for scenario lookup
            
        Returns:
            ScenarioMappingResult with scenario IDs and confidence
        """
        # Get linked work item mapping for context
        work_item_mapping = self._get_work_item_mapping(test_case)
        
        # Try HIGH confidence match first (title + steps + linked work item)
        high_result = self._match_high_confidence(test_case, repository_id, work_item_mapping)
        if high_result:
            return high_result
        
        # Try MEDIUM confidence match (title + steps)
        medium_result = self._match_medium_confidence(test_case, repository_id)
        if medium_result:
            return medium_result
        
        # Try LOW confidence match (title only)
        low_result = self._match_low_confidence(test_case, repository_id)
        if low_result:
            return low_result
        
        # No match found
        return ScenarioMappingResult(
            behavior_id=None,
            behavior_scenario_id=None,
            scenario_intent_key=None,
            confidence=0.0,
            matched_terms=[],
            reason="No matching behavior scenario found"
        )
    
    def _get_work_item_mapping(
        self,
        test_case: ExternalTestCase
    ) -> Optional[WorkItemBehaviorMapping]:
        """
        Get work item behavior mapping for context.
        
        Args:
            test_case: ExternalTestCase
            
        Returns:
            WorkItemBehaviorMapping if found, None otherwise
        """
        if not test_case.linked_work_item_keys:
            return None
        
        # Get the first linked work item key
        work_item_key = test_case.linked_work_item_keys[0] if test_case.linked_work_item_keys else None
        if not work_item_key:
            return None
        
        # Find ExternalWorkItem with this key
        from app.models.external_work_item import ExternalWorkItem
        work_item = self.db.query(ExternalWorkItem).filter(
            ExternalWorkItem.external_key == work_item_key,
            ExternalWorkItem.repository_id == test_case.repository_id
        ).first()
        
        if not work_item:
            return None
        
        # Get mapping for this work item
        mapping = self.db.query(WorkItemBehaviorMapping).filter(
            WorkItemBehaviorMapping.external_work_item_id == work_item.id
        ).first()
        
        return mapping
    
    def _match_high_confidence(
        self,
        test_case: ExternalTestCase,
        repository_id: uuid.UUID,
        work_item_mapping: Optional[WorkItemBehaviorMapping]
    ) -> Optional[ScenarioMappingResult]:
        """
        Match with HIGH confidence based on title + steps + linked work item.
        
        High match criteria:
        - Title contains scenario terms
        - Steps contain scenario-specific terms
        - Linked work item supports the match
        - Multiple term matches
        
        Args:
            test_case: ExternalTestCase to match
            repository_id: Repository ID
            work_item_mapping: Work item behavior mapping for context
            
        Returns:
            ScenarioMappingResult if high confidence match found, None otherwise
        """
        # Get all behavior scenarios for the repository
        scenarios = self.db.query(BehaviorScenario).join(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
            BehaviorScenario.status == "ACTIVE"
        ).all()
        
        if not scenarios:
            return None
        
        # Prepare test case text for matching (title + steps + linked work item context)
        test_case_text = self._prepare_test_case_text(
            test_case.title,
            test_case.description,
            test_case.steps,
            work_item_mapping
        )
        
        best_match = None
        best_score = 0.0
        best_terms = []
        
        for scenario in scenarios:
            # Prepare scenario text for matching
            scenario_text = self._prepare_scenario_text(
                scenario.title,
                scenario.description
            )
            
            # Calculate match score
            score, matched_terms = self._calculate_match_score(test_case_text, scenario_text)
            
            # Boost score if work item mapping supports this behavior
            if work_item_mapping and work_item_mapping.behavior_id == scenario.behavior_id:
                score += 0.1
            
            if score > best_score:
                best_score = score
                best_match = scenario
                best_terms = matched_terms
        
        # Check if we have a high confidence match
        if best_score >= self.HIGH_CONFIDENCE_MIN and best_match:
            return ScenarioMappingResult(
                behavior_id=best_match.behavior_id,
                behavior_scenario_id=best_match.id,
                scenario_intent_key=self._generate_scenario_intent_key(best_match),
                confidence=best_score,
                matched_terms=best_terms,
                reason=f"High confidence match: title + steps + linked work item match with {best_match.title}"
            )
        
        return None
    
    def _match_medium_confidence(
        self,
        test_case: ExternalTestCase,
        repository_id: uuid.UUID
    ) -> Optional[ScenarioMappingResult]:
        """
        Match with MEDIUM confidence based on title + steps.
        
        Medium match criteria:
        - Title contains scenario terms
        - Steps contain scenario-specific terms
        - Partial term matches
        
        Args:
            test_case: ExternalTestCase to match
            repository_id: Repository ID
            
        Returns:
            ScenarioMappingResult if medium confidence match found, None otherwise
        """
        # Get all behavior scenarios for the repository
        scenarios = self.db.query(BehaviorScenario).join(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
            BehaviorScenario.status == "ACTIVE"
        ).all()
        
        if not scenarios:
            return None
        
        # Prepare test case text (title + steps, no work item context)
        test_case_text = self._prepare_test_case_text(
            test_case.title,
            test_case.description,
            test_case.steps,
            None
        )
        
        best_match = None
        best_score = 0.0
        best_terms = []
        
        for scenario in scenarios:
            # Prepare scenario text
            scenario_text = self._prepare_scenario_text(
                scenario.title,
                scenario.description
            )
            
            # Calculate match score
            score, matched_terms = self._calculate_match_score(test_case_text, scenario_text)
            
            if score > best_score:
                best_score = score
                best_match = scenario
                best_terms = matched_terms
        
        # Check if we have a medium confidence match
        if best_score >= self.MEDIUM_CONFIDENCE_MIN and best_match:
            return ScenarioMappingResult(
                behavior_id=best_match.behavior_id,
                behavior_scenario_id=best_match.id,
                scenario_intent_key=self._generate_scenario_intent_key(best_match),
                confidence=best_score,
                matched_terms=best_terms,
                reason=f"Medium confidence match: title + steps match with {best_match.title}"
            )
        
        return None
    
    def _match_low_confidence(
        self,
        test_case: ExternalTestCase,
        repository_id: uuid.UUID
    ) -> Optional[ScenarioMappingResult]:
        """
        Match with LOW confidence based on title only.
        
        Low match criteria:
        - Title contains scenario terms
        - Broad thematic match
        - Single strong match
        
        Args:
            test_case: ExternalTestCase to match
            repository_id: Repository ID
            
        Returns:
            ScenarioMappingResult if low confidence match found, None otherwise
        """
        # Get all behavior scenarios for the repository
        scenarios = self.db.query(BehaviorScenario).join(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
            BehaviorScenario.status == "ACTIVE"
        ).all()
        
        if not scenarios:
            return None
        
        # Prepare test case text (title only)
        test_case_text = self._prepare_test_case_text(
            test_case.title,
            None,
            [],
            None
        )
        
        best_match = None
        best_score = 0.0
        best_terms = []
        
        for scenario in scenarios:
            # Prepare scenario text
            scenario_text = self._prepare_scenario_text(
                scenario.title,
                scenario.description
            )
            
            # Calculate match score
            score, matched_terms = self._calculate_match_score(test_case_text, scenario_text)
            
            if score > best_score:
                best_score = score
                best_match = scenario
                best_terms = matched_terms
        
        # Check if we have a low confidence match
        if best_score >= self.LOW_CONFIDENCE_MIN and best_match:
            return ScenarioMappingResult(
                behavior_id=best_match.behavior_id,
                behavior_scenario_id=best_match.id,
                scenario_intent_key=self._generate_scenario_intent_key(best_match),
                confidence=best_score,
                matched_terms=best_terms,
                reason=f"Low confidence match: title match with {best_match.title}"
            )
        
        return None
    
    def _prepare_test_case_text(
        self,
        title: str,
        description: Optional[str],
        steps: List[Dict[str, str]],
        work_item_mapping: Optional[WorkItemBehaviorMapping]
    ) -> str:
        """
        Prepare test case text for matching by normalizing and combining.
        
        Args:
            title: Test case title
            description: Test case description
            steps: Test case steps
            work_item_mapping: Work item behavior mapping for context
            
        Returns:
            Normalized text string
        """
        parts = []
        
        if title:
            parts.append(title.lower())
        
        if description:
            parts.append(description.lower())
        
        # Add step text
        if steps:
            for step in steps:
                if isinstance(step, dict):
                    step_text = step.get('step', '')
                    expected_text = step.get('expected', '')
                    if step_text:
                        parts.append(step_text.lower())
                    if expected_text:
                        parts.append(expected_text.lower())
        
        # Add work item context if available
        if work_item_mapping and work_item_mapping.matched_terms:
            parts.extend([term.lower() for term in work_item_mapping.matched_terms])
        
        return ' '.join(parts)
    
    def _prepare_scenario_text(
        self,
        title: str,
        description: Optional[str]
    ) -> str:
        """
        Prepare scenario text for matching by normalizing and combining.
        
        Args:
            title: Scenario title
            description: Scenario description
            
        Returns:
            Normalized text string
        """
        parts = []
        
        if title:
            parts.append(title.lower())
        
        if description:
            parts.append(description.lower())
        
        return ' '.join(parts)
    
    def _calculate_match_score(
        self,
        text1: str,
        text2: str
    ) -> Tuple[float, List[str]]:
        """
        Calculate match score between two text strings.
        
        Uses term overlap and keyword matching.
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            Tuple of (score, matched_terms)
        """
        # Extract terms from both texts
        terms1 = self._extract_terms(text1)
        terms2 = self._extract_terms(text2)
        
        if not terms1 or not terms2:
            return 0.0, []
        
        # Find matching terms
        matched_terms = set(terms1) & set(terms2)
        
        if not matched_terms:
            return 0.0, []
        
        # Calculate score based on overlap ratio
        overlap_ratio = len(matched_terms) / max(len(terms1), len(terms2))
        
        # Boost score for exact phrase matches
        phrase_boost = self._calculate_phrase_boost(text1, text2)
        
        score = min(1.0, overlap_ratio + phrase_boost)
        
        return score, list(matched_terms)
    
    def _extract_terms(self, text: str) -> List[str]:
        """
        Extract meaningful terms from text.
        
        Args:
            text: Input text
            
        Returns:
            List of terms
        """
        # Remove special characters and split into words
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        
        # Filter out common stop words
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'this',
            'that', 'with', 'they', 'from', 'will', 'more', 'when', 'what',
            'about', 'which', 'their', 'there', 'would', 'could', 'should',
            'test', 'verify', 'check', 'ensure', 'then', 'into', 'after', 'before'
        }
        
        terms = [word for word in words if word not in stop_words]
        
        return terms
    
    def _calculate_phrase_boost(self, text1: str, text2: str) -> float:
        """
        Calculate boost score for exact phrase matches.
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            Boost score (0.0 to 0.3)
        """
        boost = 0.0
        
        # Look for 2-word and 3-word phrase matches
        for phrase_length in [3, 2]:
            phrases1 = self._extract_phrases(text1, phrase_length)
            phrases2 = self._extract_phrases(text2, phrase_length)
            
            phrase_matches = set(phrases1) & set(phrases2)
            if phrase_matches:
                boost += 0.15 * len(phrase_matches)
        
        return min(0.3, boost)
    
    def _extract_phrases(self, text: str, length: int) -> List[str]:
        """
        Extract n-word phrases from text.
        
        Args:
            text: Input text
            length: Phrase length in words
            
        Returns:
            List of phrases
        """
        words = text.split()
        phrases = []
        
        for i in range(len(words) - length + 1):
            phrase = ' '.join(words[i:i + length])
            phrases.append(phrase)
        
        return phrases
    
    def _generate_scenario_intent_key(self, scenario: BehaviorScenario) -> str:
        """
        Generate scenario intent key from behavior scenario.
        
        Args:
            scenario: BehaviorScenario
            
        Returns:
            Scenario intent key string
        """
        # Generate a key based on behavior_id and scenario_id
        return f"{scenario.behavior_id}:{scenario.id}"
    
    def save_mapping(
        self,
        test_case: ExternalTestCase,
        result: ScenarioMappingResult
    ) -> ExternalTestScenarioMapping:
        """
        Save or update an external test case scenario mapping.
        
        Args:
            test_case: ExternalTestCase
            result: ScenarioMappingResult
            
        Returns:
            ExternalTestScenarioMapping
        """
        # Check for existing mapping
        existing = self.db.query(ExternalTestScenarioMapping).filter(
            ExternalTestScenarioMapping.external_test_case_id == test_case.id
        ).first()
        
        if existing:
            # Update existing mapping if new result has higher confidence
            if result.confidence > existing.confidence:
                existing.behavior_id = result.behavior_id
                existing.behavior_scenario_id = result.behavior_scenario_id
                existing.scenario_intent_key = result.scenario_intent_key
                existing.confidence = result.confidence
                existing.matched_terms = result.matched_terms
                existing.reason = result.reason
                self.db.commit()
            return existing
        else:
            # Create new mapping
            mapping = ExternalTestScenarioMapping(
                id=uuid.uuid4(),
                external_test_case_id=test_case.id,
                behavior_id=result.behavior_id,
                behavior_scenario_id=result.behavior_scenario_id,
                scenario_intent_key=result.scenario_intent_key,
                confidence=result.confidence,
                matched_terms=result.matched_terms,
                reason=result.reason,
                created_at=datetime.utcnow()
            )
            self.db.add(mapping)
            self.db.commit()
            return mapping
