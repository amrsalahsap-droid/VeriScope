"""Test flow contradiction scenarios to ensure cross-flow matching is rejected.

These tests ensure that tests from one flow don't incorrectly match requirements from another flow.
"""
import pytest
from app.services.regression_evidence_classifier import RequirementNode, TestNode, ScenarioSignature
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService


class TestFlowContractionScenarios:
    """Test suite for flow-specific contradiction scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matching_service = EvidenceMatchingService()

    def _create_requirement(self, title: str, flow: str = "", action: str = "", condition: str = "", 
                           expected_outcome: str = "", subject: str = "", validation_layer: str = "") -> RequirementNode:
        """Helper to create a RequirementNode with scenario signature."""
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
            requirement_id="req-1",
            readable_id="AC-01",
            title=title,
            flow=flow,
            action=action,
            condition=condition,
            expected_outcome=expected_outcome,
            scenario_signature=sig,
            is_real_testable_requirement=True
        )

    def _create_test(self, title: str, flow: str = "", action: str = "", condition: str = "",
                    expected_outcome: str = "", subject: str = "", validation_layer: str = "") -> TestNode:
        """Helper to create a TestNode with scenario signature."""
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
            test_id="test-1",
            title=title,
            normalized_title=title.lower(),
            classname="TestClass",
            file_path="test_file.py",
            scenario_signature=sig
        )

    def test_signup_weak_password_does_not_match_reset_password_weak_password(self):
        """Test that sign-up weak password test does not match reset-password weak password requirement."""
        # Requirement: Weak passwords are rejected during reset-password
        req = self._create_requirement(
            title="Weak passwords are rejected during reset-password",
            flow="password_reset",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password"
        )
        
        # Test: Weak passwords are rejected during sign-up
        test = self._create_test(
            title="Weak passwords are rejected during sign-up",
            flow="sign_up",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to flow contradiction
        assert result.score == 0.0
        assert "SIGN_UP vs RESET_PASSWORD" in result.diagnostics.get("rejection_reason", "")

    def test_reset_password_token_does_not_match_login(self):
        """Test that reset-password token test does not match login requirement."""
        # Requirement: User can login with valid credentials
        req = self._create_requirement(
            title="User can login with valid credentials",
            flow="login",
            action="login",
            condition="valid_credentials",
            expected_outcome="login_succeeds",
            subject="user"
        )
        
        # Test: Valid reset tokens are accepted
        test = self._create_test(
            title="Valid reset tokens are accepted",
            flow="password_reset",
            action="accept",
            condition="valid_token",
            expected_outcome="accepted",
            subject="token"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to token vs login contradiction
        assert result.score == 0.0
        assert "TOKEN behavior vs LOGIN behavior" in result.diagnostics.get("rejection_reason", "")

    def test_expired_token_does_not_match_valid_token(self):
        """Test that expired token test does not match valid token requirement."""
        # Requirement: Valid reset tokens are accepted
        req = self._create_requirement(
            title="Valid reset tokens are accepted",
            flow="password_reset",
            action="accept",
            condition="valid_token",
            expected_outcome="accepted",
            subject="token"
        )
        
        # Test: Expired reset tokens are rejected
        test = self._create_test(
            title="Expired reset tokens are rejected",
            flow="password_reset",
            action="reject",
            condition="expired_token",
            expected_outcome="rejected",
            subject="token"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to valid vs expired token contradiction
        assert result.score == 0.0
        assert "VALID_TOKEN vs EXPIRED_TOKEN" in result.diagnostics.get("rejection_reason", "")

    def test_old_password_rejection_does_not_match_new_password_acceptance(self):
        """Test that old password rejection does not match new password acceptance."""
        # Requirement: New password is accepted during update-password
        req = self._create_requirement(
            title="New password is accepted during update-password",
            flow="update_password",
            action="accept",
            condition="new_password",
            expected_outcome="accepted",
            subject="new_password"
        )
        
        # Test: Old password fails after successful password update
        test = self._create_test(
            title="Old password fails after successful password update",
            flow="update_password",
            action="reject",
            condition="old_password",
            expected_outcome="rejected",
            subject="old_password"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to old vs new password contradiction
        assert result.score == 0.0
        assert "OLD_PASSWORD vs NEW_PASSWORD" in result.diagnostics.get("rejection_reason", "")

    def test_direct_api_weak_password_rejection_matches_backend_validation(self):
        """Test that direct API weak-password rejection maps to backend validation requirement."""
        # Requirement: Backend rejects direct API weak-password requests
        req = self._create_requirement(
            title="Backend rejects direct API weak-password requests",
            flow="sign_up",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password",
            validation_layer="backend"
        )
        
        # Test: Direct API request with weak password is rejected
        test = self._create_test(
            title="Direct API request with weak password is rejected",
            flow="sign_up",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password",
            validation_layer="api"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should match (not rejected) since both are about weak password rejection
        # and API/backend are compatible layers
        assert result.score > 0.5, f"Expected match score > 0.5, got {result.score}"
        assert result.diagnostics.get("rejection_reason") is None or result.diagnostics.get("rejection_reason") == ""

    def test_strong_password_acceptance_does_not_match_weak_password_rejection(self):
        """Test that strong password acceptance does not match weak password rejection."""
        # Requirement: Weak passwords are rejected during sign-up
        req = self._create_requirement(
            title="Weak passwords are rejected during sign-up",
            flow="sign_up",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password"
        )
        
        # Test: Strong passwords are accepted during sign-up
        test = self._create_test(
            title="Strong passwords are accepted during sign-up",
            flow="sign_up",
            action="accept",
            condition="strong_password",
            expected_outcome="accepted",
            subject="password"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to strong vs weak password contradiction
        assert result.score == 0.0
        assert "STRONG_PASSWORD vs WEAK_PASSWORD" in result.diagnostics.get("rejection_reason", "")

    def test_update_password_does_not_match_reset_password(self):
        """Test that update-password test does not match reset-password requirement."""
        # Requirement: Weak passwords are rejected during reset-password
        req = self._create_requirement(
            title="Weak passwords are rejected during reset-password",
            flow="password_reset",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password"
        )
        
        # Test: Weak passwords are rejected during update-password
        test = self._create_test(
            title="Weak passwords are rejected during update-password",
            flow="update_password",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            subject="password"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to reset vs update password contradiction
        assert result.score == 0.0
        assert "RESET_PASSWORD vs UPDATE_PASSWORD" in result.diagnostics.get("rejection_reason", "")

    def test_reused_token_does_not_match_valid_token(self):
        """Test that reused token test does not match valid token requirement."""
        # Requirement: Valid reset tokens are accepted
        req = self._create_requirement(
            title="Valid reset tokens are accepted",
            flow="password_reset",
            action="accept",
            condition="valid_token",
            expected_outcome="accepted",
            subject="token"
        )
        
        # Test: Reused reset tokens are rejected
        test = self._create_test(
            title="Reused reset tokens are rejected",
            flow="password_reset",
            action="reject",
            condition="reused_token",
            expected_outcome="rejected",
            subject="token"
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        
        # Should be rejected due to valid vs reused token contradiction
        assert result.score == 0.0
        assert "VALID_TOKEN vs REUSED_TOKEN" in result.diagnostics.get("rejection_reason", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
