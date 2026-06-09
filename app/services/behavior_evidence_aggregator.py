from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session


@dataclass
class UnifiedEvidence:
    """Unified evidence from any source."""
    source_type: str  # ROUTE, TEST, MODULE, DOCUMENTATION, PAGE, SERVICE
    source_identifier: str  # Route path, test name, module name, etc.
    confidence: str  # HIGH, MODERATE, LOW
    excerpt: Optional[str] = None  # Relevant excerpt (for documentation)
    metadata: Optional[Dict[str, Any]] = None  # Additional source-specific metadata


@dataclass
class BehaviorCandidate:
    """Aggregated behavior candidate from multiple evidence sources."""
    name: str  # Behavior name
    journey: Optional[str]  # Associated journey
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: str  # HIGH, MODERATE, LOW (aggregated)
    evidences: List[UnifiedEvidence] = field(default_factory=list)
    source_confidence_score: float = 0.0  # Raw confidence score (0-100)
    description: Optional[str] = None
    
    def add_evidence(self, evidence: UnifiedEvidence) -> None:
        """Add evidence to this candidate."""
        self.evidences.append(evidence)
    
    def get_evidence_count_by_source(self) -> Dict[str, int]:
        """Get count of evidences by source type."""
        counts = {}
        for evidence in self.evidences:
            source = evidence.source_type
            if source not in counts:
                counts[source] = 0
            counts[source] += 1
        return counts
    
    def get_high_confidence_evidence_count(self) -> int:
        """Get count of high confidence evidences."""
        return sum(1 for e in self.evidences if e.confidence == "HIGH")


