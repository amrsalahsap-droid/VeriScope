"""Verification tests for Regression Evidence Classifier using password-validation scenario.

This test suite verifies the classifier with a password-validation scenario containing
18 passed JUnit tests and coverage data.
"""
import pytest
from unittest.mock import Mock, MagicMock
from app.services.regression_evidence_classifier import (
    RegressionEvidenceClassifier,
    RequirementNode,
    TestNode,
    ExecutionNode,
    CoverageNode,
    ScenarioSignature,
    EvidenceClassification,
    ScenarioSignatureGenerator,
    RequirementMatcher,
)
from app.services.evidence_graph.ac_extraction_service import ACExtractionService, ExtractionCategory
from app.services.evidence_graph.scenario_signature_service import ScenarioSignatureService
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService
from app.services.evidence_graph.missing_test_mapper import MissingTestMapper, MissingTestGenerationError
from app.services.evidence_graph.recommendation_view_model_builder import RecommendationViewModelBuilder
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService


class TestScenarioSignatureGenerator:
    """Test scenario signature generation."""

    def test_generate_signature_password_expired(self):
        """Test signature generation for expired password scenario."""
        text = "Expired password reset token should be rejected"
        signature = ScenarioSignatureGenerator.generate_signature(text)
        
        assert signature.flow == "password_reset"
        assert signature.action == "reject"
        assert signature.condition == "expired"
        assert signature.expected_outcome == "rejected"
        assert signature.polarity == "negative"
        assert signature.subject == "password"

    def test_generate_signature_password_reused(self):
        """Test signature generation for reused password scenario."""
        text = "Reused password should be rejected during signup"
        signature = ScenarioSignatureGenerator.generate_signature(text)
        
        assert signature.flow == "sign_up"
        assert signature.action == "reject"
        assert signature.condition == "reused"
        assert signature.expected_outcome == "rejected"
        assert signature.polarity == "negative"

    def test_generate_signature_whitespace_password(self):
        """Test signature generation for whitespace password scenario."""
        text = "Password with only whitespace should be rejected"
        signature = ScenarioSignatureGenerator.generate_signature(text)
        
        assert signature.condition == "whitespace"
        assert signature.expected_outcome == "rejected"
        assert signature.polarity == "negative"

    def test_generate_signature_valid_password(self):
        """Test signature generation for valid password scenario."""
        text = "Valid password should be accepted"
        signature = ScenarioSignatureGenerator.generate_signature(text)
        
        assert signature.expected_outcome == "accepted"
        assert signature.polarity == "positive"

    def test_compute_signature_hash(self):
        """Test signature hash computation."""
        signature = ScenarioSignature(
            flow="password_reset",
            action="reject",
            condition="expired",
            expected_outcome="rejected",
            subject="password",
            polarity="negative"
        )
        hash1 = ScenarioSignatureGenerator.compute_signature_hash(signature)
        hash2 = ScenarioSignatureGenerator.compute_signature_hash(signature)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length


