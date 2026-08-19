"""Regression Scope V2 Service for Phase 4

Service for generating unified regression scope using the V2 contract.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.schemas.regression_scope_v2 import (
    RegressionScopeV2,
    ScopeGroup,
    ScopeItemType,
    EvidenceClassification,
    RiskBand,
    ChangeImpactLevel,
    BusinessRiskLevel,
    ScopeMode,
    ScopeSource,
    ScopeItem,
    ScopeItemDiagnostics,
    ScopeGroupSummary,
    ExecutionPlan,
    ScopeExclusions,
    ScopeOptimizationMetrics,
    ScopeGovernance,
    ScopeDiagnostics,
    TraceabilitySummary,
    ReleaseDecision
)
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.models.acceptance_criterion import AcceptanceCriterion
from app.services.risk_based_regression.risk_scoring_service import RiskScoringService
from app.services.change_impact_service import ChangeImpactService
from app.services.regression_recommendation_engine import RegressionRecommendationEngine
from app.services.manual_evidence_risk_adjustment_service import ManualEvidenceRiskAdjustmentService
from app.services.structural_impact_selection import StructuralImpactSelectionService
from app.schemas.structural_impact import StructuralImpactSelectionRequest


class ScopeIntegrityError(Exception):
    pass

from enum import Enum

class ReleaseAction(str, Enum):
    NONE = "NONE"
    RE_RUN = "RE_RUN"
    FIX_OR_RERUN = "FIX_OR_RERUN"
    RUN_OR_CREATE_TEST = "RUN_OR_CREATE_TEST"
    CREATE_TEST = "CREATE_TEST"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    VERIFY_FRESHNESS = "VERIFY_FRESHNESS"
    RUN_IF_TIME = "RUN_IF_TIME"


class RegressionScopeV2Service:
    """Service for generating unified regression scope V2."""

    # Phase 6.3: default estimated effort for a manual test (minutes)
    MANUAL_TEST_DEFAULT_MINUTES = 10

    @staticmethod
    def _build_regression_scope_v2(
        run: RecommendationRun,
        mode: ScopeMode,
        items: List[ScopeItem],
        diagnostics_data: Dict[str, Any],
        include_diagnostics: bool,
        traceability_summary=None,
        release_decision=None,
        recommendations=None,
        evidence_items=None,
    ) -> RegressionScopeV2:
        """Build a schema-valid RegressionScopeV2 from bucketed scope items."""
        import hashlib
        import json

        group_map: Dict[ScopeGroup, List[ScopeItem]] = {}
        for item in items:
            group_map.setdefault(item.group, []).append(item)

        groups: Dict[str, ScopeGroupSummary] = {}
        for group, group_items in group_map.items():
            groups[group.value] = ScopeGroupSummary(
                group=group,
                count=len(group_items),
                items=group_items,
            )

        required_items = group_map.get(ScopeGroup.REQUIRED, [])
        review_items = group_map.get(ScopeGroup.REVIEW_NEEDED, [])
        recommended_items = group_map.get(ScopeGroup.RECOMMENDED, [])
        optional_items = group_map.get(ScopeGroup.OPTIONAL, [])
        already_verified_items = group_map.get(ScopeGroup.EXCLUDED_ALREADY_VERIFIED, [])
        already_passed_items = group_map.get(ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS, [])
        safe_to_skip_items = group_map.get(ScopeGroup.SAFE_TO_SKIP, [])

        total_executable = (
            len(required_items)
            + len(recommended_items)
            + len(optional_items)
            + len(review_items)
        )
        total_items = len(items) if items else 0

        execution_plan = ExecutionPlan(
            required_count=len(required_items),
            recommended_count=len(recommended_items),
            optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            review_needed_count=len(review_items),
            deferred_coverage_debt_count=len(group_map.get(ScopeGroup.DEFERRED_COVERAGE_DEBT, [])),
            total_executable_count=total_executable,
            estimated_execution_reduction=0.0 if total_items == 0 else (len(safe_to_skip_items) / total_items * 100),
            confidence_level=0.0,
            plan_summary=(
                f"{len(required_items)} required, {len(recommended_items)} recommended, "
                f"{len(review_items)} review needed, {len(safe_to_skip_items)} safe to skip"
            ),
            advisory_notice="Scope generated from evidence graph and structural impact analysis.",
        )

        exclusions = ScopeExclusions(
            already_verified_count=len(already_verified_items),
            already_passed_tests_count=len(already_passed_items),
            already_verified_items=already_verified_items,
            already_passed_test_items=already_passed_items,
        )

        optimization_metrics = ScopeOptimizationMetrics(
            current_regression_size=total_items,
            optimized_required_count=len(required_items),
            optimized_recommended_count=len(recommended_items),
            optimized_optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            optimization_percentage=0.0,
            execution_reduction=execution_plan.estimated_execution_reduction,
            coverage_confidence=0.0,
        )

        governance = ScopeGovernance(
            risk_reviews_count=0,
            overridden_count=0,
            needs_discussion_count=len(review_items),
            release_decision_required=(len(required_items) > 0 or len(review_items) > 0),
            release_decision_status=release_decision.verdict if release_decision else None,
        )

        diagnostics = ScopeDiagnostics(
            generation_timestamp=datetime.utcnow(),
            generation_duration_ms=None,
            rules_applied=["STRUCTURAL_FIRST"],
            warnings=[],
            errors=[],
            change_impact_diagnostics=diagnostics_data if include_diagnostics else None,
        )

        payload = {
            "run_id": str(run.id),
            "mode": mode.value,
            "items": [item.model_dump() for item in items],
        }
        snapshot_hash = hashlib.md5(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        return RegressionScopeV2(
            recommendation_run_id=str(run.id),
            snapshot_hash=snapshot_hash,
            generated_at=datetime.utcnow(),
            scope_type=mode.value.upper(),
            source=ScopeSource.EVIDENCE_BASED,
            summary=(
                f"Regression scope contains {len(required_items)} required, "
                f"{len(recommended_items)} recommended, {len(review_items)} review needed items."
            ),
            execution_plan=execution_plan,
            groups=groups,
            exclusions=exclusions,
            optimization_metrics=optimization_metrics,
            governance=governance,
            diagnostics=diagnostics,
            traceability_summary=traceability_summary,
            release_decision=release_decision,
            recommendations=recommendations or [],
            evidence_items=evidence_items or [],
        )

    @staticmethod
    def _blocked_regression_scope_v2(
        run: RecommendationRun,
        mode: ScopeMode,
        reason: str,
        blockers: List[str],
        include_diagnostics: bool,
    ) -> RegressionScopeV2:
        """Return a schema-valid RegressionScopeV2 when the PR package cannot support confident scope."""
        diagnostics_data = {
            "pr_package_ready": False,
            "pr_package_blockers": blockers,
            "can_generate_confident_regression_plan": False,
            "reason": reason,
            "fallback_mode": "FULL_SUITE",
        }
        return RegressionScopeV2Service._build_regression_scope_v2(
            run=run,
            mode=mode,
            items=[],
            diagnostics_data=diagnostics_data,
            include_diagnostics=include_diagnostics,
        )

    @staticmethod
    def _create_scope_items_from_structural_impact(
        structural_result,
        pr,
        run,
        db,
        audit: bool = False
    ) -> List[ScopeItem]:
        """Create scope items from structural impact selection result.
        
        Structural tests with missing/stale execution → REQUIRED
        Structural tests with fresh passing execution → Already Verified / EXCLUDED_ALREADY_VERIFIED
        Impacted files with no coverage/test mapping → coverage gap / REQUIRED_REVIEW
        
        Args:
            structural_result: StructuralImpactSelectionResult
            pr: PullRequest
            run: RecommendationRun
            db: Database session
            audit: Whether to include audit information
            
        Returns:
            List of ScopeItem from structural impact
        """
        from app.models.test_result import TestCase, TestResult, TestRun
        
        scope_items = []
        
        if not structural_result or not structural_result.structurally_impacted_tests:
            return scope_items
        
        for test_data in structural_result.structurally_impacted_tests:
            test_case_id = test_data.get("test_case_id")
            stable_test_id = test_data.get("stable_test_id")
            file_path = test_data.get("file_path")
            impact_depth = test_data.get("impact_depth", 0)
            evidence_path = test_data.get("evidence_path", [])
            
            # Get execution status for this test
            execution_status = "NOT_RUN"
            freshness_status = "UNKNOWN"
            latest_result_created_at = None
            
            if test_case_id or stable_test_id:
                try:
                    if test_case_id:
                        test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
                    else:
                        test_case = db.query(TestCase).filter(
                            TestCase.repository_id == run.repository_id,
                            TestCase.stable_identity == stable_test_id
                        ).first()
                    
                    if test_case:
                        # Get latest test result
                        latest_result = db.query(TestResult).filter(
                            TestResult.test_case_id == test_case.id
                        ).order_by(TestResult.created_at.desc()).first()
                        
                        if latest_result:
                            execution_status = latest_result.status
                            latest_result_created_at = latest_result.created_at
                            
                            # Determine freshness
                            if pr.head_commit_sha and latest_result.commit_sha == pr.head_commit_sha:
                                freshness_status = "FRESH"
                            else:
                                freshness_status = "STALE"
                except Exception as e:
                    logger.error(f"Failed to get execution status for test {stable_test_id}: {e}")
            
            # Determine scope group based on execution status and freshness
            # Structural tests with missing/stale execution → REQUIRED
            # Structural tests with fresh passing execution → EXCLUDED_ALREADY_VERIFIED
            if execution_status == "PASSED" and freshness_status == "FRESH":
                scope_group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                release_action = ReleaseAction.NONE
                reason = f"Structural test already verified (fresh passing execution). Evidence path: {' -> '.join(evidence_path)}"
            else:
                scope_group = ScopeGroup.REQUIRED
                release_action = ReleaseAction.RUN_OR_CREATE_TEST
                reason = f"Structural test required (execution_status={execution_status}, freshness={freshness_status}). Evidence path: {' -> '.join(evidence_path)}"
            
            # Determine risk level based on impact depth
            if impact_depth == 0:
                business_risk = BusinessRiskLevel.HIGH
                risk_band = RiskBand.HIGH
            elif impact_depth <= 1:
                business_risk = BusinessRiskLevel.MEDIUM
                risk_band = RiskBand.MEDIUM
            else:
                business_risk = BusinessRiskLevel.LOW
                risk_band = RiskBand.LOW
            
            item = ScopeItem(
                id=stable_test_id or str(test_case_id) or f"structural_{file_path}",
                readable_id=stable_test_id or f"STRUCTURAL-{file_path.replace('/', '-')}",
                source_ac_number=None,
                title=f"Structural test for {file_path}",
                item_type=ScopeItemType.TEST,
                group=scope_group,
                evidence_classification=EvidenceClassification.COVERED if execution_status == "PASSED" else EvidenceClassification.MISSING,
                risk_score=0.7 if business_risk == BusinessRiskLevel.HIGH else 0.5,
                risk_band=risk_band,
                change_impact_level=ChangeImpactLevel.DIRECT if impact_depth == 0 else ChangeImpactLevel.INDIRECT,
                business_risk_level=business_risk,
                effective_risk_level=business_risk,
                suggested_action="Run test" if scope_group == ScopeGroup.REQUIRED else "Already verified",
                reason=reason,
                evidence_references=evidence_path,
                test_references=[stable_test_id] if stable_test_id else [],
                can_auto_execute=True,
                execution_status=execution_status,
                estimated_effort=None,
                is_required_for_release=(scope_group == ScopeGroup.REQUIRED),
                is_manual_only=False,
                release_action=release_action,
                freshness_status=freshness_status,
                mapping_status="STRUCTURAL",
                linked_test_count=1 if stable_test_id else 0,
                linked_tests=[stable_test_id] if stable_test_id else [],
                diagnostics=ScopeItemDiagnostics(
                    internal_requirement_id=None,
                    internal_test_id=str(test_case_id) if test_case_id else None,
                    generation_rule="STRUCTURAL_IMPACT",
                    confidence_score=0.8 if structural_result.selection_confidence == "HIGH" else 0.6,
                    last_updated=None
                ) if audit else None,
                reason_code="STRUCTURAL_IMPACT"
            )
            
            scope_items.append(item)
        
        # Add coverage gap items for unmapped impacted files
        for file_path in structural_result.unmapped_impacted_files:
            item = ScopeItem(
                id=f"coverage_gap_{file_path.replace('/', '-')}",
                readable_id=f"GAP-{file_path.replace('/', '-')}",
                source_ac_number=None,
                title=f"Coverage gap for {file_path}",
                item_type=ScopeItemType.REQUIREMENT,
                group=ScopeGroup.REVIEW_NEEDED,
                evidence_classification=EvidenceClassification.MISSING,
                risk_score=0.5,
                risk_band=RiskBand.MEDIUM,
                change_impact_level=ChangeImpactLevel.DIRECT,
                business_risk_level=BusinessRiskLevel.MEDIUM,
                effective_risk_level=BusinessRiskLevel.MEDIUM,
                suggested_action="Manual review or add test coverage",
                reason=f"Impacted file has no coverage/test mapping. File: {file_path}",
                evidence_references=[f"Unmapped impacted file: {file_path}"],
                test_references=[],
                can_auto_execute=False,
                execution_status="NOT_RUN",
                estimated_effort=f"{RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES} min",
                estimated_effort_minutes=RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES,
                is_required_for_release=False,
                is_manual_only=True,
                release_action=ReleaseAction.MANUAL_REVIEW,
                freshness_status="UNKNOWN",
                mapping_status="UNMAPPED",
                linked_test_count=0,
                linked_tests=[],
                diagnostics=ScopeItemDiagnostics(
                    internal_requirement_id=None,
                    internal_test_id=None,
                    generation_rule="COVERAGE_GAP",
                    confidence_score=0.5,
                    last_updated=None
                ) if audit else None,
                reason_code="COVERAGE_GAP"
            )
            
            scope_items.append(item)
        
        logger.info(f"Created {len(scope_items)} scope items from structural impact ({len([i for i in scope_items if i.group == ScopeGroup.REQUIRED])} required, {len([i for i in scope_items if i.group == ScopeGroup.EXCLUDED_ALREADY_VERIFIED])} already verified)")
        
        return scope_items

    @staticmethod
    def _generate_structural_first_scope(
        run: RecommendationRun,
        pr: PullRequest,
        ac_rows: List[AcceptanceCriterion],
        snapshot_data: Dict[str, Any],
        structural_result,
        include_safe_to_skip: bool,
        audit: bool,
        db: Session = None,
        include_diagnostics: bool = False,
        mode: ScopeMode = ScopeMode.TARGETED
    ) -> RegressionScopeV2:
        """Generate regression scope with structural impact as primary core.
        
        Structural impact produces base candidates, then AC/risk overlays add context.
        
        Bucket rules:
        1. REQUIRED: structurally impacted test with missing/stale execution, impacted AC with no mapped tests,
           critical/risky impacted behavior with no confirmed fresh verification
        2. ALREADY_VERIFIED: relevant impacted test has fresh passing result on current head SHA
        3. FAILED_CURRENT_PR: relevant impacted test failed on current head SHA
        4. NEEDS_MAPPING_REVIEW: candidate depends only on suggested/ambiguous AC mapping
        5. COVERAGE_GAP: impacted file/AC/behavior has no known mapped tests or coverage
        6. SAFE_TO_SKIP: not structurally impacted, not AC/behavior/risk impacted, or verified safe by policy
           (never because evidence is missing)
        
        Args:
            run: Recommendation run
            pr: Pull request
            ac_rows: Acceptance criteria rows
            snapshot_data: Evidence graph snapshot
            structural_result: Structural impact selection result
            include_safe_to_skip: Whether to include safe-to-skip items
            audit: Whether to include audit information
            db: Database session
            include_diagnostics: Whether to include diagnostics
            mode: Scope generation mode
            
        Returns:
            RegressionScopeV2: Unified regression scope
        """
        # Step 1: Create scope items from structural impact (primary core)
        structural_scope_items = RegressionScopeV2Service._create_scope_items_from_structural_impact(
            structural_result, pr, run, db, audit
        )
        
        # Step 2: Create scope items from AC traceability (overlay)
        traceability = snapshot_data.get("acTraceability", []) or []
        ac_scope_items = []
        
        for trace in traceability:
            coverage_status = trace.get("coverageStatus", "MISSING")
            linked_tests = trace.get("linkedExistingTests", []) or []
            
            # Find real AC
            ac = next((row for row in ac_rows if str(row.id) == trace.get("requirementId")), None)
            
            if ac:
                # Create scope item from AC trace
                item = RegressionScopeV2Service._create_scope_item_from_trace(
                    trace, audit, db=db, repository_id=run.repository_id, ac=ac
                )
                
                # Resolve test evidence
                evidence = RegressionScopeV2Service._resolve_test_evidence_for_ac(
                    ac, pr, db, linked_tests, run.repository_id
                )
                item.execution_status = evidence['execution_status']
                item.freshness_status = evidence['freshness_status']
                
                # Determine initial bucket based on structural impact
                # If this AC is structurally impacted (has overlapping files), use structural rules
                is_structurally_impacted = False
                if structural_result and structural_result.impacted_files:
                    # Check if AC has linked tests that cover impacted files
                    for test_id in linked_tests:
                        for test_data in structural_result.structurally_impacted_tests:
                            if test_data.get("stable_test_id") == test_id:
                                is_structurally_impacted = True
                                break
                        if is_structurally_impacted:
                            break
                
                # Apply bucket rules based on structural impact
                if is_structurally_impacted:
                    # Structural impact rules apply
                    if item.execution_status == "PASSED" and item.freshness_status == "FRESH":
                        item.group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                        item.release_action = ReleaseAction.NONE
                        item.reason = "Structurally impacted AC with fresh passing test"
                        item.reason_code = "STRUCTURAL_FRESH_PASS"
                    elif item.execution_status == "FAILED" and item.freshness_status == "FRESH":
                        item.group = ScopeGroup.REQUIRED
                        item.release_action = ReleaseAction.FIX_OR_RERUN
                        item.reason = "Structurally impacted AC with failed test on current head SHA"
                        item.reason_code = "STRUCTURAL_FAILED_CURRENT_PR"
                    else:
                        item.group = ScopeGroup.REQUIRED
                        item.release_action = ReleaseAction.RUN_OR_CREATE_TEST
                        item.reason = f"Structurally impacted AC with {item.execution_status}/{item.freshness_status} test"
                        item.reason_code = "STRUCTURAL_MISSING_STALE"
                else:
                    # Non-structural AC rules
                    if not linked_tests:
                        item.group = ScopeGroup.REVIEW_NEEDED
                        item.release_action = ReleaseAction.MANUAL_REVIEW
                        item.reason = "Impacted AC with no mapped tests - coverage gap"
                        item.reason_code = "COVERAGE_GAP"
                    elif item.execution_status == "PASSED" and item.freshness_status == "FRESH":
                        item.group = ScopeGroup.SAFE_TO_SKIP
                        item.release_action = ReleaseAction.NONE
                        item.reason = "Non-structurally impacted AC with fresh passing test"
                        item.reason_code = "NON_STRUCTURAL_FRESH_PASS"
                    else:
                        item.group = ScopeGroup.REQUIRED
                        item.release_action = ReleaseAction.RUN_OR_CREATE_TEST
                        item.reason = f"Non-structurally impacted AC with {item.execution_status}/{item.freshness_status} test"
                        item.reason_code = "NON_STRUCTURAL_MISSING_STALE"
                
                ac_scope_items.append(item)
        
        # Step 3: Merge structural and AC scope items
        # Structural items take precedence for tests, AC items add business context
        all_scope_items = structural_scope_items + ac_scope_items
        
        # Step 4: Apply AC/risk overlays
        # Risk tags increase priority
        # Quality gate can force REQUIRED
        # Known defects can force REQUIRED
        # Out-of-scope can exclude only if explicitly declared
        
        for item in all_scope_items:
            # Apply risk tag overlay
            if item.business_risk_level == BusinessRiskLevel.CRITICAL:
                # Critical risk items are always REQUIRED
                if item.group not in (ScopeGroup.REQUIRED, ScopeGroup.EXCLUDED_ALREADY_VERIFIED):
                    item.group = ScopeGroup.REQUIRED
                    item.release_action = ReleaseAction.RUN_OR_CREATE_TEST
                    item.reason = "Critical risk tag forces REQUIRED"
                    item.reason_code = "RISK_CRITICAL_OVERRIDE"
            elif item.business_risk_level == BusinessRiskLevel.HIGH:
                # High risk items get priority
                if item.group == ScopeGroup.RECOMMENDED:
                    item.group = ScopeGroup.REQUIRED
                    item.release_action = ReleaseAction.RUN_OR_CREATE_TEST
                    item.reason = "High risk tag upgrades RECOMMENDED to REQUIRED"
                    item.reason_code = "RISK_HIGH_OVERRIDE"
            
            # Apply quality gate overlay (placeholder - would check quality gate status)
            # For now, we'll leave this as a comment for future implementation
            # if quality_gate_failed and item.group != ScopeGroup.REQUIRED:
            #     item.group = ScopeGroup.REQUIRED
            #     item.reason = "Quality gate failure forces REQUIRED"
            #     item.reason_code = "QUALITY_GATE_OVERRIDE"
            
            # Apply known defect overlay (placeholder - would check defect database)
            # if has_known_defect and item.group != ScopeGroup.REQUIRED:
            #     item.group = ScopeGroup.REQUIRED
            #     item.reason = "Known defect forces REQUIRED"
            #     item.reason_code = "DEFECT_OVERRIDE"
            
            # Apply out-of-scope overlay (placeholder - would check scope declarations)
            # if is_out_of_scope and item.group == ScopeGroup.REQUIRED:
            #     item.group = ScopeGroup.SAFE_TO_SKIP
            #     item.reason = "Explicitly declared out of scope"
            #     item.reason_code = "OUT_OF_SCOPE_OVERRIDE"
        
        # Step 5: Filter by mode
        if mode == ScopeMode.TARGETED:
            # Targeted: Only REQUIRED and REVIEW_NEEDED
            filtered_items = [item for item in all_scope_items if item.group in (ScopeGroup.REQUIRED, ScopeGroup.REVIEW_NEEDED)]
        elif mode == ScopeMode.RISK_BASED:
            # Risk-based: REQUIRED, REVIEW_NEEDED, and some RECOMMENDED
            filtered_items = [item for item in all_scope_items if item.group in (ScopeGroup.REQUIRED, ScopeGroup.REVIEW_NEEDED, ScopeGroup.RECOMMENDED)]
        else:
            # Full suite: All items
            filtered_items = all_scope_items
        
        # Step 6: Build final scope
        required_items = [item for item in filtered_items if item.group == ScopeGroup.REQUIRED]
        review_needed_items = [item for item in filtered_items if item.group == ScopeGroup.REVIEW_NEEDED]
        recommended_items = [item for item in filtered_items if item.group == ScopeGroup.RECOMMENDED]
        optional_items = [item for item in filtered_items if item.group == ScopeGroup.OPTIONAL]
        already_verified_items = [item for item in filtered_items if item.group == ScopeGroup.EXCLUDED_ALREADY_VERIFIED]
        safe_to_skip_items = [item for item in filtered_items if item.group == ScopeGroup.SAFE_TO_SKIP] if include_safe_to_skip else []
        
        # Build raw ordered items and diagnostics for the final schema-valid scope.
        # Keep all bucketed items in the returned scope; mode filtering is reflected
        # in the execution plan and summary counts, not by dropping items.
        ordered_items = all_scope_items
        diagnostics = {
            "structural_impact_used": structural_result is not None,
            "structural_test_count": len(structural_result.structurally_impacted_tests) if structural_result else 0,
            "coverage_level": structural_result.coverage_level if structural_result else None,
            "unmapped_impacted_files": structural_result.unmapped_impacted_files if structural_result else [],
            "selection_confidence": structural_result.selection_confidence if structural_result else None,
        }

        logger.info(f"Generated structural-first scope: {len(required_items)} required, {len(review_needed_items)} review needed, {len(already_verified_items)} already verified")

        return RegressionScopeV2Service._build_regression_scope_v2(
            run=run,
            mode=mode,
            items=ordered_items,
            diagnostics_data=diagnostics,
            include_diagnostics=include_diagnostics,
        )

    @staticmethod
    def generate_scope_v2(
        db: Session,
        run_id: str,
        mode: ScopeMode = ScopeMode.TARGETED,
        include_safe_to_skip: bool = False,
        include_diagnostics: bool = False,
        audit: bool = False
    ) -> RegressionScopeV2:
        """Generate regression scope V2 for a recommendation run.

        Args:
            db: Database session
            run_id: Recommendation run ID
            mode: Scope generation mode (targeted, risk_based, full)
            include_safe_to_skip: Whether to include safe-to-skip items
            include_diagnostics: Whether to include diagnostic information
            audit: Whether to include audit information

        Returns:
            RegressionScopeV2: Unified regression scope
        """
        import json
        import uuid
        if isinstance(run_id, str):
            try:
                run_id = uuid.UUID(run_id)
            except ValueError:
                pass

        # Get recommendation run
        run = db.query(RecommendationRun).filter(
            RecommendationRun.id == run_id
        ).first()

        if not run:
            raise ValueError(f"Recommendation run {run_id} not found")

        # Cast model UUID string attributes to uuid.UUID objects for SQLite compatibility
        if run.pr_id and isinstance(run.pr_id, str):
            run.pr_id = uuid.UUID(run.pr_id)
        if run.repository_id and isinstance(run.repository_id, str):
            run.repository_id = uuid.UUID(run.repository_id)

        # Get PR
        pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
        if not pr:
            raise ValueError(f"Pull request not found for run {run_id}")

        if pr.id and isinstance(pr.id, str):
            pr.id = uuid.UUID(pr.id)
        
        # Part 8: Regression Engine Guardrails - Check PR package readiness
        pr_package_ready = True
        pr_package_blockers = []
        
        # Check head_commit_sha exists
        if not pr.head_commit_sha:
            pr_package_ready = False
            pr_package_blockers.append("HEAD_SHA_MISSING")
        
        # Check changed_files_count > 0 or use the snapshot as fallback.
        snapshot_changed_files = []
        if run.requirement_evidence_snapshot_json:
            raw = run.requirement_evidence_snapshot_json
            if isinstance(raw, str):
                try:
                    import json
                    raw = json.loads(raw)
                except Exception:
                    raw = {}
            snapshot_changed_files = raw.get("changedFiles") or []
        if not snapshot_changed_files and run.changed_files_snapshot_json:
            snapshot_changed_files = run.changed_files_snapshot_json or []

        if (not pr.changed_files_count or pr.changed_files_count == 0) and not snapshot_changed_files:
            pr_package_ready = False
            pr_package_blockers.append("CHANGED_FILES_MISSING")
        
        # Check PullRequestChangedFile records exist (snapshot changed files satisfy the package)
        from app.models.pull_request import PullRequestChangedFile
        changed_file_count = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).count()
        if changed_file_count == 0 and not snapshot_changed_files:
            pr_package_ready = False
            pr_package_blockers.append("CHANGED_FILES_DB_MISSING")
        
        # Block confident targeted/risk-based regression if PR package not ready
        if not pr_package_ready and mode in (ScopeMode.TARGETED, ScopeMode.RISK_BASED):
            return RegressionScopeV2Service._blocked_regression_scope_v2(
                run=run,
                mode=mode,
                reason="PR package is incomplete. Changed files/head SHA are required for confident targeted/risk-based regression.",
                blockers=pr_package_blockers,
                include_diagnostics=include_diagnostics,
            )

        # Get acceptance criteria
        # First try to get ACs for this specific PR
        ac_rows = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pr.id
        ).all()
        
        # Get changed files for structural impact selection
        pr_changed_files = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).all()
        changed_file_paths = [cf.file_path for cf in pr_changed_files]
        
        # Perform structural impact selection
        structural_result = None
        try:
            structural_request = StructuralImpactSelectionRequest(
                repository_id=run.repository_id,
                pull_request_id=pr.id,
                head_commit_sha=pr.head_commit_sha or "",
                changed_files=changed_file_paths,
                max_expansion_depth=1,
                require_test_level=False,
            )
            structural_result = StructuralImpactSelectionService.select_structural_impact(db, structural_request)
            logger.info(f"Structural impact selection: {len(structural_result.structurally_impacted_tests)} tests, coverage_level={structural_result.coverage_level}")
        except Exception as e:
            logger.error(f"Structural impact selection failed: {e}")
            structural_result = None
        
        # If no PR-specific ACs, fall back to repository-level ACs
        if not ac_rows:
            ac_rows = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == run.repository_id
            ).all()

        # Get evidence graph snapshot - fall back to the recommendation input snapshot if missing.
        if not run.requirement_evidence_snapshot_json:
            if not run.input_snapshot:
                raise ValueError(
                    f"Evidence graph snapshot not available for run {run_id} and no recommendation input snapshot exists for fallback."
                )

            try:
                from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService

                logger.info(f"[ScopeGen] Evidence graph snapshot missing for run {run_id}; building from input snapshot.")
                changed_files_for_graph = []
                if run.input_snapshot.changed_files:
                    changed_files_for_graph = run.input_snapshot.changed_files
                elif run.changed_files_snapshot_json:
                    changed_files_for_graph = [
                        f.get("file_path") for f in run.changed_files_snapshot_json
                        if f.get("file_path")
                    ]

                graph_service = RequirementEvidenceGraphService(db)
                view_model = graph_service.build_evidence_graph(
                    repository_id=str(run.repository_id),
                    pull_request_id=str(pr.id),
                    head_sha=pr.head_commit_sha,
                    changed_files=changed_files_for_graph,
                    pr_description=None,
                    recommendation_run_id=str(run.id),
                    canonical_ac_rows=ac_rows,
                )
                graph_service.persist_graph_snapshot(str(run.id), view_model)
                # Refresh run so the persisted snapshot is visible in this session.
                db.refresh(run)

                # Defensive direct persistence for SQLite/UUID binding edge cases.
                if not run.requirement_evidence_snapshot_json:
                    snapshot = {
                        "health": view_model.health,
                        "counts": view_model.counts,
                        "decisionCopy": {
                            "headline": view_model.decision_copy.headline,
                            "explanation": view_model.decision_copy.explanation,
                            "nextAction": view_model.decision_copy.next_action,
                        },
                        "acTraceability": [
                            {
                                "requirementId": row.requirement_id,
                                "readableId": row.readable_id,
                                "title": row.title,
                                "fullText": row.full_text,
                                "coverageStatus": row.coverage_status,
                                "linkedExistingTests": row.linked_existing_tests,
                                "linkedMissingTest": row.linked_missing_test,
                                "priority": row.priority,
                                "notes": row.notes,
                            }
                            for row in (view_model.ac_traceability or [])
                        ],
                        "missingTests": [
                            {
                                "readableId": mt.readable_id,
                                "requirementTitle": mt.requirement_title,
                                "suggestedTestObjective": mt.suggested_test_objective,
                                "riskIfSkipped": mt.risk_if_skipped,
                            }
                            for mt in (view_model.missing_tests or [])
                        ],
                    }
                    run.requirement_evidence_snapshot_json = json.dumps(snapshot)
                    db.commit()
                    db.refresh(run)
            except Exception as exc:
                logger.error(f"[ScopeGen] Failed to build evidence graph snapshot fallback for run {run_id}: {exc}")
                raise ValueError(
                    f"Evidence graph snapshot not available for run {run_id} and could not be rebuilt: {exc}"
                )

        raw_snapshot = run.requirement_evidence_snapshot_json
        # JSONB columns are already deserialized by SQLAlchemy; only call json.loads on strings
        if isinstance(raw_snapshot, str):
            snapshot_data = json.loads(raw_snapshot)
        else:
            snapshot_data = raw_snapshot

        # Build changed_files list from snapshot for diagnostics
        changed_files = snapshot_data.get("changedFiles", []) or []
        evidence_items = snapshot_data.get("acTraceability", []) or []

        # Generate scope based on structural impact as primary core
        # Structural impact produces base candidates, then AC/risk overlays add context
        scope = RegressionScopeV2Service._generate_structural_first_scope(
            run, pr, ac_rows, snapshot_data, structural_result,
            include_safe_to_skip, audit, db=db, include_diagnostics=include_diagnostics, mode=mode
        )

        # Phase 7: Build traceability summary from evidence graph
        traceability = snapshot_data.get("acTraceability", []) or []
        traceability_summary = RegressionScopeV2Service._build_traceability_summary(traceability)
        
        # Phase 7: Build release decision from change impact model
        # We need to build the change impact model to get the release action scope
        from app.services.change_impact_engine import ChangeImpactEngine
        from app.models.pull_request import PullRequestChangedFile
        
        pr_changed_files = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).all()
        
        # Build test_mappings from traceability data
        test_mappings = {}
        for trace in traceability:
            database_ac_id = trace.get("databaseAcId")
            if database_ac_id:
                ac_id = str(database_ac_id)
            else:
                ac_id = str(trace.get("requirementId"))
            
            linked_tests = trace.get("linkedExistingTests", []) or []
            if linked_tests:
                test_mappings[ac_id] = linked_tests
        
        # Build change impact model for release decision and impact enrichment
        release_decision = None
        change_impact_model = None
        try:
            change_impact_model = ChangeImpactEngine.build_change_impact_model(
                pr=pr,
                changed_files=pr_changed_files,
                acceptance_criteria=ac_rows,
                test_mappings=test_mappings,
                mode=mode,
                db=db,
                repository_id=run.repository_id
            )
            release_decision = RegressionScopeV2Service._build_release_decision(
                change_impact_model, mode
            )
            
            # Phase 7: Enrich scope items with impact information from change impact model
            scope = RegressionScopeV2Service._enrich_scope_with_impact_data(
                scope, change_impact_model, traceability, ac_rows
            )
        except Exception as e:
            logger.error(f"[Phase7] Failed to build release decision or enrich scope: {e}")
            # Fallback release decision
            release_decision = ReleaseDecision(
                verdict="UNKNOWN",
                reason=f"Could not determine release decision: {str(e)}",
                required_count=0,
                recommended_count=0,
                already_verified_count=0,
                source_mode=mode.value
            )
        
        # Add traceability summary and release decision to scope
        scope.traceability_summary = traceability_summary
        scope.release_decision = release_decision
        
        # Phase 8: Gap analysis and missing test recommendations
        try:
            from app.services.gap_analyzer import GapAnalyzer
            from app.services.coverage_impact_analyzer import CoverageImpactAnalyzer
            from app.services.evidence_graph.deduplication_service import deduplicate_recommendations as deduplicate
            
            # Extract requirement nodes from PR description or fallback to DB rows
            ac_requirements = []
            if db and pr and getattr(pr, "description", None):
                try:
                    from app.services.evidence_graph.ac_extraction_service import ACExtractionService
                    ac_service = ACExtractionService()
                    context = {"flow": "general", "repository_id": str(pr.repository_id) if hasattr(pr, "repository_id") else None}
                    extraction_result = ac_service.extract_acceptance_criteria(pr.description, context)
                    ac_requirements = extraction_result.requirement_nodes
                except Exception as e:
                    logger.error(f"Failed to extract criteria in V2 service: {e}")
            
            if not ac_requirements and ac_rows:
                from app.services.regression_evidence_classifier import RequirementNode, ScenarioSignature
                for row in ac_rows:
                    flow = "sign-up"
                    text_lower = row.text.lower()
                    if "login" in text_lower:
                        flow = "login"
                    elif "reset" in text_lower:
                        flow = "reset-password"
                    elif "update" in text_lower or "change" in text_lower:
                        flow = "update-password"
                    
                    ac_requirements.append(RequirementNode(
                        requirement_id=str(row.id),
                        readable_id=row.label or f"AC-{row.source_number or 1}",
                        title=row.text,
                        flow=flow,
                        scenario_signature=ScenarioSignature(
                            flow=flow,
                            action="validate",
                            condition="general",
                            expected_outcome="success",
                            subject="password",
                            validation_layer="API",
                            polarity="positive"
                        ),
                        classification="PARTIALLY_COVERED" if "complexity" in text_lower else "MISSING",
                        is_real_testable_requirement=True,
                        database_ac_id=str(row.id)
                    ))
            
            # Extract existing test names for deduplication
            existing_test_names = set()
            for trace in traceability:
                linked_tests = trace.get('linkedExistingTests', [])
                for test in linked_tests:
                    test_name = test if isinstance(test, str) else str(test)
                    existing_test_names.add(test_name)

            # Build evidence overlay
            evidence_overlay = {}
            if change_impact_model and change_impact_model.release_action_scope:
                for item in change_impact_model.release_action_scope:
                    overlay_key = getattr(item, 'requirement_id', None) or getattr(item, 'id', None) or getattr(item, 'source_ac_id', None)
                    if overlay_key:
                        final_bucket_val = item.final_bucket.value if hasattr(item.final_bucket, 'value') else str(item.final_bucket)
                        evidence_overlay[str(overlay_key)] = final_bucket_val

            # Get coverage data
            coverage_data = CoverageImpactAnalyzer.extract_coverage_from_snapshot(snapshot_data)
            
            # Build impacted flows
            impacted_flows = set()
            if change_impact_model:
                for f in change_impact_model.directly_impacted_flows:
                    flow_name = f.flow if hasattr(f, 'flow') else str(f)
                    impacted_flows.add(flow_name)
                for f in change_impact_model.indirectly_impacted_flows:
                    flow_name = f.flow if hasattr(f, 'flow') else str(f)
                    impacted_flows.add(flow_name)

            # Get change summaries
            change_summaries = getattr(change_impact_model, "change_summaries", {}) or {}

            # Execute gap analysis pipeline
            req_gaps = GapAnalyzer.extract_requirement_gaps(ac_requirements, evidence_overlay, change_summaries, existing_test_names)
            cov_gaps = GapAnalyzer.convert_coverage_gaps_to_recommendations(coverage_data, change_summaries)
            risk_gaps = GapAnalyzer.analyze_risk_heuristics(impacted_flows, existing_test_names, change_summaries)
            
            recommendations = deduplicate(req_gaps + cov_gaps + risk_gaps, existing_test_names)

            # ── Filter out recommendations for already-verified requirements ──
            # A verified AC must never appear in Test Gaps. Build a set of
            # verified requirement identifiers from the scope groups that
            # represent verified/passed/safe-to-skip items.
            verified_ids: set = set()
            verified_readable_ids: set = set()
            verified_titles_normalized: set = set()
            for group_key in (
                ScopeGroup.EXCLUDED_ALREADY_VERIFIED.value,
                ScopeGroup.SAFE_TO_SKIP.value,
                ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS.value,
            ):
                group_data = scope.groups.get(group_key)
                if not group_data or not group_data.items:
                    continue
                for item in group_data.items:
                    if item.id:
                        verified_ids.add(str(item.id))
                    if item.readable_id:
                        verified_readable_ids.add(str(item.readable_id).strip().upper())
                    if item.source_ac_number is not None:
                        verified_readable_ids.add(f"AC-{item.source_ac_number}")
                    if item.title:
                        verified_titles_normalized.add(
                            item.title.strip().lower()
                        )

            def _is_verified(rec) -> bool:
                """Check if a recommendation corresponds to a verified AC."""
                # 1. Direct ID match
                linked_req_id = getattr(rec, 'linked_requirement_id', None)
                if linked_req_id and str(linked_req_id) in verified_ids:
                    return True

                # 2. Readable ID match (e.g. "AC-01" in title or linked_requirement_id)
                rec_title = getattr(rec, 'title', '') or ''
                rec_title_upper = rec_title.strip().upper()
                for rid in verified_readable_ids:
                    if rid and rid in rec_title_upper:
                        return True

                # 3. Normalized title overlap (exact match on lowercased text)
                rec_title_lower = rec_title.strip().lower()
                if rec_title_lower in verified_titles_normalized:
                    return True

                return False

            pre_filter_count = len(recommendations)
            recommendations = [r for r in recommendations if not _is_verified(r)]
            filtered_count = pre_filter_count - len(recommendations)
            if filtered_count > 0:
                logger.info(
                    f"[Phase8] Filtered {filtered_count} recommendation(s) "
                    f"that correspond to already-verified ACs"
                )

            recommendations = recommendations[:15]

            # Update release decision reason to include recommendation count
            if recommendations:
                current_reason = release_decision.reason
                release_decision.reason = f"{current_reason} {len(recommendations)} additional test(s) recommended for safety."
                release_decision.recommended_count = len(recommendations)
            
            scope.recommendations = recommendations
            logger.info(f"[Phase8] Generated {len(recommendations)} missing test recommendations")
            
            # Collect ALREADY_VERIFIED evidence items
            from app.schemas.regression_scope_v2 import EvidenceItem
            evidence_items = []
            if change_impact_model and change_impact_model.release_action_scope:
                for item in change_impact_model.release_action_scope:
                    if item.final_bucket and item.final_bucket.value == "ALREADY_VERIFIED":
                        req_title = "Unknown Requirement"
                        if item.source_ac_id:
                            ac_row = next((ac for ac in ac_rows if str(getattr(ac, 'id', '')) == str(item.source_ac_id) or str(getattr(ac, 'requirement_id', '')) == str(item.source_ac_id)), None)
                            if ac_row:
                                req_title = getattr(ac_row, 'title', "Unknown Requirement")
                        
                        evidence_items.append(EvidenceItem(
                            requirement_id=item.source_ac_id or item.id or "unknown",
                            requirement_title=req_title,
                            verifying_test=item.title,
                            test_status=item.execution_status,
                            test_freshness=item.freshness_status,
                            impact_reason=item.evidence_reason or item.impact_reason or "Verified by evidence overlay",
                            final_bucket="ALREADY_VERIFIED"
                        ))
            scope.evidence_items = evidence_items
            logger.info(f"[Phase8] Collected {len(evidence_items)} already verified evidence items")
            
        except Exception as e:
            logger.error(f"[Phase8] Failed to generate gap analysis recommendations: {e}")
            scope.recommendations = []
            scope.evidence_items = []
        
        # Add diagnostics if requested
        if include_diagnostics:
            # Phase 5.10: Include change impact engine diagnostics
            try:
                from app.schemas.change_impact import ChangeImpactDiagnostics
                
                # Build change impact model for diagnostics (reuse if already built)
                if 'change_impact_model' not in locals():
                    change_impact_model = ChangeImpactEngine.build_change_impact_model(
                        pr=pr,
                        changed_files=pr_changed_files,
                        acceptance_criteria=ac_rows,
                        test_mappings=test_mappings,
                        mode=mode,
                        db=db,
                        repository_id=run.repository_id
                    )
                
                # Build diagnostics
                impact_diagnostics = ChangeImpactDiagnostics(
                    change_inventory=change_impact_model.change_inventory,
                    impacted_flows={
                        "direct": change_impact_model.directly_impacted_flows,
                        "indirect": change_impact_model.indirectly_impacted_flows,
                        "cross_layer": change_impact_model.cross_layer_impacts,
                        "security_sensitive": change_impact_model.security_sensitive_impacts,
                        "unknown": change_impact_model.unknown_impacts
                    },
                    ac_impact_matrix=change_impact_model.ac_impact_matrix,
                    candidate_selection={
                        "mode": mode.value,
                        "total_candidates": len(change_impact_model.regression_candidates),
                        "by_impact_type": {
                            "DIRECT": len([c for c in change_impact_model.regression_candidates if c.impact_type.value == "DIRECT"]),
                            "INDIRECT": len([c for c in change_impact_model.regression_candidates if c.impact_type.value == "INDIRECT"]),
                            "CROSS_LAYER": len([c for c in change_impact_model.regression_candidates if c.impact_type.value == "CROSS_LAYER"]),
                            "SECURITY_SENSITIVE": len([c for c in change_impact_model.regression_candidates if c.impact_type.value == "SECURITY_SENSITIVE"])
                        }
                    },
                    evidence_overlay={
                        "total_scope_items": len(change_impact_model.release_action_scope),
                        "by_final_bucket": {
                            "REQUIRED": len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "REQUIRED"]),
                            "REVIEW_NEEDED": len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "REVIEW_NEEDED"]),
                            "ALREADY_VERIFIED": len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "ALREADY_VERIFIED"]),
                            "RECOMMENDED": len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "RECOMMENDED"]),
                            "OPTIONAL": len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "OPTIONAL"]),
                            "SAFE_TO_SKIP": len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "SAFE_TO_SKIP"])
                        }
                    },
                    mode_strategy=f"Phase 5 Change Impact Engine v1 - {mode.value.upper()} mode",
                    release_action_counts={
                        "FIX_OR_RERUN": len([s for s in change_impact_model.release_action_scope if s.release_action.value == "FIX_OR_RERUN"]),
                        "RE_RUN": len([s for s in change_impact_model.release_action_scope if s.release_action.value == "RE_RUN"]),
                        "RUN_OR_CREATE_TEST": len([s for s in change_impact_model.release_action_scope if s.release_action.value == "RUN_OR_CREATE_TEST"]),
                        "MANUAL_REVIEW": len([s for s in change_impact_model.release_action_scope if s.release_action.value == "MANUAL_REVIEW"]),
                        "NONE": len([s for s in change_impact_model.release_action_scope if s.release_action.value == "NONE"])
                    }
                )
                
                # Merge with existing diagnostics
                existing_rules = scope.diagnostics.rules_applied if scope.diagnostics else []
                existing_rules.extend([
                    "Phase 5: Change Impact Engine v1",
                    "Change inventory built from PR data",
                    "File-path classification to business flows",
                    "AC impact matrix generated",
                    "Regression candidate selection by mode",
                    "Evidence overlay applied after candidate selection"
                ])
                
                scope.diagnostics = ScopeDiagnostics(
                    generation_timestamp=datetime.utcnow(),
                    generation_duration_ms=None,
                    rules_applied=existing_rules,
                    warnings=[],
                    errors=[],
                    # Phase 5.10: Add impact diagnostics
                    change_impact_diagnostics=impact_diagnostics
                )
                
            except Exception as e:
                logger.error(f"[Phase5.10] Failed to build impact diagnostics: {e}")
                # Fallback to basic diagnostics
                scope.diagnostics = ScopeDiagnostics(
                    generation_timestamp=datetime.utcnow(),
                    generation_duration_ms=None,
                    rules_applied=scope.diagnostics.rules_applied if scope.diagnostics else [],
                    warnings=[f"Impact diagnostics failed: {str(e)}"],
                    errors=[]
                )

        return scope

    @staticmethod
    def _generate_unified_scope_v2(
        db: Session,
        run: RecommendationRun,
        pr: PullRequest,
        ac_rows: List[AcceptanceCriterion],
        snapshot_data: Dict[str, Any],
        include_safe_to_skip: bool,
        audit: bool,
        include_diagnostics: bool,
        mode: ScopeMode
    ) -> RegressionScopeV2:
        # 1. Build test_mappings from snapshot
        traceability = snapshot_data.get("acTraceability", []) or []
        test_mappings = {}
        for trace in traceability:
            database_ac_id = trace.get("databaseAcId")
            ac_id = str(database_ac_id) if database_ac_id else str(trace.get("requirementId"))
            linked_tests = trace.get("linkedExistingTests", []) or []
            if linked_tests:
                test_mappings[ac_id] = linked_tests

        # 2. Build ChangeImpactModel using ChangeImpactEngine
        from app.services.change_impact_engine import ChangeImpactEngine
        from app.models.pull_request import PullRequestChangedFile
        pr_changed_files = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).all()
        
        change_impact_model = ChangeImpactEngine.build_change_impact_model(
            pr=pr,
            changed_files=pr_changed_files,
            acceptance_criteria=ac_rows,
            test_mappings=test_mappings,
            mode=mode,
            db=db,
            repository_id=run.repository_id
        )

        # 3. Create ScopeItem lists
        from app.schemas.change_impact import FinalBucket
        from app.schemas.regression_scope_v2 import ScopeGroup, EvidenceClassification, RiskBand, ChangeImpactLevel, BusinessRiskLevel, ScopeItemType, ScopeItemDiagnostics
        
        bucket_to_group = {
            FinalBucket.REQUIRED: ScopeGroup.REQUIRED,
            FinalBucket.REVIEW_NEEDED: ScopeGroup.REVIEW_NEEDED,
            FinalBucket.ALREADY_VERIFIED: ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
            FinalBucket.RECOMMENDED: ScopeGroup.RECOMMENDED,
            FinalBucket.OPTIONAL: ScopeGroup.OPTIONAL,
            FinalBucket.SAFE_TO_SKIP: ScopeGroup.SAFE_TO_SKIP,
            FinalBucket.DEFERRED_COVERAGE_DEBT: ScopeGroup.DEFERRED_COVERAGE_DEBT
        }
        
        # Build maps for release action items
        release_action_by_ac_id = {}
        for item in change_impact_model.release_action_scope:
            if item.source_ac_id:
                release_action_by_ac_id[str(item.source_ac_id)] = item
            if item.id:
                release_action_by_ac_id[str(item.id)] = item

        # Keep lists of items
        required_items = []
        recommended_items = []
        optional_items = []
        safe_to_skip_items = []
        already_verified_items = []
        already_passed_test_items = []
        review_needed_items = []

        # Load PatternMemoryV2 records for outcome learning override
        pattern_memory_set = RegressionScopeV2Service._get_pattern_memory_keys(db, run.repository_id)

        for ac in ac_rows:
            ac_id_str = str(ac.id)
            trace = next((t for t in traceability if str(t.get("databaseAcId")) == ac_id_str or str(t.get("requirementId")) == ac_id_str), None)
            
            # Look up in release action scope (candidate selection)
            ra_item = release_action_by_ac_id.get(ac_id_str)
            
            if ra_item:
                selected_by_impact = True
                impact_type = ra_item.impact_type.value if ra_item.impact_type else "NONE"
                candidate_reason = ra_item.candidate_reason or "Selected by mode strategy"
                evidence_reason = ra_item.evidence_reason or "Evidence overlay applied"
                execution_status = ra_item.execution_status
                freshness_status = ra_item.freshness_status
                release_action = ra_item.release_action.value if ra_item.release_action else "NONE"
                final_bucket = ra_item.final_bucket
                
                # Check guard (Part 6/7)
                if execution_status == "PASSED" and freshness_status == "FRESH":
                    assert final_bucket != FinalBucket.RECOMMENDED, "PASSED/FRESH items cannot enter Recommended"
                
                scope_group = bucket_to_group.get(final_bucket, ScopeGroup.REQUIRED)
            else:
                selected_by_impact = False
                impact_type = "NONE"
                candidate_reason = "Not selected by mode strategy"
                evidence_reason = "Excluded from candidate selection"
                execution_status = "NOT_RUN"
                freshness_status = "UNKNOWN"
                release_action = "NONE"
                scope_group = ScopeGroup.SAFE_TO_SKIP

            # Get linked tests
            linked_tests = test_mappings.get(ac_id_str, [])
            
            # Determine baseline risk parameters using fallback keywords & specific high-risk rules
            title_desc = (ac.text or "").lower()
            business_risk = "MEDIUM"
            criticality = "MEDIUM"
            requirement_type = "FUNCTIONAL"
            
            keywords = ['password', 'auth', 'login', 'token', 'security', 'credential', 'session', 'permission', 'access']
            if any(kw in title_desc for kw in keywords):
                business_risk = "HIGH"
                criticality = "HIGH"
                requirement_type = "SECURITY"
                
            if "bypass" in title_desc or ("backend" in title_desc and "api" in title_desc and "validation" in title_desc):
                business_risk = "CRITICAL"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "token" in title_desc and ("reuse" in title_desc or "expired" in title_desc or "reused" in title_desc or "reset" in title_desc):
                business_risk = "CRITICAL"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "password" in title_desc and "not updated" in title_desc:
                business_risk = "HIGH"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
                
            risk_result = RiskScoringService.calculate_requirement_risk_score(
                business_risk=business_risk,
                coverage_status=execution_status or "NOT_RUN",
                criticality=criticality,
                requirement_type=requirement_type
            )
            
            # Map coverage status to evidence classification
            coverage_map = {
                "PASSED": EvidenceClassification.COVERED,
                "FAILED": EvidenceClassification.MISSING,
                "SKIPPED": EvidenceClassification.PARTIAL,
                "NOT_RUN": EvidenceClassification.MISSING
            }

            item = ScopeItem(
                id=ac_id_str,
                readable_id=ac.normalized_key or ac.label or f"AC-{ac.source_number or 1}",
                source_ac_number=ac.source_number,
                title=ac.text or "",
                item_type=ScopeItemType.REQUIREMENT,
                group=scope_group,
                evidence_classification=coverage_map.get(execution_status, EvidenceClassification.MISSING),
                risk_score=risk_result["riskScore"],
                risk_band=RiskBand(risk_result["riskBand"]),
                change_impact_level=ChangeImpactLevel(impact_type) if impact_type in ChangeImpactLevel.__members__ else ChangeImpactLevel.NONE,
                business_risk_level=BusinessRiskLevel(business_risk),
                effective_risk_level=BusinessRiskLevel(business_risk),
                suggested_action="Run test" if scope_group == ScopeGroup.REQUIRED else "Review",
                reason=evidence_reason,
                evidence_references=[],
                test_references=linked_tests,
                can_auto_execute=len(linked_tests) > 0,
                execution_status=execution_status,
                estimated_effort=None,
                is_required_for_release=(scope_group == ScopeGroup.REQUIRED),
                is_manual_only=False,
                release_action=release_action,
                freshness_status=freshness_status,
                mapping_status="VERIFIED" if len(linked_tests) > 0 else "UNVERIFIED",
                linked_test_count=len(linked_tests),
                linked_tests=linked_tests,
                diagnostics=ScopeItemDiagnostics(
                    internal_requirement_id=ac_id_str if audit else None,
                    internal_test_id=None,
                    generation_rule=None,
                    confidence_score=None,
                    last_updated=None
                ) if audit else None,
                reason_code=ra_item.reason_code if ra_item else None
            )

            # Apply manual risk adjustment if any
            if trace:
                item = RegressionScopeV2Service._apply_manual_risk_adjustment(
                    item, snapshot_data, db
                )

            # Check outcome learning override
            matched_pattern = RegressionScopeV2Service._matches_pattern_memory(
                pattern_memory_set,
                getattr(ac, 'normalized_key', None),
                ac.text,
                linked_tests
            )
            if matched_pattern:
                item.group = ScopeGroup.REQUIRED
                item.is_required_for_release = True
                item.release_action = ReleaseAction.RE_RUN.value
                item.reason = f"Outcome learning: a prior incident was recorded for this scenario. Required regardless of current coverage."
                item.suggested_action = "Review — flagged by outcome learning"
                required_items.append(item)
                continue

            # Bucketing lists
            if item.group == ScopeGroup.REQUIRED:
                required_items.append(item)
            elif item.group == ScopeGroup.REVIEW_NEEDED:
                review_needed_items.append(item)
            elif item.group == ScopeGroup.RECOMMENDED:
                recommended_items.append(item)
            elif item.group == ScopeGroup.OPTIONAL:
                optional_items.append(item)
            elif item.group == ScopeGroup.EXCLUDED_ALREADY_VERIFIED:
                already_verified_items.append(item)
            elif item.group == ScopeGroup.SAFE_TO_SKIP:
                safe_to_skip_items.append(item)
            elif item.group == ScopeGroup.DEFERRED_COVERAGE_DEBT:
                review_needed_items.append(item)

        # Merge manual items
        manual_buckets = RegressionScopeV2Service._generate_manual_scope_items(snapshot_data, audit, db)
        required_items.extend(manual_buckets.get(ScopeGroup.REQUIRED, []))
        recommended_items.extend(manual_buckets.get(ScopeGroup.RECOMMENDED, []))
        optional_items.extend(manual_buckets.get(ScopeGroup.OPTIONAL, []))
        safe_to_skip_items.extend(manual_buckets.get(ScopeGroup.SAFE_TO_SKIP, []))

        # Build groups
        groups = {
            ScopeGroup.REQUIRED.value: ScopeGroupSummary(
                group=ScopeGroup.REQUIRED,
                count=len(required_items),
                items=required_items
            ),
            ScopeGroup.RECOMMENDED.value: ScopeGroupSummary(
                group=ScopeGroup.RECOMMENDED,
                count=len(recommended_items),
                items=recommended_items
            ),
            ScopeGroup.OPTIONAL.value: ScopeGroupSummary(
                group=ScopeGroup.OPTIONAL,
                count=len(optional_items),
                items=optional_items
            ),
            ScopeGroup.SAFE_TO_SKIP.value: ScopeGroupSummary(
                group=ScopeGroup.SAFE_TO_SKIP,
                count=len(safe_to_skip_items),
                items=safe_to_skip_items if include_safe_to_skip else []
            ),
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED.value: ScopeGroupSummary(
                group=ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
                count=len(already_verified_items),
                items=already_verified_items
            ),
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS.value: ScopeGroupSummary(
                group=ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS,
                count=len(already_passed_test_items),
                items=already_passed_test_items
            ),
            ScopeGroup.REVIEW_NEEDED.value: ScopeGroupSummary(
                group=ScopeGroup.REVIEW_NEEDED,
                count=len(review_needed_items),
                items=review_needed_items
            )
        }

        # Build execution plan
        execution_plan = ExecutionPlan(
            required_count=len(required_items),
            recommended_count=len(recommended_items),
            optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            review_needed_count=len(review_needed_items),
            total_executable_count=len(required_items) + len(recommended_items) + len(optional_items),
            estimated_execution_reduction=0.0,
            confidence_level=90.0,
            plan_summary=f"Unified change impact scope - {mode.value.upper()}",
            advisory_notice="Mode-specific selection strategy applied via ChangeImpactEngine",
            manual_required_count=0,
            manual_recommended_count=0,
            manual_optional_count=0,
            manual_safe_to_skip_count=0,
            automated_required_count=len(required_items),
            automated_recommended_count=len(recommended_items),
            manual_estimated_minutes=0,
            automated_estimated_minutes=0
        )

        exclusions = ScopeExclusions(
            already_verified_count=len(already_verified_items),
            already_passed_tests_count=len(already_passed_test_items),
            already_verified_items=already_verified_items,
            already_passed_test_items=already_passed_test_items
        )

        current_tests = snapshot_data.get("counts", {}).get("uploadedPrTestsPassed", 0)
        optimization_metrics = ScopeOptimizationMetrics(
            current_regression_size=current_tests,
            optimized_required_count=len(required_items),
            optimized_recommended_count=len(recommended_items),
            optimized_optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            optimization_percentage=0.0,
            execution_reduction=0.0,
            coverage_confidence=0.0
        )

        governance = ScopeGovernance(
            risk_reviews_count=0,
            overridden_count=0,
            needs_discussion_count=0,
            release_decision_required=False,
            release_decision_status=None
        )

        diagnostics_applied = [
            f"MODE_STRATEGY_{mode.value.upper()}",
            "CANDIDATE_SELECTION_BEFORE_EVIDENCE",
            "EVIDENCE_OVERLAY_AFTER_SELECTION"
        ]

        diagnostics = ScopeDiagnostics(
            generation_timestamp=datetime.utcnow(),
            generation_duration_ms=None,
            rules_applied=diagnostics_applied,
            warnings=[],
            errors=[]
        )

        return RegressionScopeV2(
            recommendation_run_id=str(run.id),
            snapshot_hash=run.evidence_fingerprint or str(run.id),
            generated_at=datetime.utcnow(),
            scope_type=mode.value.upper(),
            source=ScopeSource.EVIDENCE_BASED,
            summary=f"Unified scope with {len(required_items)} required and {len(recommended_items)} recommended items",
            execution_plan=execution_plan,
            groups=groups,
            exclusions=exclusions,
            optimization_metrics=optimization_metrics,
            governance=governance,
            diagnostics=diagnostics
        )

    @staticmethod
    def _generate_targeted_scope(
        run: RecommendationRun,
        pr: PullRequest,
        ac_rows: List[AcceptanceCriterion],
        snapshot_data: Dict[str, Any],
        include_safe_to_skip: bool,
        audit: bool,
        db: Session = None,
        include_diagnostics: bool = False
    ) -> RegressionScopeV2:
        return RegressionScopeV2Service._generate_unified_scope_v2(
            db, run, pr, ac_rows, snapshot_data, include_safe_to_skip, audit, include_diagnostics, ScopeMode.TARGETED
        )

    def _targeted_scope_legacy_block(self):
        warnings_list = []
        # Extract coverage data from snapshot
        traceability = snapshot_data.get("acTraceability", [])

        # Load PatternMemoryV2 records for outcome learning override
        pattern_memory_set = RegressionScopeV2Service._get_pattern_memory_keys(db, run.repository_id)
        pattern_memories = RegressionScopeV2Service._get_pattern_memory_records(db, run.repository_id)

        # Load PullRequestChangedFile records for mutation check
        changed_file_paths = RegressionScopeV2Service._get_pr_changed_files(db, pr.id)
        
        # Build scope items
        required_items = []
        recommended_items = []
        optional_items = []
        safe_to_skip_items = []
        already_verified_items = []
        already_passed_test_items = []
        review_needed_items = []

        for trace in traceability:
            coverage_status = trace.get("coverageStatus", "MISSING")
            linked_tests = trace.get("linkedExistingTests", []) or []

            # Find real AC
            ac = next((row for row in ac_rows if str(row.id) == trace.get("requirementId")), None)

            # Create scope item
            item = RegressionScopeV2Service._create_scope_item_from_trace(
                trace, audit, db=db, repository_id=run.repository_id, ac=ac
            )

            # Resolve test evidence using the single source of truth
            evidence = RegressionScopeV2Service._resolve_test_evidence_for_ac(
                ac, pr, db, linked_tests, run.repository_id
            )
            item.execution_status = evidence['execution_status']
            item.freshness_status = evidence['freshness_status']
            covered_files = evidence['covered_file_paths']

            # Determine baseline risk parameters using fallback keywords & specific high-risk rules
            title_desc = (item.title or "").lower() + " " + (trace.get("fullText") or "").lower()
            business_risk = "MEDIUM"
            criticality = "MEDIUM"
            requirement_type = "FUNCTIONAL"
            
            # Fallback keywords
            keywords = ['password', 'auth', 'login', 'token', 'security', 'credential', 'session', 'permission', 'access']
            if any(kw in title_desc for kw in keywords):
                business_risk = "HIGH"
                criticality = "HIGH"
                requirement_type = "SECURITY"
                
            # Specific high-risk rules
            if "bypass" in title_desc or ("backend" in title_desc and "api" in title_desc and "validation" in title_desc):
                business_risk = "CRITICAL"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "token" in title_desc and ("reuse" in title_desc or "expired" in title_desc or "reused" in title_desc or "reset" in title_desc):
                business_risk = "CRITICAL"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "password" in title_desc and "not updated" in title_desc:
                business_risk = "HIGH"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "login" in title_desc or "log in" in title_desc:
                if "password update" in title_desc or "password change" in title_desc or "password is updated" in title_desc or "updated" in title_desc:
                    business_risk = "HIGH"
                    criticality = "HIGH"
                    requirement_type = "SECURITY"
            elif ("ui" in title_desc and "api" in title_desc) or "consistent" in title_desc or "consistency" in title_desc:
                business_risk = "HIGH"
                criticality = "HIGH"
                requirement_type = "SECURITY"
            elif "error message" in title_desc or "validation error" in title_desc:
                business_risk = "MEDIUM"
                criticality = "HIGH"
                requirement_type = "SECURITY"
                
            # Calculate risk score
            risk_result = RiskScoringService.calculate_requirement_risk_score(
                business_risk=business_risk,
                coverage_status=coverage_status or "VERIFIED",
                criticality=criticality,
                requirement_type=requirement_type
            )
            item.risk_score = risk_result["riskScore"]
            item.risk_band = RiskBand(risk_result["riskBand"])
            item.business_risk_level = BusinessRiskLevel(business_risk)
            item.effective_risk_level = item.business_risk_level

            # Apply manual risk adjustment if any
            item = RegressionScopeV2Service._apply_manual_risk_adjustment(
                item, snapshot_data, db
            )

            # Signal 2 — Outcome Learning Override
            matched_pattern = RegressionScopeV2Service._matches_pattern_memory(
                pattern_memory_set,
                ac.normalized_key if ac else None,
                ac.text if ac else None,
                linked_tests
            )

            if matched_pattern:
                item.group = ScopeGroup.REQUIRED
                item.is_required_for_release = True
                item.release_action = ReleaseAction.RE_RUN
                
                signal = next(
                    (p for p in pattern_memories if p.pattern_key == matched_pattern),
                    None
                )
                signal_type = signal.signal_type if signal else "incident"
                item.reason = f"Outcome learning: a prior {signal_type} was recorded for this scenario. Required regardless of current coverage."
                item.suggested_action = "Review — flagged by outcome learning"
                required_items.append(item)
                continue

            # Use strict decision tree for classification
            scope_group, release_action, reason = RegressionScopeV2Service._classify_ac(
                evidence=evidence,
                changed_file_paths=changed_file_paths,
                risk_band=item.risk_band.value if item.risk_band else "MEDIUM"
            )
            
            item.group = scope_group
            item.release_action = release_action
            item.suggested_action = release_action.value.replace("_", " ").title()
            item.reason = reason
            item.is_required_for_release = (scope_group == ScopeGroup.REQUIRED)
            
            # Bucketing lists
            if scope_group == ScopeGroup.REQUIRED:
                required_items.append(item)
            elif scope_group == ScopeGroup.REVIEW_NEEDED:
                review_needed_items.append(item)
            elif scope_group == ScopeGroup.RECOMMENDED:
                recommended_items.append(item)
            elif scope_group == ScopeGroup.OPTIONAL:
                optional_items.append(item)
            elif scope_group == ScopeGroup.EXCLUDED_ALREADY_VERIFIED:
                already_verified_items.append(item)
            elif scope_group == ScopeGroup.SAFE_TO_SKIP:
                safe_to_skip_items.append(item)

        # Count Integrity & Deduplication (Part 6)
        all_buckets = {
            ScopeGroup.REQUIRED: required_items,
            ScopeGroup.REVIEW_NEEDED: review_needed_items,
            ScopeGroup.RECOMMENDED: recommended_items,
            ScopeGroup.OPTIONAL: optional_items,
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED: already_verified_items,
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS: already_passed_test_items,
            ScopeGroup.SAFE_TO_SKIP: safe_to_skip_items,
        }
        
        priority_order = [
            ScopeGroup.REQUIRED,
            ScopeGroup.REVIEW_NEEDED,
            ScopeGroup.RECOMMENDED,
            ScopeGroup.OPTIONAL,
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
            ScopeGroup.SAFE_TO_SKIP,
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS
        ]
        priority_map = {g: idx for idx, g in enumerate(priority_order)}
        
        def get_stable_identity_key(x: ScopeItem) -> str:
            if x.id:
                return f"id:{x.id}"
            if x.source_ac_number is not None:
                return f"seq:{x.source_ac_number}"
            if x.readable_id:
                return f"rid:{x.readable_id}"
            return f"title:{x.title}"
            
        by_identity = {}
        for group, item_list in all_buckets.items():
            for x in item_list:
                x.group = group
                key = get_stable_identity_key(x)
                if key not in by_identity:
                    by_identity[key] = []
                by_identity[key].append(x)
                
        deduped = {g: [] for g in all_buckets.keys()}
        for key, items_list in by_identity.items():
            if len(items_list) > 1:
                if include_diagnostics:
                    warnings_list.append(f"Duplicate stable identity key detected: {key}")
                    
                items_list.sort(key=lambda x: priority_map.get(x.group, 99))
                best_item = items_list[0]
                
                has_passed_fresh = any(
                    x.execution_status == "PASSED" and x.freshness_status == "FRESH"
                    for x in items_list
                )
                if has_passed_fresh and best_item.group == ScopeGroup.REQUIRED:
                    best_item.group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                    best_item.release_action = ReleaseAction.NONE
                    best_item.is_required_for_release = False
                    
                deduped[best_item.group].append(best_item)
            else:
                x = items_list[0]
                deduped[x.group].append(x)
                
        required_items = deduped[ScopeGroup.REQUIRED]
        review_needed_items = deduped[ScopeGroup.REVIEW_NEEDED]
        recommended_items = deduped[ScopeGroup.RECOMMENDED]
        optional_items = deduped[ScopeGroup.OPTIONAL]
        already_verified_items = deduped[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]
        already_passed_test_items = deduped[ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS]
        safe_to_skip_items = deduped[ScopeGroup.SAFE_TO_SKIP]

        # Capture automated-only counts before merging manual items
        automated_required_count = len(required_items)
        automated_recommended_count = len(recommended_items)
        automated_executable_count = len(required_items) + len(recommended_items) + len(optional_items)

        # Merge MANUAL_TEST scope items
        manual_buckets = RegressionScopeV2Service._generate_manual_scope_items(snapshot_data, audit, db)
        required_items.extend(manual_buckets.get(ScopeGroup.REQUIRED, []))
        recommended_items.extend(manual_buckets.get(ScopeGroup.RECOMMENDED, []))
        optional_items.extend(manual_buckets.get(ScopeGroup.OPTIONAL, []))
        safe_to_skip_items.extend(manual_buckets.get(ScopeGroup.SAFE_TO_SKIP, []))
        manual_counts = {g: len(manual_buckets.get(g, [])) for g in priority_order}

        # Compute confidence score metrics
        all_items = required_items + recommended_items + optional_items + safe_to_skip_items + already_verified_items + review_needed_items
        total_count = len(all_items)
        
        stale_count = sum(1 for item in all_items if item.freshness_status == "STALE")
        missing_count = sum(1 for item in all_items if item.execution_status == "NOT_RUN")
        failed_count = sum(1 for item in all_items if item.execution_status == "FAILED")
        
        mutation_fired_count = sum(1 for item in all_items if item.reason and "was modified in this PR" in item.reason and item.group == ScopeGroup.REQUIRED)
        mutation_verified_count = sum(1 for item in all_items if item.reason and "was modified in this PR" in item.reason and item.execution_status == "PASSED" and item.freshness_status == "FRESH")
        
        has_outcome_signals = len(pattern_memory_set) > 0
        
        coverage_pct = None
        if "counts" in snapshot_data:
            total_reqs = snapshot_data["counts"].get("totalRequirements", 0)
            verified = snapshot_data["counts"].get("verifiedTests", 0)
            if total_reqs > 0:
                coverage_pct = (verified / total_reqs) * 100
        
        confidence_score, confidence_label = RegressionScopeV2Service._compute_confidence_score(
            required_count=len(required_items),
            already_verified_count=len(already_verified_items),
            stale_count=stale_count,
            missing_count=missing_count,
            failed_count=failed_count,
            mutation_fired_count=mutation_fired_count,
            mutation_verified_count=mutation_verified_count,
            total_count=total_count,
            has_outcome_signals=has_outcome_signals,
            coverage_pct=coverage_pct
        )

        # Build groups
        groups = {
            ScopeGroup.REQUIRED.value: ScopeGroupSummary(
                group=ScopeGroup.REQUIRED,
                count=len(required_items),
                items=required_items
            ),
            ScopeGroup.RECOMMENDED.value: ScopeGroupSummary(
                group=ScopeGroup.RECOMMENDED,
                count=len(recommended_items),
                items=recommended_items
            ),
            ScopeGroup.OPTIONAL.value: ScopeGroupSummary(
                group=ScopeGroup.OPTIONAL,
                count=len(optional_items),
                items=optional_items
            ),
            ScopeGroup.SAFE_TO_SKIP.value: ScopeGroupSummary(
                group=ScopeGroup.SAFE_TO_SKIP,
                count=len(safe_to_skip_items),
                items=safe_to_skip_items if include_safe_to_skip else []
            ),
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED.value: ScopeGroupSummary(
                group=ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
                count=len(already_verified_items),
                items=already_verified_items
            ),
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS.value: ScopeGroupSummary(
                group=ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS,
                count=len(already_passed_test_items),
                items=already_passed_test_items
            ),
            ScopeGroup.REVIEW_NEEDED.value: ScopeGroupSummary(
                group=ScopeGroup.REVIEW_NEEDED,
                count=len(review_needed_items),
                items=review_needed_items
            )
        }

        # Build execution plan
        total_manual = sum(manual_counts.values())
        manual_estimated_minutes = (
            manual_counts.get(ScopeGroup.REQUIRED, 0)
            + manual_counts.get(ScopeGroup.RECOMMENDED, 0)
            + manual_counts.get(ScopeGroup.OPTIONAL, 0)
        ) * RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES
        
        execution_plan = ExecutionPlan(
            required_count=len(required_items),
            recommended_count=len(recommended_items),
            optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            review_needed_count=len(review_needed_items),
            total_executable_count=len(required_items) + len(recommended_items) + len(optional_items),
            estimated_execution_reduction=0.0,
            confidence_level=float(confidence_score),
            plan_summary=f"Targeted scope based on evidence coverage - {confidence_label}",
            advisory_notice="Targeted mode focuses on missing and partial coverage items",
            manual_required_count=manual_counts.get(ScopeGroup.REQUIRED, 0),
            manual_recommended_count=manual_counts.get(ScopeGroup.RECOMMENDED, 0),
            manual_optional_count=manual_counts.get(ScopeGroup.OPTIONAL, 0),
            manual_safe_to_skip_count=manual_counts.get(ScopeGroup.SAFE_TO_SKIP, 0),
            automated_required_count=automated_required_count,
            automated_recommended_count=automated_recommended_count,
            manual_estimated_minutes=manual_estimated_minutes,
            automated_estimated_minutes=0
        )

        exclusions = ScopeExclusions(
            already_verified_count=len(already_verified_items),
            already_passed_tests_count=len(already_passed_test_items),
            already_verified_items=already_verified_items,
            already_passed_test_items=already_passed_test_items
        )

        current_tests = snapshot_data.get("counts", {}).get("uploadedPrTestsPassed", 0)
        optimization_metrics = ScopeOptimizationMetrics(
            current_regression_size=current_tests,
            optimized_required_count=len(required_items),
            optimized_recommended_count=len(recommended_items),
            optimized_optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            optimization_percentage=0.0,
            execution_reduction=0.0,
            coverage_confidence=0.0
        )

        governance = ScopeGovernance(
            risk_reviews_count=0,
            overridden_count=0,
            needs_discussion_count=0,
            release_decision_required=False,
            release_decision_status=None
        )

        diagnostics = ScopeDiagnostics(
            generation_timestamp=datetime.utcnow(),
            generation_duration_ms=None,
            rules_applied=[
                "INCLUDED_MISSING_AUTOMATED_COVERAGE",
                "INCLUDED_PARTIAL_COVERAGE_FOR_REVIEW",
                "EXCLUDED_VERIFIED_REQUIREMENTS"
            ],
            warnings=warnings_list,
            errors=[]
        )

        return RegressionScopeV2(
            recommendation_run_id=str(run.id),
            snapshot_hash=run.evidence_fingerprint or str(run.id),
            generated_at=datetime.utcnow(),
            scope_type="TARGETED",
            source=ScopeSource.EVIDENCE_BASED,
            summary=f"Targeted scope with {len(required_items)} required and {len(recommended_items)} recommended items",
            execution_plan=execution_plan,
            groups=groups,
            exclusions=exclusions,
            optimization_metrics=optimization_metrics,
            governance=governance,
            diagnostics=diagnostics
        )

    @staticmethod
    def _generate_risk_based_scope(
        run: RecommendationRun,
        pr: PullRequest,
        ac_rows: List[AcceptanceCriterion],
        snapshot_data: Dict[str, Any],
        include_safe_to_skip: bool,
        audit: bool,
        db: Session = None,
        include_diagnostics: bool = False
    ) -> RegressionScopeV2:
        return RegressionScopeV2Service._generate_unified_scope_v2(
            db, run, pr, ac_rows, snapshot_data, include_safe_to_skip, audit, include_diagnostics, ScopeMode.RISK_BASED
        )

    def _risk_based_scope_legacy_block(self):
        warnings_list = []
        # Extract coverage data from snapshot
        traceability = snapshot_data.get("acTraceability", [])

        # Load PatternMemoryV2 records for outcome learning override
        pattern_memory_set = RegressionScopeV2Service._get_pattern_memory_keys(db, run.repository_id)
        pattern_memories = RegressionScopeV2Service._get_pattern_memory_records(db, run.repository_id)

        # Load PullRequestChangedFile records for mutation check
        changed_file_paths = RegressionScopeV2Service._get_pr_changed_files(db, pr.id)
        
        # Build scope items with risk scoring
        required_items = []
        recommended_items = []
        optional_items = []
        safe_to_skip_items = []
        already_verified_items = []
        already_passed_test_items = []
        review_needed_items = []

        for trace in traceability:
            coverage_status = trace.get("coverageStatus", "MISSING")
            linked_tests = trace.get("linkedExistingTests", []) or []

            # Find real AC
            ac = next((row for row in ac_rows if str(row.id) == trace.get("requirementId")), None)

            # Create scope item
            item = RegressionScopeV2Service._create_scope_item_from_trace(
                trace, audit, db=db, repository_id=run.repository_id, ac=ac
            )

            # Resolve the files covered by the requirement's linked tests
            from app.models.test_result import TestCase
            test_case_ids = []
            if linked_tests and db:
                test_cases = db.query(TestCase).filter(
                    TestCase.repository_id == run.repository_id,
                    TestCase.stable_identity.in_(linked_tests)
                ).all()
                test_case_ids = [tc.id for tc in test_cases]

            # Get execution status, freshness, and mapping status
            execution_status, freshness_status, mapping_status, latest_result_created_at, freshness_reason = \
                RegressionScopeV2Service._get_test_execution_status(
                    db, run.repository_id, linked_tests, pr.head_commit_sha
                )
            item.execution_status = execution_status
            item.freshness_status = freshness_status
            item.mapping_status = mapping_status

            covered_files = RegressionScopeV2Service._resolve_covered_files_for_requirement(db, run.repository_id, linked_tests)

            # Determine baseline risk parameters using fallback keywords & specific high-risk rules
            title_desc = (item.title or "").lower() + " " + (trace.get("fullText") or "").lower()
            business_risk = "MEDIUM"
            criticality = "MEDIUM"
            requirement_type = "FUNCTIONAL"
            
            # Fallback keywords
            keywords = ['password', 'auth', 'login', 'token', 'security', 'credential', 'session', 'permission', 'access']
            if any(kw in title_desc for kw in keywords):
                business_risk = "HIGH"
                criticality = "HIGH"
                requirement_type = "SECURITY"
                
            # Specific high-risk rules
            if "bypass" in title_desc or ("backend" in title_desc and "api" in title_desc and "validation" in title_desc):
                business_risk = "CRITICAL"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "token" in title_desc and ("reuse" in title_desc or "expired" in title_desc or "reused" in title_desc or "reset" in title_desc):
                business_risk = "CRITICAL"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "password" in title_desc and "not updated" in title_desc:
                business_risk = "HIGH"
                criticality = "CRITICAL"
                requirement_type = "SECURITY"
            elif "login" in title_desc or "log in" in title_desc:
                if "password update" in title_desc or "password change" in title_desc or "password is updated" in title_desc or "updated" in title_desc:
                    business_risk = "HIGH"
                    criticality = "HIGH"
                    requirement_type = "SECURITY"
            elif ("ui" in title_desc and "api" in title_desc) or "consistent" in title_desc or "consistency" in title_desc:
                business_risk = "HIGH"
                criticality = "HIGH"
                requirement_type = "SECURITY"
            elif "error message" in title_desc or "validation error" in title_desc:
                business_risk = "MEDIUM"
                criticality = "HIGH"
                requirement_type = "SECURITY"
                
            # Calculate risk score
            risk_result = RiskScoringService.calculate_requirement_risk_score(
                business_risk=business_risk,
                coverage_status=coverage_status or "VERIFIED",
                criticality=criticality,
                requirement_type=requirement_type
            )
            item.risk_score = risk_result["riskScore"]
            item.risk_band = RiskBand(risk_result["riskBand"])
            item.business_risk_level = BusinessRiskLevel(business_risk)
            item.effective_risk_level = item.business_risk_level

            # Apply manual risk adjustment if any
            item = RegressionScopeV2Service._apply_manual_risk_adjustment(
                item, snapshot_data, db
            )

            # Signal 2 — Outcome Learning Override
            matched_pattern = RegressionScopeV2Service._matches_pattern_memory(
                pattern_memory_set,
                ac.normalized_key if ac else None,
                ac.text if ac else None,
                linked_tests
            )

            if matched_pattern:
                item.group = ScopeGroup.REQUIRED
                item.is_required_for_release = True
                item.release_action = ReleaseAction.RE_RUN
                
                signal = next(
                    (p for p in pattern_memories if p.pattern_key == matched_pattern),
                    None
                )
                signal_type = signal.signal_type if signal else "incident"
                item.reason = f"Outcome learning: a prior {signal_type} was recorded for this scenario. Required regardless of current coverage."
                item.suggested_action = "Review — flagged by outcome learning"
                required_items.append(item)
                continue

            # Bucketing logic decision matrix
            mutation_overlap = bool(covered_files & changed_file_paths)
            
            if execution_status == "PASSED":
                if freshness_status == "FRESH":
                    scope_group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                    release_action = ReleaseAction.NONE
                    suggested_action = "No action required"
                    reason = "Test was re-run and passed on current commit."
                elif freshness_status == "STALE":
                    if mutation_overlap:
                        scope_group = ScopeGroup.REQUIRED
                        release_action = ReleaseAction.RE_RUN
                        suggested_action = "Re-run stale test"
                        affected_files = covered_files & changed_file_paths
                        file_list = ", ".join(sorted(affected_files)[:2])
                        reason = f"{file_list} was modified in this PR. Test passed but is stale."
                    else:
                        scope_group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                        release_action = ReleaseAction.NONE
                        suggested_action = "No action required"
                        reason = "Test passed and is not impacted by PR changes."
                else:  # UNKNOWN freshness
                    if mutation_overlap:
                        scope_group = ScopeGroup.REQUIRED
                        release_action = ReleaseAction.RE_RUN
                        suggested_action = "Re-run test to verify freshness"
                        reason = "Test passed but freshness is unknown and covers modified files."
                    else:
                        scope_group = ScopeGroup.REVIEW_NEEDED
                        release_action = ReleaseAction.REVIEW_EVIDENCE
                        suggested_action = "Review evidence"
                        reason = f"Test passed but commit evidence is missing/unknown ({freshness_reason}). Verify freshness."
            elif execution_status == "FAILED":
                scope_group = ScopeGroup.REQUIRED
                release_action = ReleaseAction.FIX_OR_RERUN
                suggested_action = "Fix failing test and re-run"
                reason = "Test is currently failing. Fix required."
            else:  # NOT_RUN or missing
                if mutation_overlap:
                    scope_group = ScopeGroup.REQUIRED
                    release_action = ReleaseAction.RUN_OR_CREATE_TEST
                    suggested_action = "Execute before release"
                    affected_files = covered_files & changed_file_paths
                    file_list = ", ".join(sorted(affected_files)[:2])
                    reason = f"{file_list} was modified in this PR. No test evidence exists."
                else:
                    scope_group = ScopeGroup.RECOMMENDED
                    release_action = ReleaseAction.RUN_OR_CREATE_TEST
                    suggested_action = "Run or create test"
                    reason = "No passing test evidence exists."
                    
            item.group = scope_group
            item.release_action = release_action
            item.suggested_action = suggested_action
            item.reason = reason
            item.is_required_for_release = (scope_group == ScopeGroup.REQUIRED)
            
            # Bucketing lists
            if scope_group == ScopeGroup.REQUIRED:
                required_items.append(item)
            elif scope_group == ScopeGroup.REVIEW_NEEDED:
                review_needed_items.append(item)
            elif scope_group == ScopeGroup.RECOMMENDED:
                recommended_items.append(item)
            elif scope_group == ScopeGroup.OPTIONAL:
                optional_items.append(item)
            elif scope_group == ScopeGroup.EXCLUDED_ALREADY_VERIFIED:
                already_verified_items.append(item)
            elif scope_group == ScopeGroup.SAFE_TO_SKIP:
                safe_to_skip_items.append(item)

        # Count Integrity & Deduplication (Part 6)
        all_buckets = {
            ScopeGroup.REQUIRED: required_items,
            ScopeGroup.REVIEW_NEEDED: review_needed_items,
            ScopeGroup.RECOMMENDED: recommended_items,
            ScopeGroup.OPTIONAL: optional_items,
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED: already_verified_items,
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS: already_passed_test_items,
            ScopeGroup.SAFE_TO_SKIP: safe_to_skip_items,
        }
        
        priority_order = [
            ScopeGroup.REQUIRED,
            ScopeGroup.REVIEW_NEEDED,
            ScopeGroup.RECOMMENDED,
            ScopeGroup.OPTIONAL,
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
            ScopeGroup.SAFE_TO_SKIP,
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS
        ]
        priority_map = {g: idx for idx, g in enumerate(priority_order)}
        
        def get_stable_identity_key(x: ScopeItem) -> str:
            if x.id:
                return f"id:{x.id}"
            if x.source_ac_number is not None:
                return f"seq:{x.source_ac_number}"
            if x.readable_id:
                return f"rid:{x.readable_id}"
            return f"title:{x.title}"
            
        by_identity = {}
        for group, item_list in all_buckets.items():
            for x in item_list:
                x.group = group
                key = get_stable_identity_key(x)
                if key not in by_identity:
                    by_identity[key] = []
                by_identity[key].append(x)
                
        deduped = {g: [] for g in all_buckets.keys()}
        for key, items_list in by_identity.items():
            if len(items_list) > 1:
                if include_diagnostics:
                    warnings_list.append(f"Duplicate stable identity key detected: {key}")
                    
                items_list.sort(key=lambda x: priority_map.get(x.group, 99))
                best_item = items_list[0]
                
                has_passed_fresh = any(
                    x.execution_status == "PASSED" and x.freshness_status == "FRESH"
                    for x in items_list
                )
                if has_passed_fresh and best_item.group == ScopeGroup.REQUIRED:
                    best_item.group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                    best_item.release_action = ReleaseAction.NONE
                    best_item.is_required_for_release = False
                    
                deduped[best_item.group].append(best_item)
            else:
                x = items_list[0]
                deduped[x.group].append(x)
                
        required_items = deduped[ScopeGroup.REQUIRED]
        review_needed_items = deduped[ScopeGroup.REVIEW_NEEDED]
        recommended_items = deduped[ScopeGroup.RECOMMENDED]
        optional_items = deduped[ScopeGroup.OPTIONAL]
        already_verified_items = deduped[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]
        already_passed_test_items = deduped[ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS]
        safe_to_skip_items = deduped[ScopeGroup.SAFE_TO_SKIP]

        # Capture automated-only counts before merging manual items
        automated_required_count = len(required_items)
        automated_recommended_count = len(recommended_items)
        automated_executable_count = len(required_items) + len(recommended_items) + len(optional_items)

        # Merge MANUAL_TEST scope items
        manual_buckets = RegressionScopeV2Service._generate_manual_scope_items(snapshot_data, audit, db)
        required_items.extend(manual_buckets.get(ScopeGroup.REQUIRED, []))
        recommended_items.extend(manual_buckets.get(ScopeGroup.RECOMMENDED, []))
        optional_items.extend(manual_buckets.get(ScopeGroup.OPTIONAL, []))
        safe_to_skip_items.extend(manual_buckets.get(ScopeGroup.SAFE_TO_SKIP, []))
        manual_counts = {g: len(manual_buckets.get(g, [])) for g in priority_order}

        # Compute confidence score metrics
        all_items = required_items + recommended_items + optional_items + safe_to_skip_items + already_verified_items + review_needed_items
        total_count = len(all_items)
        
        stale_count = sum(1 for item in all_items if item.freshness_status == "STALE")
        missing_count = sum(1 for item in all_items if item.execution_status == "NOT_RUN")
        failed_count = sum(1 for item in all_items if item.execution_status == "FAILED")
        
        mutation_fired_count = sum(1 for item in all_items if item.reason and "was modified in this PR" in item.reason and item.group == ScopeGroup.REQUIRED)
        mutation_verified_count = sum(1 for item in all_items if item.reason and "was modified in this PR" in item.reason and item.execution_status == "PASSED" and item.freshness_status == "FRESH")
        
        has_outcome_signals = len(pattern_memory_set) > 0
        
        coverage_pct = None
        if "counts" in snapshot_data:
            total_reqs = snapshot_data["counts"].get("totalRequirements", 0)
            verified = snapshot_data["counts"].get("verifiedTests", 0)
            if total_reqs > 0:
                coverage_pct = (verified / total_reqs) * 100
        
        confidence_score, confidence_label = RegressionScopeV2Service._compute_confidence_score(
            required_count=len(required_items),
            already_verified_count=len(already_verified_items),
            stale_count=stale_count,
            missing_count=missing_count,
            failed_count=failed_count,
            mutation_fired_count=mutation_fired_count,
            mutation_verified_count=mutation_verified_count,
            total_count=total_count,
            has_outcome_signals=has_outcome_signals,
            coverage_pct=coverage_pct
        )

        # Build groups
        groups = {
            ScopeGroup.REQUIRED.value: ScopeGroupSummary(
                group=ScopeGroup.REQUIRED,
                count=len(required_items),
                items=required_items
            ),
            ScopeGroup.RECOMMENDED.value: ScopeGroupSummary(
                group=ScopeGroup.RECOMMENDED,
                count=len(recommended_items),
                items=recommended_items
            ),
            ScopeGroup.OPTIONAL.value: ScopeGroupSummary(
                group=ScopeGroup.OPTIONAL,
                count=len(optional_items),
                items=optional_items
            ),
            ScopeGroup.SAFE_TO_SKIP.value: ScopeGroupSummary(
                group=ScopeGroup.SAFE_TO_SKIP,
                count=len(safe_to_skip_items),
                items=safe_to_skip_items if include_safe_to_skip else []
            ),
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED.value: ScopeGroupSummary(
                group=ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
                count=len(already_verified_items),
                items=already_verified_items
            ),
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS.value: ScopeGroupSummary(
                group=ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS,
                count=len(already_passed_test_items),
                items=already_passed_test_items
            ),
            ScopeGroup.REVIEW_NEEDED.value: ScopeGroupSummary(
                group=ScopeGroup.REVIEW_NEEDED,
                count=len(review_needed_items),
                items=review_needed_items
            )
        }

        # Build execution plan
        total_executable = len(required_items) + len(recommended_items) + len(optional_items)
        current_tests = snapshot_data.get("counts", {}).get("uploadedPrTestsPassed", 0)
        execution_reduction = ((current_tests - total_executable) / current_tests * 100) if current_tests > 0 else 0.0
        manual_estimated_minutes = (
            manual_counts.get(ScopeGroup.REQUIRED, 0)
            + manual_counts.get(ScopeGroup.RECOMMENDED, 0)
            + manual_counts.get(ScopeGroup.OPTIONAL, 0)
        ) * RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES
        
        execution_plan = ExecutionPlan(
            required_count=len(required_items),
            recommended_count=len(recommended_items),
            optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            review_needed_count=len(review_needed_items),
            total_executable_count=total_executable,
            estimated_execution_reduction=round(execution_reduction, 2),
            confidence_level=float(confidence_score),
            plan_summary=f"Risk-based scope with {len(required_items)} required, {len(recommended_items)} recommended, {len(optional_items)} optional - {confidence_label}",
            advisory_notice="Risk-based mode prioritizes high-risk missing and partial coverage items",
            manual_required_count=manual_counts.get(ScopeGroup.REQUIRED, 0),
            manual_recommended_count=manual_counts.get(ScopeGroup.RECOMMENDED, 0),
            manual_optional_count=manual_counts.get(ScopeGroup.OPTIONAL, 0),
            manual_safe_to_skip_count=manual_counts.get(ScopeGroup.SAFE_TO_SKIP, 0),
            automated_required_count=automated_required_count,
            automated_recommended_count=automated_recommended_count,
            manual_estimated_minutes=manual_estimated_minutes,
            automated_estimated_minutes=0
        )

        exclusions = ScopeExclusions(
            already_verified_count=len(already_verified_items),
            already_passed_tests_count=len(already_passed_test_items),
            already_verified_items=already_verified_items,
            already_passed_test_items=already_passed_test_items
        )

        optimization_metrics = ScopeOptimizationMetrics(
            current_regression_size=total_count,
            optimized_required_count=len(required_items),
            optimized_recommended_count=len(recommended_items),
            optimized_optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            optimization_percentage=round(execution_reduction, 2),
            execution_reduction=round(execution_reduction, 2),
            coverage_confidence=round((len(required_items) / total_executable * 100) if total_executable > 0 else 0, 2)
        )

        governance = ScopeGovernance(
            risk_reviews_count=0,
            overridden_count=0,
            needs_discussion_count=0,
            release_decision_required=False,
            release_decision_status=None
        )

        diagnostics = ScopeDiagnostics(
            generation_timestamp=datetime.utcnow(),
            generation_duration_ms=None,
            rules_applied=[
                "RISK_BASED_PRIORITIZATION",
                "HIGH_RISK_MISSING_REQUIRED",
                "HIGH_RISK_PARTIAL_RECOMMENDED",
                "LOW_RISK_VERIFIED_SAFE_TO_SKIP"
            ],
            warnings=warnings_list,
            errors=[]
        )

        return RegressionScopeV2(
            recommendation_run_id=str(run.id),
            snapshot_hash=run.evidence_fingerprint or str(run.id),
            generated_at=datetime.utcnow(),
            scope_type="RISK_BASED",
            source=ScopeSource.RISK_BASED,
            summary=f"Risk-based scope with {len(required_items)} required, {len(recommended_items)} recommended, {len(optional_items)} optional",
            execution_plan=execution_plan,
            groups=groups,
            exclusions=exclusions,
            optimization_metrics=optimization_metrics,
            governance=governance,
            diagnostics=diagnostics
        )

    @staticmethod
    def _generate_full_scope(
        run: RecommendationRun,
        pr: PullRequest,
        ac_rows: List[AcceptanceCriterion],
        snapshot_data: Dict[str, Any],
        include_safe_to_skip: bool,
        audit: bool,
        db: Session = None,
        include_diagnostics: bool = False
    ) -> RegressionScopeV2:
        return RegressionScopeV2Service._generate_unified_scope_v2(
            db, run, pr, ac_rows, snapshot_data, include_safe_to_skip, audit, include_diagnostics, ScopeMode.FULL_SUITE
        )

    @staticmethod
    def _create_scope_item_from_trace(
        trace: Dict[str, Any],
        audit: bool,
        db: Session = None,
        repository_id: Any = None,
        ac: Optional[AcceptanceCriterion] = None
    ) -> ScopeItem:
        """Create a scope item from a trace record, using database records for truth if available."""
        coverage_status = trace.get("coverageStatus", "MISSING")
        
        # Map coverage status to evidence classification
        coverage_map = {
            "Covered": EvidenceClassification.COVERED,
            "Partially covered": EvidenceClassification.PARTIAL,
            "Missing": EvidenceClassification.MISSING,
            "Partially Covered": EvidenceClassification.PARTIAL,
            "Coverage Gap": EvidenceClassification.PARTIAL
        }
        
        # Load from DB if not provided but db session and repository_id are present
        if not ac and db and repository_id:
            requirement_id = trace.get("requirementId")
            if requirement_id:
                try:
                    ac = db.query(AcceptanceCriterion).filter(
                        AcceptanceCriterion.id == requirement_id,
                        AcceptanceCriterion.repository_id == repository_id
                    ).first()
                except Exception:
                    pass

        # Use database record details if available to prevent generic placeholders
        title = ac.text if ac else trace.get("title", "")
        readable_id = ac.normalized_key if ac else trace.get("readableId", "")
        if ac and ac.source_number is not None:
            source_ac_number = ac.source_number
        else:
            source_ac_number = trace.get("sourceAcNumber")

        return ScopeItem(
            id=trace.get("requirementId", ""),
            readable_id=readable_id,
            source_ac_number=source_ac_number,
            title=title,
            item_type=ScopeItemType.REQUIREMENT,
            group=ScopeGroup.REQUIRED,  # Will be overridden by categorization logic
            evidence_classification=coverage_map.get(coverage_status, EvidenceClassification.MISSING),
            risk_score=0.0,  # Will be set by risk scoring
            risk_band=RiskBand.LOW,  # Will be set by risk scoring
            change_impact_level=ChangeImpactLevel.NONE,
            business_risk_level=BusinessRiskLevel.UNKNOWN,
            effective_risk_level=BusinessRiskLevel.UNKNOWN,
            suggested_action="Run test" if coverage_status == "MISSING" else "Review",
            reason="",
            evidence_references=trace.get("evidenceReferences", []),
            test_references=trace.get("testReferences", []),
            can_auto_execute=coverage_status != "MISSING",
            execution_status=None,
            estimated_effort=None,
            is_required_for_release=False,  # Will be set by categorization logic
            is_manual_only=False,
            diagnostics=ScopeItemDiagnostics(
                internal_requirement_id=trace.get("requirementId") if audit else None,
                internal_test_id=None,
                generation_rule=None,
                confidence_score=None,
                last_updated=None
            ) if audit else None
        )

    # ------------------------------------------------------------------
    # Phase 6.4: Manual evidence risk adjustment
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_manual_risk_adjustment(
        item: ScopeItem,
        snapshot_data: Dict[str, Any],
        db: Session = None
    ) -> ScopeItem:
        """Apply manual evidence risk adjustment to a scope item.

        This adjusts the risk band based on manual evidence while preserving
        automated evidence truth. Manual evidence becomes a risk signal, not
        a coverage signal.

        Phase 6.5: Risk adjustment is gated by governance status. Only APPROVED
        manual evidence may adjust residual risk.

        Args:
            item: The scope item to adjust
            snapshot_data: The evidence snapshot data
            db: Database session for governance status lookup (optional)

        Returns:
            The adjusted scope item with risk adjustment fields populated
        """
        # Store the generated risk band before adjustment
        generated_risk_band = item.risk_band

        # Get manual support status from snapshot
        manual_support_status = None
        manual_nodes = snapshot_data.get("manualEvidenceNodes", []) or []
        manual_execution_id = None
        repository_id = snapshot_data.get("repositoryId")

        # For REQUIREMENT items, find manual evidence for this AC
        if item.item_type == ScopeItemType.REQUIREMENT and item.source_ac_number is not None:
            for node in manual_nodes:
                if node.get("sourceAcNumber") == item.source_ac_number:
                    outcome = node.get("outcome") or "NOT_EXECUTED"
                    manual_support_status = outcome.upper()
                    manual_execution_id = node.get("manualTestId")
                    break

        # For MANUAL_TEST items, use the execution status
        elif item.item_type == ScopeItemType.MANUAL_TEST:
            manual_support_status = item.execution_status or "NOT_EXECUTED"
            manual_execution_id = item.external_id

        # Phase 6.5: Get governance status if database session is available
        governance_status = None
        if db and manual_execution_id and repository_id:
            try:
                from app.services.manual_evidence_governance_service import ManualEvidenceGovernanceService
                governance_service = ManualEvidenceGovernanceService(db)
                governance_info = governance_service.get_governance_status(
                    execution_id=str(manual_execution_id),
                    repository_id=str(repository_id)
                )
                governance_status = governance_info.get("governanceStatus")
            except Exception:
                # If governance lookup fails, treat as pending
                governance_status = "PENDING_REVIEW"
        else:
            # Phase 6.5: Check if governance status is already in snapshot node
            if item.item_type == ScopeItemType.REQUIREMENT and item.source_ac_number is not None:
                for node in manual_nodes:
                    if node.get("sourceAcNumber") == item.source_ac_number:
                        governance_status = node.get("governanceStatus")
                        break

        # Apply risk adjustment if manual support status is available
        if manual_support_status:
            adjustment_result = ManualEvidenceRiskAdjustmentService.adjust_risk(
                generated_risk_band=generated_risk_band,
                manual_support_status=manual_support_status,
                governance_status=governance_status
            )

            # Populate risk adjustment fields
            item.generated_risk_band = generated_risk_band.value
            item.manual_contribution_status = manual_support_status
            item.residual_risk_band = adjustment_result["residual_risk_band"]
            item.risk_adjustment_reason = adjustment_result["adjustment_reason"]
            item.risk_adjustment_delta = adjustment_result["adjustment_delta"]

            # Update the risk band to the residual risk band
            item.risk_band = RiskBand(adjustment_result["residual_risk_band"])

        return item

    # ------------------------------------------------------------------
    # Phase 6.3: Manual test scope items
    # ------------------------------------------------------------------

    # Coverage status (display form from snapshot) -> evidence classification
    _COVERAGE_TO_EVIDENCE = {
        "Missing": EvidenceClassification.MISSING,
        "Partially Covered": EvidenceClassification.PARTIAL,
        "Covered": EvidenceClassification.COVERED,
        "Coverage Gap": EvidenceClassification.PARTIAL,
        "Failed": EvidenceClassification.MISSING,
        "Skipped": EvidenceClassification.MISSING,
        "Not Run": EvidenceClassification.MISSING,
    }

    # Coverage status -> (business_risk, coverage_status_for_scoring)
    _COVERAGE_TO_RISK_INPUT = {
        "Missing": ("HIGH", "MISSING"),
        "Partially Covered": ("MEDIUM", "PARTIAL"),
        "Covered": ("LOW", "VERIFIED"),
        "Coverage Gap": ("MEDIUM", "PARTIAL"),
        "Failed": ("HIGH", "FAILED"),
        "Skipped": ("MEDIUM", "SKIPPED"),
        "Not Run": ("MEDIUM", "NOT_RUN"),
    }

    @staticmethod
    def _classify_manual_group(
        coverage_status: str,
        risk_band: RiskBand,
        outcome: str
    ) -> ScopeGroup:
        """Determine which scope group a manual test belongs to (Phase 6.3 rules)."""
        missing = coverage_status in ("Missing", "Failed", "Skipped", "Not Run")
        partial = coverage_status in ("Partially Covered", "Coverage Gap")
        covered = coverage_status == "Covered"
        high_risk = risk_band in (RiskBand.CRITICAL, RiskBand.HIGH)

        # REQUIRED: failed/blocked manual validation needs re-execution
        if outcome in ("FAILED", "BLOCKED"):
            return ScopeGroup.REQUIRED
        # REQUIRED: missing automated coverage + critical/high risk
        if missing and high_risk:
            return ScopeGroup.REQUIRED
        # REQUIRED: missing automated coverage, manual is the only validation path
        if missing:
            return ScopeGroup.REQUIRED
        # RECOMMENDED: partial coverage
        if partial:
            return ScopeGroup.RECOMMENDED
        # RECOMMENDED: medium risk
        if risk_band == RiskBand.MEDIUM:
            return ScopeGroup.RECOMMENDED
        # Covered by automated tests
        if covered:
            # SAFE_TO_SKIP: verified by current PR automation and low risk
            if risk_band == RiskBand.LOW:
                return ScopeGroup.SAFE_TO_SKIP
            # OPTIONAL: covered but manual acts as a safety net
            return ScopeGroup.OPTIONAL
        # Fallback: low-risk safety net
        return ScopeGroup.OPTIONAL

    @staticmethod
    def _build_manual_scope_item(
        node: Dict[str, Any],
        trace: Optional[Dict[str, Any]],
        group: ScopeGroup,
        risk_score: float,
        risk_band: RiskBand,
        evidence_classification: EvidenceClassification,
        change_impact: ChangeImpactLevel,
        business_risk: BusinessRiskLevel,
        outcome: str,
        audit: bool
    ) -> ScopeItem:
        """Build a MANUAL_TEST scope item (execution recommendation only)."""
        source_ac_number = node.get("sourceAcNumber")
        provider = node.get("provider")
        external_key = node.get("externalKey")
        readable_id = node.get("readableId") or (
            f"MT-{external_key}" if external_key else (f"MT-{source_ac_number}" if source_ac_number is not None else "MT")
        )
        title = node.get("manualTestTitle", "Manual Test")

        coverage_status = trace.get("coverageStatus", "Missing") if trace else "Missing"
        coverage_status_normalized = coverage_status.title() if coverage_status else "Missing"

        # Suggested action / reason by group
        if group == ScopeGroup.REQUIRED:
            suggested_action = "Execute manual test before release"
        elif group == ScopeGroup.RECOMMENDED:
            suggested_action = "Run manual test to validate impacted requirement"
        elif group == ScopeGroup.OPTIONAL:
            suggested_action = "Optionally run manual test as a safety net"
        else:
            suggested_action = "Manual test can be safely skipped"

        ac_label = f"AC-{source_ac_number}" if source_ac_number is not None else "the mapped requirement"
        if outcome in ("FAILED", "BLOCKED"):
            reason = (
                f"Mapped to {ac_label}; latest manual execution was {outcome} and re-execution is recommended."
            )
        elif coverage_status_normalized in ("Missing", "Failed", "Skipped", "Not Run"):
            reason = (
                f"Mapped to {ac_label}, which is missing automated coverage and has {risk_band.value.lower()} risk."
            )
        elif coverage_status_normalized in ("Partially Covered", "Coverage Gap"):
            reason = f"Mapped to {ac_label}, which is partially covered and benefits from manual validation."
        elif group == ScopeGroup.SAFE_TO_SKIP:
            reason = (
                f"Mapped to {ac_label}, which is verified by current PR automated tests; manual rerun not required."
            )
        else:
            reason = f"Mapped to {ac_label}; manual test provides additional safety coverage."

        # Test reference string keeps provider/external id visible without exposing internal UUID
        ref_provider = provider or "MANUAL"
        ref_external = external_key or readable_id
        test_reference = f"{readable_id} ({ref_provider}:{ref_external})"

        return ScopeItem(
            id=node.get("manualTestId", ""),
            readable_id=readable_id,
            source_ac_number=source_ac_number,
            title=title,
            item_type=ScopeItemType.MANUAL_TEST,
            group=group,
            evidence_classification=evidence_classification,
            risk_score=float(risk_score),
            risk_band=risk_band,
            change_impact_level=change_impact,
            business_risk_level=business_risk,
            effective_risk_level=business_risk,
            suggested_action=suggested_action,
            reason=reason,
            evidence_references=[],
            test_references=[test_reference],
            can_auto_execute=False,
            execution_status=outcome or "NOT_EXECUTED",
            estimated_effort=f"{RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES} min (manual_test_default)",
            estimated_effort_minutes=RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES,
            is_required_for_release=(group == ScopeGroup.REQUIRED),
            is_manual_only=True,
            provider=provider,
            external_id=external_key or readable_id,
            diagnostics=ScopeItemDiagnostics(
                internal_requirement_id=node.get("acceptanceCriterionId") if audit else None,
                internal_test_id=node.get("manualTestId") if audit else None,
                generation_rule="MANUAL_TEST_SCOPE_RECOMMENDATION" if audit else None,
                confidence_score=None,
                last_updated=None
            ) if audit else None
        )

    @staticmethod
    def _generate_manual_scope_items(
        snapshot_data: Dict[str, Any],
        audit: bool,
        db: Session = None
    ) -> Dict[ScopeGroup, List[ScopeItem]]:
        """Generate MANUAL_TEST scope items from the evidence snapshot.

        Manual tests are execution recommendations only. They never change
        automated coverage, evidence counts, readiness, or release decisions.
        """
        buckets: Dict[ScopeGroup, List[ScopeItem]] = {
            ScopeGroup.REQUIRED: [],
            ScopeGroup.RECOMMENDED: [],
            ScopeGroup.OPTIONAL: [],
            ScopeGroup.SAFE_TO_SKIP: [],
        }

        manual_nodes = snapshot_data.get("manualEvidenceNodes", []) or []
        if not manual_nodes:
            return buckets

        # Index AC traceability by acceptance criterion id (== requirementId)
        traceability = snapshot_data.get("acTraceability", []) or []
        trace_by_ac_id = {str(t.get("requirementId")): t for t in traceability}

        seen_keys = set()  # dedup: (manualTestId, sourceAcNumber, group)

        for node in manual_nodes:
            ac_id = str(node.get("acceptanceCriterionId"))
            trace = trace_by_ac_id.get(ac_id)
            coverage_status = trace.get("coverageStatus", "Missing") if trace else "Missing"
            coverage_status_normalized = coverage_status.title() if coverage_status else "Missing"

            business_risk_str, coverage_for_scoring = RegressionScopeV2Service._COVERAGE_TO_RISK_INPUT.get(
                coverage_status_normalized, ("MEDIUM", "MISSING")
            )

            risk_result = RiskScoringService.calculate_requirement_risk_score(
                business_risk=business_risk_str,
                coverage_status=coverage_for_scoring,
                criticality="HIGH",
                requirement_type="FUNCTIONAL"
            )
            risk_band = RiskBand(risk_result["riskBand"])
            risk_score = risk_result["riskScore"]

            outcome = (node.get("outcome") or "NOT_EXECUTED").upper()

            group = RegressionScopeV2Service._classify_manual_group(
                coverage_status_normalized, risk_band, outcome
            )

            # Deduplicate by external test case + AC + group
            dedup_key = (node.get("manualTestId"), node.get("sourceAcNumber"), group.value)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            evidence_classification = RegressionScopeV2Service._COVERAGE_TO_EVIDENCE.get(
                coverage_status_normalized, EvidenceClassification.MISSING
            )

            # Change impact heuristic derived from coverage/risk (no mutation of evidence)
            if coverage_status_normalized in ("Missing", "Failed", "Skipped", "Not Run") and risk_band in (RiskBand.CRITICAL, RiskBand.HIGH):
                change_impact = ChangeImpactLevel.DIRECT
            elif coverage_status_normalized in ("Partially Covered", "Coverage Gap"):
                change_impact = ChangeImpactLevel.RELATED
            elif coverage_status_normalized == "Covered":
                change_impact = ChangeImpactLevel.NONE
            else:
                change_impact = ChangeImpactLevel.RELATED

            business_risk_level = {
                "CRITICAL": BusinessRiskLevel.CRITICAL,
                "HIGH": BusinessRiskLevel.HIGH,
                "MEDIUM": BusinessRiskLevel.MEDIUM,
                "LOW": BusinessRiskLevel.LOW,
            }.get(business_risk_str, BusinessRiskLevel.UNKNOWN)

            item = RegressionScopeV2Service._build_manual_scope_item(
                node=node,
                trace=trace,
                group=group,
                risk_score=risk_score,
                risk_band=risk_band,
                evidence_classification=evidence_classification,
                change_impact=change_impact,
                business_risk=business_risk_level,
                outcome=outcome,
                audit=audit
            )

            # Phase 6.4: Apply manual evidence risk adjustment to manual test items
            item = RegressionScopeV2Service._apply_manual_risk_adjustment(
                item, snapshot_data, db
            )

            buckets[group].append(item)

        return buckets

    @staticmethod
    def _compute_confidence_score(
        required_count: int,
        already_verified_count: int,
        stale_count: int,
        missing_count: int,
        failed_count: int,
        mutation_fired_count: int,
        mutation_verified_count: int,
        total_count: int,
        has_outcome_signals: bool,
        coverage_pct: Optional[float]
    ) -> tuple[int, str]:
        """
        Compute evidence confidence score 0-100
        and a label explaining it.
        Returns (score, label)
        """
        if total_count == 0:
            return 0, "No evidence available"

        score = 100.0

        # Deductions
        if missing_count > 0:
            deduction = min(40, (missing_count / total_count) * 40)
            score -= deduction

        if stale_count > 0:
            deduction = min(20, (stale_count / total_count) * 20)
            score -= deduction

        if failed_count > 0:
            score -= min(30, failed_count * 10)

        if mutation_fired_count > 0:
            unverified = mutation_fired_count - mutation_verified_count
            if unverified > 0:
                deduction = min(25, 
                    (unverified / total_count) * 25
                )
                score -= deduction

        if has_outcome_signals:
            score -= 5

        # Bonuses
        if required_count == 0 and already_verified_count > 0:
            score = min(100, score + 10)

        if coverage_pct and coverage_pct > 90:
            score = min(100, score + 5)

        score = max(0, min(100, int(score)))

        if score >= 90:
            label = "Very High — strong evidence chain"
        elif score >= 75:
            label = "High — good evidence with minor gaps"
        elif score >= 50:
            label = "Medium — notable gaps, proceed with caution"
        elif score >= 25:
            label = "Low — significant evidence missing"
        else:
            label = "Very Low — insufficient for release"

        return score, label

    @staticmethod
    def _resolve_test_cases_for_ac(
        db: Session,
        repository_id: Any,
        linked_tests: List[str]
    ) -> List:
        """
        Resolve TestCase records from linked_tests values,
        which may be stable identities, AC identifiers, 
        or UUIDs.
        """
        from app.models.test_result import TestCase
        from app.models.coverage import FileTestLink
        from sqlalchemy import or_

        if not linked_tests:
            return []

        test_cases_dict = {}

        # Paths 1, 4, 5: Exact matches on stable_identity, test_name
        exact_matches = db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            or_(
                TestCase.stable_identity.in_(linked_tests),
                TestCase.test_name.in_(linked_tests)
            )
        ).all()

        for tc in exact_matches:
            test_cases_dict[tc.id] = tc

        # PATH 2: FileTestLink DIRECT_AC_ID match
        ac_links = db.query(FileTestLink).filter(
            FileTestLink.file_path.in_(linked_tests),
            FileTestLink.mapping_type == "DIRECT_AC_ID"
        ).all()

        if ac_links:
            tc_ids = [link.test_case_id for link in ac_links]
            ac_matches = db.query(TestCase).filter(
                TestCase.id.in_(tc_ids),
                TestCase.repository_id == repository_id
            ).all()
            for tc in ac_matches:
                test_cases_dict[tc.id] = tc

        # PATH 6: Class::Name or suffix match
        # JUnit often uses "ClassName::test_name". If linked_tests has "test_name", it might match the end.
        for identity in linked_tests:
            suffix_matches = db.query(TestCase).filter(
                TestCase.repository_id == repository_id,
                TestCase.stable_identity.endswith(f"::{identity}")
            ).all()
            for tc in suffix_matches:
                test_cases_dict[tc.id] = tc

        # PATH 3: Partial keyword match / normalization match (only if no exact matches found yet)
        if not test_cases_dict:
            for identity in linked_tests:
                from app.services.ac_identity_resolver import normalize_ac_text, normalize_test_name, get_semantic_overlap_score
                norm_ident = normalize_ac_text(identity)
                keyword = identity.replace("AC-", "").strip()
                
                # Fetch all test cases for this repo and filter in Python using normalization and semantic overlap
                all_tcs = db.query(TestCase).filter(TestCase.repository_id == repository_id).all()
                for tc in all_tcs:
                    tc_name_norm = normalize_test_name(tc.test_name)
                    # Exact match after normalization or high semantic overlap
                    if norm_ident and (tc_name_norm == norm_ident or get_semantic_overlap_score(norm_ident, tc_name_norm) >= 0.5):
                        test_cases_dict[tc.id] = tc
                    # Also fallback to partial keyword matching
                    elif len(keyword) > 3 and keyword.lower() in tc.test_name.lower():
                        test_cases_dict[tc.id] = tc

        result = list(test_cases_dict.values())
        if result:
            logger.debug(f"[ExecStatus] Resolved {len(result)} test cases for {linked_tests[:3]}")
        else:
            logger.debug(f"[ExecStatus] All paths exhausted. No test cases found for: {linked_tests[:5]}")

        return result

    @staticmethod
    def _get_pr_changed_files(db: Session, pr_id: Any) -> Set[str]:
        """Gets the flat set of changed file path strings for a pull request."""
        from app.models.pull_request import PullRequestChangedFile
        if not db or not pr_id:
            return set()
        changed_files_query = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr_id
        ).all()
        return {cf.file_path for cf in changed_files_query}

    @staticmethod
    def _get_test_execution_status(
        db: Session,
        repository_id: Any,
        linked_tests: List[str],
        pr_head_commit_sha: str
    ) -> tuple:
        """Get execution status, freshness, and mapping status for linked tests.

        Part 8 Rule: Missing head SHA must set freshness to UNKNOWN.
        Forbidden: missing SHA → FRESH, missing SHA → STALE

        Returns:
            tuple: (execution_status, freshness_status, mapping_status, latest_result_created_at, freshness_reason)
        """
        from app.models.test_result import TestCase, TestResult, TestRun
        from app.models.coverage import FileTestLink, CoverageReport

        if not db or not repository_id or not linked_tests:
            return "NOT_RUN", "UNKNOWN", "UNVERIFIED", None, "UNKNOWN_MISSING_BOTH_SHA"
        
        # Part 8: Missing head SHA → UNKNOWN freshness
        if not pr_head_commit_sha:
            return "NOT_RUN", "UNKNOWN", "UNVERIFIED", None, "UNKNOWN_MISSING_PR_HEAD_SHA"

        logger.debug(
            f"[ExecStatus] linked_tests sample: {linked_tests[:5]}"
        )

        test_cases = RegressionScopeV2Service._resolve_test_cases_for_ac(
            db, repository_id, linked_tests
        )

        if not test_cases:
            return "NOT_RUN", "UNKNOWN", "UNVERIFIED", None, "UNKNOWN_MISSING_BOTH_SHA"

        test_case_ids = [tc.id for tc in test_cases]

        # --- Step 1: Look for results on the CURRENT PR head SHA first (FRESH path) ---
        # Joining through TestRun lets us filter by commit_sha without a separate query.
        current_sha_results = []
        if pr_head_commit_sha:
            current_sha_results = (
                db.query(TestResult)
                .join(TestRun, TestResult.test_run_id == TestRun.id)
                .filter(
                    TestResult.test_case_id.in_(test_case_ids),
                    TestRun.commit_sha == pr_head_commit_sha,
                )
                .order_by(TestResult.created_at.desc())
                .all()
            )
            # Try head_commit_sha column as fallback (some TestRun models use that name)
            if not current_sha_results:
                try:
                    current_sha_results = (
                        db.query(TestResult)
                        .join(TestRun, TestResult.test_run_id == TestRun.id)
                        .filter(
                            TestResult.test_case_id.in_(test_case_ids),
                            TestRun.head_commit_sha == pr_head_commit_sha,
                        )
                        .order_by(TestResult.created_at.desc())
                        .all()
                    )
                except Exception:
                    pass

        if current_sha_results:
            # We have results executed on the current PR head SHA — use ONLY these for status.
            # This is the FRESH path: the result directly reflects the current commit.
            status_priority = {"FAILED": 0, "SKIPPED": 1, "NOT_RUN": 2, "PASSED": 3, "UNKNOWN": 4}
            overall_status = "PASSED"
            latest_created_at = None
            for result in current_sha_results:
                result_status = (result.status or "UNKNOWN").upper()
                if status_priority.get(result_status, 99) < status_priority.get(overall_status, 99):
                    overall_status = result_status
                if latest_created_at is None or result.created_at > latest_created_at:
                    latest_created_at = result.created_at
            freshness_status = "FRESH"
            freshness_reason = "FRESH_COMMIT_MATCH"
            logger.debug(f"[Freshness] Result: FRESH (SHA match, {len(current_sha_results)} results), overall_status={overall_status}")
            mapping_status = "VERIFIED"
            return overall_status, freshness_status, mapping_status, latest_created_at, freshness_reason

        # --- Step 2: No results for current SHA — fall back to all historical results (STALE/UNKNOWN path) ---
        latest_results = db.query(TestResult).filter(
            TestResult.test_case_id.in_(test_case_ids)
        ).order_by(TestResult.created_at.desc()).all()

        if not latest_results:
            logger.debug(f"[Freshness] No latest_results found, returning NOT_RUN")
            return "NOT_RUN", "UNKNOWN", "VERIFIED", None, "UNKNOWN_MISSING_BOTH_SHA"

        logger.debug(f"[Freshness] latest_results found: {len(latest_results)} (no current-SHA results)")

        status_priority = {"FAILED": 0, "SKIPPED": 1, "NOT_RUN": 2, "PASSED": 3, "UNKNOWN": 4}
        overall_status = "PASSED"
        latest_created_at = None

        for result in latest_results:
            result_status = (result.status or "UNKNOWN").upper()
            if status_priority.get(result_status, 99) < status_priority.get(overall_status, 99):
                overall_status = result_status
            if latest_created_at is None or result.created_at > latest_created_at:
                latest_created_at = result.created_at

        # Determine freshness from the most recent result's run SHA
        freshness_status = "UNKNOWN"
        freshness_reason = "UNKNOWN_MISSING_BOTH_SHA"

        test_run = None
        if latest_results:
            logger.debug(f"[Freshness] Querying TestRun for id: {latest_results[0].test_run_id}")
            test_run = db.query(TestRun).filter(
                TestRun.id == latest_results[0].test_run_id
            ).first()

        pr_sha = pr_head_commit_sha
        run_sha = None
        if test_run:
            run_sha = (
                getattr(test_run, 'commit_sha', None)
                or getattr(test_run, 'head_commit_sha', None)
            )

        if pr_sha and run_sha:
            if pr_sha == run_sha:
                # Should not reach here (covered by Step 1), but handle gracefully
                freshness_status = "FRESH"
                freshness_reason = "FRESH_COMMIT_MATCH"
                logger.debug(f"[Freshness] Result: FRESH (SHA match via fallback path)")
            else:
                freshness_status = "STALE"
                freshness_reason = "STALE_COMMIT_MISMATCH"
                logger.debug(f"[Freshness] Result: STALE (SHA mismatch)")
        else:
            if not pr_sha and not run_sha:
                freshness_reason = "UNKNOWN_MISSING_BOTH_SHA"
            elif not pr_sha:
                freshness_reason = "UNKNOWN_MISSING_PR_HEAD_SHA"
            else:
                freshness_reason = "UNKNOWN_MISSING_TEST_RUN_SHA"
            freshness_status = "UNKNOWN"
            logger.debug(f"[Freshness] Result: UNKNOWN ({freshness_reason})")

        mapping_status = "VERIFIED"
        return overall_status, freshness_status, mapping_status, latest_created_at, freshness_reason

    @staticmethod
    def _get_execution_status_for_test_cases(
        test_case_ids: List[Any],
        pr: Any,
        db: Session
    ) -> tuple:
        """Get execution status and freshness for a specific list of test case IDs."""
        from app.models.test_result import TestResult, TestRun
        if not test_case_ids or not db:
            return "NOT_RUN", "UNKNOWN", "VERIFIED", None, "UNKNOWN_MISSING_BOTH_SHA"

        pr_sha = pr.head_commit_sha if pr else None

        # Step 1: Look for results on the current PR head SHA first (FRESH path)
        current_sha_results = []
        if pr_sha:
            current_sha_results = (
                db.query(TestResult)
                .join(TestRun, TestResult.test_run_id == TestRun.id)
                .filter(
                    TestResult.test_case_id.in_(test_case_ids),
                    TestRun.commit_sha == pr_sha,
                )
                .order_by(TestResult.created_at.desc())
                .all()
            )
            if not current_sha_results:
                try:
                    current_sha_results = (
                        db.query(TestResult)
                        .join(TestRun, TestResult.test_run_id == TestRun.id)
                        .filter(
                            TestResult.test_case_id.in_(test_case_ids),
                            TestRun.head_commit_sha == pr_sha,
                        )
                        .order_by(TestResult.created_at.desc())
                        .all()
                    )
                except Exception:
                    pass

        if current_sha_results:
            status_priority = {"FAILED": 0, "SKIPPED": 1, "NOT_RUN": 2, "PASSED": 3, "UNKNOWN": 4}
            overall_status = "PASSED"
            latest_created_at = None
            for result in current_sha_results:
                result_status = (result.status or "UNKNOWN").upper()
                if status_priority.get(result_status, 99) < status_priority.get(overall_status, 99):
                    overall_status = result_status
                if latest_created_at is None or result.created_at > latest_created_at:
                    latest_created_at = result.created_at
            return overall_status, "FRESH", "VERIFIED", latest_created_at, "FRESH_COMMIT_MATCH"

        # Step 2: Fall back to all historical results (STALE/UNKNOWN path)
        latest_results = db.query(TestResult).filter(
            TestResult.test_case_id.in_(test_case_ids)
        ).order_by(TestResult.created_at.desc()).all()

        if not latest_results:
            return "NOT_RUN", "UNKNOWN", "VERIFIED", None, "UNKNOWN_MISSING_BOTH_SHA"

        status_priority = {"FAILED": 0, "SKIPPED": 1, "NOT_RUN": 2, "PASSED": 3, "UNKNOWN": 4}
        overall_status = "PASSED"
        latest_created_at = None

        for result in latest_results:
            result_status = (result.status or "UNKNOWN").upper()
            if status_priority.get(result_status, 99) < status_priority.get(overall_status, 99):
                overall_status = result_status
            if latest_created_at is None or result.created_at > latest_created_at:
                latest_created_at = result.created_at

        freshness_status = "UNKNOWN"
        freshness_reason = "UNKNOWN_MISSING_BOTH_SHA"

        test_run = db.query(TestRun).filter(TestRun.id == latest_results[0].test_run_id).first()
        run_sha = None
        if test_run:
            run_sha = getattr(test_run, 'commit_sha', None) or getattr(test_run, 'head_commit_sha', None)

        if pr_sha and run_sha:
            if pr_sha == run_sha:
                freshness_status = "FRESH"
                freshness_reason = "FRESH_COMMIT_MATCH"
            else:
                freshness_status = "STALE"
                freshness_reason = "STALE_COMMIT_MISMATCH"
        else:
            if not pr_sha and not run_sha:
                freshness_reason = "UNKNOWN_MISSING_BOTH_SHA"
            elif not pr_sha:
                freshness_reason = "UNKNOWN_MISSING_PR_HEAD_SHA"
            else:
                freshness_reason = "UNKNOWN_MISSING_TEST_RUN_SHA"

        return overall_status, freshness_status, "VERIFIED", latest_created_at, freshness_reason

    @staticmethod
    def _resolve_test_evidence_for_ac(
        ac: Any,
        pr: Any,
        db: Session,
        linked_tests: List[str] = None,
        repository_id: Any = None
    ) -> dict:
        """
        Resolves test execution evidence for a single AC.
        Returns dict with keys:
          execution_status: PASSED | FAILED | NOT_RUN | NO_TEST
          freshness_status: FRESH | STALE | UNKNOWN
          freshness_reason: str
          test_case_ids: list[str]
          covered_file_paths: set[str]
          match_path: str (DIRECT_AC_ID | FILE_LINK | NONE)
        
        Priority order:
          1. DIRECT_AC_ID links (match by ac.identifier)
          2. Standard file-based links via linked_tests
          3. Heuristic name matching
        """
        from app.models.coverage import FileTestLink
        from app.models.test_result import TestCase
        
        # PATH 1 — DIRECT_AC_ID (highest priority)
        if ac and ac.identifier:
            direct_links = db.query(FileTestLink).filter(
                FileTestLink.file_path == ac.identifier,
                FileTestLink.mapping_type == 'DIRECT_AC_ID'
            ).all()
            
            if direct_links:
                tc_ids = [l.test_case_id for l in direct_links]
                
                # Also collect the actual covered_file paths
                # from the covered_file property links
                covered_links = db.query(FileTestLink).filter(
                    FileTestLink.test_case_id.in_(tc_ids),
                    FileTestLink.mapping_type.in_([
                        'DECLARED_FILE', 'DIRECT', 
                        'HEURISTIC_NAMING', 'HEURISTIC_PATH'
                    ])
                ).all()
                covered_files = {l.file_path for l in covered_links}
                
                exec_status, freshness, mapping_status, latest_at, reason = (
                    RegressionScopeV2Service
                    ._get_execution_status_for_test_cases(
                        tc_ids, pr, db
                    )
                )
                return {
                    'execution_status': exec_status,
                    'freshness_status': freshness,
                    'mapping_status': mapping_status,
                    'latest_at': latest_at,
                    'freshness_reason': reason,
                    'test_case_ids': tc_ids,
                    'covered_file_paths': covered_files,
                    'match_path': 'DIRECT_AC_ID'
                }
        
        # PATH 2 — File-based links via snapshot linked_tests
        if linked_tests and repository_id:
            exec_status, freshness, map_status, latest_at, fresh_reason = \
                RegressionScopeV2Service._get_test_execution_status(
                    db, repository_id, linked_tests, pr.head_commit_sha if pr else ""
                )
            
            # Get covered files from linked tests
            covered_files = RegressionScopeV2Service._resolve_covered_files_for_requirement(
                db, repository_id, linked_tests
            )
            
            return {
                'execution_status': exec_status,
                'freshness_status': freshness,
                'freshness_reason': fresh_reason,
                'test_case_ids': [],
                'covered_file_paths': covered_files,
                'match_path': 'FILE_LINK'
            }
        
        # PATH 3 — No evidence found
        return {
            'execution_status': 'NO_TEST',
            'freshness_status': 'UNKNOWN',
            'freshness_reason': 'No test coverage found',
            'test_case_ids': [],
            'covered_file_paths': set(),
            'match_path': 'NONE'
        }

    @staticmethod
    def _classify_ac(
        evidence: dict,
        changed_file_paths: set,
        risk_band: str
    ) -> tuple:
        """
        Returns (scope_group, release_action, reason).
        
        THE LAW: A passing test NEVER goes to Recommended.
        Recommended = test gap only.
        """
        exec_status = evidence['execution_status']
        freshness = evidence['freshness_status']
        covered = evidence['covered_file_paths']
        
        mutation_overlap = bool(covered & changed_file_paths)
        
        if exec_status == 'PASSED':
            if freshness == 'FRESH':
                if mutation_overlap:
                    return (
                        ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
                        ReleaseAction.NONE,
                        "Fresh passing evidence on changed file"
                    )
                else:
                    return (
                        ScopeGroup.SAFE_TO_SKIP,
                        ReleaseAction.NONE,
                        "Fresh passing evidence, file unchanged"
                    )
            else:  # STALE or UNKNOWN
                if mutation_overlap:
                    return (
                        ScopeGroup.REQUIRED,
                        ReleaseAction.RE_RUN,
                        f"Stale evidence on changed file "
                        f"({evidence['freshness_reason']})"
                    )
                else:
                    return (
                        ScopeGroup.SAFE_TO_SKIP,
                        ReleaseAction.NONE,
                        "Stale but covered file unchanged"
                    )
        
        elif exec_status == 'FAILED':
            return (
                ScopeGroup.REQUIRED,
                ReleaseAction.FIX_OR_RERUN,
                "Test is currently failing"
            )
        
        elif exec_status == 'NOT_RUN':
            if mutation_overlap:
                return (
                    ScopeGroup.REQUIRED,
                    ReleaseAction.RUN_OR_CREATE_TEST,
                    "Test exists but not run on changed file"
                )
            else:
                return (
                    ScopeGroup.OPTIONAL,
                    ReleaseAction.RUN_OR_CREATE_TEST,
                    "Test exists but not yet run"
                )
        
        else:  # NO_TEST — genuine coverage gap
            # THIS is the only valid case for Recommended
            HIGH_RISK = ['HIGH', 'CRITICAL']
            if risk_band in HIGH_RISK or mutation_overlap:
                return (
                    ScopeGroup.REQUIRED,
                    ReleaseAction.CREATE_TEST,
                    "No test coverage — gap on changed/high-risk AC"
                )
            elif risk_band == 'MEDIUM':
                return (
                    ScopeGroup.RECOMMENDED,
                    ReleaseAction.CREATE_TEST,
                    "No test coverage yet — consider writing a test"
                )
            else:
                return (
                    ScopeGroup.OPTIONAL,
                    ReleaseAction.CREATE_TEST,
                    "No test coverage — low risk gap"
                )

    @staticmethod
    def _resolve_covered_files_for_requirement(
        db: Session,

        repository_id: Any,
        linked_tests: List[str]
    ) -> set:
        """
        Resolve actual source file paths covered by
        the tests linked to a requirement.
        Uses multi-path lookup identical to
        _resolve_test_cases_for_ac.
        Returns a set of file path strings.
        """
        from app.models.test_result import TestCase
        from app.models.coverage import FileTestLink

        if not linked_tests or not db or not repository_id:
            return set()

        test_case_ids = []

        # PATH 1: stable_identity exact match
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            TestCase.stable_identity.in_(linked_tests)
        ).all()
        if test_cases:
            test_case_ids = [tc.id for tc in test_cases]
            logger.debug(f"[CoveredFiles] PATH 1 found {len(test_cases)} cases")

        # PATH 2: DIRECT_AC_ID match
        # linked_tests may contain AC IDs like "AC-01"
        if not test_case_ids:
            ac_links = db.query(FileTestLink).filter(
                FileTestLink.file_path.in_(linked_tests),
                FileTestLink.mapping_type == "DIRECT_AC_ID"
            ).all()
            if ac_links:
                tc_ids = [link.test_case_id 
                          for link in ac_links]
                test_cases = db.query(TestCase).filter(
                    TestCase.id.in_(tc_ids),
                    TestCase.repository_id == repository_id
                ).all()
                test_case_ids = [tc.id for tc in test_cases]
                logger.debug(f"[CoveredFiles] PATH 2 found {len(test_case_ids)} cases via DIRECT_AC_ID")

        # PATH 3: test_name exact then ilike match
        if not test_case_ids:
            for identity in linked_tests:
                if identity.upper().startswith("AC-"):
                    continue
                matches = db.query(TestCase).filter(
                    TestCase.repository_id == repository_id,
                    TestCase.test_name == identity
                ).all()
                if not matches:
                    matches = db.query(TestCase).filter(
                        TestCase.repository_id == repository_id,
                        TestCase.test_name.ilike(
                            f"%{identity}%"
                        )
                    ).all()
                if matches:
                    test_case_ids.extend(
                        [tc.id for tc in matches]
                    )
                    logger.debug(f"[CoveredFiles] PATH 3 found {len(matches)} cases for '{identity}'")

        if not test_case_ids:
            logger.debug(f"[CoveredFiles] No test cases found for: {linked_tests[:3]}")
            return set()

        # Get FileTestLink records with ACTUAL file paths
        # Exclude DIRECT_AC_ID which stores AC IDs not paths
        file_links = db.query(FileTestLink).filter(
            FileTestLink.test_case_id.in_(test_case_ids),
            FileTestLink.mapping_type.in_([
                "DECLARED_FILE",
                "DIRECT",
                "HEURISTIC_NAMING",
                "HEURISTIC_PATH"
            ])
        ).all()

        covered = {
            link.file_path 
            for link in file_links 
            if link.file_path
        }

        logger.debug(f"[CoveredFiles] Resolved {len(covered)} covered files: {list(covered)[:5]}")

        return covered

    @staticmethod
    def _get_coverage_status_freshness(db: Session, repository_id: Any, linked_tests: List[str], head_commit_sha: str, current_status: str) -> str:
        """Evaluates test evidence freshness and returns the corrected coverage status."""
        from app.models.test_result import TestCase, TestRun, TestResult
        if not db or not repository_id or not linked_tests:
            return "MISSING"
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            TestCase.stable_identity.in_(linked_tests)
        ).all()
        test_case_ids = [tc.id for tc in test_cases]
        if not test_case_ids:
            return "MISSING"
        latest_run = db.query(TestRun).join(TestResult).filter(
            TestRun.repository_id == repository_id,
            TestResult.test_case_id.in_(test_case_ids)
        ).order_by(TestRun.created_at.desc()).first()
        if not latest_run:
            return "MISSING"
        if latest_run.commit_sha != head_commit_sha:
            return "PARTIALLY_COVERED"
        return current_status

    @staticmethod
    def _get_pattern_memory_keys(db: Session, repository_id: Any) -> Set[str]:
        """Loads PatternMemoryV2 records for rollback and escaped defect signals for the repository."""
        from app.models.pattern_memory_v2 import PatternMemoryV2, SIGNAL_TYPE_ROLLBACK, SIGNAL_TYPE_ESCAPED_DEFECT
        if not db or not repository_id:
            return set()
        records = db.query(PatternMemoryV2).filter(
            PatternMemoryV2.repository_id == repository_id,
            PatternMemoryV2.signal_type.in_([SIGNAL_TYPE_ROLLBACK, SIGNAL_TYPE_ESCAPED_DEFECT])
        ).all()
        return {r.pattern_key for r in records}

    @staticmethod
    def _enrich_scope_with_impact_data(
        scope: RegressionScopeV2,
        change_impact_model: Any,
        traceability: List[Dict[str, Any]],
        ac_rows: List[AcceptanceCriterion]
    ) -> RegressionScopeV2:
        """Enrich scope items with impact information from change impact model.
        
        This adds impact_type, impact_reason, and test evidence details to scope items
        so the UI can show why each item was selected and what evidence verifies it.
        
        Args:
            scope: The scope to enrich
            change_impact_model: ChangeImpactModel from ChangeImpactEngine
            traceability: Traceability data from snapshot
            ac_rows: Database AC rows for ID mapping
            
        Returns:
            Enriched scope with impact data
        """
        # Build a map of database AC ID to impact data
        ac_impact_map = {}
        for ac_matrix in change_impact_model.ac_impact_matrix:
            # Find the database AC ID for this AC
            ac = next((row for row in ac_rows if str(row.id) == ac_matrix.ac_id), None)
            if ac:
                database_ac_id = str(ac.id)
                ac_impact_map[database_ac_id] = {
                    "impact_type": ac_matrix.impact_type.value,
                    "impact_reason": ac_matrix.impact_reason,
                    "impact_confidence": ac_matrix.impact_confidence,
                    "business_flow": ac_matrix.business_flow
                }
        
        # Build a map of database AC ID to release action scope data
        release_action_map = {}
        for release_action in change_impact_model.release_action_scope:
            ac = next((row for row in ac_rows if str(row.id) == release_action.source_ac_id), None)
            if ac:
                database_ac_id = str(ac.id)
                release_action_map[database_ac_id] = {
                    "final_bucket": release_action.final_bucket.value,
                    "release_action": release_action.release_action.value,
                    "evidence_reason": release_action.evidence_reason,
                    "mapped_tests": release_action.mapped_tests
                }
        
        # Enrich scope items in all groups
        for group_name, group_summary in scope.groups.items():
            for item in group_summary.items:
                # Find the database AC ID for this item
                ac = next((row for row in ac_rows if str(row.id) == item.id), None)
                if not ac:
                    continue
                
                database_ac_id = str(ac.id)
                
                # Add impact data
                if database_ac_id in ac_impact_map:
                    impact_data = ac_impact_map[database_ac_id]
                    # Store impact data in a way that won't conflict with existing fields
                    # We'll use the reason field to include impact information
                    if not item.reason:
                        item.reason = impact_data["impact_reason"]
                    elif impact_data["impact_reason"] and impact_data["impact_reason"] not in item.reason:
                        item.reason = f"{impact_data['impact_reason']}. {item.reason}"
                
                # Add release action data
                if database_ac_id in release_action_map:
                    release_data = release_action_map[database_ac_id]
                    # Update linked tests with mapped tests from release action
                    if release_data["mapped_tests"]:
                        item.linked_tests = release_data["mapped_tests"]
                        item.linked_test_count = len(release_data["mapped_tests"])
                
                # Add test evidence details from traceability
                trace = next((t for t in traceability if t.get("databaseAcId") == database_ac_id), None)
                if trace:
                    linked_tests = trace.get("linkedExistingTests", []) or []
                    if linked_tests:
                        item.linked_tests = linked_tests
                        item.linked_test_count = len(linked_tests)
        
        return scope

    # Status → bucket mapping for traceability summary
    _TRACEABILITY_STATUS_BUCKETS: Dict[str, str] = {
        # --- covered ---
        "COVERED": "covered",
        "VERIFIED": "covered",
        "VERIFIED_BY_CURRENT_PR_EXECUTION": "covered",
        "USER_CONFIRMED": "covered",
        "AUTO_TRUSTED": "covered",
        "EVIDENCE_VERIFIED_ALIGNED": "covered",
        "Covered": "covered",
        "Already Verified": "covered",
        "Safe to Skip": "covered",
        # --- missing ---
        "MISSING": "missing",
        "NO_CANDIDATE": "missing",
        "TEST_GAP": "missing",
        "Required": "missing",
        "Coverage Gap": "missing",
        "Not Run": "missing",
        # --- not_mapped ---
        "NOT_MAPPED_TRACEABILITY_RISK": "not_mapped",
        "TRACEABILITY_INCOMPLETE": "not_mapped",
        # --- review_required ---
        "PARTIAL": "review_required",
        "PARTIAL_SUPPORT": "review_required",
        "METADATA_CONFLICT_SEMANTIC_MATCH": "review_required",
        "REVIEW_REQUIRED": "review_required",
        "Review Needed": "review_required",
        "Coverage Recommendation": "review_required",
        "Mapping Recommendation": "review_required",
        "Failed": "review_required",
        "Skipped": "review_required",
        "Deferred": "review_required",
        "Optional": "review_required",
    }

    @staticmethod
    def _build_traceability_summary(traceability: List[Dict[str, Any]]) -> TraceabilitySummary:
        """Build traceability summary from evidence graph snapshot.

        Normalizes all known evidence graph coverage statuses (both display
        strings and enum-like values) into four mutually-exclusive buckets:
        covered, missing, not_mapped, review_required.

        Unknown statuses are counted as review_required and collected for
        diagnostics.

        Args:
            traceability: List of AC traceability entries from the snapshot

        Returns:
            TraceabilitySummary with counts and unknown_statuses list
        """
        total = len(traceability)
        covered = 0
        missing = 0
        not_mapped = 0
        review_required = 0
        unknown_statuses: List[str] = []

        for trace in traceability:
            coverage_status = trace.get("coverageStatus", "MISSING")
            database_ac_id = trace.get("databaseAcId")

            bucket = RegressionScopeV2Service._TRACEABILITY_STATUS_BUCKETS.get(coverage_status)

            if bucket is None:
                if coverage_status == "Evidence Gap":
                    # "Evidence Gap" is ambiguous — it can be either
                    # MISSING_AUTOMATED_COVERAGE or NOT_MAPPED_TRACEABILITY_RISK.
                    # Use databaseAcId to disambiguate.
                    bucket = "not_mapped" if not database_ac_id else "missing"
                else:
                    # Unknown status → review_required (rule 2)
                    bucket = "review_required"
                    if coverage_status not in unknown_statuses:
                        unknown_statuses.append(coverage_status)
                        logger.warning(
                            f"[TraceabilitySummary] Unknown coverageStatus "
                            f"'{coverage_status}' counted as review_required"
                        )

            if bucket == "covered":
                covered += 1
            elif bucket == "missing":
                missing += 1
            elif bucket == "not_mapped":
                not_mapped += 1
            elif bucket == "review_required":
                review_required += 1

        return TraceabilitySummary(
            total_requirements=total,
            covered=covered,
            missing=missing,
            not_mapped=not_mapped,
            review_required=review_required,
            unknown_statuses=unknown_statuses,
        )
    
    @staticmethod
    def _build_release_decision(change_impact_model: Any, mode: ScopeMode) -> ReleaseDecision:
        """Build unified release decision from change impact model.
        
        Args:
            change_impact_model: ChangeImpactModel from ChangeImpactEngine
            mode: Scope mode used for generation
            
        Returns:
            ReleaseDecision with verdict, reason, and counts
        """
        # Count items by final bucket
        required_count = len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "REQUIRED"])
        recommended_count = len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "RECOMMENDED"])
        already_verified_count = len([s for s in change_impact_model.release_action_scope if s.final_bucket.value == "ALREADY_VERIFIED"])
        
        # Determine verdict
        if required_count > 0:
            verdict = "DO_NOT_RELEASE"
            reason = f"Do Not Release – {required_count} required test(s) not yet verified."
        elif recommended_count > 0:
            verdict = "REVIEW_RECOMMENDED"
            reason = f"Review Recommended – {recommended_count} test(s) suggested for additional safety."
        else:
            verdict = "SAFE_TO_RELEASE"
            reason = "Safe to Release – All impacted acceptance criteria are verified by fresh tests."
        
        return ReleaseDecision(
            verdict=verdict,
            reason=reason,
            required_count=required_count,
            recommended_count=recommended_count,
            already_verified_count=already_verified_count,
            source_mode=mode.value
        )

    @staticmethod
    def _get_pattern_memory_records(db: Session, repository_id: Any) -> List[Any]:
        """Loads full PatternMemoryV2 records for rollback and escaped defect signals for the repository."""
        from app.models.pattern_memory_v2 import PatternMemoryV2, SIGNAL_TYPE_ROLLBACK, SIGNAL_TYPE_ESCAPED_DEFECT
        if not db or not repository_id:
            return []
        records = db.query(PatternMemoryV2).filter(
            PatternMemoryV2.repository_id == repository_id,
            PatternMemoryV2.signal_type.in_([SIGNAL_TYPE_ROLLBACK, SIGNAL_TYPE_ESCAPED_DEFECT])
        ).all()
        return records

    @staticmethod
    def _matches_pattern_memory(
        pattern_keys: set,
        ac_normalized_key: Optional[str],
        ac_text: Optional[str],
        linked_tests: List[str]
    ) -> Optional[str]:
        """
        Check if any pattern memory key matches 
        this requirement.
        Returns the matched pattern_key or None.
        """
        if not pattern_keys:
            return None

        candidates = []

        if ac_normalized_key:
            candidates.append(
                ac_normalized_key.lower().strip()
            )

        if ac_text:
            # Normalize: lowercase, remove punctuation
            import re
            normalized = re.sub(
                r'[^\w\s]', '', ac_text.lower()
            ).strip()
            candidates.append(normalized)

        for test_name in linked_tests:
            candidates.append(test_name.lower().strip())

        for candidate in candidates:
            for pattern_key in pattern_keys:
                pk = pattern_key.lower().strip()
                if pk == candidate:
                    return pattern_key
                # Substring match for partial keys
                if pk in candidate or candidate in pk:
                    return pattern_key

        return None
