"""Recommendation Readiness Service - Backend source of truth for recommendation readiness assessment."""
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.readiness import (
    RecommendationReadinessAssessment,
    ReadinessLevel,
    ExpectedConfidence,
    SignalType,
    GapType
)
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult
from app.models.coverage import CoverageReport
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.integration_connection import IntegrationConnection
from app.models.recommendation import RecommendationRun, RecommendationOutcome
from app.models.fragility_pattern import FragilityPattern
from app.services.signal_metadata import calculate_confidence_and_ceiling

logger = logging.getLogger(__name__)

class RecommendationReadinessService:
    """Service for assessing repository/PR readiness for recommendation generation."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def assess_readiness(
        self,
        repository_id: str,
        pull_request_id: Optional[str] = None
    ) -> RecommendationReadinessAssessment:
        """
        Assess readiness for recommendation generation.
        
        Args:
            repository_id: Repository to assess
            pull_request_id: Optional specific PR to assess
            
        Returns:
            RecommendationReadinessAssessment with detailed analysis
        """
        from uuid import UUID
        if isinstance(repository_id, str):
            try:
                repository_id = UUID(repository_id)
            except ValueError:
                pass
        if isinstance(pull_request_id, str) and pull_request_id:
            try:
                pull_request_id = UUID(pull_request_id)
            except ValueError:
                pass

        logger.info(f"Assessing readiness for repo {repository_id}, pr {pull_request_id}")
        
        # 1. Assess signals in detail (Task 2)
        signals = self._assess_signals_details(repository_id, pull_request_id)
        
        # Debug logging for readiness calculation
        logger.info(f"=== READINESS DEBUG ===")
        logger.info(f"repository_id: {repository_id}")
        logger.info(f"pull_request_id: {pull_request_id}")
        for key, sig in signals.items():
            logger.info(f"{key}: {sig['status']} (count: {sig['evidence_count']})")
        
        # Determine available / missing lists — must be mutually exclusive
        available_signal_keys = {k for k, v in signals.items() if v["status"] in ("AVAILABLE", "STALE", "HISTORICAL_ONLY", "FALLBACK")}
        missing_signal_keys = {k for k, v in signals.items() if v["status"] == "MISSING"}
        
        # Hard rule: a signal cannot be in both available and missing
        overlap = available_signal_keys & missing_signal_keys
        if overlap:
            logger.error(f"READINESS BUG: signals in both available and missing: {overlap}. Forcing to available.")
            missing_signal_keys -= overlap
        
        logger.info(f"available_signal_keys: {sorted(available_signal_keys)}")
        logger.info(f"missing_signal_keys: {sorted(missing_signal_keys)}")
        
        # 2. Determine readiness level and confidence ceiling (Task 3)
        has_source = "source_code" in available_signal_keys
        has_diff = "pull_request_diff" in available_signal_keys
        
        logger.info(f"has_source: {has_source}, has_diff: {has_diff}")
        
        # Calculate expected confidence ceiling
        has_coverage = "coverage_report" in available_signal_keys or "current_pr_coverage" in available_signal_keys
        has_test_history = "test_history" in available_signal_keys
        has_manual_tests = "managed_manual_tests" in available_signal_keys
        has_ac = "acceptance_criteria" in available_signal_keys
        has_execution = signals["current_pr_execution"]["status"] == "AVAILABLE"
        
        release_confidence_ceiling = "HIGH"
            
        if not has_source or not has_diff:
            can_generate = False
            readiness_level = "BLOCKED"
            expected_confidence = "LOW"
            logger.info(f"BLOCKED: has_source={has_source}, has_diff={has_diff}")
        else:
            can_generate = True
            
            # Check regression readiness criteria
            has_arch = "architecture_graph" in available_signal_keys
            has_behavior = "behavior_catalog" in available_signal_keys
            has_journey = "journey_catalog" in available_signal_keys
            
            is_regression_ready = has_arch and has_behavior and has_journey and has_test_history and has_coverage
            
            # Stale checks
            is_stale = (signals["test_history"]["status"] == "STALE") or (signals["coverage_report"]["status"] == "STALE")
            
            logger.info(f"is_regression_ready: {is_regression_ready}, has_ac: {has_ac}, has_execution: {has_execution}, is_stale: {is_stale}")
            
            if is_regression_ready and has_ac and has_execution:
                readiness_level = "HIGH_CONFIDENCE_READY"
                expected_confidence = "HIGH"
            elif is_regression_ready:
                readiness_level = "REGRESSION_READY"
                expected_confidence = "MEDIUM"
            elif has_test_history or has_coverage:
                readiness_level = "EVIDENCE_READY"
                expected_confidence = "LOW" if is_stale else "MEDIUM"
            else:
                readiness_level = "MINIMUM_READY"
                expected_confidence = "LOW"
            
            logger.info(f"readiness_level: {readiness_level}, expected_confidence: {expected_confidence}")
                
            # Apply confidence ceilings
            if not has_ac and expected_confidence == "HIGH":
                expected_confidence = "MEDIUM"
            if not has_execution and expected_confidence == "HIGH":
                expected_confidence = "MEDIUM"
            if not has_coverage and expected_confidence in ("HIGH", "MEDIUM"):
                expected_confidence = "LOW"
            if not has_test_history and not has_manual_tests and expected_confidence in ("HIGH", "MEDIUM"):
                expected_confidence = "LOW"
                
        # 3. Categorize signals for API response shape (Task 5)
        available_inputs = []
        missing_inputs = []
        recommended_inputs = []
        blocking_inputs = []
        next_best_actions = []
        
        # Strongly recommended keys
        strongly_recommended_keys = {
            "test_history", "coverage_report", "architecture_graph",
            "behavior_catalog", "journey_catalog", "acceptance_criteria",
            "linked_work_item"
        }
        
        # Explicit missing input action/impact mapping
        action_impact_map = {
            "acceptance_criteria": {
                "impact": "Requirement coverage cannot be proven without acceptance criteria.",
                "action": "Paste acceptance criteria"
            },
            "current_pr_execution": {
                "impact": "Existing tests are known, but Veriscope cannot confirm they passed on this PR.",
                "action": "Attach current PR test results"
            },
            "managed_manual_tests": {
                "impact": "Manual validation coverage cannot be included in the regression scope.",
                "action": "Upload manual test cases"
            },
            "linked_work_item": {
                "impact": "Business context is limited to PR title and description.",
                "action": "Link work item"
            }
        }
        
        for key, sig in signals.items():
            # Add action/impact message if defined and missing
            if sig["status"] == "MISSING" and key in action_impact_map:
                sig["impact"] = action_impact_map[key]["impact"]
                sig["action"] = action_impact_map[key]["action"]
                # Also populate explanation to be robust
                sig["explanation"] = action_impact_map[key]["impact"]
                
                next_best_actions.append({
                    "key": key,
                    "impact": action_impact_map[key]["impact"],
                    "action": action_impact_map[key]["action"]
                })
                
            if sig["status"] in ("AVAILABLE", "STALE", "HISTORICAL_ONLY", "FALLBACK"):
                available_inputs.append(sig)
            else:
                missing_inputs.append(sig)
                if key in ("source_code", "pull_request_diff"):
                    blocking_inputs.append(sig)
                elif key in strongly_recommended_keys:
                    recommended_inputs.append(sig)
                    
        # 4. Generate messages
        primary_messages = {
            "BLOCKED": "Recommendation generation is blocked. Critical input signals are missing.",
            "MINIMUM_READY": "Minimum ready. Veriscope can generate recommendations, but confidence is low.",
            "EVIDENCE_READY": "Evidence ready. Good test and coverage evidence is available.",
            "REGRESSION_READY": "Regression ready. Full behavioral and test evidence is available.",
            "HIGH_CONFIDENCE_READY": "High confidence ready. Comprehensive coverage and validation data are present."
        }
        secondary_messages = {
            "BLOCKED": "Please configure repository access and pull request diff to proceed.",
            "MINIMUM_READY": "Add test history and code coverage reports to improve confidence.",
            "EVIDENCE_READY": "Add architecture graph and behavior catalog to trace regressions.",
            "REGRESSION_READY": "Attach current PR test results and paste acceptance criteria to reach high confidence.",
            "HIGH_CONFIDENCE_READY": "Veriscope is ready to generate recommendations with high accuracy."
        }
        
        primary_message = primary_messages.get(readiness_level, "Readiness check complete.")
        secondary_message = secondary_messages.get(readiness_level, "")
        
        # Readiness score calculation with weighted signal values
        signal_weights = {
            "source_code": 20,
            "pull_request_diff": 20,
            "architecture_graph": 10,
            "behavior_catalog": 10,
            "journey_catalog": 10,
            "test_history": 10,
            "current_pr_execution": 10,
            "coverage_report": 10,
            "current_pr_coverage": 10,
            "acceptance_criteria": 10,
            "business_intent": 5,
            "linked_work_item": 5,
            "managed_manual_tests": 5,
            "historical_outcomes": 5,
            "fragility_memory": 5
        }

        # Calculate total possible weight for normalization
        total_possible_weight = sum(signal_weights.values())

        # Calculate score from available signals
        readiness_score = 0
        score_breakdown = []
        for signal_key in available_signal_keys:
            weight = signal_weights.get(signal_key, 0)
            readiness_score += weight
            score_breakdown.append(f"{signal_key}: +{weight}")

        # Normalize to 0-100 scale based on total possible weight
        readiness_score = int((readiness_score / total_possible_weight) * 100) if total_possible_weight > 0 else 0

        # Cap at 100
        readiness_score = min(readiness_score, 100)

        # Convert to 0-1 scale for API
        readiness_score_normalized = readiness_score / 100.0

        logger.info(f"=== SCORE CALCULATION DEBUG ===")
        logger.info(f"available_signal_keys: {sorted(available_signal_keys)}")
        logger.info(f"missing_signal_keys: {sorted(missing_signal_keys)}")
        logger.info(f"total_possible_weight: {total_possible_weight}")
        logger.info(f"score_breakdown: {score_breakdown}")
        logger.info(f"raw_weight_sum: {sum(signal_weights.get(k, 0) for k in available_signal_keys)}")
        logger.info(f"normalized_score: {readiness_score}")
        logger.info(f"readiness_score_normalized: {readiness_score_normalized}")
        logger.info(f"=================================")
        
        # Calculate confidence using the helper function
        signal_statuses = {key: sig["status"] for key, sig in signals.items()}
        confidence_calc = calculate_confidence_and_ceiling(
            readiness_score=readiness_score_normalized,
            available_signals=list(available_signal_keys),
            missing_signals=list(missing_signal_keys),
            signal_statuses=signal_statuses
        )
        
        # Override expected_confidence with calculated value
        expected_confidence = confidence_calc["expected_confidence"]
        confidence_ceiling = confidence_calc["confidence_ceiling"]
        release_confidence_ceiling = confidence_ceiling
        confidence_reason = confidence_calc["confidence_reason"]
        generation_blockers = confidence_calc["generation_blockers"]
        confidence_limiters = confidence_calc["confidence_limiters"]
        
        logger.info(f"Calculated confidence: {expected_confidence}, ceiling: {confidence_ceiling}")
        logger.info(f"Confidence reason: {confidence_reason}")
        logger.info(f"Generation blockers: {generation_blockers}")
        logger.info(f"Confidence limiters: {confidence_limiters}")
        
        # Save to DB (map new enums to closest DB enums)
        db_readiness_level = readiness_level
        if readiness_level == "MINIMUM_READY":
            db_readiness_level = "CONNECTED"
        elif readiness_level == "REGRESSION_READY":
            db_readiness_level = "RECOMMENDATION_READY"
            
        # Gap analysis (old format gaps for compatibility)
        blocking_gaps = []
        optional_gaps = []
        if not has_source:
            blocking_gaps.append("Source code access is required for any recommendation")
        if not has_diff:
            blocking_gaps.append("Pull request diff is required to analyze changes")
        for key in strongly_recommended_keys:
            if key not in available_signal_keys:
                optional_gaps.append(f"Missing {key} signal.")
                
        # Recommended actions (old format)
        recommended_actions = [act["action"] for act in next_best_actions]
        
        confidence_impact_summary = (
            f"Confidence: {expected_confidence}. "
            f"Available signals: {', '.join(sorted(available_signal_keys))}. "
            f"Missing signals: {', '.join(sorted(missing_signal_keys))}."
        )
        
        assessment = RecommendationReadinessAssessment(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            readiness_level=db_readiness_level,
            expected_confidence=expected_confidence,
            readiness_score=readiness_score_normalized,
            available_signals=list(available_signal_keys),
            missing_signals=list(missing_signal_keys),
            blocking_gaps=blocking_gaps,
            optional_gaps=optional_gaps,
            recommended_actions=recommended_actions,
            confidence_impact_summary=confidence_impact_summary,
            can_generate=can_generate,
            can_generate_reason=primary_message,
            created_at=datetime.utcnow()
        )
        
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        
        # Override fields for Task 5 API shape
        assessment.readiness_level = readiness_level
        assessment.intelligence_completeness_score = int(readiness_score)
        assessment.release_confidence_ceiling = release_confidence_ceiling
        assessment.available_inputs = available_inputs
        assessment.missing_inputs = missing_inputs
        assessment.recommended_inputs = recommended_inputs
        assessment.blocking_inputs = blocking_inputs
        assessment.next_best_actions = next_best_actions
        assessment.primary_message = primary_message
        assessment.secondary_message = secondary_message
        
        # Set confidence explanation fields
        assessment.confidence_reason = confidence_reason
        assessment.confidence_ceiling = confidence_ceiling
        assessment.confidence_blockers = generation_blockers
        
        # Build confidence_limiters from signal keys
        confidence_limiters_signals = []
        for limiter_key in confidence_limiters:
            # Find the corresponding signal from missing_inputs
            for sig in missing_inputs:
                if sig.get("key") == limiter_key:
                    confidence_limiters_signals.append(sig)
                    break
        assessment.confidence_limiters = confidence_limiters_signals
        
        self.db.expunge(assessment)
        logger.info(f"Readiness assessment complete: {readiness_level}, score {readiness_score}")
        return assessment
        
    def populate_assessment_fields(self, assessment: RecommendationReadinessAssessment) -> RecommendationReadinessAssessment:
        """Populate dynamic fields on a stored database assessment object."""
        signals = self._assess_signals_details(
            str(assessment.repository_id),
            str(assessment.pull_request_id) if assessment.pull_request_id else None
        )
        
        available_signal_keys = {k for k, v in signals.items() if v["status"] in ("AVAILABLE", "STALE", "HISTORICAL_ONLY", "FALLBACK")}
        
        has_coverage = "coverage_report" in available_signal_keys or "current_pr_coverage" in available_signal_keys
        has_test_history = "test_history" in available_signal_keys
        has_manual_tests = "managed_manual_tests" in available_signal_keys
        has_ac = "acceptance_criteria" in available_signal_keys
        has_execution = signals["current_pr_execution"]["status"] == "AVAILABLE"
        
        release_confidence_ceiling = "HIGH"
            
        has_source = "source_code" in available_signal_keys
        has_diff = "pull_request_diff" in available_signal_keys
        
        if not has_source or not has_diff:
            readiness_level = "BLOCKED"
        else:
            has_arch = "architecture_graph" in available_signal_keys
            has_behavior = "behavior_catalog" in available_signal_keys
            has_journey = "journey_catalog" in available_signal_keys
            is_regression_ready = has_arch and has_behavior and has_journey and has_test_history and has_coverage
            
            if is_regression_ready and has_ac and has_execution:
                readiness_level = "HIGH_CONFIDENCE_READY"
            elif is_regression_ready:
                readiness_level = "REGRESSION_READY"
            elif has_test_history or has_coverage:
                readiness_level = "EVIDENCE_READY"
            else:
                readiness_level = "MINIMUM_READY"
                
        available_inputs = []
        missing_inputs = []
        recommended_inputs = []
        blocking_inputs = []
        next_best_actions = []
        
        strongly_recommended_keys = {
            "test_history", "coverage_report", "architecture_graph",
            "behavior_catalog", "journey_catalog", "acceptance_criteria",
            "linked_work_item"
        }
        
        action_impact_map = {
            "acceptance_criteria": {
                "impact": "Requirement coverage cannot be proven without acceptance criteria.",
                "action": "Paste acceptance criteria"
            },
            "current_pr_execution": {
                "impact": "Existing tests are known, but Veriscope cannot confirm they passed on this PR.",
                "action": "Attach current PR test results"
            },
            "managed_manual_tests": {
                "impact": "Manual validation coverage cannot be included in the regression scope.",
                "action": "Upload manual test cases"
            },
            "linked_work_item": {
                "impact": "Business context is limited to PR title and description.",
                "action": "Link work item"
            }
        }
        
        for key, sig in signals.items():
            if sig["status"] == "MISSING" and key in action_impact_map:
                sig["impact"] = action_impact_map[key]["impact"]
                sig["action"] = action_impact_map[key]["action"]
                sig["explanation"] = action_impact_map[key]["impact"]
                next_best_actions.append({
                    "key": key,
                    "impact": action_impact_map[key]["impact"],
                    "action": action_impact_map[key]["action"]
                })
                
            if sig["status"] in ("AVAILABLE", "STALE", "HISTORICAL_ONLY", "FALLBACK"):
                available_inputs.append(sig)
            else:
                missing_inputs.append(sig)
                if key in ("source_code", "pull_request_diff"):
                    blocking_inputs.append(sig)
                elif key in strongly_recommended_keys:
                    recommended_inputs.append(sig)
                    
        primary_messages = {
            "BLOCKED": "Recommendation generation is blocked. Critical input signals are missing.",
            "MINIMUM_READY": "Minimum ready. Veriscope can generate recommendations, but confidence is low.",
            "EVIDENCE_READY": "Evidence ready. Good test and coverage evidence is available.",
            "REGRESSION_READY": "Regression ready. Full behavioral and test evidence is available.",
            "HIGH_CONFIDENCE_READY": "High confidence ready. Comprehensive coverage and validation data are present."
        }
        secondary_messages = {
            "BLOCKED": "Please configure repository access and pull request diff to proceed.",
            "MINIMUM_READY": "Add test history and code coverage reports to improve confidence.",
            "EVIDENCE_READY": "Add architecture graph and behavior catalog to trace regressions.",
            "REGRESSION_READY": "Attach current PR test results and paste acceptance criteria to reach high confidence.",
            "HIGH_CONFIDENCE_READY": "Veriscope is ready to generate recommendations with high accuracy."
        }
        
        primary_message = primary_messages.get(readiness_level, "Readiness check complete.")
        secondary_message = secondary_messages.get(readiness_level, "")
        
        # Readiness score calculation with weighted signal values
        signal_weights = {
            "source_code": 20,
            "pull_request_diff": 20,
            "architecture_graph": 10,
            "behavior_catalog": 10,
            "journey_catalog": 10,
            "test_history": 10,
            "current_pr_execution": 10,
            "coverage_report": 10,
            "current_pr_coverage": 10,
            "acceptance_criteria": 10,
            "business_intent": 5,
            "linked_work_item": 5,
            "managed_manual_tests": 5,
            "historical_outcomes": 5,
            "fragility_memory": 5
        }

        # Calculate total possible weight for normalization
        total_possible_weight = sum(signal_weights.values())

        # Calculate score from available signals
        readiness_score = 0
        score_breakdown = []
        for signal_key in available_signal_keys:
            weight = signal_weights.get(signal_key, 0)
            readiness_score += weight
            score_breakdown.append(f"{signal_key}: +{weight}")

        # Normalize to 0-100 scale based on total possible weight
        readiness_score = int((readiness_score / total_possible_weight) * 100) if total_possible_weight > 0 else 0

        # Cap at 100
        readiness_score = min(readiness_score, 100)

        # Convert to 0-1 scale for API
        readiness_score_normalized = readiness_score / 100.0

        logger.info(f"populate_assessment_fields - total_possible_weight: {total_possible_weight}")
        logger.info(f"populate_assessment_fields - score_breakdown: {score_breakdown}")
        logger.info(f"populate_assessment_fields - readiness_score: {readiness_score}")
        
        # Calculate confidence using the helper function
        missing_signal_keys = {k for k, v in signals.items() if v["status"] == "MISSING"}
        signal_statuses = {key: sig["status"] for key, sig in signals.items()}
        confidence_calc = calculate_confidence_and_ceiling(
            readiness_score=readiness_score_normalized,
            available_signals=list(available_signal_keys),
            missing_signals=list(missing_signal_keys),
            signal_statuses=signal_statuses
        )
        
        expected_confidence = confidence_calc["expected_confidence"]
        confidence_ceiling = confidence_calc["confidence_ceiling"]
        release_confidence_ceiling = confidence_ceiling
        confidence_reason = confidence_calc["confidence_reason"]
        generation_blockers = confidence_calc["generation_blockers"]
        confidence_limiters = confidence_calc["confidence_limiters"]
        
        logger.info(f"populate_assessment_fields - Generation blockers: {generation_blockers}")
        logger.info(f"populate_assessment_fields - Confidence limiters: {confidence_limiters}")
        
        # Override fields for API shape
        assessment.readiness_level = readiness_level
        assessment.intelligence_completeness_score = int(readiness_score)
        assessment.release_confidence_ceiling = release_confidence_ceiling
        assessment.available_inputs = available_inputs
        assessment.missing_inputs = missing_inputs
        assessment.recommended_inputs = recommended_inputs
        assessment.blocking_inputs = blocking_inputs
        assessment.next_best_actions = next_best_actions
        assessment.primary_message = primary_message
        assessment.secondary_message = secondary_message
        
        # Set confidence explanation fields
        assessment.confidence_reason = confidence_reason
        assessment.confidence_ceiling = confidence_ceiling
        assessment.confidence_blockers = generation_blockers
        
        # Build confidence_limiters from signal keys
        confidence_limiters_signals = []
        for limiter_key in confidence_limiters:
            # Find the corresponding signal from missing_inputs
            for sig in missing_inputs:
                if sig.get("key") == limiter_key:
                    confidence_limiters_signals.append(sig)
                    break
        assessment.confidence_limiters = confidence_limiters_signals
        self.db.expunge(assessment)
        return assessment

    def _assess_signals_details(self, repository_id: str, pull_request_id: Optional[str]) -> Dict[str, dict]:
        from uuid import UUID
        if isinstance(repository_id, str):
            try:
                repository_id = UUID(repository_id)
            except ValueError:
                pass
        if isinstance(pull_request_id, str) and pull_request_id:
            try:
                pull_request_id = UUID(pull_request_id)
            except ValueError:
                pass

        from app.models.architecture_node import ArchitectureNode
        from app.models.architecture_edge import ArchitectureEdge
        from app.models.acceptance_criterion import AcceptanceCriterion
        from app.models.business_intent import BusinessIntentOverride
        from app.models.pull_request_work_item_link import PullRequestWorkItemLink
        from app.models.external_work_item import ExternalWorkItem
        from app.models.external_test_case_detailed import ExternalTestCase
        from app.models.journey_behavior import JourneyBehavior
        from app.models.behavior_evidence import BehaviorEvidence
        from app.models.webhook_event import WebhookEvent
        from app.models.pull_request import PullRequestChangedFile
        import re

        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        pr = None
        if pull_request_id:
            pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()

        signals = {}

        # 1. source_code
        has_source = repo is not None and repo.is_active and repo.selected_for_analysis
        signals["source_code"] = {
            "key": "source_code",
            "status": "AVAILABLE" if has_source else "MISSING",
            "evidence_count": 1 if has_source else 0,
            "linked_to_current_pr": False,
            "explanation": "Source code access is configured." if has_source else "Source code access is not configured.",
            "estimated_confidence_gain": 0.0
        }

        # 2. pull_request_diff
        has_diff = False
        diff_count = 0
        if pr:
            # Check changed_files_count first
            if pr.changed_files_count and pr.changed_files_count > 0:
                has_diff = True
                diff_count = pr.changed_files_count
            else:
                # Fallback: check PullRequestChangedFile rows
                changed_files = self.db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == pr.id
                ).count()
                if changed_files > 0:
                    has_diff = True
                    diff_count = changed_files
                # Fallback: check stored changed_files JSON if available
                elif hasattr(pr, 'changed_files') and pr.changed_files:
                    if isinstance(pr.changed_files, list):
                        diff_count = len(pr.changed_files)
                        has_diff = diff_count > 0
                    elif isinstance(pr.changed_files, dict) and 'files' in pr.changed_files:
                        diff_count = len(pr.changed_files['files'])
                        has_diff = diff_count > 0

        signals["pull_request_diff"] = {
            "key": "pull_request_diff",
            "status": "AVAILABLE" if has_diff else "MISSING",
            "evidence_count": diff_count,
            "linked_to_current_pr": True,
            "explanation": f"Pull request contains {diff_count} changed files." if has_diff else "No pull request changes found.",
            "estimated_confidence_gain": 0.0
        }

        # 3. architecture_graph
        node_count = self.db.query(ArchitectureNode).filter(ArchitectureNode.repository_id == repository_id).count()
        edge_count = self.db.query(ArchitectureEdge).filter(ArchitectureEdge.repository_id == repository_id).count()
        has_arch = (node_count > 0 or edge_count > 0)
        signals["architecture_graph"] = {
            "key": "architecture_graph",
            "status": "AVAILABLE" if has_arch else "MISSING",
            "evidence_count": node_count + edge_count,
            "linked_to_current_pr": False,
            "explanation": f"Architecture graph populated with {node_count} nodes and {edge_count} edges." if has_arch else "Architecture graph is missing.",
            "estimated_confidence_gain": 15.0 if not has_arch else 0.0
        }

        # 4. behavior_catalog
        behavior_count = self.db.query(Behavior).filter(Behavior.repository_id == repository_id).count()
        has_behavior = behavior_count > 0
        signals["behavior_catalog"] = {
            "key": "behavior_catalog",
            "status": "AVAILABLE" if has_behavior else "MISSING",
            "evidence_count": behavior_count,
            "linked_to_current_pr": False,
            "explanation": f"Behavior catalog contains {behavior_count} behaviors." if has_behavior else "Behavior catalog is empty.",
            "estimated_confidence_gain": 15.0 if not has_behavior else 0.0
        }

        # 5. journey_catalog
        journey_count = self.db.query(Journey).filter(Journey.repository_id == repository_id).count()
        has_journey = journey_count > 0
        signals["journey_catalog"] = {
            "key": "journey_catalog",
            "status": "AVAILABLE" if has_journey else "MISSING",
            "evidence_count": journey_count,
            "linked_to_current_pr": False,
            "explanation": f"Journey catalog contains {journey_count} journeys." if has_journey else "Journey catalog is empty.",
            "estimated_confidence_gain": 10.0 if not has_journey else 0.0
        }

        # 6. test_history
        stale_threshold = datetime.utcnow() - timedelta(days=7)
        latest_run = self.db.query(TestRun).filter(TestRun.repository_id == repository_id).order_by(TestRun.created_at.desc()).first()
        test_runs_count = self.db.query(TestRun).filter(TestRun.repository_id == repository_id).count()

        if test_runs_count > 0:
            if latest_run and latest_run.created_at < stale_threshold:
                test_history_status = "STALE"
                test_history_exp = f"Test history contains {test_runs_count} runs, but latest is stale (older than 7 days)."
            else:
                test_history_status = "AVAILABLE"
                test_history_exp = f"Test history contains {test_runs_count} runs."
        else:
            test_history_status = "MISSING"
            test_history_exp = "No test history uploaded."

        signals["test_history"] = {
            "key": "test_history",
            "status": test_history_status,
            "evidence_count": test_runs_count,
            "linked_to_current_pr": False,
            "explanation": test_history_exp,
            "estimated_confidence_gain": 15.0 if test_history_status == "MISSING" else 0.0
        }

        # 7. current_pr_execution
        is_current_execution = False
        current_runs_count = 0

        if pr:
            for run in self.db.query(TestRun).filter(TestRun.repository_id == repository_id).all():
                matches_pr = False
                if run.pull_request_id == pr.id:
                    matches_pr = True
                elif run.commit_sha == pr.head_commit_sha:
                    matches_pr = True
                else:
                    run_branch = None
                    if run.ingestion_diagnostics and isinstance(run.ingestion_diagnostics, dict):
                        run_branch = run.ingestion_diagnostics.get("branch")
                    if not run_branch and run.pull_request_id:
                        run_pr = self.db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
                        if run_pr:
                            run_branch = run_pr.source_branch
                    if not run_branch and run.commit_sha:
                        run_pr = self.db.query(PullRequest).filter(
                            PullRequest.repository_id == repository_id,
                            PullRequest.head_commit_sha == run.commit_sha
                        ).first()
                        if run_pr:
                            run_branch = run_pr.source_branch
                    
                    pr_opened_at = pr.created_at
                    if pr.github_created_at:
                        pr_opened_at = min(pr.created_at, pr.github_created_at)
                        
                    if run_branch == pr.source_branch and run.created_at >= pr_opened_at:
                        matches_pr = True
                
                if matches_pr:
                    is_current_execution = True
                    current_runs_count += 1

        if is_current_execution:
            pr_exec_status = "AVAILABLE"
            pr_exec_exp = f"Test results attached to current PR ({current_runs_count} runs)."
            pr_exec_count = current_runs_count
            pr_exec_linked = True
        else:
            if test_runs_count > 0:
                pr_exec_status = "HISTORICAL_ONLY"
                pr_exec_exp = "Existing tests are known, but Veriscope cannot confirm they passed on this PR."
                pr_exec_count = test_runs_count
                pr_exec_linked = False
            else:
                pr_exec_status = "MISSING"
                pr_exec_exp = "No test results found for this repository."
                pr_exec_count = 0
                pr_exec_linked = False

        signals["current_pr_execution"] = {
            "key": "current_pr_execution",
            "status": pr_exec_status,
            "evidence_count": pr_exec_count,
            "linked_to_current_pr": pr_exec_linked,
            "explanation": pr_exec_exp,
            "estimated_confidence_gain": 10.0 if pr_exec_status != "AVAILABLE" else 0.0
        }

        # 8. coverage_report
        coverage_reports_count = self.db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).count()
        latest_coverage = self.db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).order_by(CoverageReport.created_at.desc()).first()

        if coverage_reports_count > 0:
            if latest_coverage and latest_coverage.created_at < stale_threshold:
                coverage_status = "STALE"
                coverage_exp = f"Coverage report populated with {coverage_reports_count} records, but latest is stale."
            else:
                coverage_status = "AVAILABLE"
                coverage_exp = f"Coverage report populated with {coverage_reports_count} records."
        else:
            coverage_status = "MISSING"
            coverage_exp = "No coverage reports uploaded."

        signals["coverage_report"] = {
            "key": "coverage_report",
            "status": coverage_status,
            "evidence_count": coverage_reports_count,
            "linked_to_current_pr": False,
            "explanation": coverage_exp,
            "estimated_confidence_gain": 15.0 if coverage_status == "MISSING" else 0.0
        }

        # 9. current_pr_coverage
        is_current_coverage = False
        current_coverage_count = 0

        if pr:
            for cov in self.db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).all():
                matches_cov = False
                if cov.pull_request_id == pr.id:
                    matches_cov = True
                elif cov.commit_sha == pr.head_commit_sha:
                    matches_cov = True
                else:
                    pr_opened_at = pr.created_at
                    if pr.github_created_at:
                        pr_opened_at = min(pr.created_at, pr.github_created_at)
                    if cov.branch == pr.source_branch and cov.created_at >= pr_opened_at:
                        matches_cov = True
                        
                if matches_cov:
                    is_current_coverage = True
                    current_coverage_count += 1

        if is_current_coverage:
            pr_cov_status = "AVAILABLE"
            pr_cov_exp = "Coverage report matching current PR is available."
            pr_cov_count = current_coverage_count
            pr_cov_linked = True
        else:
            if coverage_reports_count > 0:
                pr_cov_status = "HISTORICAL_ONLY"
                pr_cov_exp = "Coverage reports exist, but none match the current PR."
                pr_cov_count = coverage_reports_count
                pr_cov_linked = False
            else:
                pr_cov_status = "MISSING"
                pr_cov_exp = "No coverage reports exist."
                pr_cov_count = 0
                pr_cov_linked = False

        signals["current_pr_coverage"] = {
            "key": "current_pr_coverage",
            "status": pr_cov_status,
            "evidence_count": pr_cov_count,
            "linked_to_current_pr": pr_cov_linked,
            "explanation": pr_cov_exp,
            "estimated_confidence_gain": 10.0 if pr_cov_status != "AVAILABLE" else 0.0
        }

        # 10. acceptance_criteria
        has_ac_record = False
        ac_count = 0
        struct_ac_count = 0
        bio_ac_count = 0
        work_item_ac_items = []

        if pr:
            # Source 1: structured AC rows (repository_id + pull_request_id for correctness)
            struct_ac_count = self.db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == repository_id,
                AcceptanceCriterion.pull_request_id == pr.id
            ).count()
            ac_count += struct_ac_count

            # Source 2: BusinessIntentOverride with acceptance_criteria field
            bio_ac_count = self.db.query(BusinessIntentOverride).filter(
                BusinessIntentOverride.pull_request_id == pr.id,
                BusinessIntentOverride.is_active == True,
                BusinessIntentOverride.acceptance_criteria.isnot(None)
            ).count()
            # Only count BIO AC if no structured rows already captured it (avoid double-counting)
            if struct_ac_count == 0:
                ac_count += bio_ac_count

            # Source 3: ExternalWorkItem with acceptance_criteria
            work_item_ac_items = self.db.query(ExternalWorkItem).join(
                PullRequestWorkItemLink, PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id
            ).filter(
                PullRequestWorkItemLink.pull_request_id == pr.id,
                ExternalWorkItem.acceptance_criteria.isnot(None)
            ).all()
            for wi in work_item_ac_items:
                if isinstance(wi.acceptance_criteria, list):
                    if len(wi.acceptance_criteria) > 0:
                        ac_count += len(wi.acceptance_criteria)
                elif isinstance(wi.acceptance_criteria, str):
                    if wi.acceptance_criteria.strip():
                        ac_count += 1

            has_ac_record = ac_count > 0

        ac_status = "AVAILABLE" if has_ac_record else "MISSING"
        ac_exp = f"Acceptance criteria available for requirement coverage ({ac_count} criteria)." if has_ac_record else "Requirement coverage cannot be proven without acceptance criteria."
        signals["acceptance_criteria"] = {
            "key": "acceptance_criteria",
            "label": "Acceptance Criteria",
            "status": ac_status,
            "evidence_count": ac_count,
            "linked_to_current_pr": True if has_ac_record else False,
            "explanation": ac_exp,
            "estimated_confidence_gain": 10.0 if not has_ac_record else 0.0
        }

        logger.info(f"AC Detection: pr_id={pr.id if pr else None}, repo_id={repository_id}, struct_ac_count={struct_ac_count}, bio_ac_count={bio_ac_count}, work_item_ac_count={len(work_item_ac_items)}, total_ac_count={ac_count}, has_ac_record={has_ac_record}")

        # 11. business_intent
        # Available if: (a) an active BusinessIntentOverride exists, OR
        #               (b) manual AC rows with MANUAL_USER_INPUT source exist (implies business context was entered)
        has_bio = False
        bio_evidence_count = 0
        manual_ac_bio_count = 0
        if pr:
            bio_evidence_count = self.db.query(BusinessIntentOverride).filter(
                BusinessIntentOverride.pull_request_id == pr.id,
                BusinessIntentOverride.is_active == True
            ).count()
            if bio_evidence_count > 0:
                has_bio = True

            # Also count manual AC rows as business intent evidence (user entered business change summary)
            if not has_bio:
                manual_ac_bio_count = self.db.query(AcceptanceCriterion).filter(
                    AcceptanceCriterion.repository_id == repository_id,
                    AcceptanceCriterion.pull_request_id == pr.id,
                    AcceptanceCriterion.source == "MANUAL_USER_INPUT"
                ).count()
                if manual_ac_bio_count > 0:
                    has_bio = True
                    bio_evidence_count = manual_ac_bio_count

        bio_status = "AVAILABLE" if has_bio else "MISSING"
        bio_exp = (
            f"Business intent defined for current PR ({bio_evidence_count} source{'s' if bio_evidence_count != 1 else ''})."
            if has_bio
            else "No business intent override found."
        )
        signals["business_intent"] = {
            "key": "business_intent",
            "label": "Business Intent",
            "status": bio_status,
            "evidence_count": bio_evidence_count,
            "linked_to_current_pr": True if has_bio else False,
            "explanation": bio_exp,
            "estimated_confidence_gain": 5.0 if not has_bio else 0.0
        }

        logger.info(f"Business Intent Detection: pr_id={pr.id if pr else None}, bio_evidence_count={bio_evidence_count}, manual_ac_bio_count={manual_ac_bio_count}, has_bio={has_bio}")

        # 12. linked_work_item
        has_work_items = False
        wi_count = 0

        if pr:
            wi_count = self.db.query(PullRequestWorkItemLink).filter(PullRequestWorkItemLink.pull_request_id == pr.id).count()
            if wi_count > 0:
                has_work_items = True
            else:
                JIRA_KEY_PATTERN = r'\b([A-Z]+-\d+)\b'
                AZURE_NUMERIC_PATTERN = r'#(\d{4,})\b'
                AZURE_PREFIX_PATTERN = r'\b([A-Z]+)#(\d+)\b'
                JIRA_URL_PATTERN = r'atlassian\.net/browse/([A-Z]+-\d+)'
                AZURE_URL_PATTERN = r'dev\.azure\.com/[^/]+/[^/]+/_workitems/edit/(\d+)'
                
                def has_patterns(text: str) -> bool:
                    if not text:
                        return False
                    for pat in [JIRA_KEY_PATTERN, AZURE_NUMERIC_PATTERN, AZURE_PREFIX_PATTERN, JIRA_URL_PATTERN, AZURE_URL_PATTERN]:
                        if re.search(pat, text):
                            return True
                    return False
                    
                if has_patterns(pr.title) or has_patterns(pr.source_branch):
                    has_work_items = True
                    wi_count = 1

        wi_status = "AVAILABLE" if has_work_items else "MISSING"
        wi_exp = "Work items linked to pull request." if has_work_items else "Business context is limited to PR title and description."
        signals["linked_work_item"] = {
            "key": "linked_work_item",
            "status": wi_status,
            "evidence_count": wi_count,
            "linked_to_current_pr": True if has_work_items else False,
            "explanation": wi_exp,
            "estimated_confidence_gain": 10.0 if not has_work_items else 0.0
        }

        # 13. managed_manual_tests
        has_manual_tests = False
        manual_tests_count = 0
        manual_tests_linked_pr = False
        manual_tests_exp = "No manual test cases exist."

        repo_manual_tests = self.db.query(ExternalTestCase).filter(ExternalTestCase.repository_id == repository_id).all()
        total_repo_manual_tests = len(repo_manual_tests)

        if total_repo_manual_tests > 0:
            any_has_mapping = False
            for tc in repo_manual_tests:
                if tc.behavior_id or tc.journey_id or (isinstance(tc.linked_work_item_keys, list) and len(tc.linked_work_item_keys) > 0):
                    any_has_mapping = True
                    break
                    
            if not any_has_mapping:
                has_manual_tests = True
                manual_tests_count = total_repo_manual_tests
                manual_tests_linked_pr = False
                manual_tests_exp = f"Manual test cases exist for the repository ({total_repo_manual_tests} tests)."
            elif pr:
                pr_files = self.db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == pr.id
                ).all()
                changed_files = [f.file_path for f in pr_files]
                
                behaviors = self.db.query(Behavior).filter(Behavior.repository_id == repository_id).all()
                evidences = self.db.query(BehaviorEvidence).filter(BehaviorEvidence.repository_id == repository_id).all()
                journey_behaviors = self.db.query(JourneyBehavior).filter(JourneyBehavior.repository_id == repository_id).all()
                journeys = self.db.query(Journey).filter(Journey.repository_id == repository_id).all()
                
                matcher = ChangedFileBehaviorMatcher(self.db)
                matches = matcher.match_changed_files(
                    changed_files=changed_files,
                    behaviors=behaviors,
                    evidences=evidences,
                    journey_behaviors=journey_behaviors,
                    journeys=journeys
                )
                affected_behavior_ids = {m["behavior_id"] for m in matches}
                affected_journey_ids = {str(jb.journey_id) for jb in journey_behaviors if str(jb.behavior_id) in affected_behavior_ids}
                
                linked_work_items = self.db.query(ExternalWorkItem).join(
                    PullRequestWorkItemLink, PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id
                ).filter(
                    PullRequestWorkItemLink.pull_request_id == pr.id
                ).all()
                linked_work_item_keys = [wi.external_key for wi in linked_work_items]
                
                matching_tcs = []
                for tc in repo_manual_tests:
                    maps_to_behavior = tc.behavior_id and str(tc.behavior_id) in affected_behavior_ids
                    maps_to_journey = tc.journey_id and str(tc.journey_id) in affected_journey_ids
                    maps_to_work_item = False
                    if isinstance(tc.linked_work_item_keys, list):
                        if any(k in linked_work_item_keys for k in tc.linked_work_item_keys):
                            maps_to_work_item = True
                    
                    if maps_to_behavior or maps_to_journey or maps_to_work_item:
                        matching_tcs.append(tc)
                        
                if len(matching_tcs) > 0:
                    has_manual_tests = True
                    manual_tests_count = len(matching_tcs)
                    manual_tests_linked_pr = True
                    manual_tests_exp = f"{len(matching_tcs)} manual test cases map to current PR changes."
                else:
                    has_manual_tests = False
                    manual_tests_count = total_repo_manual_tests
                    manual_tests_linked_pr = False
                    manual_tests_exp = "Manual validation coverage cannot be included in the regression scope."
            else:
                has_manual_tests = True
                manual_tests_count = total_repo_manual_tests
                manual_tests_linked_pr = False
                manual_tests_exp = f"Manual test cases exist for the repository ({total_repo_manual_tests} tests)."

        manual_tests_status = "AVAILABLE" if has_manual_tests else ("HISTORICAL_ONLY" if total_repo_manual_tests > 0 else "MISSING")
        signals["managed_manual_tests"] = {
            "key": "managed_manual_tests",
            "status": manual_tests_status,
            "evidence_count": manual_tests_count,
            "linked_to_current_pr": manual_tests_linked_pr,
            "explanation": manual_tests_exp,
            "estimated_confidence_gain": 7.0 if manual_tests_status != "AVAILABLE" else 0.0
        }

        # 14. historical_outcomes
        historical_outcomes_count = self.db.query(RecommendationOutcome).join(
            RecommendationRun, RecommendationOutcome.recommendation_run_id == RecommendationRun.id
        ).filter(RecommendationRun.repository_id == repository_id).count()
        historical_outcomes_available = historical_outcomes_count > 0
        signals["historical_outcomes"] = {
            "key": "historical_outcomes",
            "status": "AVAILABLE" if historical_outcomes_available else "MISSING",
            "evidence_count": historical_outcomes_count,
            "linked_to_current_pr": False,
            "explanation": f"Recommendation outcomes recorded: {historical_outcomes_count}." if historical_outcomes_available else "No historical outcomes found.",
            "estimated_confidence_gain": 8.0 if not historical_outcomes_available else 0.0
        }

        # 15. fragility_memory
        fragility_memory_count = self.db.query(FragilityPattern).filter(FragilityPattern.repository_id == repository_id).count()
        fragility_memory_available = fragility_memory_count > 0
        signals["fragility_memory"] = {
            "key": "fragility_memory",
            "status": "AVAILABLE" if fragility_memory_available else "MISSING",
            "evidence_count": fragility_memory_count,
            "linked_to_current_pr": False,
            "explanation": f"Fragility memory has {fragility_memory_count} patterns." if fragility_memory_available else "Fragility memory is empty.",
            "estimated_confidence_gain": 8.0 if not fragility_memory_available else 0.0
        }

        return signals

    # Legacy placeholder methods updated to be database-driven
    def _has_source_code(self, repository_id: str) -> bool:
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        return repo is not None and repo.is_active and repo.selected_for_analysis
        
    def _has_pull_request_diff(self, pull_request_id: str) -> bool:
        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        return pr is not None and pr.changed_files_count > 0
        
    def _has_junit_test_history(self, repository_id: str) -> bool:
        test_runs = self.db.query(TestRun).filter(TestRun.repository_id == repository_id).limit(1).all()
        return len(test_runs) > 0
        
    def _has_coverage_report(self, repository_id: str) -> bool:
        coverage = self.db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).limit(1).all()
        return len(coverage) > 0
        
    def _has_architecture_graph(self, repository_id: str) -> bool:
        from app.models.architecture_node import ArchitectureNode
        from app.models.architecture_edge import ArchitectureEdge
        node_count = self.db.query(ArchitectureNode).filter(ArchitectureNode.repository_id == repository_id).count()
        edge_count = self.db.query(ArchitectureEdge).filter(ArchitectureEdge.repository_id == repository_id).count()
        return node_count > 0 or edge_count > 0
        
    def _has_behavior_catalog(self, repository_id: str) -> bool:
        behaviors = self.db.query(Behavior).filter(Behavior.repository_id == repository_id).limit(1).all()
        return len(behaviors) > 0
        
    def _has_journey_catalog(self, repository_id: str) -> bool:
        journeys = self.db.query(Journey).filter(Journey.repository_id == repository_id).limit(1).all()
        return len(journeys) > 0
        
    def _has_acceptance_criteria(self, repository_id: str, pull_request_id: str) -> bool:
        from app.models.acceptance_criterion import AcceptanceCriterion
        from app.models.business_intent import BusinessIntentOverride
        from app.models.pull_request_work_item_link import PullRequestWorkItemLink
        from app.models.external_work_item import ExternalWorkItem
        
        ac_count = self.db.query(AcceptanceCriterion).filter(AcceptanceCriterion.pull_request_id == pull_request_id).count()
        if ac_count > 0:
            return True
            
        bio_count = self.db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.pull_request_id == pull_request_id,
            BusinessIntentOverride.is_active == True
        ).count()
        if bio_count > 0:
            return True
            
        work_item_ac_count = self.db.query(ExternalWorkItem).join(
            PullRequestWorkItemLink, PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id
        ).filter(
            PullRequestWorkItemLink.pull_request_id == pull_request_id,
            ExternalWorkItem.acceptance_criteria.isnot(None)
        ).all()
        valid_wi_acs = [wi for wi in work_item_ac_count if isinstance(wi.acceptance_criteria, list) and len(wi.acceptance_criteria) > 0]
        return len(valid_wi_acs) > 0
        
    def _has_linked_work_items(self, repository_id: str, pull_request_id: str) -> bool:
        from app.models.pull_request_work_item_link import PullRequestWorkItemLink
        wi_count = self.db.query(PullRequestWorkItemLink).filter(PullRequestWorkItemLink.pull_request_id == pull_request_id).count()
        if wi_count > 0:
            return True
            
        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        if pr:
            import re
            JIRA_KEY_PATTERN = r'\b([A-Z]+-\d+)\b'
            AZURE_NUMERIC_PATTERN = r'#(\d{4,})\b'
            AZURE_PREFIX_PATTERN = r'\b([A-Z]+)#(\d+)\b'
            JIRA_URL_PATTERN = r'atlassian\.net/browse/([A-Z]+-\d+)'
            AZURE_URL_PATTERN = r'dev\.azure\.com/[^/]+/[^/]+/_workitems/edit/(\d+)'
            
            def has_patterns(text: str) -> bool:
                if not text:
                    return False
                for pat in [JIRA_KEY_PATTERN, AZURE_NUMERIC_PATTERN, AZURE_PREFIX_PATTERN, JIRA_URL_PATTERN, AZURE_URL_PATTERN]:
                    if re.search(pat, text):
                        return True
                return False
                
            return has_patterns(pr.title) or has_patterns(pr.source_branch)
        return False
        
    def _has_managed_manual_tests(self, repository_id: str, pull_request_id: Optional[str] = None) -> bool:
        from app.models.external_test_case_detailed import ExternalTestCase
        from app.models.behavior_evidence import BehaviorEvidence
        from app.models.journey_behavior import JourneyBehavior
        from app.services.changed_file_behavior_matcher import ChangedFileBehaviorMatcher
        
        repo_manual_tests = self.db.query(ExternalTestCase).filter(ExternalTestCase.repository_id == repository_id).all()
        if not repo_manual_tests:
            return False
            
        any_has_mapping = False
        for tc in repo_manual_tests:
            if tc.behavior_id or tc.journey_id or (isinstance(tc.linked_work_item_keys, list) and len(tc.linked_work_item_keys) > 0):
                any_has_mapping = True
                break
                
        if not any_has_mapping:
            return True
            
        if not pull_request_id:
            return True
            
        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        if not pr:
            return True
            
        pr_files = self.db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).all()
        changed_files = [f.file_path for f in pr_files]
        
        behaviors = self.db.query(Behavior).filter(Behavior.repository_id == repository_id).all()
        evidences = self.db.query(BehaviorEvidence).filter(BehaviorEvidence.repository_id == repository_id).all()
        journey_behaviors = self.db.query(JourneyBehavior).filter(JourneyBehavior.repository_id == repository_id).all()
        journeys = self.db.query(Journey).filter(Journey.repository_id == repository_id).all()
        
        matcher = ChangedFileBehaviorMatcher(self.db)
        matches = matcher.match_changed_files(
            changed_files=changed_files,
            behaviors=behaviors,
            evidences=evidences,
            journey_behaviors=journey_behaviors,
            journeys=journeys
        )
        affected_behavior_ids = {m["behavior_id"] for m in matches}
        affected_journey_ids = {str(jb.journey_id) for jb in journey_behaviors if str(jb.behavior_id) in affected_behavior_ids}
        
        linked_work_items = self.db.query(ExternalWorkItem).join(
            PullRequestWorkItemLink, PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id
        ).filter(
            PullRequestWorkItemLink.pull_request_id == pr.id
        ).all()
        linked_work_item_keys = [wi.external_key for wi in linked_work_items]
        
        for tc in repo_manual_tests:
            maps_to_behavior = tc.behavior_id and str(tc.behavior_id) in affected_behavior_ids
            maps_to_journey = tc.journey_id and str(tc.journey_id) in affected_journey_ids
            maps_to_work_item = False
            if isinstance(tc.linked_work_item_keys, list):
                if any(k in linked_work_item_keys for k in tc.linked_work_item_keys):
                    maps_to_work_item = True
            
            if maps_to_behavior or maps_to_journey or maps_to_work_item:
                return True
                
        return False
        
    def _has_historical_outcomes(self, repository_id: str) -> bool:
        outcomes = self.db.query(RecommendationOutcome).join(
            RecommendationRun, RecommendationOutcome.recommendation_run_id == RecommendationRun.id
        ).filter(RecommendationRun.repository_id == repository_id).limit(1).all()
        return len(outcomes) > 0
        
    def _has_fragility_memory(self, repository_id: str) -> bool:
        fragility = self.db.query(FragilityPattern).filter(FragilityPattern.repository_id == repository_id).limit(1).all()
        return len(fragility) > 0
        
    def _has_current_pr_execution(self, repository_id: str, pull_request_id: str) -> bool:
        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        if not pr:
            return False
            
        for run in self.db.query(TestRun).filter(TestRun.repository_id == repository_id).all():
            if run.pull_request_id == pr.id:
                return True
            if run.commit_sha == pr.head_commit_sha:
                return True
                
            run_branch = None
            if run.ingestion_diagnostics and isinstance(run.ingestion_diagnostics, dict):
                run_branch = run.ingestion_diagnostics.get("branch")
            if not run_branch and run.pull_request_id:
                run_pr = self.db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
                if run_pr:
                    run_branch = run_pr.source_branch
            if not run_branch and run.commit_sha:
                run_pr = self.db.query(PullRequest).filter(
                    PullRequest.repository_id == repository_id,
                    PullRequest.head_commit_sha == run.commit_sha
                ).first()
                if run_pr:
                    run_branch = run_pr.source_branch
                    
            pr_opened_at = pr.created_at
            if pr.github_created_at:
                pr_opened_at = min(pr.created_at, pr.github_created_at)
                
            if run_branch == pr.source_branch and run.created_at >= pr_opened_at:
                return True
                
        return False
        
    def _has_github_connection(self, repository_id: str) -> bool:
        connection = self.db.query(IntegrationConnection).filter(
            and_(
                IntegrationConnection.repository_id == repository_id,
                IntegrationConnection.provider == "github",
                IntegrationConnection.status == "CONNECTED"
            )
        ).limit(1).all()
        return len(connection) > 0
        
    def _has_webhook_activity(self, repository_id: str) -> bool:
        from app.models.webhook_event import WebhookEvent
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return False
            
        try:
            if repo.github_repo_id:
                count = self.db.query(WebhookEvent).filter(
                    WebhookEvent.repository_id == repo.github_repo_id,
                    WebhookEvent.received_at >= datetime.utcnow() - timedelta(hours=24)
                ).count()
                if count > 0:
                    return True
        except Exception:
            pass
            
        if repo.last_webhook_at and repo.last_webhook_at >= datetime.utcnow() - timedelta(hours=24):
            return True
            
        if repo.last_synced_at and repo.last_synced_at >= datetime.utcnow() - timedelta(hours=24):
            return True
            
        return False
