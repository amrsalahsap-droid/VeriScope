"""Signal metadata and action definitions for readiness assessment."""

# Signal metadata with labels, impacts, and confidence contributions
SIGNAL_METADATA = {
    'source_code': {
        'label': 'Source code',
        'severity': 'REQUIRED',
        'impact': 'Required for any recommendation generation.',
        'confidence_contribution': 20,
        'available_impact': 'Veriscope can analyze repository structure and code changes.',
    },
    'pull_request_diff': {
        'label': 'Pull request changes',
        'severity': 'REQUIRED',
        'impact': 'Required to analyze specific changes for targeted recommendations.',
        'confidence_contribution': 20,
        'available_impact': 'Veriscope can identify changed files and analyze code modifications.',
    },
    'junit_test_history': {
        'label': 'Test history',
        'severity': 'RECOMMENDED',
        'impact': 'Improves failure pattern detection and test relevance.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'Scenario precision and failure pattern detection are reduced.',
    },
    'coverage_report': {
        'label': 'Code coverage',
        'severity': 'RECOMMENDED',
        'impact': 'Helps identify untested code areas and improve test selection.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'Cannot identify untested code areas or coverage gaps.',
    },
    'architecture_graph': {
        'label': 'Architecture graph',
        'severity': 'RECOMMENDED',
        'impact': 'Enables dependency analysis and impact assessment.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'Limited dependency analysis and impact assessment.',
    },
    'behavior_catalog': {
        'label': 'Behavior catalog',
        'severity': 'RECOMMENDED',
        'impact': 'Maps test scenarios to business logic for better coverage.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'Scenario precision and requirement coverage are reduced.',
    },
    'journey_catalog': {
        'label': 'Journey catalog',
        'severity': 'RECOMMENDED',
        'impact': 'Provides user flow understanding for comprehensive testing.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'Limited user flow understanding and scenario coverage.',
    },
    'acceptance_criteria': {
        'label': 'Acceptance criteria',
        'severity': 'RECOMMENDED',
        'impact': 'Directly improves requirement coverage and scenario precision.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'Scenario precision and requirement coverage are reduced.',
    },
    'linked_work_item': {
        'label': 'Linked work items',
        'severity': 'RECOMMENDED',
        'impact': 'Provides business context and requirement tracing.',
        'confidence_contribution': 5,
        'estimated_confidence_gain': 5,
        'missing_impact': 'Limited business requirement tracing and context.',
    },
    'managed_manual_tests': {
        'label': 'Manual tests',
        'severity': 'OPTIONAL',
        'impact': 'Completes test coverage with manual test scenarios.',
        'confidence_contribution': 5,
        'estimated_confidence_gain': 5,
        'missing_impact': 'Incomplete test coverage, missing manual test scenarios.',
    },
    'historical_outcomes': {
        'label': 'Historical outcomes',
        'severity': 'OPTIONAL',
        'impact': 'Learns from past recommendations to improve accuracy.',
        'confidence_contribution': 5,
        'estimated_confidence_gain': 5,
        'missing_impact': 'No learning from past recommendations.',
    },
    'current_pr_execution': {
        'label': 'Current PR execution',
        'severity': 'OPTIONAL',
        'impact': 'Provides real-time validation of current changes.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'No real-time validation data for current changes.',
    },
    'current_pr_coverage': {
        'label': 'Current PR coverage',
        'severity': 'OPTIONAL',
        'impact': 'Provides coverage analysis of the current changes.',
        'confidence_contribution': 10,
        'estimated_confidence_gain': 10,
        'missing_impact': 'No coverage analysis of the current changes is available.',
    },
    'business_intent': {
        'label': 'Business intent override',
        'severity': 'RECOMMENDED',
        'impact': 'Provides change reasoning and business impact context.',
        'confidence_contribution': 5,
        'estimated_confidence_gain': 5,
        'missing_impact': 'Business context is limited to pull request title and description.',
    },
    'github_connection': {
        'label': 'GitHub connection',
        'severity': 'OPTIONAL',
        'impact': 'Enhances repository intelligence and automation.',
        'confidence_contribution': 0,
        'estimated_confidence_gain': 0,
        'missing_impact': 'Limited repository intelligence and manual processes.',
    },
    'webhook_activity': {
        'label': 'Webhook activity',
        'severity': 'OPTIONAL',
        'impact': 'Enables automated triggers and real-time updates.',
        'confidence_contribution': 0,
        'estimated_confidence_gain': 0,
        'missing_impact': 'Manual trigger required and delayed updates.',
    },
    'fragility_memory': {
        'label': 'Fragility memory',
        'severity': 'OPTIONAL',
        'impact': 'Identifies high-risk areas for targeted testing.',
        'confidence_contribution': 5,
        'estimated_confidence_gain': 5,
        'missing_impact': 'Limited risk area identification and targeted testing.',
    }
}

