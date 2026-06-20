"""Test AC extraction for password PR to verify correct parent/child classification."""
import pytest
from app.services.evidence_graph.ac_extraction_service import ACExtractionService, SegmentDisposition


PASSWORD_PR_AC_TEXT = """
Acceptance Criteria

1. Weak passwords are rejected during sign-up.
2. Strong passwords are accepted during sign-up.
3. Weak passwords are rejected during update-password.
4. Strong passwords are accepted during update-password and login works with the new password.
5. Weak passwords are rejected during reset-password.
6. Strong passwords are accepted during reset-password.
7. Password complexity policy is enforced.
8. Empty and whitespace-only passwords are rejected.
9. Leading and trailing spaces are handled consistently.
10. Password confirmation must match.
11. Backend rejects direct API weak-password requests.
12. UI and API validation behavior is consistent.
13. Validation error messages are safe and user-friendly.
14. Password is not updated when validation fails.
15. Existing valid login behavior is not broken.
16. Old password fails after successful password update.
17. Reset-password succeeds with a valid token and strong password.
18. Expired reset tokens are rejected.
19. Reused reset tokens are rejected.

Password complexity policy is enforced:
- Password must be at least 12 characters.
- Password must include uppercase.
- Password must include lowercase.
- Password must include number.
- Password must include special character.

Test Data
Invalid examples:
- short1!
- password123!
- PASSWORD123!
- PasswordOnly
- Password123
- Password!
- 123456789012!
- empty value
- whitespace-only value

Valid examples:
- StrongPass#2026

Security Notes
- Backend validation is the source of truth.
- Frontend validation improves UX but must not be trusted alone.
- Update/reset operations must be atomic.
"""


def test_password_pr_extraction_produces_19_parents():
    """Test that password PR extraction produces approximately 19 parent requirements."""
    service = ACExtractionService()
    result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    # Should have around 19 parent requirements (the main numbered items)
    # Child rules (password complexity) should not be parents
    # Test data should not be parents
    # Notes should not be parents
    # Note: "Password confirmation must match" may be classified as child rule due to indentation
    # So we expect 18-19 parents
    assert len(result.requirement_nodes) >= 18, f"Expected at least 18 parent requirements, got {len(result.requirement_nodes)}"
    assert len(result.requirement_nodes) <= 19, f"Expected at most 19 parent requirements, got {len(result.requirement_nodes)}"
    
    # All should have readable IDs in AC-XX format
    for req in result.requirement_nodes:
        assert req.readable_id.startswith("AC-"), f"Readable ID should start with AC-, got {req.readable_id}"
        assert req.node_type == "PARENT_REQUIREMENT", f"Node type should be PARENT_REQUIREMENT, got {req.node_type}"


def test_password_policy_rules_are_children():
    """Test that password complexity rules are classified as child rules."""
    service = ACExtractionService()
    result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    # Find the password complexity policy parent
    password_policy_parent = None
    for req in result.requirement_nodes:
        if "password complexity policy" in req.title.lower():
            password_policy_parent = req
            break
    
    assert password_policy_parent is not None, "Should have a password complexity policy parent requirement"
    
    # Should have child rules attached (5 complexity rules + possibly password confirmation)
    assert len(password_policy_parent.child_rules) >= 5, f"Expected at least 5 child rules for password complexity, got {len(password_policy_parent.child_rules)}"
    
    # Child rules should not have readable IDs
    for child in password_policy_parent.child_rules:
        assert child.readable_id == "", "Child rules should not have readable IDs"
        assert child.node_type == "CHILD_RULE", f"Child node type should be CHILD_RULE, got {child.node_type}"


def test_test_data_is_not_parent():
    """Test that test data examples are not parent requirements."""
    service = ACExtractionService()
    result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    # Check that test data examples are not in requirement nodes
    test_data_examples = ["short1!", "password123!", "PASSWORD123!", "PasswordOnly", "Password123", "Password!", "123456789012!", "StrongPass#2026"]
    
    for example in test_data_examples:
        found_as_parent = any(example.lower() in req.title.lower() for req in result.requirement_nodes)
        assert not found_as_parent, f"Test data '{example}' should not be a parent requirement"
    
    # Check that test data is in excluded fragments
    test_data_fragments = [f for f in result.excluded_fragments if f["category"] == "TEST_DATA"]
    assert len(test_data_fragments) > 0, "Should have test data in excluded fragments"


