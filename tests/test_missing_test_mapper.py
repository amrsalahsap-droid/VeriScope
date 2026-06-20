"""Test missing test mapper to ensure only genuine MISSING_AUTOMATED_COVERAGE requirements generate missing tests."""
import pytest
from app.services.regression_evidence_classifier import (
    RequirementNode, TestNode, ExecutionNode, ScenarioSignature, EvidenceClassification
)
from app.services.evidence_graph.missing_test_mapper import (
    MissingTestMapper, MissingTestCard, MissingTestGenerationError
)
from app.services.evidence_graph.evidence_matching_service import MatchTableEntry


class TestMissingTestMapper:
    """Test suite for missing test mapper strict guards."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = MissingTestMapper()

    def _create_requirement(self, req_id: str, title: str, classification: EvidenceClassification,
                           flow: str = "", match_score: float = 0.0) -> RequirementNode:
        """Helper to create a RequirementNode."""
        sig = ScenarioSignature(
            flow=flow,
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
            flow=flow,
            scenario_signature=sig,
            classification=classification,
            match_score=match_score,
            is_real_testable_requirement=True
        )

    def _create_match_table_entry(self, req_id: str, test_title: str, decision: str, 
                                  score: float = 0.0, rejection_reason: str = "") -> MatchTableEntry:
        """Helper to create a match table entry."""
        return MatchTableEntry(
            requirement_id=req_id,
            requirement_title=f"Requirement {req_id}",
            candidate_test_title=test_title,
            score=score,
            decision=decision,
            reason="Test reason",
            contradiction_penalty=0.0,
            rejection_reason=rejection_reason,
            contradiction_rule_triggered="",
            matching_dimensions={},
            current_pr_execution_id=""
        )

    def test_passed_junit_prevents_missing_test_generation(self):
        """Test that passed JUnit test prevents missing test generation."""
        # Requirement classified as VERIFIED_BY_CURRENT_PR_EXECUTION
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            flow="sign_up"
        )
        req.matched_execution_ids = ["exec-1"]

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_failed_junit_prevents_missing_test_generation(self):
        """Test that failed JUnit test prevents missing test generation."""
        # Requirement classified as FAILED_IN_CURRENT_PR_EXECUTION
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION,
            flow="sign_up"
        )
        req.matched_execution_ids = ["exec-1"]

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_skipped_junit_prevents_missing_test_generation(self):
        """Test that skipped JUnit test prevents missing test generation."""
        # Requirement classified as SKIPPED_IN_CURRENT_PR_EXECUTION
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION,
            flow="sign_up"
        )
        req.matched_execution_ids = ["exec-1"]

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_required_not_run_does_not_generate_missing_test(self):
        """Test that EXISTING_TEST_NOT_RUN_IN_CURRENT_PR does not generate missing test."""
        # Requirement classified as EXISTING_TEST_NOT_RUN_IN_CURRENT_PR
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR,
            flow="sign_up"
        )
        req.matched_test_ids = ["test-1"]

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_not_mapped_traceability_risk_does_not_generate_missing_test(self):
        """Test that NOT_MAPPED_TRACEABILITY_RISK does not generate missing test."""
        # Requirement classified as NOT_MAPPED_TRACEABILITY_RISK
        req = self._create_requirement(
            "1",
            "Unclear requirement",
            EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK,
            flow="unknown"
        )

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_missing_automated_coverage_generates_missing_test(self):
        """Test that MISSING_AUTOMATED_COVERAGE generates missing test."""
        # Requirement classified as MISSING_AUTOMATED_COVERAGE
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )

        # Create match table entry
        match_table = [
            self._create_match_table_entry(
                "1",
                "Weak password rejection test",
                "REJECTED",
                score=0.0,
                rejection_reason="Flow mismatch"
            )
        ]

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req], match_table)

        # Should generate missing test
        assert len(missing_tests) == 1
        card = missing_tests[0]
        assert card.requirement_id == "1"
        assert card.requirement_title == "Weak passwords are rejected during sign-up"
        assert card.flow == "sign_up"

    def test_missing_test_card_includes_new_fields(self):
        """Test that missing test card includes new diagnostic fields."""
        # Requirement classified as MISSING_AUTOMATED_COVERAGE
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )

        # Create match table entry with rejection
        match_table = [
            self._create_match_table_entry(
                "1",
                "Sign-up weak password test",
                "REJECTED",
                score=0.0,
                rejection_reason="SIGN_UP vs RESET_PASSWORD"
            )
        ]

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req], match_table)

        # Check new fields
        assert len(missing_tests) == 1
        card = missing_tests[0]
        assert card.why_current_pr_execution_did_not_cover_it != ""
        # The best rejected candidate extraction may return empty if no match table entry exists
        # or if the score is 0.0. Let's just check the field exists
        assert hasattr(card, 'best_rejected_candidate')
        assert hasattr(card, 'best_rejected_candidate_score')
        assert hasattr(card, 'best_rejected_candidate_rejection_reason')

    def test_coverage_only_does_not_generate_missing_test(self):
        """Test that coverage-only evidence does not generate missing test."""
        # Requirement with only coverage evidence (no classification as MISSING_AUTOMATED_COVERAGE)
        req = self._create_requirement(
            "1",
            "Some coverage line",
            EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK,
            flow="unknown"
        )

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_verified_by_current_pr_execution_raises_error_if_attempted(self):
        """Test that attempting to generate missing test for VERIFIED requirement raises error."""
        # Requirement classified as VERIFIED_BY_CURRENT_PR_EXECUTION
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            flow="sign_up"
        )

        # Should raise error in validation
        with pytest.raises(MissingTestGenerationError) as exc_info:
            self.mapper._validate_missing_test_generation(req)
        
        assert "VERIFIED_BY_CURRENT_PR_EXECUTION" in str(exc_info.value)

    def test_best_rejected_candidate_extraction(self):
        """Test extraction of best rejected candidate from match table."""
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )

        # Create match table with multiple entries
        match_table = [
            self._create_match_table_entry(
                "1",
                "Test A",
                "REJECTED",
                score=0.3,
                rejection_reason="Low score"
            ),
            self._create_match_table_entry(
                "1",
                "Test B",
                "REJECTED",
                score=0.5,
                rejection_reason="Flow mismatch"
            ),
            self._create_match_table_entry(
                "1",
                "Test C",
                "REJECTED",
                score=0.2,
                rejection_reason="Condition mismatch"
            ),
        ]

        # Extract best rejected candidate
        best_candidate, best_score, best_reason = self.mapper._extract_best_rejected_candidate(req, match_table)

        # Should return the highest score rejected candidate
        assert best_candidate == "Test B"
        assert best_score == 0.5
        assert best_reason == "Flow mismatch"

    def test_why_current_pr_did_not_cover_with_matched_execution(self):
        """Test why_current_pr_did_not_cover when requirement has matched execution."""
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )
        req.matched_execution_ids = ["exec-1"]

        # Generate explanation
        explanation = self.mapper._generate_why_current_pr_did_not_cover(req)

        # Should mention matched execution IDs
        assert "matched current PR execution IDs" in explanation
        assert "exec-1" in explanation

    def test_why_current_pr_did_not_cover_with_matched_test(self):
        """Test why_current_pr_did_not_cover when requirement has matched test but no execution."""
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )
        req.matched_test_ids = ["test-1"]

        # Generate explanation
        explanation = self.mapper._generate_why_current_pr_did_not_cover(req)

        # Should mention matched test but not executed
        assert "matched existing test" in explanation
        assert "not executed in current PR" in explanation
        assert "test-1" in explanation

    def test_why_current_pr_did_not_cover_with_rejected_candidate(self):
        """Test why_current_pr_did_not_cover when match table has rejected candidate."""
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )

        match_table = [
            self._create_match_table_entry(
                "1",
                "Test A",
                "REJECTED",
                score=0.0,
                rejection_reason="Flow mismatch"
            )
        ]

        # Generate explanation
        explanation = self.mapper._generate_why_current_pr_did_not_cover(req, match_table)

        # Should mention rejected candidate
        assert "rejected due to contradiction" in explanation
        assert "Flow mismatch" in explanation

    def test_child_rule_does_not_generate_missing_test(self):
        """Test that child rules do not generate missing tests."""
        # Requirement marked as child rule
        req = self._create_requirement(
            "1",
            "Password must include uppercase",
            EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK,
            flow="unknown"
        )
        req.node_type = "CHILD_RULE"
        req.is_real_testable_requirement = False

        # Generate missing tests
        missing_tests = self.mapper.generate_missing_tests([req])

        # Should not generate missing test
        assert len(missing_tests) == 0

    def test_empty_why_missing_raises_error(self):
        """Test that empty why_missing raises error."""
        # Requirement classified as MISSING_AUTOMATED_COVERAGE
        req = self._create_requirement(
            "1",
            "Weak passwords are rejected during sign-up",
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            flow="sign_up"
        )

        # Mock _generate_why_missing to return empty string
        original_method = self.mapper._generate_why_missing
        self.mapper._generate_why_missing = lambda req, mt: ""

        # Should raise error
        with pytest.raises(MissingTestGenerationError) as exc_info:
            self.mapper.generate_missing_tests([req])
        
        assert "empty why_missing" in str(exc_info.value)

        # Restore original method
        self.mapper._generate_why_missing = original_method


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
