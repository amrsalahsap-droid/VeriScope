"""Test script to verify confidence calculation logic."""
import sys
sys.path.insert(0, 'c:/Users/amrsa/Downloads/veriscope')

from app.services.signal_metadata import calculate_confidence_and_ceiling

# Test case 1: High score with all signals
print("Test 1: High score (80%) with all signals available")
result = calculate_confidence_and_ceiling(
    readiness_score=0.8,
    available_signals=['source_code', 'pull_request_diff', 'coverage_report', 'test_history', 'acceptance_criteria', 'current_pr_execution', 'architecture_graph', 'behavior_catalog', 'journey_catalog'],
    missing_signals=[],
    signal_statuses={}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

# Test case 2: High score but missing coverage (should cap at MEDIUM)
print("Test 2: High score (80%) but missing coverage_report")
result = calculate_confidence_and_ceiling(
    readiness_score=0.8,
    available_signals=['source_code', 'pull_request_diff', 'test_history', 'acceptance_criteria', 'current_pr_execution', 'architecture_graph', 'behavior_catalog', 'journey_catalog'],
    missing_signals=['coverage_report'],
    signal_statuses={}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

# Test case 3: High score but missing required signals (should cap at LOW)
print("Test 3: High score (80%) but missing source_code")
result = calculate_confidence_and_ceiling(
    readiness_score=0.8,
    available_signals=['pull_request_diff', 'coverage_report', 'test_history', 'acceptance_criteria', 'current_pr_execution'],
    missing_signals=['source_code'],
    signal_statuses={}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

# Test case 4: Medium score with missing test history and manual tests (should cap at LOW)
print("Test 4: Medium score (50%) missing both junit_test_history and manual tests")
result = calculate_confidence_and_ceiling(
    readiness_score=0.5,
    available_signals=['source_code', 'pull_request_diff', 'coverage_report', 'acceptance_criteria', 'current_pr_execution'],
    missing_signals=['junit_test_history', 'managed_manual_tests'],
    signal_statuses={}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

# Test case 5: Low score with no blockers
print("Test 5: Low score (30%) with no blockers")
result = calculate_confidence_and_ceiling(
    readiness_score=0.3,
    available_signals=['source_code', 'pull_request_diff'],
    missing_signals=['coverage_report', 'test_history', 'acceptance_criteria'],
    signal_statuses={}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

# Test case 6: Stale coverage (should cap at MEDIUM)
print("Test 6: High score (80%) with stale coverage")
result = calculate_confidence_and_ceiling(
    readiness_score=0.8,
    available_signals=['source_code', 'pull_request_diff', 'coverage_report', 'test_history', 'acceptance_criteria', 'current_pr_execution'],
    missing_signals=[],
    signal_statuses={'coverage_report': 'STALE'}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

# Test case 7: Missing all architecture/behavior/journey (should cap at MEDIUM)
print("Test 7: High score (80%) missing architecture, behavior, and journey catalogs")
result = calculate_confidence_and_ceiling(
    readiness_score=0.8,
    available_signals=['source_code', 'pull_request_diff', 'coverage_report', 'test_history', 'acceptance_criteria', 'current_pr_execution'],
    missing_signals=['architecture_graph', 'behavior_catalog', 'journey_catalog'],
    signal_statuses={}
)
print(f"  Expected Confidence: {result['expected_confidence']}")
print(f"  Confidence Ceiling: {result['confidence_ceiling']}")
print(f"  Confidence Reason: {result['confidence_reason']}")
print(f"  Confidence Blockers: {result['confidence_blockers']}")
print()

print("All tests completed!")