class TestRequirementMatcher:
    """Test 6-layer matching pipeline."""

    def test_layer1_direct_id_match(self):
        """Test Layer 1: Direct ID matching."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired password should be rejected",
            flow="password_reset"
        )
        test = TestNode(
            test_id="test-1",
            title="Test expired password rejection",
            normalized_title="test expired password rejection",
            mapped_requirement_ids=["req-1"]
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        
        assert score == 1.0
        assert "Direct ID match" in diagnostics["signals"]

    def test_layer2_exact_title_match(self):
        """Test Layer 2: Exact normalized title matching."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired password should be rejected",
            flow="password_reset"
        )
        test = TestNode(
            test_id="test-1",
            title="Expired password should be rejected",
            normalized_title="expired password should be rejected"
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        
        assert score >= 0.95
        assert "Exact title match" in diagnostics["signals"]

    def test_layer3_signature_match_positive(self):
        """Test Layer 3: Signature matching with positive outcome."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password should be accepted",
            flow="sign_up",
            scenario_signature=ScenarioSignature(
                flow="sign_up",
                action="accept",
                condition="valid",
                expected_outcome="accepted",
                polarity="positive"
            )
        )
        test = TestNode(
            test_id="test-1",
            title="Test valid password acceptance",
            normalized_title="test valid password acceptance",
            scenario_signature=ScenarioSignature(
                flow="sign_up",
                action="accept",
                condition="valid",
                expected_outcome="accepted",
                polarity="positive"
            )
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        
        assert score > 0.5
        assert not diagnostics["signature_diagnostics"]["outcome_contradiction"]

    def test_layer3_signature_match_contradiction(self):
        """Test Layer 3: Signature matching with outcome contradiction."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired password should be rejected",
            flow="password_reset",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="reject",
                condition="expired",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        test = TestNode(
            test_id="test-1",
            title="Test expired password acceptance",
            normalized_title="test expired password acceptance",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="accept",
                condition="expired",
                expected_outcome="accepted",
                polarity="positive"
            )
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        
        assert diagnostics["signature_diagnostics"]["outcome_contradiction"]
        assert score < 0.5  # Penalty applied

    def test_layer4_path_hints(self):
        """Test Layer 4: Path/classname hints."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Password reset flow",
            flow="password_reset"
        )
        test = TestNode(
            test_id="test-1",
            title="Test password reset",
            normalized_title="test password reset",
            classname="com.example.auth.PasswordResetServiceTest"
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        
        assert diagnostics["layer_scores"]["path"] > 0

    def test_layer5_keyword_scoring(self):
        """Test Layer 5: Keyword scoring."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired password token should be rejected",
            flow="password_reset"
        )
        test = TestNode(
            test_id="test-1",
            title="Test expired token rejection",
            normalized_title="test expired token rejection"
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        
        assert diagnostics["layer_scores"]["keyword"] > 0

    def test_normalize_title(self):
        """Test title normalization."""
        title1 = "Expired password should be rejected"
        title2 = "Should reject expired password"
        
        normalized1 = RequirementMatcher.normalize_title(title1)
        normalized2 = RequirementMatcher.normalize_title(title2)
        
        # Both should contain the same key terms after normalization
        assert "expired" in normalized1
        assert "password" in normalized1
        assert "reject" in normalized1


class TestRegressionEvidenceClassifier:
    """Test Regression Evidence Classifier with password-validation scenario."""

    def test_password_validation_scenario_18_passed_tests(self):
        """Test classification with 18 passed JUnit tests for password validation."""
        # Create requirement nodes for password validation
        requirements = [
            RequirementNode(
                requirement_id="req-1",
                readable_id="AC-01",
                title="Expired password reset token should be rejected",
                flow="password_reset",
                action="reject",
                condition="expired",
                expected_outcome="rejected",
                polarity="negative",
                is_real_testable_requirement=True
            ),
            RequirementNode(
                requirement_id="req-2",
                readable_id="AC-02",
                title="Reused password should be rejected during signup",
                flow="sign_up",
                action="reject",
                condition="reused",
                expected_outcome="rejected",
                polarity="negative",
                is_real_testable_requirement=True
            ),
            RequirementNode(
                requirement_id="req-3",
                readable_id="AC-03",
                title="Password with only whitespace should be rejected",
                flow="sign_up",
                action="reject",
                condition="whitespace",
                expected_outcome="rejected",
                polarity="negative",
                is_real_testable_requirement=True
            ),
            RequirementNode(
                requirement_id="req-4",
                readable_id="AC-04",
                title="Valid password should be accepted",
                flow="sign_up",
                action="accept",
                condition="valid",
                expected_outcome="accepted",
                polarity="positive",
                is_real_testable_requirement=True
            ),
            RequirementNode(
                requirement_id="req-5",
                readable_id="AC-05",
                title="Empty password should be rejected",
                flow="sign_up",
                action="reject",
                condition="empty",
                expected_outcome="rejected",
                polarity="negative",
                is_real_testable_requirement=True
            ),
        ]

        # Create test nodes for 18 JUnit tests
        tests = []
        for i in range(18):
            test = TestNode(
                test_id=f"test-{i}",
                title=f"PasswordValidationTest.testPasswordValidation{i}",
                normalized_title=f"passwordvalidationtest testpasswordvalidation{i}",
                classname="com.example.auth.PasswordValidationTest",
                test_type="unit",
                automation_status="existing_automated"
            )
            tests.append(test)

        # Create execution nodes for 18 passed tests
        executions = []
        for i in range(18):
            execution = ExecutionNode(
                test_id=f"exec-{i}",
                test_name=f"testPasswordValidation{i}",
                classname="com.example.auth.PasswordValidationTest",
                status="passed",
                duration=0.5,
                pull_request_id="pr-1",
                head_sha="abc123",
                mapped_test_node_id=f"test-{i}"
            )
            executions.append(execution)

        # Create coverage nodes
        coverage_nodes = [
            CoverageNode(
                file_path="src/main/java/com/example/auth/PasswordValidator.java",
                line_coverage=85.0,
                branch_coverage=75.0,
                related_flows=["sign_up", "password_reset"],
                coverage_strength="strong"
            )
        ]

        # Run classification
        classifier = RegressionEvidenceClassifier()
        report = classifier.classify(
            requirements=requirements,
            tests=tests,
            executions=executions,
            coverage_nodes=coverage_nodes,
            excluded_fragments=[]
        )

        # Verify PR execution stats
        assert report.uploaded_pr_tests_total == 18
        assert report.uploaded_pr_tests_passed == 18
        assert report.uploaded_pr_tests_failed == 0
        assert report.uploaded_pr_tests_skipped == 0

        # Verify total requirements
        assert report.total_requirements == 5

        # Verify UI decision copy doesn't claim false completeness
        assert "No remaining" not in report.ui_decision_copy.lower()
        assert "all required regression evidence is covered" not in report.ui_decision_copy.lower()

    def test_classification_verified_by_current_pr_execution(self):
        """Test classification for requirements verified by current PR execution."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired password should be rejected",
            flow="password_reset",
            action="reject",
            condition="expired",
            expected_outcome="rejected",
            polarity="negative",
            is_real_testable_requirement=True
        )

        test = TestNode(
            test_id="test-1",
            title="Test expired password rejection",
            normalized_title="test expired password rejection",
            classname="com.example.auth.PasswordTest",
            automation_status="existing_automated"
        )

        execution = ExecutionNode(
            test_id="exec-1",
            test_name="testExpiredPasswordRejection",
            classname="com.example.auth.PasswordTest",
            status="passed",
            duration=0.5,
            pull_request_id="pr-1",
            head_sha="abc123",
            mapped_test_node_id="test-1"
        )

        classifier = RegressionEvidenceClassifier()
        report = classifier.classify(
            requirements=[req],
            tests=[test],
            executions=[execution],
            coverage_nodes=[],
            excluded_fragments=[]
        )

        assert report.verified_by_current_pr_execution == 1
        assert req.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION

    def test_classification_missing_automated_coverage(self):
        """Test classification for requirements with missing automated coverage."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired password should be rejected",
            flow="password_reset",
            action="reject",
            condition="expired",
            expected_outcome="rejected",
            polarity="negative",
            is_real_testable_requirement=True
        )

        # No tests or executions
        classifier = RegressionEvidenceClassifier()
        report = classifier.classify(
            requirements=[req],
            tests=[],
            executions=[],
            coverage_nodes=[],
            excluded_fragments=[]
        )

        assert report.missing_automated_coverage == 1
        assert req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE

    def test_classification_excluded_fragment(self):
        """Test classification for excluded fragments."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="rejected",
            flow="unknown",
            is_real_testable_requirement=False  # Marked as not a real requirement
        )

        classifier = RegressionEvidenceClassifier()
        report = classifier.classify(
            requirements=[req],
            tests=[],
            executions=[],
            coverage_nodes=[],
            excluded_fragments=[]
        )

        assert report.excluded_fragment_or_test_data == 1
        assert req.classification == EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA

    def test_ui_decision_copy_no_false_claims(self):
        """Test that UI decision copy never makes false claims about completeness."""
        # Scenario: Some requirements verified, but missing automated coverage exists
        req1 = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password should be accepted",
            flow="sign_up",
            is_real_testable_requirement=True
        )
        req2 = RequirementNode(
            requirement_id="req-2",
            readable_id="AC-02",
            title="Expired password should be rejected",
            flow="password_reset",
            is_real_testable_requirement=True
        )

        test = TestNode(
            test_id="test-1",
            title="Test valid password",
            normalized_title="test valid password",
            automation_status="existing_automated"
        )

        execution = ExecutionNode(
            test_id="exec-1",
            test_name="testValidPassword",
            classname="com.example.auth.PasswordTest",
            status="passed",
            duration=0.5,
            pull_request_id="pr-1",
            head_sha="abc123",
            mapped_test_node_id="test-1"
        )

        classifier = RegressionEvidenceClassifier()
        report = classifier.classify(
            requirements=[req1, req2],
            tests=[test],
            executions=[execution],
            coverage_nodes=[],
            excluded_fragments=[]
        )

        # Should not claim completeness when there are missing automated scenarios
        assert "No remaining" not in report.ui_decision_copy.lower()
        assert "all required regression evidence is covered" not in report.ui_decision_copy.lower()
        assert "missing" in report.ui_decision_copy.lower() or "additional" in report.ui_decision_copy.lower()


class TestACExtractionService:
    """Test AC extraction service."""

    def test_ac_extractor_excludes_test_data(self):
        """Test 1: AC extractor excludes test data."""
        service = ACExtractionService()
        text = """
        Suggested Valid Test Data
        Password123
        short1
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have no real requirements
        assert len(result.requirement_nodes) == 0
        # Should have excluded fragments
        assert len(result.excluded_fragments) > 0
        # All should be excluded as test data
        for fragment in result.excluded_fragments:
            assert fragment["category"] == ExtractionCategory.TEST_DATA.value

    def test_ac_extractor_excludes_fragments(self):
        """Test 2: AC extractor excludes fragments."""
        service = ACExtractionService()
        text = """
        must be rejected
        must be shown
        Backend validation is the source of truth
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have no real requirements
        assert len(result.requirement_nodes) == 0
        # Should have excluded fragments
        assert len(result.excluded_fragments) > 0

    def test_ac_extractor_produces_stable_readable_ids(self):
        """Test 3: AC extractor produces stable readable AC IDs."""
        service = ACExtractionService()
        text = """
        - Weak passwords are rejected during sign-up
        - Strong passwords are accepted during sign-up
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have 2 requirements
        assert len(result.requirement_nodes) == 2
        # Should have readable IDs
        assert result.requirement_nodes[0].readable_id == "AC-01"
        assert result.requirement_nodes[1].readable_id == "AC-02"
        # IDs should not contain UUIDs
        assert "uuid" not in result.requirement_nodes[0].readable_id.lower()

    def test_ac_extractor_excludes_headings(self):
        """Test 4: AC extractor excludes headings."""
        service = ACExtractionService()
        text = """
        ACCEPTANCE CRITERIA
        Test Data
        Examples
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have no real requirements
        assert len(result.requirement_nodes) == 0
        # Should have excluded fragments
        assert len(result.excluded_fragments) > 0
        # All should be excluded as headings
        for fragment in result.excluded_fragments:
            assert fragment["category"] == ExtractionCategory.HEADING.value

    def test_ac_extractor_excludes_notes(self):
        """Test 5: AC extractor excludes notes."""
        service = ACExtractionService()
        text = """
        Note: Backend validation is the source of truth
        Comment: Frontend validation improves UX
        Security notes
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have no real requirements
        assert len(result.requirement_nodes) == 0
        # Should have excluded fragments
        assert len(result.excluded_fragments) > 0
        # All should be excluded as notes
        for fragment in result.excluded_fragments:
            assert fragment["category"] in (ExtractionCategory.NOTE.value, ExtractionCategory.SECURITY_NOTE.value)

    def test_ac_extractor_identifies_child_details(self):
        """Test 6: AC extractor identifies child details for merging."""
        service = ACExtractionService()
        text = """
        - Password must include uppercase
        - Password must include lowercase
        - Password must include number
        - Password must include special character
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have no real requirements (child details are excluded)
        assert len(result.requirement_nodes) == 0
        # Should have excluded fragments
        assert len(result.excluded_fragments) > 0
        # All should be excluded as child details
        for fragment in result.excluded_fragments:
            assert fragment["category"] == ExtractionCategory.CHILD_DETAIL.value

    def test_ac_extractor_produces_audit(self):
        """Test 7: AC extractor produces extraction audit."""
        service = ACExtractionService()
        text = """
        - Weak passwords are rejected during sign-up
        - Strong passwords are accepted during sign-up
        must be rejected
        Password123
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have audit
        assert result.audit is not None
        # Should count raw segments
        assert result.audit.raw_segments_count > 0
        # Should count real requirements
        assert result.audit.real_requirements_count == 2
        # Should count excluded fragments
        assert result.audit.excluded_fragments_count > 0
        # Should count test data
        assert result.audit.test_data_count > 0
        # Should have extracted requirement nodes in audit
        assert len(result.audit.extracted_requirement_nodes) == 2
        # Should have excluded segments in audit
        assert len(result.audit.excluded_segments) > 0

    def test_ac_extractor_calculates_confidence(self):
        """Test 8: AC extractor calculates confidence scores."""
        service = ACExtractionService()
        text = """
        - Weak passwords are rejected during sign-up
        - must be rejected
        """
        result = service.extract_acceptance_criteria(text)
        
        # Real requirement should have high confidence
        if result.requirement_nodes:
            assert result.requirement_nodes[0].match_score > 0.5
        
        # Excluded fragment should have low confidence
        for fragment in result.excluded_fragments:
            assert fragment["confidence"] >= 0.0
            assert fragment["confidence"] <= 1.0

    def test_ac_extractor_password_validation_scenario(self):
        """Test 9: AC extractor handles password validation scenario."""
        service = ACExtractionService()
        text = """
        Acceptance Criteria

        - Weak passwords are rejected during sign-up
        - Strong passwords are accepted during sign-up
        - Weak passwords are rejected during update-password
        - Strong passwords are accepted during update-password
        - Login works with the new password after successful password update
        - Old password is rejected after successful password update
        - Weak passwords are rejected during reset-password
        - Strong passwords are accepted during reset-password
        - Password must be at least 12 characters
        - Password must include uppercase, lowercase, number, and special character
        - Empty password is rejected
        - Whitespace-only password is rejected
        - Leading and trailing spaces are handled consistently
        - Password confirmation must match
        - Backend/API validation is mandatory
        - Direct API requests with weak passwords are rejected
        - UI and API validation behavior is consistent
        - Validation error messages are safe and user-friendly
        - Password is not updated when validation fails
        - Reset-password with valid token succeeds when password is strong
        - Expired reset tokens are rejected
        - Reused reset tokens are rejected
        - Existing valid login behavior is not broken
        - Password update/reset operation is atomic

        Test Data
        short1!
        password123!
        PASSWORD123!
        PasswordOnly
        Password123
        Password!
        123456789012!
        empty value
        whitespace-only value

        Notes
        Backend validation is the source of truth
        Frontend validation improves UX
        """
        result = service.extract_acceptance_criteria(text)
        
        # Should have reasonable number of real requirements (not 62)
        assert result.audit.real_requirements_count <= 30
        assert result.audit.real_requirements_count >= 15
        
        # Should have excluded test data
        assert result.audit.test_data_count > 0
        
        # Should have excluded notes
        assert result.audit.note_count > 0
        
        # All real requirements should have readable IDs
        for req in result.requirement_nodes:
            assert req.readable_id.startswith("AC-")
            assert len(req.readable_id) <= 5  # AC-01 to AC-99
        
        # No test data should appear as real requirements
        for req in result.requirement_nodes:
            assert "password123" not in req.title.lower()
            assert "short1" not in req.title.lower()
            assert "123456789012" not in req.title.lower()


