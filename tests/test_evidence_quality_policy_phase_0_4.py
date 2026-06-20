import pytest
import os
import uuid
from unittest.mock import patch, MagicMock

from app.services.regression_evidence_classifier import (
    RequirementNode, TestNode, ExecutionNode, ScenarioSignature, EvidenceClassification
)
from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy
from app.services.evidence_graph.evidence_health_evaluator import EvidenceHealthEvaluator
from app.services.evidence_graph.recommendation_view_model_builder import RecommendationViewModelBuilder
from app.services.evidence_graph.missing_test_mapper import MissingTestMapper, MissingTestGenerationError
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService, MatchTableEntry

# ==========================================
# TEST 1: Search/no-active-runtime-hardcoding test
# ==========================================
def test_no_active_runtime_hardcoding():
    """Assert no active service code contains is_password_scenario or magic numbers."""
    paths_to_check = [
        "app/services/evidence_graph/missing_test_mapper.py",
        "app/services/evidence_graph/recommendation_view_model_builder.py",
        "app/services/evidence_graph/evidence_matching_service.py",
        "app/services/evidence_graph/ac_extraction_service.py",
        "app/routers/recommendation.py"
    ]
    forbidden = [
        "is_password_scenario",
        "verified_count < 15",
        "required minimum of 15",
        "Password-related scenario"
    ]

    for rel_path in paths_to_check:
        abs_path = os.path.join(os.getcwd(), rel_path.replace("/", os.sep))
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
                for phrase in forbidden:
                    assert phrase not in content, f"Active runtime code in {rel_path} contains forbidden phrase: '{phrase}'"


