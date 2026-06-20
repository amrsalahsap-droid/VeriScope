"""Regression Scope V2 Service for Phase 4

Service for generating unified regression scope using the V2 contract.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

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
    ScopeDiagnostics
)
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest
from app.models.acceptance_criterion import AcceptanceCriterion
from app.services.risk_based_regression.risk_scoring_service import RiskScoringService
from app.services.change_impact_service import ChangeImpactService
from app.services.regression_recommendation_engine import RegressionRecommendationEngine
from app.services.manual_evidence_risk_adjustment_service import ManualEvidenceRiskAdjustmentService


class RegressionScopeV2Service:
    """Service for generating unified regression scope V2."""

    # Phase 6.3: default estimated effort for a manual test (minutes)
    MANUAL_TEST_DEFAULT_MINUTES = 10

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

        # Get acceptance criteria
        ac_rows = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pr.id
        ).all()

        # Get evidence graph snapshot
        if not run.requirement_evidence_snapshot_json:
            raise ValueError(f"Evidence graph snapshot not available for run {run_id}")

        import json
        raw_snapshot = run.requirement_evidence_snapshot_json
        # JSONB columns are already deserialized by SQLAlchemy; only call json.loads on strings
        if isinstance(raw_snapshot, str):
            snapshot_data = json.loads(raw_snapshot)
        else:
            snapshot_data = raw_snapshot

        # Build changed_files list from snapshot for diagnostics
        changed_files = snapshot_data.get("changedFiles", []) or []
        evidence_items = snapshot_data.get("acTraceability", []) or []

        # Generate scope based on mode (db passed so manual risk adjustment can use it)
        if mode == ScopeMode.TARGETED:
            scope = RegressionScopeV2Service._generate_targeted_scope(
                run, pr, ac_rows, snapshot_data, include_safe_to_skip, audit, db=db
            )
        elif mode == ScopeMode.RISK_BASED:
            scope = RegressionScopeV2Service._generate_risk_based_scope(
                run, pr, ac_rows, snapshot_data, include_safe_to_skip, audit, db=db
            )
        else:  # FULL
            scope = RegressionScopeV2Service._generate_full_scope(
                run, pr, ac_rows, snapshot_data, include_safe_to_skip, audit, db=db
            )

        # Add diagnostics if requested
        if include_diagnostics:
            scope.diagnostics = ScopeDiagnostics(
                generation_timestamp=datetime.utcnow(),
                generation_duration_ms=None,
                rules_applied=scope.diagnostics.rules_applied if scope.diagnostics else [],
                warnings=[],
                errors=[]
            )

        return scope

    @staticmethod
    def _generate_targeted_scope(
        run: RecommendationRun,
        pr: PullRequest,
        ac_rows: List[AcceptanceCriterion],
        snapshot_data: Dict[str, Any],
        include_safe_to_skip: bool,
        audit: bool,
        db: Session = None
    ) -> RegressionScopeV2:
        """Generate targeted scope using Phase 1/2 logic."""
        # Extract coverage data from snapshot
        traceability = snapshot_data.get("acTraceability", [])
        
        # Build scope items
        required_items = []
        recommended_items = []
        optional_items = []
        safe_to_skip_items = []
        already_verified_items = []
        already_passed_test_items = []

        for trace in traceability:
            coverage_status = trace.get("coverageStatus", "MISSING")

            # Create scope item
            item = RegressionScopeV2Service._create_scope_item_from_trace(
                trace, audit
            )

            # Phase 6.4: Apply manual evidence risk adjustment
            item = RegressionScopeV2Service._apply_manual_risk_adjustment(
                item, snapshot_data, db
            )

            # Categorize based on coverage (Phase 1/2 logic)
            if coverage_status.upper() == "MISSING":
                item.group = ScopeGroup.REQUIRED
                item.is_required_for_release = True
                required_items.append(item)
            elif coverage_status.upper() == "PARTIALLY COVERED":
                item.group = ScopeGroup.RECOMMENDED
                item.is_required_for_release = False
                recommended_items.append(item)
            elif coverage_status.upper() == "COVERED":
                item.group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                item.is_required_for_release = False
                already_verified_items.append(item)

        # Capture automated-only counts before merging manual items (Phase 6.3)
        automated_required_count = len(required_items)
        automated_recommended_count = len(recommended_items)
        automated_executable_count = len(required_items) + len(recommended_items) + len(optional_items)

        # Phase 6.3: merge MANUAL_TEST scope items (execution recommendations only)
        manual_buckets = RegressionScopeV2Service._generate_manual_scope_items(snapshot_data, audit)
        required_items.extend(manual_buckets[ScopeGroup.REQUIRED])
        recommended_items.extend(manual_buckets[ScopeGroup.RECOMMENDED])
        optional_items.extend(manual_buckets[ScopeGroup.OPTIONAL])
        safe_to_skip_items.extend(manual_buckets[ScopeGroup.SAFE_TO_SKIP])
        manual_counts = {g: len(items) for g, items in manual_buckets.items()}

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
            )
        }

        # Build execution plan
        total_manual = sum(manual_counts.values())
        manual_estimated_minutes = (
            manual_counts[ScopeGroup.REQUIRED]
            + manual_counts[ScopeGroup.RECOMMENDED]
            + manual_counts[ScopeGroup.OPTIONAL]
        ) * RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES
        execution_plan = ExecutionPlan(
            required_count=len(required_items),
            recommended_count=len(recommended_items),
            optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            total_executable_count=len(required_items) + len(recommended_items) + len(optional_items),
            estimated_execution_reduction=0.0,
            confidence_level=80.0,
            plan_summary="Targeted scope based on evidence coverage",
            advisory_notice="Targeted mode focuses on missing and partial coverage items",
            manual_required_count=manual_counts[ScopeGroup.REQUIRED],
            manual_recommended_count=manual_counts[ScopeGroup.RECOMMENDED],
            manual_optional_count=manual_counts[ScopeGroup.OPTIONAL],
            manual_safe_to_skip_count=manual_counts[ScopeGroup.SAFE_TO_SKIP],
            automated_required_count=automated_required_count,
            automated_recommended_count=automated_recommended_count,
            manual_estimated_minutes=manual_estimated_minutes,
            automated_estimated_minutes=0
        )

        # Build exclusions
        exclusions = ScopeExclusions(
            already_verified_count=len(already_verified_items),
            already_passed_tests_count=len(already_passed_test_items),
            already_verified_items=already_verified_items,
            already_passed_test_items=already_passed_test_items
        )

        # Build optimization metrics
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

        # Build governance
        governance = ScopeGovernance(
            risk_reviews_count=0,
            overridden_count=0,
            needs_discussion_count=0,
            release_decision_required=False,
            release_decision_status=None
        )

        # Build diagnostics
        diagnostics = ScopeDiagnostics(
            generation_timestamp=datetime.utcnow(),
            generation_duration_ms=None,
            rules_applied=[
                "INCLUDED_MISSING_AUTOMATED_COVERAGE",
                "INCLUDED_PARTIAL_COVERAGE_FOR_REVIEW",
                "EXCLUDED_VERIFIED_REQUIREMENTS"
            ],
            warnings=[],
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
        db: Session = None
    ) -> RegressionScopeV2:
        """Generate risk-based scope using Phase 3 logic."""
        # Extract coverage data from snapshot
        traceability = snapshot_data.get("acTraceability", [])
        
        # Build scope items with risk scoring
        required_items = []
        recommended_items = []
        optional_items = []
        safe_to_skip_items = []
        already_verified_items = []
        already_passed_test_items = []

        for trace in traceability:
            coverage_status = trace.get("coverageStatus", "MISSING")
            coverage_status_upper = coverage_status.upper()

            # Calculate risk score
            risk_result = RiskScoringService.calculate_requirement_risk_score(
                business_risk="HIGH" if coverage_status_upper == "MISSING" else "MEDIUM",
                coverage_status=coverage_status,
                criticality="HIGH",
                requirement_type="FUNCTIONAL"
            )

            # Create scope item
            item = RegressionScopeV2Service._create_scope_item_from_trace(
                trace, audit
            )
            item.risk_score = risk_result["riskScore"]
            item.risk_band = RiskBand(risk_result["riskBand"])
            item.change_impact_level = ChangeImpactLevel.RELATED
            item.business_risk_level = BusinessRiskLevel.HIGH if coverage_status_upper == "MISSING" else BusinessRiskLevel.MEDIUM
            item.effective_risk_level = item.business_risk_level

            # Phase 6.4: Apply manual evidence risk adjustment
            item = RegressionScopeV2Service._apply_manual_risk_adjustment(
                item, snapshot_data, db
            )

            # Categorize based on risk and coverage (Phase 3 logic)
            if coverage_status_upper == "MISSING" and item.risk_band in [RiskBand.CRITICAL, RiskBand.HIGH]:
                item.group = ScopeGroup.REQUIRED
                item.is_required_for_release = True
                required_items.append(item)
            elif coverage_status_upper == "MISSING":
                item.group = ScopeGroup.RECOMMENDED
                item.is_required_for_release = False
                recommended_items.append(item)
            elif coverage_status_upper == "PARTIALLY COVERED" and item.risk_band in [RiskBand.CRITICAL, RiskBand.HIGH]:
                item.group = ScopeGroup.RECOMMENDED
                item.is_required_for_release = False
                recommended_items.append(item)
            elif coverage_status_upper == "PARTIALLY COVERED":
                item.group = ScopeGroup.OPTIONAL
                item.is_required_for_release = False
                optional_items.append(item)
            elif coverage_status_upper == "COVERED" and item.risk_band == RiskBand.LOW:
                item.group = ScopeGroup.SAFE_TO_SKIP
                item.is_required_for_release = False
                safe_to_skip_items.append(item)
            else:
                item.group = ScopeGroup.EXCLUDED_ALREADY_VERIFIED
                item.is_required_for_release = False
                already_verified_items.append(item)

        # Capture automated-only counts before merging manual items (Phase 6.3)
        automated_required_count = len(required_items)
        automated_recommended_count = len(recommended_items)

        # Phase 6.3: merge MANUAL_TEST scope items (execution recommendations only)
        manual_buckets = RegressionScopeV2Service._generate_manual_scope_items(snapshot_data, audit)
        required_items.extend(manual_buckets[ScopeGroup.REQUIRED])
        recommended_items.extend(manual_buckets[ScopeGroup.RECOMMENDED])
        optional_items.extend(manual_buckets[ScopeGroup.OPTIONAL])
        safe_to_skip_items.extend(manual_buckets[ScopeGroup.SAFE_TO_SKIP])
        manual_counts = {g: len(items) for g, items in manual_buckets.items()}

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
            )
        }

        # Build execution plan
        total_executable = len(required_items) + len(recommended_items) + len(optional_items)
        current_tests = snapshot_data.get("counts", {}).get("uploadedPrTestsPassed", 0)
        execution_reduction = ((current_tests - total_executable) / current_tests * 100) if current_tests > 0 else 0.0
        manual_estimated_minutes = (
            manual_counts[ScopeGroup.REQUIRED]
            + manual_counts[ScopeGroup.RECOMMENDED]
            + manual_counts[ScopeGroup.OPTIONAL]
        ) * RegressionScopeV2Service.MANUAL_TEST_DEFAULT_MINUTES

        execution_plan = ExecutionPlan(
            required_count=len(required_items),
            recommended_count=len(recommended_items),
            optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            total_executable_count=total_executable,
            estimated_execution_reduction=round(execution_reduction, 2),
            confidence_level=75.0,
            plan_summary=f"Risk-based scope with {len(required_items)} required, {len(recommended_items)} recommended, {len(optional_items)} optional",
            advisory_notice="Risk-based mode prioritizes high-risk missing and partial coverage items",
            manual_required_count=manual_counts[ScopeGroup.REQUIRED],
            manual_recommended_count=manual_counts[ScopeGroup.RECOMMENDED],
            manual_optional_count=manual_counts[ScopeGroup.OPTIONAL],
            manual_safe_to_skip_count=manual_counts[ScopeGroup.SAFE_TO_SKIP],
            automated_required_count=automated_required_count,
            automated_recommended_count=automated_recommended_count,
            manual_estimated_minutes=manual_estimated_minutes,
            automated_estimated_minutes=0
        )

        # Build exclusions
        exclusions = ScopeExclusions(
            already_verified_count=len(already_verified_items),
            already_passed_tests_count=len(already_passed_test_items),
            already_verified_items=already_verified_items,
            already_passed_test_items=already_passed_test_items
        )

        # Build optimization metrics
        optimization_metrics = ScopeOptimizationMetrics(
            current_regression_size=current_tests,
            optimized_required_count=len(required_items),
            optimized_recommended_count=len(recommended_items),
            optimized_optional_count=len(optional_items),
            safe_to_skip_count=len(safe_to_skip_items),
            optimization_percentage=round(execution_reduction, 2),
            execution_reduction=round(execution_reduction, 2),
            coverage_confidence=round((len(required_items) / total_executable * 100) if total_executable > 0 else 0, 2)
        )

        # Build governance
        governance = ScopeGovernance(
            risk_reviews_count=0,
            overridden_count=0,
            needs_discussion_count=0,
            release_decision_required=False,
            release_decision_status=None
        )

        # Build diagnostics
        diagnostics = ScopeDiagnostics(
            generation_timestamp=datetime.utcnow(),
            generation_duration_ms=None,
            rules_applied=[
                "RISK_BASED_PRIORITIZATION",
                "HIGH_RISK_MISSING_REQUIRED",
                "HIGH_RISK_PARTIAL_RECOMMENDED",
                "LOW_RISK_VERIFIED_SAFE_TO_SKIP"
            ],
            warnings=[],
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
        db: Session = None
    ) -> RegressionScopeV2:
        """Generate full scope including all items."""
        # Use risk-based logic but include all items
        scope = RegressionScopeV2Service._generate_risk_based_scope(
            run, pr, ac_rows, snapshot_data, True, audit, db=db
        )
        scope.scope_type = "FULL"
        scope.source = ScopeSource.HYBRID
        scope.summary = f"Full scope including all items with {len(scope.groups[ScopeGroup.REQUIRED.value].items)} required"
        return scope

    @staticmethod
    def _create_scope_item_from_trace(
        trace: Dict[str, Any],
        audit: bool
    ) -> ScopeItem:
        """Create a scope item from a trace record."""
        coverage_status = trace.get("coverageStatus", "MISSING")
        
        # Map coverage status to evidence classification
        coverage_map = {
            "Covered": EvidenceClassification.COVERED,
            "Partially covered": EvidenceClassification.PARTIAL,
            "Missing": EvidenceClassification.MISSING
        }
        
        return ScopeItem(
            id=trace.get("requirementId", ""),
            readable_id=trace.get("readableId", ""),
            source_ac_number=trace.get("sourceAcNumber"),
            title=trace.get("title", ""),
            item_type=ScopeItemType.REQUIREMENT,
            group=ScopeGroup.REQUIRED,  # Will be overridden by categorization logic
            evidence_classification=coverage_map.get(coverage_status, EvidenceClassification.MISSING),
            risk_score=0.0,  # Will be set by risk scoring
            risk_band=RiskBand.LOW,  # Will be set by risk scoring
            change_impact_level=ChangeImpactLevel.NONE,
            business_risk_level=BusinessRiskLevel.UNKNOWN,
            effective_risk_level=BusinessRiskLevel.UNKNOWN,
            suggested_action="Run test" if coverage_status == "MISSING" else "Review",
            reason=f"Coverage status: {coverage_status}",
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
        audit: bool
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
