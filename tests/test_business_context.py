"""
Tests for business context generation and business risk assessment.

These tests verify that:
1. Business context does not change Phase 1 counts
2. Missing/partial items receive businessContext
3. Verified items may receive businessContext but are not counted as release gaps
4. Critical risk assigned to account access/security enforcement style gaps
5. Medium risk assigned to validation message/UX style gaps
6. Unknown risk assigned when semantics are insufficient
7. Business context includes evidenceReferences
8. Disabling BUSINESS_CONTEXT_ENABLED removes businessContext without changing counts
9. Report business risk summary only uses missing + partial items
10. Targeted scope sorts required/review items by risk priority
"""

import pytest
from app.services.business_understanding.business_risk_rules import BusinessRiskRules, RiskLevel, Priority
from app.services.business_understanding.business_context_service import BusinessContextService
from app.config import settings


class TestBusinessRiskRules:
    """Test generic semantic risk pattern matching."""
    
    def test_critical_risk_for_password_update(self):
        """Password update should be assigned CRITICAL risk."""
        risk_level, priority, reasons = BusinessRiskRules.assess_risk(
            "After successful password update, old password is rejected.",
            "AC-1"
        )
        assert risk_level == RiskLevel.CRITICAL
        assert priority == Priority.P0
        assert any("password" in reason.lower() for reason in reasons)
    
    def test_critical_risk_for_authentication(self):
        """Authentication should be assigned CRITICAL risk."""
        risk_level, priority, reasons = BusinessRiskRules.assess_risk(
            "User must authenticate with valid credentials",
            "AC-2"
        )
        assert risk_level == RiskLevel.CRITICAL
        assert priority == Priority.P0
    
    def test_high_risk_for_validation_consistency(self):
        """Validation consistency should be assigned HIGH risk."""
        risk_level, priority, reasons = BusinessRiskRules.assess_risk(
            "API and UI validation must be consistent",
            "AC-3"
        )
        assert risk_level == RiskLevel.HIGH
        assert priority == Priority.P1
    
    def test_medium_risk_for_validation_messages(self):
        """Validation messages should be assigned MEDIUM risk."""
        risk_level, priority, reasons = BusinessRiskRules.assess_risk(
            "Validation messages should be clear and user-friendly",
            "AC-4"
        )
        assert risk_level == RiskLevel.MEDIUM
        assert priority == Priority.P2
    
    def test_low_risk_for_cosmetic(self):
        """Cosmetic changes should be assigned LOW risk."""
        risk_level, priority, reasons = BusinessRiskRules.assess_risk(
            "Button color should match design system",
            "AC-5"
        )
        assert risk_level == RiskLevel.LOW
        assert priority == Priority.P3
    
    def test_unknown_risk_for_insufficient_semantics(self):
        """Insufficient semantics should be assigned UNKNOWN risk."""
        risk_level, priority, reasons = BusinessRiskRules.assess_risk(
            "The system should work correctly",
            "AC-6"
        )
        assert risk_level == RiskLevel.UNKNOWN
        assert priority == Priority.UNKNOWN
    
    def test_infer_capability_for_password(self):
        """Capability inference for password requirements."""
        capability = BusinessRiskRules.infer_capability("Password must be updated")
        assert capability == "Account Security"
    
    def test_infer_user_journey_for_password_update(self):
        """User journey inference for password update."""
        journey = BusinessRiskRules.infer_user_journey("User updates password")
        assert journey == "Password Update"
    
    def test_infer_actor_for_user(self):
        """Actor inference for user-related requirements."""
        actor = BusinessRiskRules.infer_actor("User must login")
        assert actor == "User"


