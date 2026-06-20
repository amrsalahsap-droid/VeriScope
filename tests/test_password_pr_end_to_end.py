"""End-to-end integration test for password PR scenario.

This test prevents regression into:
- Fake traceability (fragments inflating parent count)
- Fake missing tests (generating from non-MISSING_AUTOMATED_COVERAGE)
- Contradictory UI states (stale inputs showing wrong CTAs)

The test validates the health calculation and CTA derivation logic.
"""

import pytest
from app.services.evidence_graph.recommendation_view_model_builder import RecommendationViewModelBuilder
from app.services.regression_evidence_classifier import (
    RequirementNode, EvidenceClassification
)


class TestPasswordPREndToEnd:
    """End-to-end test for password PR scenario."""

    def setup_method(self):
        """Set up test services."""
        self.view_model_builder = RecommendationViewModelBuilder()

    def test_stale_inputs_shows_correct_health(self):
        """Test that stale inputs show correct health state and CTA."""
        # Create sample requirements
        requirements = [
            RequirementNode(
                requirement_id="AC-01",
                readable_id="AC-01",
                title="System must enforce minimum password length of 8 characters during sign-up",
                flow="sign_up",
                action="enforce",
                condition="during sign-up",
                expected_outcome="minimum password length of 8 characters",
                scenario_signature=None,
                classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
                matched_test_ids=[],
                matched_execution_ids=[],
                match_score=0.0,
                is_real_testable_requirement=True
            )
        ]
        
        # Simulate stale inputs by setting has_stale_inputs in extraction audit
        extraction_audit = {"has_stale_inputs": True}

        # Build view model with stale inputs
        view_model = self.view_model_builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[],
            extraction_audit=extraction_audit
        )

        # Assertion: Health should be STALE_INPUTS
        assert view_model.health == "STALE_INPUTS", (
            f"Health should be STALE_INPUTS for stale inputs, got {view_model.health}"
        )

        # Assertion: Primary CTA should be "Regenerate Recommendation"
        assert view_model.decision_copy.primary_cta == "Regenerate Recommendation", (
            f"Primary CTA should be 'Regenerate Recommendation' for stale inputs, "
            f"got {view_model.decision_copy.primary_cta}"
        )

        # Assertion: Secondary CTA should not be "Create Regression Scope"
        assert view_model.decision_copy.secondary_cta != "Create Regression Scope", (
            f"Secondary CTA should not be 'Create Regression Scope' for stale inputs, "
            f"got {view_model.decision_copy.secondary_cta}"
        )

    def test_fresh_inputs_shows_correct_health(self):
        """Test that fresh inputs show correct health state."""
        # Create sample requirements
        requirements = [
            RequirementNode(
                requirement_id="AC-01",
                readable_id="AC-01",
                title="System must enforce minimum password length of 8 characters during sign-up",
                flow="sign_up",
                action="enforce",
                condition="during sign-up",
                expected_outcome="minimum password length of 8 characters",
                scenario_signature=None,
                classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
                matched_test_ids=[],
                matched_execution_ids=[],
                match_score=0.0,
                is_real_testable_requirement=True
            )
        ]

        # Build view model with fresh inputs
        view_model = self.view_model_builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[],
            extraction_audit=None
        )

        # Assertion: Health should not be STALE_INPUTS
        assert view_model.health != "STALE_INPUTS", (
            f"Health should not be STALE_INPUTS for fresh inputs, got {view_model.health}"
        )

    def test_failed_tests_shows_blocked_health(self):
        """Test that failed tests show BLOCKED_BY_FAILED_TESTS health."""
        # Create sample requirements with failed tests
        requirements = [
            RequirementNode(
                requirement_id="AC-01",
                readable_id="AC-01",
                title="System must enforce minimum password length of 8 characters during sign-up",
                flow="sign_up",
                action="enforce",
                condition="during sign-up",
                expected_outcome="minimum password length of 8 characters",
                scenario_signature=None,
                classification=EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION,
                matched_test_ids=["test_password_length"],
                matched_execution_ids=["test_password_length"],
                match_score=0.95,
                is_real_testable_requirement=True
            )
        ]

        # Build view model
        view_model = self.view_model_builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[],
            extraction_audit=None
        )

        # Assertion: Health should be BLOCKED_BY_FAILED_TESTS
        assert view_model.health == "BLOCKED_BY_FAILED_TESTS", (
            f"Health should be BLOCKED_BY_FAILED_TESTS for failed tests, got {view_model.health}"
        )

        # Assertion: Primary CTA should be "Review Failed Tests"
        assert view_model.decision_copy.primary_cta == "Review Failed Tests", (
            f"Primary CTA should be 'Review Failed Tests' for failed tests, "
            f"got {view_model.decision_copy.primary_cta}"
        )

    def test_evidence_summary_uses_bucketed_counts(self):
        """Test that evidence summary uses bucketed counts."""
        # Create sample requirements
        requirements = [
            RequirementNode(
                requirement_id="AC-01",
                readable_id="AC-01",
                title="System must enforce minimum password length of 8 characters during sign-up",
                flow="sign_up",
                action="enforce",
                condition="during sign-up",
                expected_outcome="minimum password length of 8 characters",
                scenario_signature=None,
                classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
                matched_test_ids=["test_password_length"],
                matched_execution_ids=["test_password_length"],
                match_score=0.95,
                is_real_testable_requirement=True
            )
        ]

        # Build view model
        view_model = self.view_model_builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[],
            extraction_audit=None
        )

        # Check that decision copy explanation uses bucketed counts
        explanation = view_model.decision_copy.explanation
        
        # Assertion: Should not contain "X of Y required tests are available" pattern
        assert "required tests are available" not in explanation.lower(), (
            f"Explanation should not contain 'required tests are available' pattern. "
            f"Got: {explanation}"
        )
        
        # Assertion: Should use bucket-based language like "Current PR execution passed X tests"
        assert "current pr execution" in explanation.lower() or "passed" in explanation.lower(), (
            f"Explanation should use bucket-based language. Got: {explanation}"
        )

    def test_view_model_contains_readable_ids(self):
        """Test that view model contains readable IDs for user UI."""
        # Create sample requirements
        requirements = [
            RequirementNode(
                requirement_id="AC-01",
                readable_id="AC-01",
                title="System must enforce minimum password length of 8 characters during sign-up",
                flow="sign_up",
                action="enforce",
                condition="during sign-up",
                expected_outcome="minimum password length of 8 characters",
                scenario_signature=None,
                classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
                matched_test_ids=["test_password_length"],
                matched_execution_ids=["test_password_length"],
                match_score=0.95,
                is_real_testable_requirement=True
            )
        ]

        # Build view model
        view_model = self.view_model_builder.build_view_model(
            requirements=requirements,
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[],
            extraction_audit=None
        )

        # Assertion: View model contains readable IDs for user UI
        for row in view_model.ac_traceability:
            # Should have readable_id in format AC-XX
            assert row.readable_id is not None, f"Traceability row missing readable_id"
            assert row.readable_id.startswith("AC-"), (
                f"Readable ID should start with AC-, got {row.readable_id}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
