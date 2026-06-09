"""
Test script for JourneyCoverageAnalyzer.

Tests journey-level coverage measurement.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.journey_coverage_analyzer import JourneyCoverageAnalyzer
from app.services.journey_coverage import JourneyCoverage
from dataclasses import dataclass
import uuid


# Mock Journey class for testing
@dataclass
class MockJourney:
    id: str
    name: str
    slug: str


# Mock Behavior class for testing
@dataclass
class MockBehavior:
    id: str
    name: str


# Mock JourneyBehavior class for testing
@dataclass
class MockJourneyBehavior:
    journey_id: str
    behavior_id: str


# Mock BehaviorScenario class for testing
@dataclass
class MockBehaviorScenario:
    id: str
    behavior_id: str


def test_journey_coverage_analyzer():
    """Test journey-level coverage measurement."""
    print("=" * 60)
    print("JOURNEY COVERAGE ANALYZER TEST")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = JourneyCoverageAnalyzer(db=None)
    
    # Test 1: Authentication Journey Coverage
    print("\nTest 1: Authentication Journey Coverage")
    print("-" * 60)
    
    auth_journey = MockJourney(
        id=uuid.uuid4(),
        name="Authentication",
        slug="authentication",
    )
    
    auth_behaviors = [
        MockBehavior(id=uuid.uuid4(), name="Login"),
        MockBehavior(id=uuid.uuid4(), name="Logout"),
        MockBehavior(id=uuid.uuid4(), name="Password Reset"),
        MockBehavior(id=uuid.uuid4(), name="Token Reuse Protection"),
    ]
    
    journey_behaviors = [
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=b.id)
        for b in auth_behaviors
    ]
    
    # Test coverage map (behavior_id -> coverage percentage)
    test_coverage_map = {
        str(auth_behaviors[0].id): 95.0,  # Login - covered
        str(auth_behaviors[1].id): 85.0,  # Logout - covered
        str(auth_behaviors[2].id): 45.0,  # Password Reset - partial
        str(auth_behaviors[3].id): 10.0,  # Token Reuse Protection - uncovered
    }
    
    # Behavior scenarios
    behavior_scenarios = {
        str(auth_behaviors[0].id): [MockBehaviorScenario(uuid.uuid4(), auth_behaviors[0].id)],
        str(auth_behaviors[1].id): [MockBehaviorScenario(uuid.uuid4(), auth_behaviors[1].id)],
        str(auth_behaviors[2].id): [MockBehaviorScenario(uuid.uuid4(), auth_behaviors[2].id)],
    }
    
    coverage = analyzer.analyze_journey_coverage(
        auth_journey,
        auth_behaviors,
        journey_behaviors,
        behavior_scenarios,
        test_coverage_map,
    )
    
    print(f"Journey: {coverage.journey_name}")
    print(f"Coverage Score: {coverage.coverage_score}%")
    print(f"Confidence: {coverage.confidence}")
    print(f"\nCovered Behaviors ({len(coverage.covered_behaviors)}):")
    for behavior in coverage.covered_behaviors:
        print(f"  - {behavior}")
    print(f"\nPartially Covered ({len(coverage.partially_covered_behaviors)}):")
    for behavior in coverage.partially_covered_behaviors:
        print(f"  - {behavior}")
    print(f"\nUncovered ({len(coverage.uncovered_behaviors)}):")
    for behavior in coverage.uncovered_behaviors:
        print(f"  - {behavior}")
    
    assert "Login" in coverage.covered_behaviors, "Expected Login in covered"
    assert "Logout" in coverage.covered_behaviors, "Expected Logout in covered"
    assert "Password Reset" in coverage.partially_covered_behaviors, "Expected Password Reset in partial"
    assert "Token Reuse Protection" in coverage.uncovered_behaviors, "Expected Token Reuse Protection in uncovered"
    print("[PASS] Authentication journey coverage analyzed correctly")
    
    # Test 2: Coverage Gaps
    print("\n\nTest 2: Coverage Gaps")
    print("-" * 60)
    
    gaps = analyzer.get_coverage_gaps(coverage)
    
    print(f"Coverage Gaps:")
    for gap in gaps:
        print(f"  - {gap}")
    
    assert len(gaps) > 0, "Expected coverage gaps"
    print("[PASS] Coverage gaps identified")
    
    # Test 3: Full Coverage
    print("\n\nTest 3: Full Coverage Journey")
    print("-" * 60)
    
    full_coverage_map = {
        str(b.id): 100.0 for b in auth_behaviors
    }
    
    coverage = analyzer.analyze_journey_coverage(
        auth_journey,
        auth_behaviors,
        journey_behaviors,
        behavior_scenarios,
        full_coverage_map,
    )
    
    print(f"Journey: {coverage.journey_name}")
    print(f"Coverage Score: {coverage.coverage_score}%")
    print(f"Covered: {len(coverage.covered_behaviors)}")
    print(f"Partial: {len(coverage.partially_covered_behaviors)}")
    print(f"Uncovered: {len(coverage.uncovered_behaviors)}")
    
    assert coverage.coverage_score == 100.0, "Expected 100% coverage"
    assert len(coverage.uncovered_behaviors) == 0, "Expected no uncovered behaviors"
    print("[PASS] Full coverage calculated correctly")
    
    # Test 4: No Coverage
    print("\n\nTest 4: No Coverage Journey")
    print("-" * 60)
    
    no_coverage_map = {
        str(b.id): 0.0 for b in auth_behaviors
    }
    
    coverage = analyzer.analyze_journey_coverage(
        auth_journey,
        auth_behaviors,
        journey_behaviors,
        behavior_scenarios,
        no_coverage_map,
    )
    
    print(f"Journey: {coverage.journey_name}")
    print(f"Coverage Score: {coverage.coverage_score}%")
    print(f"Uncovered: {len(coverage.uncovered_behaviors)}")
    
    assert coverage.coverage_score == 0.0, "Expected 0% coverage"
    assert len(coverage.uncovered_behaviors) == 4, "Expected all behaviors uncovered"
    print("[PASS] No coverage calculated correctly")
    
    # Test 5: Batch Coverage Analysis
    print("\n\nTest 5: Batch Coverage Analysis")
    print("-" * 60)
    
    billing_journey = MockJourney(
        id=uuid.uuid4(),
        name="Billing",
        slug="billing",
    )
    
    billing_behaviors = [
        MockBehavior(id=uuid.uuid4(), name="Subscription"),
        MockBehavior(id=uuid.uuid4(), name="Payment Processing"),
    ]
    
    billing_journey_behaviors = [
        MockJourneyBehavior(journey_id=billing_journey.id, behavior_id=b.id)
        for b in billing_behaviors
    ]
    
    billing_coverage_map = {
        str(billing_behaviors[0].id): 90.0,
        str(billing_behaviors[1].id): 70.0,
    }
    
    journeys = [auth_journey, billing_journey]
    all_behaviors = auth_behaviors + billing_behaviors
    all_journey_behaviors = journey_behaviors + billing_journey_behaviors
    combined_coverage_map = {**test_coverage_map, **billing_coverage_map}
    
    coverages = analyzer.batch_analyze_coverage(
        journeys,
        all_behaviors,
        all_journey_behaviors,
        behavior_scenarios,
        combined_coverage_map,
    )
    
    print(f"Analyzed coverage for {len(coverages)} journeys:")
    for cov in coverages:
        print(f"  - {cov.journey_name}: {cov.coverage_score}% ({cov.confidence} confidence)")
    
    assert len(coverages) == 2, "Expected 2 coverages"
    print("[PASS] Batch coverage analysis successful")
    
    # Test 6: Coverage Summary
    print("\n\nTest 6: Coverage Summary")
    print("-" * 60)
    
    summary = analyzer.get_coverage_summary(coverages)
    
    print(f"Total Journeys: {summary['total_journeys']}")
    print(f"Average Coverage: {summary['average_coverage']}%")
    print(f"Total Covered Behaviors: {summary['total_covered_behaviors']}")
    print(f"Total Partially Covered: {summary['total_partially_covered']}")
    print(f"Total Uncovered: {summary['total_uncovered']}")
    print(f"By Confidence: {summary['by_confidence']}")
    
    assert summary['total_journeys'] == 2, "Expected 2 journeys"
    print("[PASS] Coverage summary calculated correctly")
    
    # Test 7: Empty Journey
    print("\n\nTest 7: Empty Journey (No Behaviors)")
    print("-" * 60)
    
    empty_journey = MockJourney(
        id=uuid.uuid4(),
        name="Empty Journey",
        slug="empty-journey",
    )
    
    coverage = analyzer.analyze_journey_coverage(
        empty_journey,
        [],
        [],
        {},
        {},
    )
    
    print(f"Journey: {coverage.journey_name}")
    print(f"Coverage Score: {coverage.coverage_score}%")
    print(f"Confidence: {coverage.confidence}")
    
    assert coverage.coverage_score == 0.0, "Expected 0% coverage"
    assert coverage.confidence == "LOW", "Expected LOW confidence"
    print("[PASS] Empty journey handled correctly")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_journey_coverage_analyzer()