class BehaviorEvidenceAggregator:
    """Aggregator to combine evidence from all discovery sources."""
    
    # Confidence weighting for each source type
    SOURCE_WEIGHTS: Dict[str, float] = {
        "ROUTE": 25.0,
        "TEST": 20.0,
        "MODULE": 15.0,
        "DOCUMENTATION": 15.0,
        "PAGE": 15.0,
        "SERVICE": 10.0,
    }
    
    # Confidence level values
    CONFIDENCE_VALUES: Dict[str, float] = {
        "HIGH": 1.0,
        "MODERATE": 0.6,
        "LOW": 0.3,
    }
    
    # Threshold for behavior candidate acceptance
    CONFIDENCE_THRESHOLD: float = 30.0  # Minimum score to be considered a valid candidate
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the aggregator with optional database session."""
        self.db = db
        self._pattern_library = None
    
    def _get_pattern_library(self):
        """Get or initialize the pattern library."""
        if self._pattern_library is None and self.db:
            from app.services.behavior_pattern_library import BehaviorPatternLibrary
            self._pattern_library = BehaviorPatternLibrary(self.db)
            self._pattern_library.load_patterns()
        return self._pattern_library
    
    def aggregate_evidence(
        self,
        route_evidences: Optional[List] = None,
        test_evidences: Optional[List] = None,
        module_evidences: Optional[List] = None,
        documentation_evidences: Optional[List] = None,
        page_evidences: Optional[List] = None,
        service_evidences: Optional[List] = None,
    ) -> List[BehaviorCandidate]:
        """Aggregate evidence from all sources and generate behavior candidates."""
        # Collect all evidence by behavior name
        evidence_by_behavior: Dict[str, List[UnifiedEvidence]] = {}
        
        # Process route evidences
        if route_evidences:
            for evidence in route_evidences:
                unified = self._convert_route_evidence(evidence)
                if unified:
                    if unified.source_identifier not in evidence_by_behavior:
                        evidence_by_behavior[unified.source_identifier] = []
                    evidence_by_behavior[unified.source_identifier].append(unified)
        
        # Process test evidences
        if test_evidences:
            for evidence in test_evidences:
                unified = self._convert_test_evidence(evidence)
                if unified:
                    if unified.source_identifier not in evidence_by_behavior:
                        evidence_by_behavior[unified.source_identifier] = []
                    evidence_by_behavior[unified.source_identifier].append(unified)
        
        # Process module evidences
        if module_evidences:
            for evidence in module_evidences:
                unified = self._convert_module_evidence(evidence)
                if unified:
                    if unified.source_identifier not in evidence_by_behavior:
                        evidence_by_behavior[unified.source_identifier] = []
                    evidence_by_behavior[unified.source_identifier].append(unified)
        
        # Process documentation evidences
        if documentation_evidences:
            for evidence in documentation_evidences:
                unified = self._convert_documentation_evidence(evidence)
                if unified:
                    if unified.source_identifier not in evidence_by_behavior:
                        evidence_by_behavior[unified.source_identifier] = []
                    evidence_by_behavior[unified.source_identifier].append(unified)
        
        # Process page evidences
        if page_evidences:
            for evidence in page_evidences:
                unified = self._convert_page_evidence(evidence)
                if unified:
                    if unified.source_identifier not in evidence_by_behavior:
                        evidence_by_behavior[unified.source_identifier] = []
                    evidence_by_behavior[unified.source_identifier].append(unified)
        
        # Process service evidences
        if service_evidences:
            for evidence in service_evidences:
                unified = self._convert_service_evidence(evidence)
                if unified:
                    if unified.source_identifier not in evidence_by_behavior:
                        evidence_by_behavior[unified.source_identifier] = []
                    evidence_by_behavior[unified.source_identifier].append(unified)
        
        # Generate behavior candidates
        candidates = []
        for behavior_name, evidences in evidence_by_behavior.items():
            candidate = self._create_candidate(behavior_name, evidences)
            if candidate and candidate.source_confidence_score >= self.CONFIDENCE_THRESHOLD:
                candidates.append(candidate)
        
        # Sort by confidence score (descending)
        candidates.sort(key=lambda c: c.source_confidence_score, reverse=True)
        
        return candidates
    
    def _convert_route_evidence(self, evidence) -> Optional[UnifiedEvidence]:
        """Convert route evidence to unified format."""
        return UnifiedEvidence(
            source_type="ROUTE",
            source_identifier=evidence.behavior,
            confidence=evidence.confidence,
            metadata={
                "route": evidence.route,
                "http_method": evidence.http_method,
                "matched_alias": evidence.matched_alias,
            },
        )
    
    def _convert_test_evidence(self, evidence) -> Optional[UnifiedEvidence]:
        """Convert test evidence to unified format."""
        return UnifiedEvidence(
            source_type="TEST",
            source_identifier=evidence.behavior,
            confidence=evidence.confidence,
            metadata={
                "test_identifier": evidence.test_identifier,
                "test_type": evidence.test_type,
                "matched_alias": evidence.matched_alias,
                "normalized_tokens": evidence.normalized_tokens,
            },
        )
    
    def _convert_module_evidence(self, evidence) -> Optional[UnifiedEvidence]:
        """Convert module evidence to unified format."""
        return UnifiedEvidence(
            source_type="MODULE",
            source_identifier=evidence.behavior,
            confidence=evidence.confidence,
            metadata={
                "module": evidence.module,
                "module_type": evidence.module_type,
                "matched_alias": evidence.matched_alias,
                "normalized_tokens": evidence.normalized_tokens,
            },
        )
    
    def _convert_documentation_evidence(self, evidence) -> Optional[UnifiedEvidence]:
        """Convert documentation evidence to unified format."""
        return UnifiedEvidence(
            source_type="DOCUMENTATION",
            source_identifier=evidence.behavior,
            confidence=evidence.confidence,
            excerpt=evidence.excerpt,
            metadata={
                "source_document": evidence.source_document,
                "document_type": evidence.document_type,
                "matched_alias": evidence.matched_alias,
                "line_number": evidence.line_number,
            },
        )
    
    def _convert_page_evidence(self, evidence) -> Optional[UnifiedEvidence]:
        """Convert page evidence to unified format."""
        return UnifiedEvidence(
            source_type="PAGE",
            source_identifier=evidence.behavior,
            confidence=evidence.confidence,
            metadata={
                "page": evidence.page,
                "matched_alias": evidence.matched_alias,
            },
        )
    
    def _convert_service_evidence(self, evidence) -> Optional[UnifiedEvidence]:
        """Convert service evidence to unified format."""
        return UnifiedEvidence(
            source_type="SERVICE",
            source_identifier=evidence.behavior,
            confidence=evidence.confidence,
            metadata={
                "service": evidence.service,
                "matched_alias": evidence.matched_alias,
            },
        )
    
    def _create_candidate(self, behavior_name: str, evidences: List[UnifiedEvidence]) -> Optional[BehaviorCandidate]:
        """Create a behavior candidate from aggregated evidence."""
        # Calculate weighted confidence score
        score = self._calculate_weighted_score(evidences)
        
        # Determine aggregated confidence level
        aggregated_confidence = self._determine_confidence_level(score)
        
        # Get journey and risk from pattern library
        pattern_library = self._get_pattern_library()
        journey = None
        risk_level = "MEDIUM"
        description = None
        
        if pattern_library:
            pattern = pattern_library.get_pattern(behavior_name)
            if pattern:
                journey = pattern.journey
                risk_level = pattern.risk_level
                description = pattern.description
        
        # Create candidate
        candidate = BehaviorCandidate(
            name=behavior_name,
            journey=journey,
            risk_level=risk_level,
            confidence=aggregated_confidence,
            evidences=evidences,
            source_confidence_score=score,
            description=description,
        )
        
        return candidate
    
    def _calculate_weighted_score(self, evidences: List[UnifiedEvidence]) -> float:
        """Calculate weighted confidence score from evidences."""
        total_score = 0.0
        
        for evidence in evidences:
            source_weight = self.SOURCE_WEIGHTS.get(evidence.source_type, 0.0)
            confidence_value = self.CONFIDENCE_VALUES.get(evidence.confidence, 0.0)
            total_score += source_weight * confidence_value
        
        return total_score
    
    def _determine_confidence_level(self, score: float) -> str:
        """Determine confidence level from weighted score."""
        if score >= 60.0:
            return "HIGH"
        elif score >= 30.0:
            return "MODERATE"
        else:
            return "LOW"
    
    def get_aggregation_stats(self, candidates: List[BehaviorCandidate]) -> Dict[str, Any]:
        """Get statistics about the aggregation results."""
        if not candidates:
            return {
                "total_candidates": 0,
                "total_evidences": 0,
                "average_score": 0.0,
                "by_confidence": {},
                "by_source": {},
            }
        
        total_evidences = sum(len(c.evidences) for c in candidates)
        average_score = sum(c.source_confidence_score for c in candidates) / len(candidates)
        
        by_confidence = {"HIGH": 0, "MODERATE": 0, "LOW": 0}
        for candidate in candidates:
            by_confidence[candidate.confidence] += 1
        
        by_source = {}
        for candidate in candidates:
            source_counts = candidate.get_evidence_count_by_source()
            for source, count in source_counts.items():
                if source not in by_source:
                    by_source[source] = 0
                by_source[source] += count
        
        return {
            "total_candidates": len(candidates),
            "total_evidences": total_evidences,
            "average_score": average_score,
            "by_confidence": by_confidence,
            "by_source": by_source,
        }