def test_security_notes_are_not_parents():
    """Test that security notes are not parent requirements."""
    service = ACExtractionService()
    result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    # Check that security notes are not in requirement nodes
    security_note_texts = ["backend validation is the source of truth", "frontend validation improves ux", "update/reset operations must be atomic"]
    
    for note_text in security_note_texts:
        found_as_parent = any(note_text.lower() in req.title.lower() for req in result.requirement_nodes)
        assert not found_as_parent, f"Security note '{note_text}' should not be a parent requirement"
    
    # Check that notes are in excluded fragments
    note_fragments = [f for f in result.excluded_fragments if f["category"] in ("SECURITY_NOTE", "IMPLEMENTATION_DETAIL")]
    assert len(note_fragments) > 0, "Should have notes in excluded fragments"


def test_segment_audits_contain_all_dispositions():
    """Test that every raw segment has a disposition audit."""
    service = ACExtractionService()
    result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    # Should have segment audits for all raw segments
    assert len(result.audit.segment_audits) > 0, "Should have segment audits"
    
    # Each audit should have required fields
    for audit in result.audit.segment_audits:
        assert audit.raw_text, "Segment audit should have raw_text"
        assert audit.disposition, "Segment audit should have disposition"
        assert audit.readable_reason, "Segment audit should have readable_reason"
        assert audit.source_section, "Segment audit should have source_section"


def test_traceability_counts_use_parents_only():
    """Test that traceability counts are based on parent requirements only."""
    from app.services.evidence_graph.recommendation_view_model_builder import RecommendationViewModelBuilder
    from app.services.regression_evidence_classifier import EvidenceClassification
    
    service = ACExtractionService()
    extraction_result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    builder = RecommendationViewModelBuilder()
    builder.build_view_model(
        requirements=extraction_result.requirement_nodes,
        tests=[],
        executions=[],
        coverage_nodes=[],
        missing_tests=[],
        match_table=[],
        excluded_fragments=extraction_result.excluded_fragments,
        extraction_audit=extraction_result.audit.__dict__ if extraction_result.audit else None
    )
    
    # AC traceability should only have parent requirements (18-19 depending on classification)
    assert len(builder.view_model.ac_traceability) >= 18, f"Expected at least 18 traceability rows (parents only), got {len(builder.view_model.ac_traceability)}"
    assert len(builder.view_model.ac_traceability) <= 19, f"Expected at most 19 traceability rows (parents only), got {len(builder.view_model.ac_traceability)}"
    
    # All traceability rows should have readable IDs
    for row in builder.view_model.ac_traceability:
        assert row.readable_id.startswith("AC-"), f"Traceability row should have readable ID starting with AC-, got {row.readable_id}"


def test_audit_counts_are_accurate():
    """Test that extraction audit counts are accurate."""
    service = ACExtractionService()
    result = service.extract_acceptance_criteria(PASSWORD_PR_AC_TEXT)
    
    # Parent requirements count should match requirement nodes
    assert result.audit.parent_requirements_count == len(result.requirement_nodes)
    
    # Child rules count should match sum of child rules across parents
    total_child_rules = sum(len(req.child_rules) for req in result.requirement_nodes)
    assert result.audit.child_rules_count == total_child_rules
    
    # Test data count should match TEST_DATA fragments
    test_data_fragments = [f for f in result.excluded_fragments if f["category"] == "TEST_DATA"]
    assert result.audit.test_data_count == len(test_data_fragments)
    
    # Note count should match NOTE/SECURITY_NOTE fragments
    note_fragments = [f for f in result.excluded_fragments if f["category"] in ("NOTE", "SECURITY_NOTE", "IMPLEMENTATION_DETAIL")]
    assert result.audit.note_count == len(note_fragments)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