# Action definitions with labels and priorities
ACTION_DEFINITIONS = {
    'PASTE_ACCEPTANCE_CRITERIA': {
        'label': 'Paste acceptance criteria',
        'priority': 'HIGH',
        'estimated_confidence_gain': 12,
        'description': 'Add acceptance criteria to improve requirement coverage.',
    },
    'CONNECT_JIRA': {
        'label': 'Connect to JIRA',
        'priority': 'HIGH',
        'estimated_confidence_gain': 10,
        'description': 'Link work items to trace business requirements.',
    },
    'UPLOAD_COVERAGE': {
        'label': 'Upload coverage report',
        'priority': 'HIGH',
        'estimated_confidence_gain': 15,
        'description': 'Add coverage reports to identify untested areas.',
    },
    'IMPORT_JUNIT': {
        'label': 'Import JUnit results',
        'priority': 'HIGH',
        'estimated_confidence_gain': 15,
        'description': 'Add test history to improve failure pattern detection.',
    },
    'GENERATE_ARCHITECTURE': {
        'label': 'Generate architecture graph',
        'priority': 'MEDIUM',
        'estimated_confidence_gain': 15,
        'description': 'Create dependency graph for impact analysis.',
    },
    'DISCOVER_BEHAVIORS': {
        'label': 'Discover behavior catalog',
        'priority': 'MEDIUM',
        'estimated_confidence_gain': 15,
        'description': 'Map test scenarios to business logic.',
    },
    'CREATE_JOURNEYS': {
        'label': 'Create journey catalog',
        'priority': 'MEDIUM',
        'estimated_confidence_gain': 10,
        'description': 'Document user flows for comprehensive testing.',
    },
    'IMPORT_MANUAL_TESTS': {
        'label': 'Import manual tests',
        'priority': 'MEDIUM',
        'estimated_confidence_gain': 7,
        'description': 'Add manual test cases for complete coverage.',
    },
    'ENABLE_WEBHOOKS': {
        'label': 'Enable webhooks',
        'priority': 'LOW',
        'estimated_confidence_gain': 5,
        'description': 'Configure automated triggers and real-time updates.',
    },
    'BUILD_FRAGILITY_MEMORY': {
        'label': 'Build fragility memory',
        'priority': 'LOW',
        'estimated_confidence_gain': 8,
        'description': 'Create risk area identification system.',
    }
}

# Signal to actions mapping
SIGNAL_ACTIONS = {
    'acceptance_criteria': ['PASTE_ACCEPTANCE_CRITERIA'],
    'linked_work_item': ['CONNECT_JIRA'],
    'coverage_report': ['UPLOAD_COVERAGE'],
    'junit_test_history': ['IMPORT_JUNIT'],
    'architecture_graph': ['GENERATE_ARCHITECTURE'],
    'behavior_catalog': ['DISCOVER_BEHAVIORS'],
    'journey_catalog': ['CREATE_JOURNEYS'],
    'managed_manual_tests': ['IMPORT_MANUAL_TESTS'],
    'webhook_activity': ['ENABLE_WEBHOOKS'],
    'fragility_memory': ['BUILD_FRAGILITY_MEMORY'],
    'github_connection': ['CONNECT_JIRA'],  # Reuse JIRA connection for GitHub
    'current_pr_execution': ['ENABLE_WEBHOOKS'],  # Webhooks enable PR execution tracking
    'historical_outcomes': [],  # No direct action, accumulates over time
    'source_code': [],  # Required, no action needed
    'pull_request_diff': [],  # Required, no action needed
}

def get_signal_metadata(signal_key: str) -> dict:
    """Get metadata for a signal."""
    return SIGNAL_METADATA.get(signal_key, {})

def get_action_definition(action_key: str) -> dict:
    """Get definition for an action."""
    return ACTION_DEFINITIONS.get(action_key, {})

def get_actions_for_signal(signal_key: str) -> List[str]:
    """Get actions that can address a missing signal."""
    return SIGNAL_ACTIONS.get(signal_key, [])

def get_all_signals_ordered() -> List[str]:
    """Get all signals in deterministic order."""
    # Required signals first, then recommended, then optional
    required = ['source_code', 'pull_request_diff']
    recommended = [
        'junit_test_history', 'coverage_report', 'architecture_graph',
        'behavior_catalog', 'journey_catalog', 'acceptance_criteria',
        'linked_work_item'
    ]
    optional = [
        'managed_manual_tests', 'historical_outcomes', 'current_pr_execution',
        'github_connection', 'webhook_activity', 'fragility_memory'
    ]
    return required + recommended + optional


