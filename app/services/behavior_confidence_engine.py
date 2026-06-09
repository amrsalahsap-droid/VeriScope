from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session


@dataclass
class ConfidenceBreakdown:
    """Breakdown of confidence score components."""
    evidence_count_score: float  # Score based on number of evidences
    evidence_diversity_score: float  # Score based on source diversity
    pattern_quality_score: float  # Score based on pattern match quality
    repository_coverage_score: float  # Score based on repository coverage
    total_score: float  # Combined confidence score (0-100)
    confidence_level: str  # LOW, MEDIUM, HIGH
    
    # Detailed breakdown for explainability
    evidence_count: int = 0
    evidence_sources: List[str] = field(default_factory=list)
    high_confidence_evidence_count: int = 0
    pattern_match_type: Optional[str] = None  # DIRECT, PARTIAL, INFERRED
    coverage_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert breakdown to dictionary for serialization."""
        return {
            "evidence_count_score": self.evidence_count_score,
            "evidence_diversity_score": self.evidence_diversity_score,
            "pattern_quality_score": self.pattern_quality_score,
            "repository_coverage_score": self.repository_coverage_score,
            "total_score": self.total_score,
            "confidence_level": self.confidence_level,
            "evidence_count": self.evidence_count,
            "evidence_sources": self.evidence_sources,
            "high_confidence_evidence_count": self.high_confidence_evidence_count,
            "pattern_match_type": self.pattern_match_type,
            "coverage_percentage": self.coverage_percentage,
        }


class BehaviorConfidenceEngine:
    """Engine to generate explainable confidence scores for behaviors."""
    
    # Score weights for each component
    EVIDENCE_COUNT_WEIGHT: float = 0.3
    EVIDENCE_DIVERSITY_WEIGHT: float = 0.3
    PATTERN_QUALITY_WEIGHT: float = 0.25
    REPOSITORY_COVERAGE_WEIGHT: float = 0.15
    
    # Confidence level thresholds
    HIGH_THRESHOLD: float = 70.0
    MEDIUM_THRESHOLD: float = 40.0
    
    # Evidence count scoring parameters
    MIN_EVIDENCE_FOR_HIGH: int = 5
    MIN_EVIDENCE_FOR_MEDIUM: int = 2
    
    # Diversity scoring parameters
    MAX_UNIQUE_SOURCES: int = 6  # ROUTE, TEST, MODULE, DOCUMENTATION, PAGE, SERVICE
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the confidence engine with optional database session."""
        self.db = db
    
    def calculate_confidence(
        self,
        evidences: List[Any],
        repository_total_files: Optional[int] = None,
        repository_behavior_files: Optional[int] = None,
    ) -> ConfidenceBreakdown:
        """Calculate explainable confidence score for a behavior."""
        # Calculate individual component scores
        evidence_count_score, evidence_count, high_conf_count = self._calculate_evidence_count_score(evidences)
        diversity_score, sources = self._calculate_diversity_score(evidences)
        pattern_score, match_type = self._calculate_pattern_quality_score(evidences)
        coverage_score, coverage_pct = self._calculate_coverage_score(
            repository_total_files,
            repository_behavior_files,
        )
        
        # Calculate weighted total score
        total_score = (
            evidence_count_score * self.EVIDENCE_COUNT_WEIGHT +
            diversity_score * self.EVIDENCE_DIVERSITY_WEIGHT +
            pattern_score * self.PATTERN_QUALITY_WEIGHT +
            coverage_score * self.REPOSITORY_COVERAGE_WEIGHT
        )
        
        # Determine confidence level
        confidence_level = self._determine_confidence_level(total_score)
        
        # Create breakdown
        breakdown = ConfidenceBreakdown(
            evidence_count_score=evidence_count_score,
            evidence_diversity_score=diversity_score,
            pattern_quality_score=pattern_score,
            repository_coverage_score=coverage_score,
            total_score=total_score,
            confidence_level=confidence_level,
            evidence_count=evidence_count,
            evidence_sources=sources,
            high_confidence_evidence_count=high_conf_count,
            pattern_match_type=match_type,
            coverage_percentage=coverage_pct,
        )
        
        return breakdown
    
    def _calculate_evidence_count_score(self, evidences: List[Any]) -> tuple[float, int, int]:
        """Calculate score based on evidence count."""
        count = len(evidences)
        high_conf_count = sum(1 for e in evidences if getattr(e, 'confidence', 'LOW') == 'HIGH')
        
        if count >= self.MIN_EVIDENCE_FOR_HIGH:
            score = 100.0
        elif count >= self.MIN_EVIDENCE_FOR_MEDIUM:
            # Linear interpolation between MEDIUM and HIGH
            ratio = (count - self.MIN_EVIDENCE_FOR_MEDIUM) / (self.MIN_EVIDENCE_FOR_HIGH - self.MIN_EVIDENCE_FOR_MEDIUM)
            score = 50.0 + (ratio * 50.0)
        elif count >= 1:
            score = 30.0
        else:
            score = 0.0
        
        return score, count, high_conf_count
    
    def _calculate_diversity_score(self, evidences: List[Any]) -> tuple[float, List[str]]:
        """Calculate score based on evidence source diversity."""
        # Get unique source types
        sources = set()
        for evidence in evidences:
            source_type = getattr(evidence, 'source_type', 'UNKNOWN')
            sources.add(source_type)
        
        source_list = list(sources)
        unique_count = len(source_list)
        
        # Score based on number of unique sources
        if unique_count >= 4:
            score = 100.0
        elif unique_count >= 3:
            score = 75.0
        elif unique_count >= 2:
            score = 50.0
        elif unique_count >= 1:
            score = 25.0
        else:
            score = 0.0
        
        return score, source_list
    
    def _calculate_pattern_quality_score(self, evidences: List[Any]) -> tuple[float, Optional[str]]:
        """Calculate score based on pattern match quality."""
        if not evidences:
            return 0.0, None
        
        # Determine match type based on evidence metadata
        direct_matches = 0
        partial_matches = 0
        
        for evidence in evidences:
            metadata = getattr(evidence, 'metadata', {})
            matched_alias = metadata.get('matched_alias') if metadata else None
            
            if matched_alias:
                # Check if it's a direct match (alias equals the source identifier)
                source_identifier = getattr(evidence, 'source_identifier', '')
                if matched_alias.lower() in source_identifier.lower():
                    direct_matches += 1
                else:
                    partial_matches += 1
        
        total_matches = direct_matches + partial_matches
        
        if total_matches == 0:
            return 0.0, "INFERRED"
        
        # Calculate match type
        if direct_matches / total_matches >= 0.7:
            match_type = "DIRECT"
            score = 100.0
        elif direct_matches / total_matches >= 0.3:
            match_type = "PARTIAL"
            score = 70.0
        else:
            match_type = "INFERRED"
            score = 40.0
        
        # Boost for high confidence evidence
        high_conf_ratio = sum(1 for e in evidences if getattr(e, 'confidence', 'LOW') == 'HIGH') / len(evidences)
        score += high_conf_ratio * 20.0
        
        return min(score, 100.0), match_type
    
    def _calculate_coverage_score(
        self,
        repository_total_files: Optional[int],
        repository_behavior_files: Optional[int],
    ) -> tuple[float, float]:
        """Calculate score based on repository coverage."""
        if repository_total_files is None or repository_behavior_files is None:
            return 50.0, 0.0  # Default to medium if no data
        
        if repository_total_files == 0:
            return 0.0, 0.0
        
        coverage_pct = (repository_behavior_files / repository_total_files) * 100.0
        
        # Score based on coverage percentage
        if coverage_pct >= 10.0:
            score = 100.0
        elif coverage_pct >= 5.0:
            score = 75.0
        elif coverage_pct >= 2.0:
            score = 50.0
        elif coverage_pct >= 1.0:
            score = 25.0
        else:
            score = 10.0
        
        return score, coverage_pct
    
    def _determine_confidence_level(self, score: float) -> str:
        """Determine confidence level from score."""
        if score >= self.HIGH_THRESHOLD:
            return "HIGH"
        elif score >= self.MEDIUM_THRESHOLD:
            return "MODERATE"
        else:
            return "LOW"
    
    def explain_confidence(self, breakdown: ConfidenceBreakdown) -> str:
        """Generate human-readable explanation of confidence score."""
        explanation_parts = []
        
        # Evidence count explanation
        explanation_parts.append(
            f"Found {breakdown.evidence_count} evidence(s) "
            f"({breakdown.high_confidence_evidence_count} high confidence)"
        )
        
        # Diversity explanation
        explanation_parts.append(
            f"Evidence from {len(breakdown.evidence_sources)} source(s): "
            f"{', '.join(breakdown.evidence_sources)}"
        )
        
        # Pattern quality explanation
        explanation_parts.append(
            f"Pattern match type: {breakdown.pattern_match_type}"
        )
        
        # Coverage explanation
        if breakdown.coverage_percentage > 0:
            explanation_parts.append(
                f"Repository coverage: {breakdown.coverage_percentage:.1f}%"
            )
        
        # Score breakdown
        explanation_parts.append(
            f"Score breakdown: "
            f"Count({breakdown.evidence_count_score:.1f}) + "
            f"Diversity({breakdown.evidence_diversity_score:.1f}) + "
            f"Pattern({breakdown.pattern_quality_score:.1f}) + "
            f"Coverage({breakdown.repository_coverage_score:.1f}) = "
            f"{breakdown.total_score:.1f}"
        )
        
        return ". ".join(explanation_parts) + "."
