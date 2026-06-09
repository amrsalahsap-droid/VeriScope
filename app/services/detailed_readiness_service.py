"""Detailed Readiness Service for Frontend API with signal impact analysis."""
from typing import List, Dict, Set, Optional
from sqlalchemy.orm import Session
import logging

from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.services.signal_metadata import (
    get_signal_metadata, get_action_definition, get_actions_for_signal,
    get_all_signals_ordered, SIGNAL_METADATA, ACTION_DEFINITIONS
)
from app.schemas.readiness_detailed import (
    AvailableSignal, MissingSignal, RecommendedAction, DetailedReadinessResponse,
    SignalStatus, SignalSeverity, ActionPriority
)

logger = logging.getLogger(__name__)

class DetailedReadinessService:
    """Service for detailed readiness assessment with signal impact analysis."""
    
    def __init__(self, db: Session):
        self.db = db
        self.base_service = RecommendationReadinessService(db)
    
    def get_detailed_readiness(
        self,
        repository_id: str,
        pull_request_id: Optional[str] = None
    ) -> DetailedReadinessResponse:
        """Get detailed readiness assessment with signal impact analysis."""
        
        # Get base readiness assessment
        assessment = self.base_service.assess_readiness(repository_id, pull_request_id)
        
        # Construct AvailableSignal, MissingSignal, RecommendedAction for backward compatibility
        available_signals = []
        missing_signals = []
        recommended_actions = []
        
        # Loop through all available inputs and missing inputs from Phase 1B
        for sig in assessment.available_inputs:
            key = sig["key"]
            metadata_key = "junit_test_history" if key == "test_history" else key
            meta = get_signal_metadata(metadata_key)
            available_signals.append(AvailableSignal(
                key=key,
                label=meta.get("label") or key,
                status=sig["status"],
                impact=meta.get("available_impact") or meta.get("impact") or sig.get("explanation"),
                confidence_contribution=int(meta.get("confidence_contribution") or 0)
            ))
            
        for sig in assessment.missing_inputs:
            key = sig["key"]
            metadata_key = "junit_test_history" if key == "test_history" else key
            meta = get_signal_metadata(metadata_key)
            actions = [get_action_definition(act_key).get("label") for act_key in get_actions_for_signal(metadata_key) if get_action_definition(act_key)]
            # If next best actions has action for this sig, use it
            next_action = next((act["action"] for act in assessment.next_best_actions if act["key"] == key), None)
            if next_action and next_action not in actions:
                actions.insert(0, next_action)
                
            missing_signals.append(MissingSignal(
                key=key,
                label=meta.get("label") or key,
                severity=meta.get("severity") or "OPTIONAL",
                impact=meta.get("missing_impact") or meta.get("impact") or sig.get("explanation"),
                estimated_confidence_gain=int(meta.get("estimated_confidence_gain") or sig.get("estimated_confidence_gain") or 0),
                actions=actions
            ))
            
        # Add next best actions as recommended actions
        for act in assessment.next_best_actions:
            sig_meta = get_signal_metadata("junit_test_history" if act["key"] == "test_history" else act["key"])
            recommended_actions.append(RecommendedAction(
                action=act["key"],
                label=act["action"],
                priority="HIGH" if sig_meta.get("severity") == "REQUIRED" else "MEDIUM",
                estimated_confidence_gain=int(sig_meta.get("estimated_confidence_gain") or 0)
            ))
            
        return DetailedReadinessResponse(
            id=str(assessment.id) if assessment.id else None,
            repository_id=str(assessment.repository_id),
            pull_request_id=str(assessment.pull_request_id) if assessment.pull_request_id else None,
            readiness_level=assessment.readiness_level,
            expected_confidence=assessment.expected_confidence,
            readiness_score=assessment.readiness_score,
            available_signals=available_signals,
            missing_signals=missing_signals,
            blocking_gaps=assessment.blocking_gaps,
            optional_gaps=assessment.optional_gaps,
            recommended_actions=recommended_actions,
            confidence_impact_summary=assessment.confidence_impact_summary,
            can_generate=assessment.can_generate,
            can_generate_reason=assessment.can_generate_reason,
            created_at=assessment.created_at,
            intelligence_completeness_score=assessment.intelligence_completeness_score,
            release_confidence_ceiling=assessment.release_confidence_ceiling,
            available_inputs=assessment.available_inputs,
            missing_inputs=assessment.missing_inputs,
            recommended_inputs=assessment.recommended_inputs,
            blocking_inputs=assessment.blocking_inputs,
            next_best_actions=assessment.next_best_actions,
            primary_message=assessment.primary_message,
            secondary_message=assessment.secondary_message,
            confidence_reason=assessment.confidence_reason,
            confidence_ceiling=assessment.confidence_ceiling,
            confidence_blockers=assessment.confidence_blockers,
            confidence_limiters=assessment.confidence_limiters
        )
        
    def calculate_confidence_impact_summary(self, available_signals: Set[str], missing_signals: Set[str]) -> str:
        """Calculate confidence impact summary based on available and missing signals."""
        available_str = ", ".join(sorted(list(available_signals)))
        missing_str = ", ".join(sorted(list(missing_signals)))
        
        has_coverage = "coverage_report" in available_signals or "current_pr_coverage" in available_signals
        has_test_history = "test_history" in available_signals or "junit_test_history" in available_signals
        has_manual_tests = "managed_manual_tests" in available_signals
        has_ac = "acceptance_criteria" in available_signals
        has_execution = "current_pr_execution" in available_signals
        
        if not has_coverage or (not has_test_history and not has_manual_tests):
            expected_confidence = "LOW"
        elif not has_ac or not has_execution:
            expected_confidence = "MEDIUM"
        else:
            expected_confidence = "HIGH"
            
        return f"Confidence: {expected_confidence}. Available signals: {available_str}. Missing signals: {missing_str}."