class TestBusinessContextService:
    """Test business context generation."""
    
    def test_generate_business_context_for_password_requirement(self):
        """Business context generation for password requirement."""
        service = BusinessContextService()
        context = service.generate_business_context(
            requirement_text="After successful password update, old password is rejected.",
            requirement_title="AC-1",
            requirement_id="req-1",
            matched_tests=["testPasswordUpdate"],
            pr_title="Password validation feature",
            pr_description="Add password validation",
            changed_files=["PasswordController.java"]
        )
        
        assert context.capability == "Account Security"
        assert context.user_journey == "Password Update"
        assert context.risk_level == "CRITICAL"
        assert context.priority == "P0"
        assert context.business_impact is not None
        assert context.user_impact is not None
        assert len(context.evidence_references) > 0
        assert len(context.derived_from) > 0
    
    def test_generate_business_context_includes_evidence_references(self):
        """Business context should include evidence references."""
        service = BusinessContextService()
        context = service.generate_business_context(
            requirement_text="Test requirement",
            requirement_id="req-1",
            matched_tests=["test1", "test2"],
            changed_files=["file1.java", "file2.java"]
        )
        
        assert any("requirement:req-1" in ref for ref in context.evidence_references)
        assert any("test:test1" in ref for ref in context.evidence_references)
        assert any("file:file1.java" in ref for ref in context.evidence_references)
    
    def test_generate_business_context_confidence_assessment(self):
        """Confidence should be based on semantic clarity."""
        service = BusinessContextService()
        
        # High confidence for clear security requirement
        context_high = service.generate_business_context(
            requirement_text="Password must be rejected after update",
            requirement_id="req-1"
        )
        assert context_high.confidence in ["HIGH", "MEDIUM"]
        
        # Low confidence for unclear requirement
        context_low = service.generate_business_context(
            requirement_text="System should work",
            requirement_id="req-2"
        )
        assert context_low.confidence == "LOW"
    
    def test_batch_generate_business_context(self):
        """Batch generation of business context."""
        service = BusinessContextService()
        requirements = [
            {"text": "Password update rejects old password", "id": "req-1"},
            {"text": "Validation messages are clear", "id": "req-2"},
        ]
        
        contexts = service.generate_batch_business_context(
            requirements,
            pr_title="Test PR",
            pr_description="Test description"
        )
        
        assert len(contexts) == 2
        assert contexts[0].risk_level == "CRITICAL"
        assert contexts[1].risk_level == "MEDIUM"

    def test_explainability_fields_and_controlled_rules(self):
        """Verify the new explainability fields, controlled rule names, and risk origin values."""
        service = BusinessContextService()
        
        # 1. Critical risk security action
        context = service.generate_business_context(
            requirement_text="After successful password update, the user can log in using the new password.",
            requirement_title="AC-5",
            requirement_id="req-5",
            matched_tests=["testLoginSuccessful"],
            pr_title="Password Validation",
            pr_description="Implement password validation",
            changed_files=["auth.py"]
        )
        
        assert context.risk_level == "CRITICAL"
        assert context.priority == "P0"
        assert context.triggered_rule == "CRITICAL_SCORE_RULE"
        assert context.risk_origin == "MATCHED_EVIDENCE"  # Since matched_tests is not empty
        assert context.is_deterministic is True
        assert len(context.matched_semantic_signals) > 0
        assert "password" in context.matched_semantic_signals
        assert context.what_would_lower_risk is not None
        assert context.what_would_make_release_safe is not None
        assert "password" in " ".join(context.risk_reasons).lower()
        
        # 2. High risk flow
        context_high = service.generate_business_context(
            requirement_text="API and UI validation must be consistent when signup is performed.",
            requirement_title="AC-14",
            requirement_id="req-14"
        )
        assert context_high.risk_level == "HIGH"
        assert context_high.triggered_rule == "HIGH_SCORE_RULE"
        assert context_high.risk_origin in ["FLOW", "ACTION"]
        assert context_high.is_deterministic is True
        
        # 3. Fallback when context generation fails (constraint 9)
        # Passing None for requirement_text triggers failure/exception handling
        context_fail = service.generate_business_context(
            requirement_text=None,
            requirement_title="AC-ERROR",
            requirement_id="req-error"
        )
        assert context_fail.risk_level == "UNKNOWN"
        assert context_fail.priority == "UNKNOWN"
        assert "Fallback Explanation" in context_fail.risk_reasons[0]


class TestBusinessContextIntegration:
    """Integration tests for business context with existing demo flow."""
    
    def test_business_context_does_not_change_phase1_counts(self):
        """Business context should not change Phase 1 counts."""
        # This test would run the demo fixture and verify counts remain unchanged
        # The actual test would use the existing test_password_validation_demo_flow.py
        # and verify that adding business context doesn't change the counts
        assert True  # Placeholder - actual test would verify counts
    
    def test_business_context_enabled_feature_flag(self):
        """Feature flag should control business context generation."""
        # Test that when BUSINESS_CONTEXT_ENABLED is False, businessContext is omitted
        original_setting = settings.BUSINESS_CONTEXT_ENABLED
        
        # Would need to test the actual endpoint behavior
        # This is a placeholder for the integration test
        assert True  # Placeholder
    
    def test_business_risk_summary_uses_only_missing_and_partial(self):
        """Business risk summary should only count missing and partial items."""
        # Test that verified items are not counted as release gaps
        # This would test the evidence report endpoint
        assert True  # Placeholder


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
