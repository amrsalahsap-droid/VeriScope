"""
Regression Scope V2 Contract Tests for Phase 4

Tests for the unified regression scope V2 contract.
"""

import pytest
from app.schemas.regression_scope_v2 import (
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
    RegressionScopeV2,
    RegressionScopeV2Request,
    RegressionScopeV2Response
)


class TestRegressionScopeV2Contract:
    """Test suite for RegressionScopeV2 contract."""

    def test_scope_item_contract_complete(self):
        """Verify scope item contract includes all required fields."""
        item = ScopeItem(
            id="test-id",
            readable_id="AC-01",
            source_ac_number=1,
            title="Test Requirement",
            item_type=ScopeItemType.REQUIREMENT,
            group=ScopeGroup.REQUIRED,
            evidence_classification=EvidenceClassification.MISSING,
            risk_score=95.0,
            risk_band=RiskBand.CRITICAL,
            change_impact_level=ChangeImpactLevel.DIRECT,
            business_risk_level=BusinessRiskLevel.CRITICAL,
            effective_risk_level=BusinessRiskLevel.CRITICAL,
            suggested_action="Run test",
            reason="Missing coverage",
            evidence_references=["test-1"],
            test_references=["test-1"],
            can_auto_execute=False,
            execution_status=None,
            estimated_effort=None,
            is_required_for_release=True,
            is_manual_only=False,
            diagnostics=None
        )

        assert item.id == "test-id"
        assert item.readable_id == "AC-01"
        assert item.source_ac_number == 1
        assert item.title == "Test Requirement"
        assert item.item_type == ScopeItemType.REQUIREMENT
        assert item.group == ScopeGroup.REQUIRED
        assert item.evidence_classification == EvidenceClassification.MISSING
        assert item.risk_score == 95.0
        assert item.risk_band == RiskBand.CRITICAL
        assert item.change_impact_level == ChangeImpactLevel.DIRECT
        assert item.business_risk_level == BusinessRiskLevel.CRITICAL
        assert item.effective_risk_level == BusinessRiskLevel.CRITICAL
        assert item.suggested_action == "Run test"
        assert item.reason == "Missing coverage"
        assert item.can_auto_execute == False
        assert item.is_required_for_release == True
        assert item.is_manual_only == False

    def test_scope_groups_enum_complete(self):
        """Verify scope groups enum includes all required groups."""
        assert ScopeGroup.REQUIRED.value == "REQUIRED"
        assert ScopeGroup.RECOMMENDED.value == "RECOMMENDED"
        assert ScopeGroup.OPTIONAL.value == "OPTIONAL"
        assert ScopeGroup.SAFE_TO_SKIP.value == "SAFE_TO_SKIP"
        assert ScopeGroup.EXCLUDED_ALREADY_VERIFIED.value == "EXCLUDED_ALREADY_VERIFIED"
        assert ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS.value == "EXCLUDED_ALREADY_PASSED_TESTS"

    def test_scope_mode_enum_complete(self):
        """Verify scope mode enum includes all required modes."""
        assert ScopeMode.TARGETED.value == "targeted"
        assert ScopeMode.RISK_BASED.value == "risk_based"
        assert ScopeMode.FULL.value == "full"

    def test_execution_plan_contract_complete(self):
        """Verify execution plan contract includes all required fields."""
        plan = ExecutionPlan(
            required_count=5,
            recommended_count=4,
            optional_count=6,
            safe_to_skip_count=3,
            total_executable_count=15,
            estimated_execution_reduction=50.0,
            confidence_level=80.0,
            plan_summary="Test plan",
            advisory_notice="Advisory notice"
        )

        assert plan.required_count == 5
        assert plan.recommended_count == 4
        assert plan.optional_count == 6
        assert plan.safe_to_skip_count == 3
        assert plan.total_executable_count == 15
        assert plan.estimated_execution_reduction == 50.0
        assert plan.confidence_level == 80.0
        assert plan.plan_summary == "Test plan"
        assert plan.advisory_notice == "Advisory notice"

    def test_regression_scope_v2_contract_complete(self):
        """Verify RegressionScopeV2 contract includes all required fields."""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        # Test that the schema can be instantiated
        scope = RegressionScopeV2(
            recommendation_run_id="test-run-id",
            snapshot_hash="test-hash",
            generated_at=now,
            scope_type="TARGETED",
            source=ScopeSource.EVIDENCE_BASED,
            summary="Test scope",
            execution_plan=ExecutionPlan(
                required_count=5,
                recommended_count=4,
                optional_count=6,
                safe_to_skip_count=3,
                total_executable_count=15,
                estimated_execution_reduction=50.0,
                confidence_level=80.0,
                plan_summary="Test plan",
                advisory_notice="Advisory notice"
            ),
            groups={
                ScopeGroup.REQUIRED.value: ScopeGroupSummary(
                    group=ScopeGroup.REQUIRED,
                    count=5,
                    items=[]
                )
            },
            exclusions=ScopeExclusions(
                already_verified_count=10,
                already_passed_tests_count=8,
                already_verified_items=[],
                already_passed_test_items=[]
            ),
            optimization_metrics=ScopeOptimizationMetrics(
                current_regression_size=18,
                optimized_required_count=5,
                optimized_recommended_count=4,
                optimized_optional_count=6,
                safe_to_skip_count=3,
                optimization_percentage=50.0,
                execution_reduction=50.0,
                coverage_confidence=33.33
            ),
            governance=ScopeGovernance(
                risk_reviews_count=0,
                overridden_count=0,
                needs_discussion_count=0,
                release_decision_required=False,
                release_decision_status=None
            ),
            diagnostics=ScopeDiagnostics(
                generation_timestamp=now,
                generation_duration_ms=100,
                rules_applied=["RULE_1"],
                warnings=[],
                errors=[]
            )
        )

        # Verify basic fields
        assert scope.recommendation_run_id == "test-run-id"
        assert scope.snapshot_hash == "test-hash"
        assert scope.scope_type == "TARGETED"
        assert scope.source == ScopeSource.EVIDENCE_BASED
        assert scope.summary == "Test scope"
        assert scope.execution_plan.required_count == 5
        assert len(scope.groups) > 0
        assert scope.exclusions.already_verified_count == 10
        assert scope.optimization_metrics.current_regression_size == 18
        assert scope.governance.risk_reviews_count == 0
        assert scope.diagnostics.generation_timestamp is not None

    def test_v2_request_contract_complete(self):
        """Verify V2 request contract includes all required fields."""
        request = RegressionScopeV2Request(
            mode=ScopeMode.TARGETED,
            include_safe_to_skip=False,
            include_diagnostics=False,
            audit=False
        )

        assert request.mode == ScopeMode.TARGETED
        assert request.include_safe_to_skip == False
        assert request.include_diagnostics == False
        assert request.audit == False

    def test_v2_response_contract_complete(self):
        """Verify V2 response contract includes all required fields."""
        response = RegressionScopeV2Response(
            status="SUCCESS",
            scope=None,
            error_code=None,
            message=None
        )

        assert response.status == "SUCCESS"
        assert response.scope is None
        assert response.error_code is None
        assert response.message is None

    def test_v2_response_error_contract_complete(self):
        """Verify V2 response error contract includes all required fields."""
        response = RegressionScopeV2Response(
            status="ERROR",
            scope=None,
            error_code="VALIDATION_ERROR",
            message="Test error"
        )

        assert response.status == "ERROR"
        assert response.scope is None
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Test error"

    def test_scope_item_diagnostics_contract(self):
        """Verify scope item diagnostics contract."""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        diagnostics = ScopeItemDiagnostics(
            internal_requirement_id="internal-id",
            internal_test_id="test-id",
            generation_rule="RULE_1",
            confidence_score=0.95,
            last_updated=now
        )

        assert diagnostics.internal_requirement_id == "internal-id"
        assert diagnostics.internal_test_id == "test-id"
        assert diagnostics.generation_rule == "RULE_1"
        assert diagnostics.confidence_score == 0.95
        assert diagnostics.last_updated is not None

    def test_scope_group_summary_contract(self):
        """Verify scope group summary contract."""
        summary = ScopeGroupSummary(
            group=ScopeGroup.REQUIRED,
            count=5,
            items=[]
        )

        assert summary.group == ScopeGroup.REQUIRED
        assert summary.count == 5
        assert summary.items == []

    def test_optimization_metrics_contract(self):
        """Verify optimization metrics contract."""
        metrics = ScopeOptimizationMetrics(
            current_regression_size=18,
            optimized_required_count=5,
            optimized_recommended_count=4,
            optimized_optional_count=6,
            safe_to_skip_count=3,
            optimization_percentage=50.0,
            execution_reduction=50.0,
            coverage_confidence=33.33
        )

        assert metrics.current_regression_size == 18
        assert metrics.optimized_required_count == 5
        assert metrics.optimized_recommended_count == 4
        assert metrics.optimized_optional_count == 6
        assert metrics.safe_to_skip_count == 3
        assert metrics.optimization_percentage == 50.0
        assert metrics.execution_reduction == 50.0
        assert metrics.coverage_confidence == 33.33

    def test_governance_contract(self):
        """Verify governance contract."""
        governance = ScopeGovernance(
            risk_reviews_count=5,
            overridden_count=2,
            needs_discussion_count=1,
            release_decision_required=True,
            release_decision_status="PENDING"
        )

        assert governance.risk_reviews_count == 5
        assert governance.overridden_count == 2
        assert governance.needs_discussion_count == 1
        assert governance.release_decision_required == True
        assert governance.release_decision_status == "PENDING"

    def test_diagnostics_contract(self):
        """Verify diagnostics contract."""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        diagnostics = ScopeDiagnostics(
            generation_timestamp=now,
            generation_duration_ms=100,
            rules_applied=["RULE_1", "RULE_2"],
            warnings=["Warning 1"],
            errors=["Error 1"]
        )

        assert diagnostics.generation_timestamp is not None
        assert diagnostics.generation_duration_ms == 100
        assert len(diagnostics.rules_applied) == 2
        assert len(diagnostics.warnings) == 1
        assert len(diagnostics.errors) == 1

    def test_exclusions_contract(self):
        """Verify exclusions contract."""
        exclusions = ScopeExclusions(
            already_verified_count=10,
            already_passed_tests_count=8,
            already_verified_items=[],
            already_passed_test_items=[]
        )

        assert exclusions.already_verified_count == 10
        assert exclusions.already_passed_tests_count == 8
        assert exclusions.already_verified_items == []
        assert exclusions.already_passed_test_items == []

    def test_all_scope_groups_present(self):
        """Verify all required scope groups are present in the contract."""
        required_groups = [
            ScopeGroup.REQUIRED,
            ScopeGroup.RECOMMENDED,
            ScopeGroup.OPTIONAL,
            ScopeGroup.SAFE_TO_SKIP,
            ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
            ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS
        ]

        for group in required_groups:
            assert group in ScopeGroup

    def test_all_scope_modes_present(self):
        """Verify all required scope modes are present in the contract."""
        required_modes = [
            ScopeMode.TARGETED,
            ScopeMode.RISK_BASED,
            ScopeMode.FULL
        ]

        for mode in required_modes:
            assert mode in ScopeMode

    def test_all_scope_item_types_present(self):
        """Verify all required scope item types are present in the contract."""
        required_types = [
            ScopeItemType.REQUIREMENT,
            ScopeItemType.TEST,
            ScopeItemType.SCENARIO,
            ScopeItemType.MANUAL_TEST
        ]

        for item_type in required_types:
            assert item_type in ScopeItemType

    def test_all_risk_bands_present(self):
        """Verify all required risk bands are present in the contract."""
        required_bands = [
            RiskBand.CRITICAL,
            RiskBand.HIGH,
            RiskBand.MEDIUM,
            RiskBand.LOW
        ]

        for band in required_bands:
            assert band in RiskBand

    def test_all_change_impact_levels_present(self):
        """Verify all required change impact levels are present in the contract."""
        required_levels = [
            ChangeImpactLevel.DIRECT,
            ChangeImpactLevel.RELATED,
            ChangeImpactLevel.INDIRECT,
            ChangeImpactLevel.NONE
        ]

        for level in required_levels:
            assert level in ChangeImpactLevel

    def test_all_business_risk_levels_present(self):
        """Verify all required business risk levels are present in the contract."""
        required_levels = [
            BusinessRiskLevel.CRITICAL,
            BusinessRiskLevel.HIGH,
            BusinessRiskLevel.MEDIUM,
            BusinessRiskLevel.LOW,
            BusinessRiskLevel.UNKNOWN
        ]

        for level in required_levels:
            assert level in BusinessRiskLevel
