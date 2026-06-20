"""Password PR fixture for end-to-end regression testing.

This fixture represents a real-world scenario:
- PR #1: Implement modern password validation rules and fix test suites
- 18 passed JUnit tests
- 93% line coverage, 79% branch coverage
- 21 password validation ACs
- Test data examples
- Security notes

This fixture is used to prevent regression into:
- Fake traceability (fragments inflating parent count)
- Fake missing tests (generating from non-MISSING_AUTOMATED_COVERAGE)
- Contradictory UI states (stale inputs showing wrong CTAs)
"""

from datetime import datetime
from typing import List, Dict, Any
from app.services.regression_evidence_classifier import (
    RequirementNode, TestNode, ExecutionNode, ScenarioSignature,
    EvidenceClassification, ValidationLayer
)

# Password PR AC text (21 acceptance criteria)
PASSWORD_PR_AC_TEXT = """
# Password Validation Policy

## General Requirements
- System must enforce minimum password length of 8 characters during sign-up
- System must reject passwords shorter than 8 characters with clear error message
- System must require at least one uppercase letter in passwords
- System must require at least one lowercase letter in passwords
- System must require at least one number in passwords
- System must require at least one special character in passwords
- System must reject passwords containing common weak patterns (e.g., "password123")
- System must validate password complexity before account creation

## Sign-up Flow
- During sign-up, user must enter password twice for confirmation
- System must compare both password entries for exact match
- System must show inline validation feedback as user types
- System must prevent sign-up submission if passwords do not match
- System must display password strength indicator during sign-up

## Reset Password Flow
- System must send password reset link to user's email
- System must validate reset token before allowing password change
- System must enforce same complexity rules for password reset
- System must invalidate old password after successful reset
- System must require user to log in with new password after reset

## Update Password Flow
- System must require current password before allowing password change
- System must validate current password matches stored hash
- System must enforce same complexity rules for password update
- System must invalidate all active sessions after password change
- System must send confirmation email after successful password update

## Security Notes
- Backend is source of truth for password validation
- Frontend UX only provides user-friendly feedback
- Password changes must be atomic (update or reset, not both simultaneously)
"""

# Current PR JUnit test results (18 passed, 0 failed, 0 skipped)
PASSWORD_PR_JUNIT_RESULTS = [
    {
        "test_id": "test_password_length_validation",
        "title": "Password length validation during sign-up",
        "classname": "com.example.auth.PasswordValidationTest",
        "status": "PASSED",
        "duration": 0.045,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_uppercase_requirement",
        "title": "Password uppercase letter requirement",
        "classname": "com.example.auth.PasswordValidationTest",
        "status": "PASSED",
        "duration": 0.032,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_lowercase_requirement",
        "title": "Password lowercase letter requirement",
        "classname": "com.example.auth.PasswordValidationTest",
        "status": "PASSED",
        "duration": 0.028,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_number_requirement",
        "title": "Password number requirement",
        "classname": "com.example.auth.PasswordValidationTest",
        "status": "PASSED",
        "duration": 0.035,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_special_char_requirement",
        "title": "Password special character requirement",
        "classname": "com.example.auth.PasswordValidationTest",
        "status": "PASSED",
        "duration": 0.041,
        "flow": "sign_up"
    },
    {
        "test_id": "test_weak_password_rejection",
        "title": "Weak password pattern rejection",
        "classname": "com.example.auth.PasswordValidationTest",
        "status": "PASSED",
        "duration": 0.038,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_confirmation_match",
        "title": "Password confirmation matching during sign-up",
        "classname": "com.example.auth.SignUpTest",
        "status": "PASSED",
        "duration": 0.052,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_confirmation_mismatch",
        "title": "Password confirmation mismatch rejection",
        "classname": "com.example.auth.SignUpTest",
        "status": "PASSED",
        "duration": 0.047,
        "flow": "sign_up"
    },
    {
        "test_id": "test_inline_validation_feedback",
        "title": "Inline password validation feedback",
        "classname": "com.example.auth.SignUpTest",
        "status": "PASSED",
        "duration": 0.061,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_strength_indicator",
        "title": "Password strength indicator display",
        "classname": "com.example.auth.SignUpTest",
        "status": "PASSED",
        "duration": 0.055,
        "flow": "sign_up"
    },
    {
        "test_id": "test_password_reset_link_sent",
        "title": "Password reset link email sent",
        "classname": "com.example.auth.PasswordResetTest",
        "status": "PASSED",
        "duration": 0.089,
        "flow": "reset_password"
    },
    {
        "test_id": "test_reset_token_validation",
        "title": "Password reset token validation",
        "classname": "com.example.auth.PasswordResetTest",
        "status": "PASSED",
        "duration": 0.076,
        "flow": "reset_password"
    },
    {
        "test_id": "test_reset_password_complexity",
        "title": "Password reset complexity enforcement",
        "classname": "com.example.auth.PasswordResetTest",
        "status": "PASSED",
        "duration": 0.068,
        "flow": "reset_password"
    },
    {
        "test_id": "test_old_password_invalidation",
        "title": "Old password invalidation after reset",
        "classname": "com.example.auth.PasswordResetTest",
        "status": "PASSED",
        "duration": 0.072,
        "flow": "reset_password"
    },
    {
        "test_id": "test_current_password_verification",
        "title": "Current password verification before update",
        "classname": "com.example.auth.PasswordUpdateTest",
        "status": "PASSED",
        "duration": 0.083,
        "flow": "update_password"
    },
    {
        "test_id": "test_update_password_complexity",
        "title": "Password update complexity enforcement",
        "classname": "com.example.auth.PasswordUpdateTest",
        "status": "PASSED",
        "duration": 0.079,
        "flow": "update_password"
    },
    {
        "test_id": "test_session_invalidation_after_update",
        "title": "Session invalidation after password update",
        "classname": "com.example.auth.PasswordUpdateTest",
        "status": "PASSED",
        "duration": 0.091,
        "flow": "update_password"
    },
    {
        "test_id": "test_confirmation_email_after_update",
        "title": "Confirmation email after password update",
        "classname": "com.example.auth.PasswordUpdateTest",
        "status": "PASSED",
        "duration": 0.087,
        "flow": "update_password"
    },
]

