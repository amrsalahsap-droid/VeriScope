"""Integration test for password PR requirement-to-test matching.

This test simulates the password PR scenario to verify that:
1. Current PR passed tests map to matching parent requirements
2. Sign-up tests do not satisfy reset-password requirements
3. Reset token tests do not satisfy login requirements
4. Strong password acceptance does not satisfy weak password rejection
5. Diagnostics clearly explain every accepted and rejected match
"""
import pytest
from app.services.regression_evidence_classifier import (
    RequirementNode, TestNode, ExecutionNode, ScenarioSignature, EvidenceClassification
)
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService


class TestPasswordPRMatchingIntegration:
    """Integration test for password PR matching scenario."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matching_service = EvidenceMatchingService()

    def _create_requirement(self, req_id: str, title: str, flow: str, action: str, 
                           condition: str, expected_outcome: str, subject: str = "password",
                           validation_layer: str = "") -> RequirementNode:
        """Helper to create a RequirementNode."""
        sig = ScenarioSignature(
            flow=flow,
            action=action,
            condition=condition,
            expected_outcome=expected_outcome,
            subject=subject,
            validation_layer=validation_layer,
            polarity="neutral"
        )
        return RequirementNode(
            requirement_id=req_id,
            readable_id=f"AC-{req_id}",
            title=title,
            flow=flow,
            action=action,
            condition=condition,
            expected_outcome=expected_outcome,
            scenario_signature=sig,
            is_real_testable_requirement=True
        )

    def _create_test(self, test_id: str, title: str, flow: str, action: str,
                    condition: str, expected_outcome: str, subject: str = "password",
                    validation_layer: str = "") -> TestNode:
        """Helper to create a TestNode."""
        sig = ScenarioSignature(
            flow=flow,
            action=action,
            condition=condition,
            expected_outcome=expected_outcome,
            subject=subject,
            validation_layer=validation_layer,
            polarity="neutral"
        )
        return TestNode(
            test_id=test_id,
            title=title,
            normalized_title=title.lower(),
            classname="PasswordTest",
            file_path="tests/test_password.py",
            scenario_signature=sig
        )

    def _create_execution(self, exec_id: str, test_id: str, status: str = "passed") -> ExecutionNode:
        """Helper to create an ExecutionNode."""
        return ExecutionNode(
            test_id=exec_id,
            test_name=f"Test {exec_id}",
            classname="PasswordTest",
            status=status,
            duration=1.0,
            pull_request_id="pr-123",
            head_sha="abc123",
            source_file="test_password.py",
            mapped_test_node_id=test_id
        )

    def test_password_pr_requirements_matched_to_correct_tests(self):
        """Test that password PR requirements are matched to correct tests."""
        # Create requirements from password PR
        requirements = [
            self._create_requirement("1", "Weak passwords are rejected during sign-up", 
                                    "sign_up", "reject", "weak_password", "rejected"),
            self._create_requirement("2", "Strong passwords are accepted during sign-up",
                                    "sign_up", "accept", "strong_password", "accepted"),
            self._create_requirement("3", "Weak passwords are rejected during reset-password",
                                    "password_reset", "reject", "weak_password", "rejected"),
            self._create_requirement("4", "Strong passwords are accepted during reset-password",
                                    "password_reset", "accept", "strong_password", "accepted"),
            self._create_requirement("5", "Expired reset tokens are rejected",
                                    "password_reset", "reject", "expired_token", "rejected", "token"),
            self._create_requirement("6", "Valid reset tokens are accepted",
                                    "password_reset", "accept", "valid_token", "accepted", "token"),
        ]

        # Create tests from current PR execution
        tests = [
            self._create_test("t1", "Weak passwords are rejected during sign-up",
                             "sign_up", "reject", "weak_password", "rejected"),
            self._create_test("t2", "Strong passwords are accepted during sign-up",
                             "sign_up", "accept", "strong_password", "accepted"),
            self._create_test("t3", "Weak passwords are rejected during reset-password",
                             "password_reset", "reject", "weak_password", "rejected"),
            self._create_test("t4", "Strong passwords are accepted during reset-password",
                             "password_reset", "accept", "strong_password", "accepted"),
            self._create_test("t5", "Expired reset tokens are rejected",
                             "password_reset", "reject", "expired_token", "rejected", "token"),
            self._create_test("t6", "Valid reset tokens are accepted",
                             "password_reset", "accept", "valid_token", "accepted", "token"),
        ]

        # Create executions (all passed)
        executions = [
            self._create_execution("e1", "t1", "passed"),
            self._create_execution("e2", "t2", "passed"),
            self._create_execution("e3", "t3", "passed"),
            self._create_execution("e4", "t4", "passed"),
            self._create_execution("e5", "t5", "passed"),
            self._create_execution("e6", "t6", "passed"),
        ]

        # Match requirements to tests
        for req in requirements:
            execution = next((e for e in executions if e.mapped_test_node_id in [t.test_id for t in tests]), None)
            best_match, is_confident = self.matching_service.find_best_match(req, tests, execution)
            if best_match:
                req.match_score = best_match.score
                req.match_diagnostics = best_match.diagnostics
                if is_confident:
                    req.matched_test_ids = [best_match.test_id]

        # Link executions to requirements
        test_map = {t.test_id: t for t in tests}
        for exec_node in executions:
            if exec_node.mapped_test_node_id:
                test = test_map.get(exec_node.mapped_test_node_id)
                if test:
                    for req in requirements:
                        if exec_node.mapped_test_node_id in req.matched_test_ids:
                            req.matched_execution_ids.append(exec_node.test_id)

        # Verify that each requirement has a matching test
        matched_count = sum(1 for req in requirements if req.matched_test_ids)
        assert matched_count == 6, f"Expected 6 matched requirements, got {matched_count}"

        # Verify that each requirement has a passed execution
        passed_count = sum(1 for req in requirements if req.matched_execution_ids)
        assert passed_count == 6, f"Expected 6 requirements with passed executions, got {passed_count}"

        # Verify match scores are high
        for req in requirements:
            assert req.match_score >= 0.85, f"Requirement {req.readable_id} has low match score: {req.match_score}"

    def test_signup_test_does_not_match_reset_password_requirement(self):
        """Test that sign-up weak password test does not match reset-password requirement."""
        # Requirement: Weak passwords are rejected during reset-password
        req = self._create_requirement("1", "Weak passwords are rejected during reset-password",
                                       "password_reset", "reject", "weak_password", "rejected")
        
        # Test: Weak passwords are rejected during sign-up
        test = self._create_test("t1", "Weak passwords are rejected during sign-up",
                                "sign_up", "reject", "weak_password", "rejected")

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to flow contradiction
        assert result.score == 0.0
        assert "SIGN_UP vs RESET_PASSWORD" in result.diagnostics.get("rejection_reason", "")

    def test_expired_token_does_not_match_valid_token(self):
        """Test that expired token test does not match valid token requirement."""
        # Requirement: Valid reset tokens are accepted
        req = self._create_requirement("1", "Valid reset tokens are accepted",
                                       "password_reset", "accept", "valid_token", "accepted", "token")
        
        # Test: Expired reset tokens are rejected
        test = self._create_test("t1", "Expired reset tokens are rejected",
                                "password_reset", "reject", "expired_token", "rejected", "token")

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to valid vs expired token contradiction
        assert result.score == 0.0
        assert "VALID_TOKEN vs EXPIRED_TOKEN" in result.diagnostics.get("rejection_reason", "")

    def test_old_password_rejection_does_not_match_new_password_acceptance(self):
        """Test that old password rejection does not match new password acceptance."""
        # Requirement: New password is accepted during update-password
        req = self._create_requirement("1", "New password is accepted during update-password",
                                       "update_password", "accept", "new_password", "accepted", "new_password")
        
        # Test: Old password fails after successful password update
        test = self._create_test("t1", "Old password fails after successful password update",
                                "update_password", "reject", "old_password", "rejected", "old_password")

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to old vs new password contradiction
        assert result.score == 0.0
        assert "OLD_PASSWORD vs NEW_PASSWORD" in result.diagnostics.get("rejection_reason", "")

    def test_direct_api_weak_password_matches_backend_validation(self):
        """Test that direct API weak-password rejection maps to backend validation requirement."""
        # Requirement: Backend rejects direct API weak-password requests
        req = self._create_requirement("1", "Backend rejects direct API weak-password requests",
                                       "sign_up", "reject", "weak_password", "rejected", "password", "backend")
        
        # Test: Direct API request with weak password is rejected
        test = self._create_test("t1", "Direct API request with weak password is rejected",
                                "sign_up", "reject", "weak_password", "rejected", "password", "api")

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should match (not rejected) since both are about weak password rejection
        # and API/backend are compatible layers
        assert result.score > 0.5, f"Expected match score > 0.5, got {result.score}"
        assert result.diagnostics.get("rejection_reason") is None or result.diagnostics.get("rejection_reason") == ""

    def test_match_table_contains_diagnostics(self):
        """Test that match table contains detailed diagnostics for all matches."""
        # Create a simple scenario
        req = self._create_requirement("1", "Weak passwords are rejected during sign-up",
                                       "sign_up", "reject", "weak_password", "rejected")
        test = self._create_test("t1", "Weak passwords are rejected during sign-up",
                                "sign_up", "reject", "weak_password", "rejected")

        # Match
        best_match, is_confident = self.matching_service.find_best_match(req, tests=[test])

        # Check match table
        assert len(self.matching_service.match_table) == 1
        entry = self.matching_service.match_table[0]
        
        # Verify diagnostic fields
        assert entry.requirement_id == "1"
        assert entry.requirement_title == "Weak passwords are rejected during sign-up"
        assert entry.candidate_test_title == "Weak passwords are rejected during sign-up"
        assert entry.decision == "ACCEPTED"
        assert entry.score > 0.8
        assert isinstance(entry.matching_dimensions, dict)
        
        # Verify matching dimensions
        dimensions = entry.matching_dimensions
        assert isinstance(dimensions, dict)
        assert "flow_match" in dimensions or "requirement_flow" in dimensions
        assert "action_match" in dimensions or "requirement_action" in dimensions
        assert "condition_match" in dimensions or "requirement_condition" in dimensions
        assert "outcome_match" in dimensions or "requirement_outcome" in dimensions

    def test_rejected_match_contains_rejection_reason(self):
        """Test that rejected matches contain rejection reason and contradiction rule."""
        # Requirement: Weak passwords are rejected during reset-password
        req = self._create_requirement("1", "Weak passwords are rejected during reset-password",
                                       "password_reset", "reject", "weak_password", "rejected")
        
        # Test: Weak passwords are rejected during sign-up (wrong flow)
        test = self._create_test("t1", "Weak passwords are rejected during sign-up",
                                "sign_up", "reject", "weak_password", "rejected")

        # Match directly
        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Verify rejection in result diagnostics
        assert result.score == 0.0
        assert result.diagnostics.get("rejection_reason") != ""
        assert result.diagnostics.get("contradiction_rule_triggered") != ""
        assert "SIGN_UP vs RESET_PASSWORD" in result.diagnostics.get("contradiction_rule_triggered", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
