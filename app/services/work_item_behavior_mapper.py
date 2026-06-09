"""
Work Item Behavior Mapper Service

Maps external work items (Jira, Azure DevOps, etc.) to Veriscope Behavior Catalog and Journeys.
Uses title, acceptance criteria, description, and domain vocabulary to find matches.
"""

import re
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.external_work_item import ExternalWorkItem
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping


logger = logging.getLogger("veriscope.work_item_behavior_mapper")


@dataclass
class MappingResult:
    """Result of work item to behavior/journey mapping."""
    behavior_id: Optional[uuid.UUID]
    journey_id: Optional[uuid.UUID]
    confidence: float
    matched_terms: List[str]
    reason: str


class WorkItemBehaviorMapper:
    """
    Maps external work items to behaviors and journeys.
    
    Confidence levels:
    - HIGH (0.8-1.0): Strong title/AC behavior match
    - MEDIUM (0.5-0.8): Description/domain match
    - LOW (0.2-0.5): Broad journey match
    
    Rules:
    - Do not overclaim - evidence required
    - Track matched terms for explainability
    - Store reason for mapping decision
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE_MIN = 0.8
    MEDIUM_CONFIDENCE_MIN = 0.5
    LOW_CONFIDENCE_MIN = 0.2
    
    def __init__(self, db: Session):
        """Initialize the mapper with database session."""
        self.db = db
    
    def map_work_item(
        self,
        work_item: ExternalWorkItem,
        repository_id: uuid.UUID
    ) -> MappingResult:
        """
        Map a work item to behaviors and journeys.
        
        Args:
            work_item: ExternalWorkItem to map
            repository_id: Repository ID for behavior/journey lookup
            
        Returns:
            MappingResult with behavior/journey IDs and confidence
        """
        # Try HIGH confidence match first (title/AC behavior match)
        high_result = self._match_high_confidence(work_item, repository_id)
        if high_result:
            return high_result
        
        # Try MEDIUM confidence match (description/domain match)
        medium_result = self._match_medium_confidence(work_item, repository_id)
        if medium_result:
            return medium_result
        
        # Try LOW confidence match (journey match)
        low_result = self._match_low_confidence(work_item, repository_id)
        if low_result:
            return low_result
        
        # No match found
        return MappingResult(
            behavior_id=None,
            journey_id=None,
            confidence=0.0,
            matched_terms=[],
            reason="No matching behavior or journey found"
        )
    
    def _match_high_confidence(
        self,
        work_item: ExternalWorkItem,
        repository_id: uuid.UUID
    ) -> Optional[MappingResult]:
        """
        Match with HIGH confidence based on title/AC behavior match.
        
        Strong match criteria:
        - Title contains behavior name or key terms
        - Acceptance criteria contain behavior-specific terms
        - Multiple term matches
        
        Args:
            work_item: ExternalWorkItem to match
            repository_id: Repository ID
            
        Returns:
            MappingResult if high confidence match found, None otherwise
        """
        # Get all behaviors for the repository
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False
        ).all()
        
        if not behaviors:
            return None
        
        # Prepare work item text for matching
        work_item_text = self._prepare_text_for_matching(
            work_item.title,
            work_item.description,
            work_item.acceptance_criteria
        )
        
        best_match = None
        best_score = 0.0
        best_terms = []
        
        for behavior in behaviors:
            # Prepare behavior text for matching
            behavior_text = self._prepare_text_for_matching(
                behavior.name,
                behavior.description,
                []  # Behaviors don't have AC
            )
            
            # Calculate match score
            score, matched_terms = self._calculate_match_score(work_item_text, behavior_text)
            
            if score > best_score:
                best_score = score
                best_match = behavior
                best_terms = matched_terms
        
        # Check if we have a high confidence match
        if best_score >= self.HIGH_CONFIDENCE_MIN and best_match:
            return MappingResult(
                behavior_id=best_match.id,
                journey_id=best_match.journey_id,
                confidence=best_score,
                matched_terms=best_terms,
                reason=f"High confidence match: title/AC behavior match with {best_match.name}"
            )
        
        return None
    
    def _match_medium_confidence(
        self,
        work_item: ExternalWorkItem,
        repository_id: uuid.UUID
    ) -> Optional[MappingResult]:
        """
        Match with MEDIUM confidence based on description/domain match.
        
        Medium match criteria:
        - Description contains domain vocabulary
        - Partial term matches
        - Single strong match
        
        Args:
            work_item: ExternalWorkItem to match
            repository_id: Repository ID
            
        Returns:
            MappingResult if medium confidence match found, None otherwise
        """
        # Get all behaviors for the repository
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False
        ).all()
        
        if not behaviors:
            return None
        
        # Prepare work item text (focus on description)
        work_item_text = self._prepare_text_for_matching(
            work_item.title,
            work_item.description,
            []  # Don't include AC for medium match
        )
        
        best_match = None
        best_score = 0.0
        best_terms = []
        
        for behavior in behaviors:
            # Prepare behavior text
            behavior_text = self._prepare_text_for_matching(
                behavior.name,
                behavior.description,
                []
            )
            
            # Calculate match score
            score, matched_terms = self._calculate_match_score(work_item_text, behavior_text)
            
            if score > best_score:
                best_score = score
                best_match = behavior
                best_terms = matched_terms
        
        # Check if we have a medium confidence match
        if best_score >= self.MEDIUM_CONFIDENCE_MIN and best_match:
            return MappingResult(
                behavior_id=best_match.id,
                journey_id=best_match.journey_id,
                confidence=best_score,
                matched_terms=best_terms,
                reason=f"Medium confidence match: description/domain match with {best_match.name}"
            )
        
        return None
    
    def _match_low_confidence(
        self,
        work_item: ExternalWorkItem,
        repository_id: uuid.UUID
    ) -> Optional[MappingResult]:
        """
        Match with LOW confidence based on broad journey match.
        
        Low match criteria:
        - Title/description contains journey name
        - Broad thematic match
        - No specific behavior match
        
        Args:
            work_item: ExternalWorkItem to match
            repository_id: Repository ID
            
        Returns:
            MappingResult if low confidence match found, None otherwise
        """
        # Get all journeys for the repository
        journeys = self.db.query(Journey).filter(
            Journey.repository_id == repository_id,
            Journey.is_deleted == False
        ).all()
        
        if not journeys:
            return None
        
        # Prepare work item text
        work_item_text = self._prepare_text_for_matching(
            work_item.title,
            work_item.description,
            []
        )
        
        best_match = None
        best_score = 0.0
        best_terms = []
        
        for journey in journeys:
            # Prepare journey text
            journey_text = self._prepare_text_for_matching(
                journey.name,
                journey.description,
                []
            )
            
            # Calculate match score
            score, matched_terms = self._calculate_match_score(work_item_text, journey_text)
            
            if score > best_score:
                best_score = score
                best_match = journey
                best_terms = matched_terms
        
        # Check if we have a low confidence match
        if best_score >= self.LOW_CONFIDENCE_MIN and best_match:
            return MappingResult(
                behavior_id=None,  # No specific behavior match
                journey_id=best_match.id,
                confidence=best_score,
                matched_terms=best_terms,
                reason=f"Low confidence match: broad journey match with {best_match.name}"
            )
        
        return None
    
    def _prepare_text_for_matching(
        self,
        title: str,
        description: Optional[str],
        acceptance_criteria: List[str]
    ) -> str:
        """
        Prepare text for matching by normalizing and combining.
        
        Args:
            title: Work item/behavior title
            description: Description text
            acceptance_criteria: List of acceptance criteria
            
        Returns:
            Normalized text string
        """
        parts = []
        
        if title:
            parts.append(title.lower())
        
        if description:
            parts.append(description.lower())
        
        if acceptance_criteria:
            for ac in acceptance_criteria:
                if isinstance(ac, str):
                    parts.append(ac.lower())
        
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
            'about', 'which', 'their', 'there', 'would', 'could', 'should'
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
    
    def save_mapping(
        self,
        work_item: ExternalWorkItem,
        result: MappingResult
    ) -> WorkItemBehaviorMapping:
        """
        Save or update a work item behavior mapping.
        
        Args:
            work_item: ExternalWorkItem
            result: MappingResult
            
        Returns:
            WorkItemBehaviorMapping
        """
        # Check for existing mapping
        existing = self.db.query(WorkItemBehaviorMapping).filter(
            WorkItemBehaviorMapping.external_work_item_id == work_item.id
        ).first()
        
        if existing:
            # Update existing mapping if new result has higher confidence
            if result.confidence > existing.confidence:
                existing.behavior_id = result.behavior_id
                existing.journey_id = result.journey_id
                existing.confidence = result.confidence
                existing.matched_terms = result.matched_terms
                existing.reason = result.reason
                self.db.commit()
            return existing
        else:
            # Create new mapping
            mapping = WorkItemBehaviorMapping(
                id=uuid.uuid4(),
                external_work_item_id=work_item.id,
                behavior_id=result.behavior_id,
                journey_id=result.journey_id,
                confidence=result.confidence,
                matched_terms=result.matched_terms,
                reason=result.reason,
                created_at=datetime.utcnow()
            )
            self.db.add(mapping)
            self.db.commit()
            return mapping