# Coverage data
PASSWORD_PR_COVERAGE = {
    "line_coverage": 0.93,
    "branch_coverage": 0.79,
    "uncovered_lines": ["PasswordValidator.java:45", "PasswordValidator.java:67"],
    "partially_covered_branches": ["PasswordValidator.java:52"]
}

# Expected traceability results
EXPECTED_PARENT_REQUIREMENTS = 19  # Approximately 19 parent requirements
EXPECTED_CHILD_RULES = 5  # Complexity rules (uppercase, lowercase, number, special, length)
EXPECTED_TEST_DATA_ITEMS = 2  # invalid examples, StrongPass#2026
EXPECTED_SECURITY_NOTES = 3  # backend source of truth, frontend UX only, atomic update/reset

# Expected health state for fresh inputs
EXPECTED_HEALTH_FRESH = "READY_WITH_TRACEABILITY_ISSUES"  # Some requirements may lack coverage

# Expected health state for stale inputs
EXPECTED_HEALTH_STALE = "STALE_INPUTS"


def create_password_pr_requirements() -> List[RequirementNode]:
    """Create RequirementNodes for password PR scenario."""
    # This would typically be generated by AC extraction service
    # For fixture purposes, we'll create a representative subset
    requirements = []
    
    # Sign-up flow requirements
    requirements.append(RequirementNode(
        requirement_id="AC-01",
        readable_id="AC-01",
        title="System must enforce minimum password length of 8 characters during sign-up",
        flow="sign_up",
        action="enforce",
        condition="during sign-up",
        expected_outcome="minimum password length of 8 characters",
        scenario_signature=ScenarioSignature(
            flow="sign_up",
            action="enforce",
            condition="during sign-up",
            expected_outcome="minimum password length of 8 characters",
            subject="password",
            validation_layer="API",
            polarity="positive"
        ),
        classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
        matched_test_ids=["test_password_length_validation"],
        matched_execution_ids=["test_password_length_validation"],
        match_score=0.95,
        is_real_testable_requirement=True
    ))
    
    requirements.append(RequirementNode(
        requirement_id="AC-02",
        readable_id="AC-02",
        title="System must reject passwords shorter than 8 characters with clear error message",
        flow="sign_up",
        action="reject",
        condition="password shorter than 8 characters",
        expected_outcome="clear error message",
        scenario_signature=ScenarioSignature(
            flow="sign_up",
            action="reject",
            condition="password shorter than 8 characters",
            expected_outcome="clear error message",
            subject="password",
            validation_layer="API",
            polarity="negative"
        ),
        classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
        matched_test_ids=["test_password_length_validation"],
        matched_execution_ids=["test_password_length_validation"],
        match_score=0.92,
        is_real_testable_requirement=True
    ))
    
    # Add more representative requirements...
    # (In a real fixture, this would include all 21 ACs)
    
    return requirements


def create_password_pr_tests() -> List[TestNode]:
    """Create TestNodes for password PR scenario."""
    tests = []
    
    for junit_result in PASSWORD_PR_JUNIT_RESULTS:
        tests.append(TestNode(
            test_id=junit_result["test_id"],
            test_name=junit_result["title"],
            classname=junit_result["classname"],
            scenario_signature=ScenarioSignature(
                flow=junit_result["flow"],
                action="validate" if "validation" in junit_result["title"].lower() else "test",
                condition="",
                expected_outcome="",
                subject="password",
                validation_layer="API",
                polarity="positive"
            ),
            is_real_test=True
        ))
    
    return tests


def create_password_pr_executions() -> List[ExecutionNode]:
    """Create ExecutionNodes for password PR scenario."""
    executions = []
    
    for junit_result in PASSWORD_PR_JUNIT_RESULTS:
        executions.append(ExecutionNode(
            test_id=junit_result["test_id"],
            test_name=junit_result["title"],
            classname=junit_result["classname"],
            status=junit_result["status"],
            duration=junit_result["duration"],
            pull_request_id="pr-1",
            head_sha="abc123",
            source_file=junit_result["classname"].replace(".", "/") + ".java"
        ))
    
    return executions


def get_password_pr_fixture() -> Dict[str, Any]:
    """Get complete password PR fixture data."""
    return {
        "pr_title": "Implement modern password validation rules and fix test suites",
        "pr_number": 1,
        "ac_text": PASSWORD_PR_AC_TEXT,
        "junit_results": PASSWORD_PR_JUNIT_RESULTS,
        "coverage": PASSWORD_PR_COVERAGE,
        "requirements": create_password_pr_requirements(),
        "tests": create_password_pr_tests(),
        "executions": create_password_pr_executions(),
        "expected_parent_count": EXPECTED_PARENT_REQUIREMENTS,
        "expected_child_rules": EXPECTED_CHILD_RULES,
        "expected_test_data": EXPECTED_TEST_DATA_ITEMS,
        "expected_security_notes": EXPECTED_SECURITY_NOTES,
        "expected_health_fresh": EXPECTED_HEALTH_FRESH,
        "expected_health_stale": EXPECTED_HEALTH_STALE,
    }