def calculate_confidence_and_ceiling(
    readiness_score: float,
    available_signals: List[str],
    missing_signals: List[str],
    signal_statuses: dict = None
) -> dict:
    """
    Calculate expected confidence and apply confidence ceilings based on signal availability.

    Args:
        readiness_score: Readiness score from 0.0 to 1.0 (multiplied by 100 for percentage)
        available_signals: List of available signal keys
        missing_signals: List of missing signal keys
        signal_statuses: Optional dict of signal statuses (e.g., {'coverage_report': 'STALE'})

    Returns:
        dict with keys:
            - expected_confidence: 'LOW', 'MEDIUM', or 'HIGH'
            - confidence_ceiling: 'LOW', 'MEDIUM', or 'HIGH'
            - confidence_reason: Explanation string
            - generation_blockers: List of signals that block generation (source_code, pull_request_diff)
            - confidence_limiters: List of signals that limit confidence (coverage, AC, etc.)
    """
    if signal_statuses is None:
        signal_statuses = {}

    # Convert score to percentage (0-100)
    score_percentage = int(readiness_score * 100)

    # Base confidence from score.
    # Score 40 = only the two required signals (source_code + pull_request_diff, 20+20).
    # That is the bare minimum state; treat it as LOW, not MEDIUM.
    if score_percentage <= 40:
        base_confidence = "LOW"
    elif score_percentage < 75:
        base_confidence = "MEDIUM"
    else:
        base_confidence = "HIGH"

    # Start with base confidence and apply ceilings
    confidence_ceiling = "HIGH"
    generation_blockers = []
    confidence_limiters = []

    # Check for hard ceiling blockers
    missing_set = set(missing_signals)
    available_set = set(available_signals)

    # Critical: missing source_code or pull_request_diff → blocks generation
    if 'source_code' in missing_set:
        generation_blockers.append('source_code')
        confidence_ceiling = "LOW"
    if 'pull_request_diff' in missing_set:
        generation_blockers.append('pull_request_diff')
        confidence_ceiling = "LOW"

    # Confidence limiters (not blockers, but cap confidence)
    limiter_signals = ['acceptance_criteria', 'current_pr_execution']
    
    for signal in limiter_signals:
        status = signal_statuses.get(signal) if signal_statuses else None
        is_missing = (status != "AVAILABLE") if status is not None else (signal in missing_set)
        if is_missing:
            confidence_ceiling = min(confidence_ceiling, "MEDIUM", key=lambda x: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[x])
            confidence_limiters.append(signal)

    # Apply ceiling to base confidence
    confidence_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    if confidence_order[base_confidence] > confidence_order[confidence_ceiling]:
        expected_confidence = confidence_ceiling
    else:
        expected_confidence = base_confidence

    # Build confidence reason based on actual missing signals
    if generation_blockers:
        # Build specific blocker message
        blocker_labels = []
        for blocker in generation_blockers:
            if blocker == 'source_code':
                blocker_labels.append('Source Code')
            elif blocker == 'pull_request_diff':
                blocker_labels.append('PR Diff')
        
        if len(blocker_labels) == 1:
            blocker_msg = f"Generation is blocked because {blocker_labels[0]} is missing."
        else:
            blocker_msg = f"Generation is blocked because {', '.join(blocker_labels)} are missing."
        
        # Add confidence limiter note if applicable
        if confidence_limiters:
            limiter_count = len(confidence_limiters)
            if limiter_count <= 2:
                limiter_msg = f" Additional evidence such as coverage, acceptance criteria, and PR execution will improve confidence after the blocker is resolved."
            else:
                limiter_msg = f" Additional evidence will improve confidence after the blocker is resolved."
            confidence_reason = blocker_msg + limiter_msg
        else:
            confidence_reason = blocker_msg
    elif confidence_limiters:
        # Not blocked, but confidence is limited
        if expected_confidence != base_confidence:
            confidence_reason = f"Confidence is capped at {expected_confidence} because {len(confidence_limiters)} signals are missing."
        else:
            confidence_reason = f"Confidence based on readiness score ({score_percentage}%)."
    else:
        confidence_reason = f"Confidence based on readiness score ({score_percentage}%)."

    return {
        "expected_confidence": expected_confidence,
        "confidence_ceiling": confidence_ceiling,
        "confidence_reason": confidence_reason,
        "generation_blockers": generation_blockers,
        "confidence_limiters": confidence_limiters
    }

