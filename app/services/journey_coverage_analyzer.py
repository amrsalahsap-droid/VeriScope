from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey_behavior import JourneyBehavior
from app.services.journey_coverage import JourneyCoverage


class JourneyCoverageAnalyzer:
    """Analyzer to measure journey-level test coverage."""
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the journey coverage analyzer with optional database session."""
        self.db = db
    
    def analyze_journey_coverage(
        self,
        journey: Journey,
        behaviors: List[Behavior],
        journey_behaviors: List[JourneyBehavior],
        behavior_scenarios: Dict[str, List[BehaviorScenario]],
        test_coverage_map: Dict[str, float],  # behavior_id -> coverage percentage
    ) -> JourneyCoverage:
        """Analyze coverage for a journey."""
        # Get behaviors for this journey
        journey_behavior_ids = set(str(jb.behavior_id) for jb in journey_behaviors if str(jb.journey_id) == str(journey.id))
        journey_behaviors_list = [b for b in behaviors if str(b.id) in journey_behavior_ids]
        
        if not journey_behaviors_list:
            return JourneyCoverage(
                journey_id=str(journey.id),
                journey_name=journey.name,
                covered_behaviors=[],
                partially_covered_behaviors=[],
                uncovered_behaviors=[],
                coverage_score=0.0,
                confidence="LOW",
            )
        
        # Categorize behaviors by coverage
        covered = []
        partially_covered = []
        uncovered = []
        
        for behavior in journey_behaviors_list:
            coverage = test_coverage_map.get(str(behavior.id), 0.0)
            
            if coverage >= 80:
                covered.append(behavior.name)
            elif coverage >= 30:
                partially_covered.append(behavior.name)
            else:
                uncovered.append(behavior.name)
        
        # Calculate coverage score
        coverage_score = self._calculate_coverage_score(
            covered,
            partially_covered,
            uncovered,
            journey_behaviors_list,
        )
        
        # Determine confidence
        confidence = self._determine_confidence(
            journey_behaviors_list,
            behavior_scenarios,
            test_coverage_map,
        )
        
        return JourneyCoverage(
            journey_id=str(journey.id),
            journey_name=journey.name,
            covered_behaviors=covered,
            partially_covered_behaviors=partially_covered,
            uncovered_behaviors=uncovered,
            coverage_score=coverage_score,
            confidence=confidence,
        )
    
    def _calculate_coverage_score(
        self,
        covered: List[str],
        partially_covered: List[str],
        uncovered: List[str],
        all_behaviors: List[Behavior],
    ) -> float:
        """Calculate overall coverage score (0-100)."""
        if not all_behaviors:
            return 0.0
        
        total = len(all_behaviors)
        covered_count = len(covered)
        partially_count = len(partially_covered)
        
        # Weighted score: full coverage = 100%, partial = 50%, none = 0%
        score = (covered_count * 100 + partially_count * 50) / total
        return round(score, 2)
    
    def _determine_confidence(
        self,
        behaviors: List[Behavior],
        behavior_scenarios: Dict[str, List[BehaviorScenario]],
        test_coverage_map: Dict[str, float],
    ) -> str:
        """Determine confidence in coverage assessment."""
        if not behaviors:
            return "LOW"
        
        # Check scenario coverage
        behaviors_with_scenarios = 0
        behaviors_with_tests = 0
        
        for behavior in behaviors:
            scenarios = behavior_scenarios.get(str(behavior.id), [])
            if scenarios:
                behaviors_with_scenarios += 1
            
            coverage = test_coverage_map.get(str(behavior.id), 0.0)
            if coverage > 0:
                behaviors_with_tests += 1
        
        total = len(behaviors)
        
        # High confidence if most behaviors have scenarios and tests
        if behaviors_with_scenarios / total >= 0.7 and behaviors_with_tests / total >= 0.7:
            return "HIGH"
        elif behaviors_with_scenarios / total >= 0.4 or behaviors_with_tests / total >= 0.4:
            return "MODERATE"
        else:
            return "LOW"
    
    def batch_analyze_coverage(
        self,
        journeys: List[Journey],
        behaviors: List[Behavior],
        journey_behaviors: List[JourneyBehavior],
        behavior_scenarios: Dict[str, List[BehaviorScenario]],
        test_coverage_map: Dict[str, float],
    ) -> List[JourneyCoverage]:
        """Analyze coverage for multiple journeys."""
        coverages = []
        
        for journey in journeys:
            coverage = self.analyze_journey_coverage(
                journey,
                behaviors,
                journey_behaviors,
                behavior_scenarios,
                test_coverage_map,
            )
            coverages.append(coverage)
        
        return coverages
    
    def get_coverage_summary(self, coverages: List[JourneyCoverage]) -> Dict:
        """Get summary of journey coverage."""
        if not coverages:
            return {
                "total_journeys": 0,
                "average_coverage": 0.0,
                "total_covered_behaviors": 0,
                "total_partially_covered": 0,
                "total_uncovered": 0,
                "by_confidence": {"HIGH": 0, "MODERATE": 0, "LOW": 0},
            }
        
        total_covered = sum(len(c.covered_behaviors) for c in coverages)
        total_partial = sum(len(c.partially_covered_behaviors) for c in coverages)
        total_uncovered = sum(len(c.uncovered_behaviors) for c in coverages)
        average_coverage = sum(c.coverage_score for c in coverages) / len(coverages)
        
        by_confidence = {"HIGH": 0, "MODERATE": 0, "LOW": 0}
        for coverage in coverages:
            by_confidence[coverage.confidence] += 1
        
        return {
            "total_journeys": len(coverages),
            "average_coverage": round(average_coverage, 2),
            "total_covered_behaviors": total_covered,
            "total_partially_covered": total_partial,
            "total_uncovered": total_uncovered,
            "by_confidence": by_confidence,
        }
    
    def get_coverage_gaps(self, coverage: JourneyCoverage) -> List[str]:
        """Get coverage gaps for a journey."""
        gaps = []
        
        if coverage.uncovered_behaviors:
            gaps.append(f"Uncovered behaviors: {', '.join(coverage.uncovered_behaviors)}")
        
        if coverage.partially_covered_behaviors:
            gaps.append(f"Partially covered: {', '.join(coverage.partially_covered_behaviors)}")
        
        if coverage.coverage_score < 50:
            gaps.append(f"Low overall coverage: {coverage.coverage_score}%")
        
        return gaps