class TestEvidenceQualityAndHealthRules:
    """Covers tests 2 to 10 of Phase 0.4 validation."""

    def _create_requirement(self, req_id: str, title: str, classification: EvidenceClassification, node_type: str = "PARENT_REQUIREMENT") -> RequirementNode:
        sig = ScenarioSignature(
            flow="unknown",
            action="unknown",
            condition="unknown",
            expected_outcome="unknown",
            subject="unknown",
            validation_layer="",
            polarity="neutral"
        )
        return RequirementNode(
            requirement_id=req_id,
            readable_id=f"AC-{req_id}",
            title=title,
            flow="unknown",
            scenario_signature=sig,
            classification=classification,
            match_score=0.0,
            is_real_testable_requirement=(node_type == "PARENT_REQUIREMENT"),
            node_type=node_type
        )

    # ==========================================
    # TEST 2: Given 25 requirements and 6 verified
    # ==========================================
    def test_low_verified_requirement_coverage_diagnostics(self):
        """Test low verified coverage ratio resolves to needs traceability review and diagnostics exists."""
        requirements = []
        # 6 verified
        for i in range(6):
            requirements.append(self._create_requirement(str(i), f"Req {i}", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION))
        # 19 unmapped (traceability risks) -> Total 25
        for i in range(6, 25):
            requirements.append(self._create_requirement(str(i), f"Req {i}", EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK))

        builder = RecommendationViewModelBuilder()
        policy = EvidenceQualityPolicy(
            min_verified_ratio_for_ready=0.85,
            max_not_mapped_ratio_for_ready=0.20,
            max_not_mapped_count_for_ready=5,
            minimum_parent_requirements_for_ratio_rules=10
        )

        # Build view model directly to test diagnostics and health
        view_model = builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )

        print("DEBUG DIAGNOSTICS:", view_model.health, view_model.diagnostics)
        assert view_model.health == "NEEDS_TRACEABILITY_REVIEW"
        assert view_model.can_render_recommendation is True

        # Check diagnostic code is present
        violations = view_model.diagnostics.get("policy_violations", [])
        codes = [v["code"] for v in violations]
        assert "LOW_VERIFIED_REQUIREMENT_COVERAGE" in codes

        # Verify diagnostic payload fields
        diag = next(v for v in violations if v["code"] == "LOW_VERIFIED_REQUIREMENT_COVERAGE")
        assert diag["details"]["verified_count"] == 6
        assert diag["details"]["total_parent_requirements"] == 25
        assert diag["details"]["verified_ratio"] == 6 / 25
        assert diag["details"]["policy_threshold"] == 0.85

    # ==========================================
    # TEST 3: Given 25 requirements, many not mapped
    # ==========================================
    def test_high_unmapped_requirement_ratio_diagnostics(self):
        """Test high unmapped ratio resolves to needs review and diagnostics exists."""
        requirements = []
        # 15 verified
        for i in range(15):
            requirements.append(self._create_requirement(str(i), f"Req {i}", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION))
        # 10 not mapped -> Total 25 (unmapped ratio = 0.40, count = 10)
        for i in range(15, 25):
            requirements.append(self._create_requirement(str(i), f"Req {i}", EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK))

        builder = RecommendationViewModelBuilder()
        policy = EvidenceQualityPolicy(
            min_verified_ratio_for_ready=0.85,
            max_not_mapped_ratio_for_ready=0.20,
            max_not_mapped_count_for_ready=5,
            minimum_parent_requirements_for_ratio_rules=10
        )

        # Build view model directly
        view_model = builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )

        assert view_model.health == "NEEDS_TRACEABILITY_REVIEW"
        violations = view_model.diagnostics.get("policy_violations", [])
        codes = [v["code"] for v in violations]
        assert "HIGH_UNMAPPED_REQUIREMENT_RATIO" in codes

        diag = next(v for v in violations if v["code"] == "HIGH_UNMAPPED_REQUIREMENT_RATIO")
        assert diag["details"]["not_mapped_count"] == 10
        assert diag["details"]["total_parent_requirements"] == 25
        assert diag["details"]["unmapped_ratio"] == 10 / 25
        assert diag["details"]["policy_threshold"] == 0.20

    # ==========================================
    # TEST 4: Given all requirements verified and no failed/skipped/missing/not-mapped
    # ==========================================
    def test_ready_state_all_verified(self):
        """Test that all requirements verified results in READY health."""
        requirements = []
        for i in range(25):
            requirements.append(self._create_requirement(str(i), f"Req {i}", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION))

        builder = RecommendationViewModelBuilder()
        view_model = builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )

        assert view_model.health == "READY"
        assert view_model.can_render_recommendation is True

    # ==========================================
    # TEST 5: Given graph invariant failure
    # ==========================================
    def test_graph_invariant_failure_health(self):
        """Test that invariant failures block rendering and set correct health."""
        requirements = []
        # Create duplicate requirement IDs to fail invariant checks
        requirements.append(self._create_requirement("1", "Req 1", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION))
        requirements.append(self._create_requirement("1", "Req 1 Duplicate", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION))

        builder = RecommendationViewModelBuilder()
        view_model = builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )

        assert view_model.health == "INTERNAL_EVIDENCE_MODEL_INCONSISTENT"
        assert view_model.can_render_recommendation is False

        violations = view_model.diagnostics.get("policy_violations", [])
        codes = [v["code"] for v in violations]
        assert "GRAPH_BUCKET_INVARIANT_FAILED" in codes

        diag = next(v for v in violations if v["code"] == "GRAPH_BUCKET_INVARIANT_FAILED")
        assert diag["details"]["total_parent_requirements"] == 2
        assert diag["details"]["bucket_sum"] == 2
        assert "1" in diag["details"]["duplicate_requirement_ids"]

    # ==========================================
    # TEST 6: Given missing requirements (MISSING_AUTOMATED_COVERAGE)
    # ==========================================
    def test_missing_test_cards_generated_only_for_missing_automated_coverage(self):
        """Test that missing test mapper only generates cards for requirements classified as MISSING_AUTOMATED_COVERAGE."""
        req_missing = self._create_requirement("1", "Missing automated coverage req", EvidenceClassification.MISSING_AUTOMATED_COVERAGE)
        req_verified = self._create_requirement("2", "Verified req", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION)
        
        mapper = MissingTestMapper()
        
        # Test missing req generates card
        cards = mapper.generate_missing_tests([req_missing])
        assert len(cards) == 1
        assert cards[0].requirement_id == "1"

    # ==========================================
    # TEST 7: Given verified requirement
    # ==========================================
    def test_verified_requirement_no_missing_card(self):
        """Test that verified requirements do not generate missing test cards."""
        req_verified = self._create_requirement("1", "Verified requirement", EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION)
        
        mapper = MissingTestMapper()
        cards = mapper.generate_missing_tests([req_verified])
        assert len(cards) == 0

    # ==========================================
    # TEST 8: Given not-mapped requirement
    # ==========================================
    def test_not_mapped_requirement_no_missing_card(self):
        """Test that not-mapped requirements do not generate missing test cards."""
        req_unmapped = self._create_requirement("1", "Not-mapped requirement", EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK)
        
        mapper = MissingTestMapper()
        cards = mapper.generate_missing_tests([req_unmapped])
        assert len(cards) == 0

    # ==========================================
    # TEST 9: Given optional hardening suggestion
    # ==========================================
    def test_optional_hardening_suggestion_not_missing_coverage(self):
        """Test that optional improvements/hardening do not generate missing automated coverage cards."""
        req_optional = self._create_requirement("1", "Optional hardening suggestion", EvidenceClassification.OPTIONAL_IMPROVEMENT)
        
        mapper = MissingTestMapper()
        cards = mapper.generate_missing_tests([req_optional])
        
        # Should not generate missing tests
        assert len(cards) == 0

    # ==========================================
    # TEST 10: Given contradictory evidence candidate
    # ==========================================
    def test_contradictory_evidence_candidate(self):
        """Test that contradictory evidence candidates are rejected by matching service."""
        req_sig = ScenarioSignature(
            flow="sign_up",
            action="register",
            condition="valid",
            expected_outcome="accepted",
            subject="user",
            validation_layer="backend",
            polarity="neutral"
        )
        test_sig = ScenarioSignature(
            flow="password_reset", # Contradicts sign_up flow
            action="reset",
            condition="valid",
            expected_outcome="accepted",
            subject="user",
            validation_layer="backend",
            polarity="neutral"
        )

        req = RequirementNode(
            requirement_id="AC-1",
            readable_id="AC-1",
            title="User signs up successfully",
            flow="sign_up",
            scenario_signature=req_sig,
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            match_score=0.0
        )
        test = TestNode(
            test_id="test-1",
            title="Reset password flow works",
            normalized_title="reset password flow works",
            file_path="auth_test.py",
            classname="AuthTest",
            scenario_signature=test_sig
        )

        matcher = EvidenceMatchingService()
        result = matcher.match_requirement_to_test(req, test)

        # Match score must be 0.0 due to hard contradiction gate
        assert result.score == 0.0
        assert "rejection_reason" in result.diagnostics
        assert "SIGN_UP vs RESET_PASSWORD" in result.diagnostics["contradiction_rule_triggered"]
        assert result.diagnostics["signature_diagnostics"]["flow_contradiction"] is True