class TestEvidenceMatchingService:
    """Test evidence matching service."""

    def test_expired_token_junit_maps_to_expired_token_ac(self):
        """Test 4: Expired reset token JUnit passed test maps to expired reset token AC."""
        service = EvidenceMatchingService()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Expired reset token should be rejected",
            flow="password_reset",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="reject",
                condition="expired",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        
        test = TestNode(
            test_id="test-1",
            title="testExpiredTokenRejected",
            normalized_title="testexpiredtokenrejected",
            classname="com.example.auth.PasswordResetTest",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="reject",
                condition="expired",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        
        result = service.match_requirement_to_test(req, test)
        
        # Should have high confidence match
        assert result.score >= 0.85

    def test_reused_token_junit_maps_to_reused_token_ac(self):
        """Test 5: Reused reset token JUnit passed test maps to reused reset token AC."""
        service = EvidenceMatchingService()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Reused reset token should be rejected",
            flow="password_reset",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="reject",
                condition="reused",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        
        test = TestNode(
            test_id="test-1",
            title="testReusedTokenRejected",
            normalized_title="testreusedtokenrejected",
            classname="com.example.auth.PasswordResetTest",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="reject",
                condition="reused",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        
        result = service.match_requirement_to_test(req, test)
        
        # Should have high confidence match
        assert result.score >= 0.85

    def test_valid_token_junit_maps_to_valid_token_ac(self):
        """Test 6: Valid reset token JUnit passed test maps to valid reset token AC."""
        service = EvidenceMatchingService()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid reset token should be accepted",
            flow="password_reset",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="accept",
                condition="valid",
                expected_outcome="accepted",
                polarity="positive"
            )
        )
        
        test = TestNode(
            test_id="test-1",
            title="testValidTokenAccepted",
            normalized_title="testvalidtokenaccepted",
            classname="com.example.auth.PasswordResetTest",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="accept",
                condition="valid",
                expected_outcome="accepted",
                polarity="positive"
            )
        )
        
        result = service.match_requirement_to_test(req, test)
        
        # Should have high confidence match
        assert result.score >= 0.85

    def test_signup_weak_password_does_not_map_to_reset_password_ac(self):
        """Test 7: Sign-up weak password test does not map to reset-password weak password AC."""
        service = EvidenceMatchingService()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Weak passwords are rejected during password reset",
            flow="password_reset",
            scenario_signature=ScenarioSignature(
                flow="password_reset",
                action="reject",
                condition="weak",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        
        test = TestNode(
            test_id="test-1",
            title="testWeakPasswordRejectedDuringSignup",
            normalized_title="testweakpasswordrejectedduringsignup",
            classname="com.example.auth.SignUpTest",
            scenario_signature=ScenarioSignature(
                flow="sign_up",
                action="reject",
                condition="weak",
                expected_outcome="rejected",
                polarity="negative"
            )
        )
        
        result = service.match_requirement_to_test(req, test)
        
        # Should have flow contradiction penalty
        assert result.diagnostics["signature_diagnostics"]["flow_contradiction"]
        # Score should be reduced due to contradiction
        assert result.score < 0.85


class TestClassificationRules:
    """Test classification rules."""

    def test_passed_current_pr_test_not_shown_as_missing(self):
        """Test 8: Passed current PR test is not shown as missing test."""
        mapper = MissingTestMapper()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password should be accepted",
            flow="sign_up",
            classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            is_real_testable_requirement=True
        )
        
        missing_tests = mapper.generate_missing_tests([req])
        
        # Should not generate missing test for verified requirement
        assert len(missing_tests) == 0

    def test_existing_test_not_run_appears_under_required_not_run(self):
        """Test 9: Existing test not run appears under Required Tests Not Run."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password should be accepted",
            flow="sign_up",
            classification=EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR,
            is_real_testable_requirement=True
        )
        
        # Should be classified as EXISTING_TEST_NOT_RUN_IN_CURRENT_PR
        assert req.classification == EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR

    def test_coverage_only_does_not_mark_ac_as_fully_covered(self):
        """Test 10: Coverage-only evidence does not mark AC as fully covered."""
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password should be accepted",
            flow="sign_up",
            classification=EvidenceClassification.PARTIALLY_COVERED,
            is_real_testable_requirement=True
        )
        
        # Should be PARTIALLY_COVERED, not VERIFIED
        assert req.classification == EvidenceClassification.PARTIALLY_COVERED
        assert req.classification != EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION

    def test_coverage_gap_does_not_create_duplicate_missing_test(self):
        """Test 11: Coverage gap does not create duplicate missing test if behavior already passed in current PR."""
        mapper = MissingTestMapper()
        
        # One requirement verified by current PR
        req1 = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password should be accepted",
            flow="sign_up",
            classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            is_real_testable_requirement=True
        )
        
        # One requirement with coverage gap only
        req2 = RequirementNode(
            requirement_id="req-2",
            readable_id="AC-02",
            title="Some other requirement",
            flow="sign_up",
            classification=EvidenceClassification.COVERAGE_GAP_ONLY,
            is_real_testable_requirement=True
        )
        
        missing_tests = mapper.generate_missing_tests([req1, req2])
        
        # Should only generate from MISSING_AUTOMATED_COVERAGE, not from verified or coverage gap only
        assert len(missing_tests) == 0


class TestMissingTestMapperQualityGates:
    """Test Quality Gate validations in MissingTestMapper."""

    def test_gate_covered_requirements_count(self):
        """Test Gate: No longer raise error if password-related and verified count < 15."""
        mapper = MissingTestMapper()
        
        # 10 password-related requirements, only 1 verified (others not_mapped/missing)
        requirements = []
        for i in range(10):
            requirements.append(RequirementNode(
                requirement_id=f"req-{i}",
                readable_id=f"AC-{i}",
                title="Password strength validation",
                flow="sign_up",
                classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION if i == 0 else EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
                is_real_testable_requirement=True
            ))

        # Should NOT raise MissingTestGenerationError
        cards = mapper.generate_missing_tests(requirements)
        assert len(cards) == 9

    def test_gate_unmapped_parent_requirements_count(self):
        """Test Gate: No longer raise error if unmapped parent requirements count > 5."""
        mapper = MissingTestMapper()
        
        # 22 requirements, 15 verified, 6 unmapped (NOT_MAPPED_TRACEABILITY_RISK)
        requirements = []
        for i in range(15):
            requirements.append(RequirementNode(
                requirement_id=f"req-verified-{i}",
                readable_id=f"AC-V-{i}",
                title="Password verification rule",
                flow="sign_up",
                classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
                is_real_testable_requirement=True
            ))
        for i in range(6):
            requirements.append(RequirementNode(
                requirement_id=f"req-unmapped-{i}",
                readable_id=f"AC-U-{i}",
                title="Password strength validation unmapped",
                flow="sign_up",
                classification=EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK,
                is_real_testable_requirement=True
            ))
        requirements.append(RequirementNode(
            requirement_id="req-missing",
            readable_id="AC-M",
            title="Password strength validation missing",
            flow="sign_up",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        ))

        from app.services.evidence_graph.evidence_matching_service import MatchTableEntry
        match_table = [MatchTableEntry(
            requirement_id="req-missing",
            requirement_title="Password strength validation missing",
            candidate_test_title="testPasswordStrength",
            score=0.5,
            decision="REJECTED",
            reason="Low score",
            contradiction_penalty=0.0
        )]

        # Should NOT raise MissingTestGenerationError
        cards = mapper.generate_missing_tests(requirements, match_table)
        assert len(cards) == 1

    def test_gate_passed_junit_token_scenario(self):
        """Test Gate: No longer raise error if token test is marked missing but JUnit passed test exists."""
        mapper = MissingTestMapper()
        
        req = RequirementNode(
            requirement_id="req-token",
            readable_id="AC-TOKEN",
            title="Expired reset token should be rejected",
            flow="password_reset",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )

        from app.services.evidence_graph.evidence_matching_service import MatchTableEntry
        match_table = [MatchTableEntry(
            requirement_id="req-token",
            requirement_title="Expired reset token should be rejected",
            candidate_test_title="testExpiredResetTokenRejected",
            score=0.6,
            decision="REJECTED",
            reason="Slight mismatch",
            contradiction_penalty=0.0
        )]

        # Should NOT raise MissingTestGenerationError
        cards = mapper.generate_missing_tests([req], match_table)
        assert len(cards) == 1

    def test_gate_token_mapped_to_login(self):
        """Test Gate: No longer raise error if token requirement maps to login/update candidate test."""
        mapper = MissingTestMapper()
        
        req = RequirementNode(
            requirement_id="req-token",
            readable_id="AC-TOKEN",
            title="Expired reset token should be rejected",
            flow="password_reset",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )

        from app.services.evidence_graph.evidence_matching_service import MatchTableEntry
        match_table = [MatchTableEntry(
            requirement_id="req-token",
            requirement_title="Expired reset token should be rejected",
            candidate_test_title="testNewPasswordLoginWorks",
            score=0.5,
            decision="REJECTED",
            reason="Incorrect mapping",
            contradiction_penalty=0.0
        )]

        # Should NOT raise MissingTestGenerationError
        cards = mapper.generate_missing_tests([req], match_table)
        assert len(cards) == 1

    def test_gate_signup_mapped_to_reset(self):
        """Test Gate: No longer raise error if signup requirement maps to reset candidate test."""
        mapper = MissingTestMapper()
        
        req = RequirementNode(
            requirement_id="req-signup",
            readable_id="AC-SIGNUP",
            title="Weak passwords are rejected during sign-up",
            flow="sign_up",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )

        from app.services.evidence_graph.evidence_matching_service import MatchTableEntry
        match_table = [MatchTableEntry(
            requirement_id="req-signup",
            requirement_title="Weak passwords are rejected during sign-up",
            candidate_test_title="testWeakPasswordRejectedDuringResetPassword",
            score=0.5,
            decision="REJECTED",
            reason="Incorrect mapping",
            contradiction_penalty=0.0
        )]

        # Should NOT raise MissingTestGenerationError
        cards = mapper.generate_missing_tests([req], match_table)
        assert len(cards) == 1

    def test_why_missing_explanation_and_diagnostic_details(self):
        """Test: Ensure why_missing is non-empty and contains best candidate details."""
        mapper = MissingTestMapper()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Simple testable requirement",
            flow="other",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )

        from app.services.evidence_graph.evidence_matching_service import MatchTableEntry
        match_table = [MatchTableEntry(
            requirement_id="req-1",
            requirement_title="Simple testable requirement",
            candidate_test_title="testSomeCandidate",
            score=0.4,
            decision="REJECTED",
            reason="Low score",
            contradiction_penalty=0.0
        )]

        cards = mapper.generate_missing_tests([req], match_table)
        assert len(cards) == 1
        assert "testSomeCandidate" in cards[0].why_missing
        assert "best candidate" in cards[0].why_missing.lower()


class TestViewModelBuilder:
    """Test view model builder."""

    def test_executive_counts_match_rendered_sections(self):
        """Test 12: Executive counts match rendered sections."""
        builder = RecommendationViewModelBuilder()
        
        req1 = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Valid password",
            flow="sign_up",
            classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            is_real_testable_requirement=True
        )
        
        req2 = RequirementNode(
            requirement_id="req-2",
            readable_id="AC-02",
            title="Missing requirement",
            flow="sign_up",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )
        
        view_model = builder.build_view_model(
            requirements=[req1, req2],
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        # Counts should match
        assert view_model.counts["verifiedTests"] == 1
        assert view_model.counts["missingAutomatedCoverage"] == 1

    def test_no_remaining_tests_message_only_when_no_gaps(self):
        """Test 13: 'No remaining tests' message appears only when no missing/failed/skipped/not-run/critical gap exists."""
        builder = RecommendationViewModelBuilder()
        
        # Scenario with gaps
        req1 = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Missing requirement",
            flow="sign_up",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )
        
        view_model = builder.build_view_model(
            requirements=[req1],
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        # Should not claim completeness
        assert "No remaining" not in view_model.decision_copy.explanation.lower()
        assert "all required regression evidence is covered" not in view_model.decision_copy.explanation.lower()

    def test_not_mapped_contains_only_real_acs(self):
        """Test 14: Not mapped contains only real ACs, not fragments."""
        builder = RecommendationViewModelBuilder()
        
        # Real AC
        req1 = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Real requirement",
            flow="sign_up",
            classification=EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK,
            is_real_testable_requirement=True
        )
        
        # Fragment
        req2 = RequirementNode(
            requirement_id="req-2",
            readable_id="AC-02",
            title="rejected",
            flow="unknown",
            classification=EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA,
            is_real_testable_requirement=False
        )
        
        view_model = builder.build_view_model(
            requirements=[req1, req2],
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        # AC traceability should only include real ACs
        assert len(view_model.ac_traceability) == 1
        assert view_model.ac_traceability[0].readable_id == "AC-01"

    def test_internal_ac_ids_not_displayed_in_ui(self):
        """Test 15: Internal AC IDs are not displayed in UI."""
        builder = RecommendationViewModelBuilder()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Real requirement",
            flow="sign_up",
            classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            is_real_testable_requirement=True
        )
        
        view_model = builder.build_view_model(
            requirements=[req],
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        # AC traceability should use readable ID, not internal UUID
        assert view_model.ac_traceability[0].readable_id == "AC-01"
        assert view_model.ac_traceability[0].requirement_id != "AC-01"

    def test_coverage_gap_signup_leak_prevention(self):
        """Test 16: Reset-password coverage gaps do not link to signup tests unless shared policy logic exists."""
        builder = RecommendationViewModelBuilder()
        
        # Test 1: SignUp test and Reset Password Gap, no shared policy validation.
        # Should NOT link (link is None / No directly linked test).
        test_signup = TestNode(
            test_id="test-signup",
            title="should_reject_weak_password_during_signup",
            normalized_title="should_reject_weak_password_during_signup",
            classname="SignupTest",
            mapped_requirement_ids=["req-signup"]
        )
        
        gap_reset = CoverageNode(
            file_path="src/main/java/com/example/auth/PasswordResetService.java",
            line_coverage=50.0,
            branch_coverage=40.0,
            related_flows=["password_reset"],
            related_requirement_ids=["req-reset"],
            coverage_strength="weak"
        )
        
        view_model = builder.build_view_model(
            requirements=[],
            tests=[test_signup],
            executions=[],
            coverage_nodes=[gap_reset],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        assert len(view_model.coverage_gaps) == 1
        cg = view_model.coverage_gaps[0]
        assert cg.linked_test_id is None
        assert cg.linked_test_title == "No directly linked test"

        # Test 2: SignUp test and Reset Password Gap, WITH shared policy validation (e.g. gap or test contains 'policy').
        # Should link successfully and say "Linked through shared password policy validation logic."
        test_policy = TestNode(
            test_id="test-policy",
            title="should_validate_password_policy",
            normalized_title="should_validate_password_policy",
            classname="PasswordPolicyTest",
            mapped_requirement_ids=["req-policy"]
        )
        
        gap_policy = CoverageNode(
            file_path="src/main/java/com/example/auth/password_policy.py",
            line_coverage=50.0,
            branch_coverage=40.0,
            related_flows=["password_reset"],
            related_requirement_ids=["req-policy"],
            coverage_strength="weak"
        )
        
        view_model_policy = builder.build_view_model(
            requirements=[],
            tests=[test_policy],
            executions=[],
            coverage_nodes=[gap_policy],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        assert len(view_model_policy.coverage_gaps) == 1
        cg_policy = view_model_policy.coverage_gaps[0]
        assert cg_policy.linked_test_id == "test-policy"
        assert cg_policy.why_link_relevant == "Linked through shared password policy validation logic."

    def test_coverage_gap_optional_severity_if_verified(self):
        """Test 17: Coverage gap severity is Optional if its associated requirement is already verified by current PR."""
        builder = RecommendationViewModelBuilder()
        
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Verified requirement",
            flow="password_reset",
            classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
            is_real_testable_requirement=True
        )
        
        gap = CoverageNode(
            file_path="src/main/java/com/example/auth/PasswordResetService.java",
            line_coverage=50.0,
            branch_coverage=40.0,
            related_flows=["password_reset"],
            related_requirement_ids=["req-1"],
            coverage_strength="weak"
        )
        
        view_model = builder.build_view_model(
            requirements=[req],
            tests=[],
            executions=[],
            coverage_nodes=[gap],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        assert len(view_model.coverage_gaps) == 1
        assert view_model.coverage_gaps[0].severity == "Optional"

    def test_coverage_gap_diagnostics_and_severity(self):
        """Test 18: Severity is Must for high-risk requirements with no tests, and Recommended for weak security-sensitive logic."""
        builder = RecommendationViewModelBuilder()
        
        # Must severity: high risk requirement + missing automated coverage
        req_high = RequirementNode(
            requirement_id="req-high",
            readable_id="AC-01",
            title="High risk auth requirement",
            flow="login",
            risk_level="high",
            classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            is_real_testable_requirement=True
        )
        
        gap_must = CoverageNode(
            file_path="src/main/java/com/example/auth/LoginService.java",
            line_coverage=50.0,
            branch_coverage=40.0,
            related_flows=["login"],
            related_requirement_ids=["req-high"],
            coverage_strength="weak"
        )
        
        view_model_must = builder.build_view_model(
            requirements=[req_high],
            tests=[],
            executions=[],
            coverage_nodes=[gap_must],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        assert len(view_model_must.coverage_gaps) == 1
        assert view_model_must.coverage_gaps[0].severity == "Must"

        # Recommended severity: weak branch coverage (<60%) for auth/password/token file paths
        gap_rec = CoverageNode(
            file_path="src/main/java/com/example/auth/TokenService.java",
            line_coverage=80.0,
            branch_coverage=50.0,  # weak (<60%)
            related_flows=["login"],
            related_requirement_ids=[],
            coverage_strength="weak"
        )
        
        view_model_rec = builder.build_view_model(
            requirements=[],
            tests=[],
            executions=[],
            coverage_nodes=[gap_rec],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[]
        )
        
        assert len(view_model_rec.coverage_gaps) == 1
        assert view_model_rec.coverage_gaps[0].severity == "Recommended"


class TestDirectACIDMatching:
    """Tests for direct AC ID matching logic."""

    def test_junit_parser_extracts_acceptance_criterion_property(self):
        """Verify SafeJUnitParser parses acceptance_criterion property from JUnit XML."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite name="core_suite" tests="1">
            <testcase name="test_password_validation" classname="PasswordTest" time="0.05">
                <properties>
                    <property name="acceptance_criterion" value="AC-01"/>
                </properties>
            </testcase>
        </testsuite>
        """
        from app.services.junit_parser import SafeJUnitParser
        results = SafeJUnitParser.parse_xml(xml_content)
        
        assert len(results["test_cases"]) == 1
        tc = results["test_cases"][0]
        assert tc["declared_ac_id"] == "AC-01"

    def test_requirement_matcher_direct_ac_id_match_success(self):
        """Verify RequirementMatcher returns score 1.0 when declared_ac_id matches requirement."""
        req = RequirementNode(
            requirement_id="req-ac1",
            readable_id="AC-01",
            title="Password must contain at least one digit",
            flow="signup"
        )
        test = TestNode(
            test_id="test-ac1",
            title="Test digit validation",
            declared_ac_id="AC-01"
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        assert score == 1.0
        assert "Direct ID match" in diagnostics["signals"]
        assert diagnostics["mapping_type"] == "DIRECT_AC_ID"

    def test_requirement_matcher_direct_ac_id_match_case_insensitivity(self):
        """Verify direct AC ID match is case-insensitive."""
        req = RequirementNode(
            requirement_id="req-ac1",
            readable_id="AC-01",
            title="Password must contain at least one digit",
            flow="signup"
        )
        test = TestNode(
            test_id="test-ac1",
            title="Test digit validation",
            declared_ac_id="ac-01" # lowercase
        )
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        assert score == 1.0
        assert "Direct ID match" in diagnostics["signals"]
        assert diagnostics["mapping_type"] == "DIRECT_AC_ID"

    def test_requirement_matcher_direct_ac_id_mismatch_skips_text_similarity(self, monkeypatch):
        """Verify requirement matcher returns 0.0 and skips text similarity if AC ID matches a different AC."""
        req = RequirementNode(
            requirement_id="req-ac2",
            readable_id="AC-02",
            title="Password validation reset digit",
            flow="signup"
        )
        test = TestNode(
            test_id="test-ac1",
            title="Password validation reset digit",
            declared_ac_id="AC-01"
        )
        
        # Mock SessionLocal and the query
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        
        mock_curr_ac = MagicMock()
        mock_curr_ac.repository_id = "repo-1"
        
        mock_matched_ac = MagicMock()
        mock_matched_ac.id = "req-ac1"
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.side_effect = [mock_curr_ac, mock_matched_ac]
        
        class MockSessionLocal:
            def __enter__(self):
                return mock_db
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
                
        monkeypatch.setattr("app.db.session.SessionLocal", MockSessionLocal)
        
        score, diagnostics = RequirementMatcher.match_requirement_to_test(req, test)
        assert score == 0.0

    def test_evidence_matching_service_direct_ac_id_match(self):
        """Verify EvidenceMatchingService populates mapping_type in MatchTableEntry."""
        req = RequirementNode(
            requirement_id="req-ac1",
            readable_id="AC-01",
            title="Password must contain at least one digit",
            flow="signup"
        )
        test = TestNode(
            test_id="test-ac1",
            title="Test digit validation",
            declared_ac_id="AC-01"
        )
        
        matcher = EvidenceMatchingService()
        result, is_confident = matcher.find_best_match(req, [test])
        
        assert is_confident is True
        assert result.score == 1.0
        assert len(matcher.match_table) == 1
        entry = matcher.match_table[0]
        assert entry.mapping_type == "DIRECT_AC_ID"

    def test_evidence_matching_service_direct_ac_id_mismatch(self, monkeypatch):
        """Verify EvidenceMatchingService returns 0.0 and skips text similarity when declared_ac_id matches a different AC."""
        req = RequirementNode(
            requirement_id="req-ac2",
            readable_id="AC-02",
            title="Password validation reset digit",
            flow="signup"
        )
        test = TestNode(
            test_id="test-ac1",
            title="Password validation reset digit",
            declared_ac_id="AC-01"
        )
        
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        
        mock_curr_ac = MagicMock()
        mock_curr_ac.repository_id = "repo-1"
        
        mock_matched_ac = MagicMock()
        mock_matched_ac.id = "req-ac1"
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.side_effect = [mock_curr_ac, mock_matched_ac]
        
        class MockSessionLocal:
            def __enter__(self):
                return mock_db
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
                
        monkeypatch.setattr("app.db.session.SessionLocal", MockSessionLocal)
        
        matcher = EvidenceMatchingService()
        result, is_confident = matcher.find_best_match(req, [test])
        
        assert is_confident is False
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
