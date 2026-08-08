"""
PR Regression Decision Service.

Service for generating PR-level regression decisions with bucket-based output
focused on test decisions rather than input scores.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.schemas.pr_regression_decision import (
    PRRegressionDecision,
    RegressionCandidate,
    RegressionBucket,
    ActiveAction,
    MappingReviewStatus,
    ExecutionStatus,
    EvidencePath,
    EvidenceEdge,
)
from app.services.regression_scope_v2_service import RegressionScopeV2Service, ScopeGroup, ReleaseAction
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest

logger = logging.getLogger(__name__)


class PRRegressionDecisionService:
    """Service for generating PR-level regression decisions."""
    
    @staticmethod
    def generate_pr_regression_decision(
        db: Session,
        run_id: str,
        include_safe_to_skip: bool = False
    ) -> PRRegressionDecision:
        """Generate PR regression decision from recommendation run.
        
        Args:
            db: Database session
            run_id: Recommendation run ID
            include_safe_to_skip: Whether to include safe-to-skip items
            
        Returns:
            PRRegressionDecision with bucket-based output
        """
        # Get recommendation run
        run = db.query(RecommendationRun).filter(
            RecommendationRun.id == run_id
        ).first()
        
        if not run:
            raise ValueError(f"Recommendation run {run_id} not found")
        
        # Get PR
        pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
        if not pr:
            raise ValueError(f"Pull request not found for run {run_id}")
        
        # Generate regression scope V2
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=run_id,
            mode=RegressionScopeV2Service.ScopeMode.TARGETED,
            include_safe_to_skip=include_safe_to_skip,
            include_diagnostics=True,
            audit=True
        )
        
        # Convert scope items to regression candidates
        candidates = PRRegressionDecisionService._convert_scope_to_candidates(
            scope.items, pr.head_commit_sha
        )
        
        # Bucket candidates
        bucketed = PRRegressionDecisionService._bucket_candidates(candidates)
        
        # Determine if output is confident
        is_confident, readiness_blocker = PRRegressionDecisionService._determine_confidence(run, scope)
        
        # Calculate evidence path coverage
        evidence_path_coverage, missing_evidence_count = PRRegressionDecisionService._calculate_evidence_coverage(candidates)
        
        # Build decision
        decision = PRRegressionDecision(
            recommendation_run_id=str(run.id),
            pull_request_id=str(pr.id),
            repository_id=str(run.repository_id),
            current_head_sha=pr.head_commit_sha or "",
            is_draft=not is_confident,
            is_confident=is_confident,
            readiness_blocker=readiness_blocker,
            already_verified=bucketed[RegressionBucket.ALREADY_VERIFIED],
            must_run=bucketed[RegressionBucket.MUST_RUN],
            should_run=bucketed[RegressionBucket.SHOULD_RUN],
            failed_current_pr=bucketed[RegressionBucket.FAILED_CURRENT_PR],
            stale_rerun_required=bucketed[RegressionBucket.STALE_RERUN_REQUIRED],
            mapping_review_needed=bucketed[RegressionBucket.MAPPING_REVIEW_NEEDED],
            coverage_gaps=bucketed[RegressionBucket.COVERAGE_GAP],
            safe_to_skip=bucketed[RegressionBucket.SAFE_TO_SKIP],
            total_candidates=len(candidates),
            already_verified_count=len(bucketed[RegressionBucket.ALREADY_VERIFIED]),
            must_run_count=len(bucketed[RegressionBucket.MUST_RUN]),
            should_run_count=len(bucketed[RegressionBucket.SHOULD_RUN]),
            failed_current_pr_count=len(bucketed[RegressionBucket.FAILED_CURRENT_PR]),
            stale_rerun_required_count=len(bucketed[RegressionBucket.STALE_RERUN_REQUIRED]),
            mapping_review_needed_count=len(bucketed[RegressionBucket.MAPPING_REVIEW_NEEDED]),
            coverage_gaps_count=len(bucketed[RegressionBucket.COVERAGE_GAP]),
            safe_to_skip_count=len(bucketed[RegressionBucket.SAFE_TO_SKIP]),
            evidence_path_coverage=evidence_path_coverage,
            missing_evidence_count=missing_evidence_count,
            structural_impact_used=scope.diagnostics.get("structural_impact_used", False) if scope.diagnostics else False,
            coverage_level=scope.diagnostics.get("coverage_level") if scope.diagnostics else None,
        )
        
        logger.info(
            f"Generated PR regression decision: "
            f"{decision.already_verified_count} already verified, "
            f"{decision.must_run_count} must run, "
            f"{decision.coverage_gaps_count} gaps, "
            f"is_confident={is_confident}"
        )
        
        return decision
    
    @staticmethod
    def _convert_scope_to_candidates(
        scope_items: List[Any],
        current_head_sha: str
    ) -> List[RegressionCandidate]:
        """Convert scope items to regression candidates.
        
        Args:
            scope_items: Scope items from RegressionScopeV2
            current_head_sha: Current head commit SHA
            
        Returns:
            List of RegressionCandidate objects
        """
        candidates = []
        
        for item in scope_items:
            # Extract test information
            stable_test_id = item.test_id if hasattr(item, 'test_id') else str(item.id)
            test_name = item.test_name if hasattr(item, 'test_name') else f"Test {stable_test_id}"
            
            # Determine mapping review status
            mapping_review_status = PRRegressionDecisionService._determine_mapping_status(item)
            
            # Determine execution status
            execution_status = PRRegressionDecisionService._determine_execution_status(item)
            
            # Generate evidence path
            evidence_path = PRRegressionDecisionService._generate_evidence_path(item)
            
            # Extract linked IDs
            linked_ac_ids = item.ac_ids if hasattr(item, 'ac_ids') else []
            linked_behavior_ids = item.behavior_ids if hasattr(item, 'behavior_ids') else []
            linked_file_paths = item.file_paths if hasattr(item, 'file_paths') else []
            
            candidate = RegressionCandidate(
                stable_test_id=stable_test_id,
                test_name=test_name,
                bucket=PRRegressionDecisionService._map_scope_group_to_bucket(item.group),
                active_action=PRRegressionDecisionService._map_release_action_to_active_action(item.release_action),
                would_have_been_priority=item.priority if hasattr(item, 'priority') else None,
                reason_codes=[item.reason_code] if hasattr(item, 'reason_code') and item.reason_code else [],
                evidence_path=evidence_path,
                mapping_review_status=mapping_review_status,
                execution_status=execution_status,
                execution_commit_sha=item.execution_commit_sha if hasattr(item, 'execution_commit_sha') else None,
                current_head_sha=current_head_sha,
                confidence=item.confidence if hasattr(item, 'confidence') else 0.0,
                linked_ac_ids=linked_ac_ids,
                linked_behavior_ids=linked_behavior_ids,
                linked_file_paths=linked_file_paths,
            )
            
            candidates.append(candidate)
        
        return candidates
    
    @staticmethod
    def _map_scope_group_to_bucket(scope_group: ScopeGroup) -> RegressionBucket:
        """Map ScopeGroup to RegressionBucket."""
        mapping = {
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED: RegressionBucket.ALREADY_VERIFIED,
            ScopeGroup.REQUIRED: RegressionBucket.MUST_RUN,
            ScopeGroup.RECOMMENDED: RegressionBucket.SHOULD_RUN,
            ScopeGroup.REVIEW_NEEDED: RegressionBucket.MAPPING_REVIEW_NEEDED,
            ScopeGroup.SAFE_TO_SKIP: RegressionBucket.SAFE_TO_SKIP,
        }
        return mapping.get(scope_group, RegressionBucket.MUST_RUN)
    
    @staticmethod
    def _map_release_action_to_active_action(release_action: ReleaseAction) -> ActiveAction:
        """Map ReleaseAction to ActiveAction."""
        mapping = {
            ReleaseAction.NONE: ActiveAction.NONE,
            ReleaseAction.RUN_OR_CREATE_TEST: ActiveAction.RUN,
            ReleaseAction.FIX_OR_RERUN: ActiveAction.RERUN,
            ReleaseAction.MANUAL_REVIEW: ActiveAction.REVIEW,
        }
        return mapping.get(release_action, ActiveAction.RUN)
    
    @staticmethod
    def _determine_mapping_status(item: Any) -> MappingReviewStatus:
        """Determine mapping review status from scope item."""
        if hasattr(item, 'mapping_status'):
            mapping_status = item.mapping_status
            if mapping_status == "CONFIRMED":
                return MappingReviewStatus.CONFIRMED
            elif mapping_status == "SUGGESTED":
                return MappingReviewStatus.SUGGESTED
            elif mapping_status == "AMBIGUOUS":
                return MappingReviewStatus.AMBIGUOUS
            elif mapping_status == "REVIEW_NEEDED":
                return MappingReviewStatus.REVIEW_NEEDED
        
        # Default based on reason code
        if hasattr(item, 'reason_code'):
            if "COVERAGE_GAP" in item.reason_code:
                return MappingReviewStatus.MISSING
            elif "MAPPING_REVIEW" in item.reason_code:
                return MappingReviewStatus.REVIEW_NEEDED
        
        return MappingReviewStatus.MISSING
    
    @staticmethod
    def _determine_execution_status(item: Any) -> ExecutionStatus:
        """Determine execution status from scope item."""
        if hasattr(item, 'execution_status'):
            execution_status = item.execution_status
            if execution_status == "PASSED":
                return ExecutionStatus.PASSED
            elif execution_status == "FAILED":
                return ExecutionStatus.FAILED
            elif execution_status == "SKIPPED":
                return ExecutionStatus.SKIPPED
            elif execution_status == "NOT_RUN":
                return ExecutionStatus.NOT_RUN
        
        return ExecutionStatus.NOT_RUN
    
    @staticmethod
    def _generate_evidence_path(item: Any) -> EvidencePath:
        """Generate evidence path for a scope item."""
        edges = []
        
        # Add file -> dependency edge if available
        if hasattr(item, 'file_paths') and item.file_paths:
            for file_path in item.file_paths:
                edges.append(EvidenceEdge(
                    edge_type="changed_file -> dependency",
                    source=file_path,
                    target="impacted",
                    confidence=0.9
                ))
        
        # Add behavior -> AC edge if available
        if hasattr(item, 'behavior_ids') and item.behavior_ids:
            for behavior_id in item.behavior_ids:
                edges.append(EvidenceEdge(
                    edge_type="behavior -> AC",
                    source=behavior_id,
                    target=item.test_id if hasattr(item, 'test_id') else "test",
                    confidence=0.8
                ))
        
        # Add AC -> Test edge if available
        if hasattr(item, 'ac_ids') and item.ac_ids:
            for ac_id in item.ac_ids:
                edges.append(EvidenceEdge(
                    edge_type="AC -> Test",
                    source=ac_id,
                    target=item.test_id if hasattr(item, 'test_id') else "test",
                    confidence=0.9
                ))
        
        # Add Test -> Execution edge if available
        if hasattr(item, 'execution_status') and item.execution_status:
            edges.append(EvidenceEdge(
                edge_type="Test -> Execution",
                source=item.test_id if hasattr(item, 'test_id') else "test",
                target=item.execution_status,
                confidence=1.0
            ))
        
        # Determine if evidence path is complete
        complete = len(edges) > 0
        
        return EvidencePath(
            edges=edges,
            complete=complete,
            missing_evidence_reason=None if complete else "No evidence path available"
        )
    
    @staticmethod
    def _bucket_candidates(candidates: List[RegressionCandidate]) -> Dict[RegressionBucket, List[RegressionCandidate]]:
        """Bucket candidates by their bucket field."""
        bucketed = {
            RegressionBucket.ALREADY_VERIFIED: [],
            RegressionBucket.MUST_RUN: [],
            RegressionBucket.SHOULD_RUN: [],
            RegressionBucket.FAILED_CURRENT_PR: [],
            RegressionBucket.STALE_RERUN_REQUIRED: [],
            RegressionBucket.MAPPING_REVIEW_NEEDED: [],
            RegressionBucket.COVERAGE_GAP: [],
            RegressionBucket.SAFE_TO_SKIP: [],
        }
        
        for candidate in candidates:
            # Adjust bucket based on execution status
            if candidate.execution_status == ExecutionStatus.FAILED and candidate.current_head_sha == candidate.execution_commit_sha:
                candidate.bucket = RegressionBucket.FAILED_CURRENT_PR
            elif candidate.execution_status == ExecutionStatus.PASSED and candidate.current_head_sha != candidate.execution_commit_sha:
                candidate.bucket = RegressionBucket.STALE_RERUN_REQUIRED
            
            bucketed[candidate.bucket].append(candidate)
        
        return bucketed
    
    @staticmethod
    def _determine_confidence(run: RecommendationRun, scope: Any) -> tuple[bool, Optional[str]]:
        """Determine if output is confident based on readiness.
        
        Args:
            run: Recommendation run
            scope: Regression scope
            
        Returns:
            Tuple of (is_confident, readiness_blocker)
        """
        # Check if Input 5 is partial or missing
        if hasattr(run, 'requirement_evidence_snapshot_json') and not run.requirement_evidence_snapshot_json:
            return False, "Input 5 (Requirement Evidence) missing"
        
        # Check scope diagnostics for blockers
        if scope.diagnostics:
            if scope.diagnostics.get("pr_package_ready") is False:
                blockers = scope.diagnostics.get("pr_package_blockers", [])
                return False, f"PR package not ready: {', '.join(blockers)}"
        
        # Check for coverage gaps
        if hasattr(scope, 'items'):
            for item in scope.items:
                if hasattr(item, 'reason_code') and "COVERAGE_GAP" in item.reason_code:
                    return False, "Coverage gaps detected"
        
        return True, None
    
    @staticmethod
    def _calculate_evidence_coverage(candidates: List[RegressionCandidate]) -> tuple[float, int]:
        """Calculate evidence path coverage.
        
        Args:
            candidates: List of regression candidates
            
        Returns:
            Tuple of (coverage_percentage, missing_count)
        """
        if not candidates:
            return 0.0, 0
        
        complete_count = sum(1 for c in candidates if c.evidence_path.complete)
        missing_count = len(candidates) - complete_count
        
        coverage = complete_count / len(candidates) if candidates else 0.0
        
        return coverage, missing_count
