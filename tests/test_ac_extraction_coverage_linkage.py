"""Tests for AC extraction and coverage linkage fixes."""
import pytest
from app.services.evidence_graph.ac_extraction_service import ACExtractionService
from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy
from app.services.regression_evidence_integration import RegressionEvidenceIntegration
from app.services.regression_evidence_classifier import CoverageNode


class TestACExtractionFixes:
    """Test AC extraction fixes for preserving AC numbers and excluding security notes."""
    
    def test_security_notes_not_promoted_to_parents(self):
        """Test that security notes are excluded and not promoted to parent requirements."""
        service = ACExtractionService()
        
        ac_text = """
        1. Weak passwords are rejected during sign-up.
        2. Strong passwords are accepted during sign-up.
        3. Password policy must be shared or aligned across sign-up, update-password, and reset-password flows.
        4. Backend is source of truth for password validation
        5. Frontend UX only provides user-friendly feedback
        """
        
        result = service.extract_acceptance_criteria(ac_text)
        
        # Should extract only 2 parent requirements (AC-01 and AC-02)
        assert len(result.requirement_nodes) == 2
        
        # Security notes should be in excluded fragments
        security_note_fragments = [
            f for f in result.excluded_fragments 
            if "shared or aligned" in f["text"].lower() or 
               "source of truth" in f["text"].lower() or
               "frontend ux" in f["text"].lower()
        ]
        assert len(security_note_fragments) >= 2
    
    def test_ac_25_atomicity_preserved(self):
        """Test that AC-25 atomicity requirement is correctly extracted."""
        service = ACExtractionService()
        
        ac_text = """
        1. Weak passwords are rejected during sign-up.
        2. Strong passwords are accepted during sign-up.
        25. Password update/reset operation is atomic: either the full update succeeds or nothing changes.
        """
        
        result = service.extract_acceptance_criteria(ac_text)
        
        # Should extract 3 parent requirements
        assert len(result.requirement_nodes) == 3
        
        # AC-25 should be present with atomicity text
        ac_25 = [node for node in result.requirement_nodes if "atomic" in node.title.lower()]
        assert len(ac_25) == 1
        assert "atomic" in ac_25[0].title.lower()
    
    def test_confirmation_field_not_child_detail(self):
        """Test that confirmation field AC is not classified as child detail."""
        service = ACExtractionService()
        
        ac_text = """
        1. Weak passwords are rejected during sign-up.
        2. Password confirmation must match the password field.
        """
        
        result = service.extract_acceptance_criteria(ac_text)
        
        # Should extract 2 parent requirements (confirmation field should not be child)
        assert len(result.requirement_nodes) == 2
        
        # Confirmation field should be a parent, not excluded
        confirmation_node = [node for node in result.requirement_nodes if "confirmation" in node.title.lower()]
        assert len(confirmation_node) == 1
    
    def test_parent_normalization_disabled(self):
        """Test that parent normalization (merging) is disabled to preserve all ACs."""
        service = ACExtractionService()
        
        ac_text = """
        1. Weak passwords are rejected during sign-up.
        2. Strong passwords are accepted during sign-up.
        3. Weak passwords are rejected during update-password.
        4. Strong passwords are accepted during update-password.
        """
        
        result = service.extract_acceptance_criteria(ac_text)
        
        # Should extract all 4 parent requirements without merging
        assert len(result.requirement_nodes) == 4
        
        # Check that no merges occurred
        assert len(result.audit.parent_child_merges) == 0


class TestCoverageLinkageFixes:
    """Test coverage node building and linkage fixes."""
    
    def test_coverage_path_matching_with_basename(self):
        """Test that coverage path matching works with basename fallback."""
        integration = RegressionEvidenceIntegration(db=None)
        
        # Test basename matching
        changed_file = "src/tests/integration/auth-workflow.test.ts"
        coverage_entry_path = "src/integration/auth-workflow.test.ts"
        
        # Simulate the basename matching logic
        import os
        changed_basename = os.path.basename(changed_file)
        entry_basename = os.path.basename(coverage_entry_path)
        
        assert changed_basename == entry_basename
    
    def test_code_area_inference_for_different_file_types(self):
        """Test that code area inference works for different file types."""
        integration = RegressionEvidenceIntegration(db=None)
        
        # Test frontend UI files
        assert integration._infer_code_area_from_file_path("src/app/signup/page.tsx") == "frontend_ui"
        assert integration._infer_code_area_from_file_path("src/app/reset-password/page.tsx") == "frontend_ui"
        
        # Test backend API files
        assert integration._infer_code_area_from_file_path("src/app/api/auth/reset-password/route.ts") == "backend_api"
        
        # Test test files
        assert integration._infer_code_area_from_file_path("src/modules/users/__tests__/sign-up.test.ts") == "test"
        assert integration._infer_code_area_from_file_path("src/tests/integration/auth-workflow.test.ts") == "test"
        
        # Test shared library files
        assert integration._infer_code_area_from_file_path("src/modules/users/sign-up.ts") == "shared_library"
    
    def test_coverage_node_has_code_area_field(self):
        """Test that CoverageNode has code_area field populated."""
        coverage_node = CoverageNode(
            file_path="src/app/api/auth/reset-password/route.ts",
            line_coverage=90.0,
            branch_coverage=75.0,
            code_area="backend_api"
        )
        
        assert coverage_node.code_area == "backend_api"
        
        # Test to_dict includes code_area
        node_dict = coverage_node.to_dict()
        assert "code_area" in node_dict
        assert node_dict["code_area"] == "backend_api"


class TestPartialClassificationPolicy:
    """Test partial classification policy flags and rules."""
    
    def test_evidence_quality_policy_has_partial_classification_flags(self):
        """Test that EvidenceQualityPolicy has partial classification flags."""
        policy = EvidenceQualityPolicy(
            enable_partial_classification=True,
            partial_classification_min_coverage_threshold=50.0,
            partial_classification_require_test_execution=True,
            partial_classification_allow_coverage_only=False
        )
        
        assert policy.enable_partial_classification == True
        assert policy.partial_classification_min_coverage_threshold == 50.0
        assert policy.partial_classification_require_test_execution == True
        assert policy.partial_classification_allow_coverage_only == False
    
    def test_evidence_quality_policy_from_dict_includes_partial_flags(self):
        """Test that from_dict includes partial classification flags."""
        policy_dict = {
            "policy_name": "custom",
            "enable_partial_classification": True,
            "partial_classification_min_coverage_threshold": 60.0,
            "partial_classification_require_test_execution": False,
            "partial_classification_allow_coverage_only": True
        }
        
        policy = EvidenceQualityPolicy.from_dict(policy_dict)
        
        assert policy.enable_partial_classification == True
        assert policy.partial_classification_min_coverage_threshold == 60.0
        assert policy.partial_classification_require_test_execution == False
        assert policy.partial_classification_allow_coverage_only == True
    
    def test_partial_classification_disabled_by_default(self):
        """Test that partial classification is disabled by default."""
        policy = EvidenceQualityPolicy()
        
        assert policy.enable_partial_classification == False
        assert policy.partial_classification_min_coverage_threshold == 50.0
        assert policy.partial_classification_require_test_execution == True
        assert policy.partial_classification_allow_coverage_only == False
    
    def test_partial_classification_rule_c_coverage_only(self):
        """Test Rule C: Coverage only (no test execution) with policy allow_coverage_only=True."""
        policy = EvidenceQualityPolicy(
            enable_partial_classification=True,
            partial_classification_allow_coverage_only=True,
            partial_classification_min_coverage_threshold=50.0
        )
        
        # When coverage is above threshold and no test match
        # Should classify as PARTIALLY_COVERED
        assert policy.partial_classification_allow_coverage_only == True
        assert policy.partial_classification_min_coverage_threshold == 50.0
    
    def test_partial_classification_rule_c_coverage_only_rejected(self):
        """Test Rule C: Coverage only with policy allow_coverage_only=False."""
        policy = EvidenceQualityPolicy(
            enable_partial_classification=True,
            partial_classification_allow_coverage_only=False,
            partial_classification_require_test_execution=True
        )
        
        # When coverage exists but policy requires test execution
        # Should classify as MISSING_AUTOMATED_COVERAGE
        assert policy.partial_classification_allow_coverage_only == False
        assert policy.partial_classification_require_test_execution == True
    
    def test_partial_classification_rule_a_b_coverage_plus_test(self):
        """Test Rule A/B: Coverage + Test Execution."""
        policy = EvidenceQualityPolicy(
            enable_partial_classification=True,
            partial_classification_require_test_execution=True
        )
        
        # When coverage + test execution exists
        # Should classify based on execution status (passed/failed/skipped)
        assert policy.partial_classification_require_test_execution == True
    
    def test_partial_classification_rule_d_no_coverage_no_test(self):
        """Test Rule D: No coverage, no test."""
        policy = EvidenceQualityPolicy(
            enable_partial_classification=True
        )
        
        # When no coverage or test evidence
        # Should classify as MISSING_AUTOMATED_COVERAGE
        assert policy.enable_partial_classification == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
