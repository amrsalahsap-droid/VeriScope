import pytest
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.acceptance_criterion import AcceptanceCriterion
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.evidence_graph.recommendation_view_model_builder import RecommendationViewModelBuilder
from app.services.regression_evidence_classifier import (
    RequirementNode, TestNode, ExecutionNode, ScenarioSignature, EvidenceClassification
)
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService
from app.services.evidence_graph.evidence_health_evaluator import EvidenceHealthEvaluator
from app.services.evidence_graph.evidence_quality_policy import EvidenceQualityPolicy


class TestPasswordValidationPRGoldenTraceability:
    """Golden traceability test suite for modern password validation PR."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matching_service = EvidenceMatchingService()
        self.db = SessionLocal()

    def teardown_method(self):
        """Clean up database session."""
        self.db.close()

    def test_golden_traceability_assertions(self):
        """Assert golden traceability rules for this PR."""
        pr = self.db.query(PullRequest).filter(PullRequest.title == "Add password validation feature").first()
        assert pr is not None, "Demo PR not found in database"
        repo_id = str(pr.repository_id)
        pr_id = str(pr.id)

        # Load AC text
        acs = self.db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pr_id
        ).order_by(AcceptanceCriterion.created_at.asc()).all()
        ac_text = "\n".join([f"{i+1}. {ac.text}" for i, ac in enumerate(acs)])

        # Run extraction & matching
        graph_service = RequirementEvidenceGraphService(self.db)
        test_nodes = graph_service._build_test_nodes(repo_id)
        execution_nodes = graph_service._build_execution_nodes(pr_id, pr.head_commit_sha, test_nodes)
        
        # Changed files
        changed_files = ["app/services/auth.py", "tests/test_auth.py"] # standard simulated changed files
        coverage_nodes = graph_service._build_coverage_nodes(repo_id, pr.head_commit_sha, changed_files, pr_id)

        # Build complete view model
        view_model = graph_service.build_evidence_graph(
            repository_id=repo_id,
            pull_request_id=pr_id,
            head_sha=pr.head_commit_sha,
            changed_files=changed_files,
            pr_description=ac_text
        )

        requirements = [node for node in graph_service.ac_extraction_service.extract_acceptance_criteria(ac_text).requirement_nodes]
        graph_service._generate_signatures(requirements, test_nodes, execution_nodes)
        graph_service._match_evidence(requirements, test_nodes, execution_nodes)
        graph_service._classify_requirements(
            requirements, 
            test_nodes, 
            execution_nodes, 
            coverage_nodes,
            repository_id=repo_id,
            pull_request_id=pr_id
        )

        # 1. 25 parent requirements extracted
        assert len(requirements) == 25, f"Expected 25 requirements, got {len(requirements)}"

        # 2. 18 current PR tests parsed
        assert len(execution_nodes) == 18, f"Expected 18 tests, got {len(execution_nodes)}"

        # 3. No security notes are parent requirements
        security_keywords = {"source of truth", "improves ux", "must be atomic", "security notes"}
        for req in requirements:
            assert not any(kw in req.title.lower() for kw in security_keywords), (
                f"Security note found as requirement: {req.title}"
            )

        # 4. Bucket sum equals 25
        verified_count = sum(1 for r in requirements if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION)
        missing_count = sum(1 for r in requirements if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE)
        partial_count = sum(1 for r in requirements if r.classification == EvidenceClassification.PARTIALLY_COVERED)
        not_mapped_count = sum(1 for r in requirements if r.classification == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK)
        bucket_sum = verified_count + missing_count + partial_count + not_mapped_count
        assert bucket_sum == 25, f"Expected bucket sum of 25, got {bucket_sum}"

        # 5. Missing cards are generated only from missing ACs
        for card in view_model.missing_tests:
            # find corresponding requirement
            req = next((r for r in requirements if r.requirement_id == card.requirement_id or r.readable_id == card.requirement_id), None)
            if req:
                assert req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE, (
                    f"Missing test card generated for non-missing requirement: {req.readable_id} ({req.classification})"
                )

        # 6. No verified requirement appears as missing
        verified_ids = {r.requirement_id for r in requirements if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION}
        for card in view_model.missing_tests:
            assert card.requirement_id not in verified_ids, (
                f"Verified requirement {card.requirement_id} appeared in missing tests"
            )

        # 7. No not-mapped requirement generates missing test
        not_mapped_ids = {r.requirement_id for r in requirements if r.classification == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK}
        for card in view_model.missing_tests:
            assert card.requirement_id not in not_mapped_ids, (
                f"Not-mapped requirement {card.requirement_id} generated a missing test card"
            )

        # 8. Coverage does not verify requirements by itself
        # Verify that any requirement classified as verified has at least one confident test match, not just coverage
        for req in requirements:
            if req.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION:
                assert req.matched_test_ids, (
                    f"Requirement {req.readable_id} is VERIFIED but has no matching test executions"
                )

        # 9. JUnit AC IDs are not trusted without matching source hash
        # If hash is mismatched, they should get direct_id = 0.5 (weak hint)
        for t in test_nodes:
            meta = t.acceptance_criterion_metadata
            if meta:
                source_hash = meta.get("source_hash") or meta.get("hash")
                ac_id = meta.get("acceptance_criterion_id") or meta.get("ac_id")
                if ac_id:
                    matching_req = next((r for r in requirements if r.readable_id == ac_id or r.requirement_id == ac_id), None)
                    if matching_req:
                        if not source_hash or source_hash != matching_req.source_hash:
                            # Direct ID match should be weak hint (0.5), not strong (1.0)
                            id_score = self.matching_service._layer1_direct_id(matching_req, t)
                            assert id_score <= 0.5, (
                                f"Untrusted JUnit ID match scored {id_score} for test {t.title} without matching hash"
                            )

        # 10. Reset-password tests do not map to sign-up requirements
        signup_reqs = [r for r in requirements if "sign-up" in r.title.lower()]
        reset_tests = [t for t in test_nodes if "reset" in t.title.lower()]
        for req in signup_reqs:
            for test in reset_tests:
                res = self.matching_service.match_requirement_to_test(req, test)
                assert res.score == 0.0 or "SIGN_UP vs RESET_PASSWORD" in res.diagnostics.get("rejection_reason", ""), (
                    f"Reset test matched signup req: {test.title} -> {req.title}"
                )

        # 11. Token tests do not map to password-policy-only requirements
        pwd_policy_reqs = [r for r in requirements if "complexity" in r.title.lower() or "length" in r.title.lower()]
        token_tests = [t for t in test_nodes if "token" in t.title.lower()]
        for req in pwd_policy_reqs:
            for test in token_tests:
                res = self.matching_service.match_requirement_to_test(req, test)
                assert res.score == 0.0 or "SCOPED_TOKEN_PASSWORD_MISMATCH" in res.diagnostics.get("rejection_reason", ""), (
                    f"Token test matched password-policy-only req: {test.title} -> {req.title}"
                )

        # 12. Update-password ACs remain missing if no direct update-password tests exist
        # There is only a test `should_not_update_password_when_validation_fails` which maps to AC-17 (Password is not updated when validation fails)
        # But other update-password ACs (AC-03, AC-04, AC-05, AC-06) should remain missing
        missing_ac_ids = {"AC-03", "AC-04", "AC-05", "AC-06"}
        for req in requirements:
            if req.readable_id in missing_ac_ids:
                assert req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE, (
                    f"Expected {req.readable_id} to be MISSING_AUTOMATED_COVERAGE, got {req.classification}"
                )

        # 13. Passed reset token tests verify the corresponding token ACs
        # AC-21: Reset-password with an expired token is rejected.
        ac21 = next(r for r in requirements if r.readable_id == "AC-21")
        assert ac21.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION, (
            f"Expected AC-21 to be verified, got {ac21.classification}"
        )
        # AC-22: Reset-password with a reused token is rejected.
        ac22 = next(r for r in requirements if r.readable_id == "AC-22")
        assert ac22.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION, (
            f"Expected AC-22 to be verified, got {ac22.classification}"
        )

        # 14. Passed sign-up tests verify sign-up ACs (AC-01 and AC-02)
        ac01 = next(r for r in requirements if r.readable_id == "AC-01")
        ac02 = next(r for r in requirements if r.readable_id == "AC-02")
        assert ac01.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
        assert ac02.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION

        # 15. Partial is assigned only when supporting evidence exists and policy allows it
        # In this PR, AC-07 and AC-08 are partially covered because they have matching policy tests
        ac07 = next(r for r in requirements if r.readable_id == "AC-07")
        ac08 = next(r for r in requirements if r.readable_id == "AC-08")
        assert ac07.classification == EvidenceClassification.PARTIALLY_COVERED
        assert ac08.classification == EvidenceClassification.PARTIALLY_COVERED

    def test_case_insensitive_matching(self):
        """Test that casing normalization is case-insensitive for signatures and matching."""
        # Lowercase signature values should trigger hard contradictions
        req_sig = ScenarioSignature(
            flow="sign_up",
            action="accept",
            condition="weak_password",
            expected_outcome="accepted",
            subject="password"
        )
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-01",
            title="Weak passwords are accepted during sign-up.",
            flow="sign_up",
            action="accept",
            condition="weak_password",
            expected_outcome="accepted",
            scenario_signature=req_sig,
            is_real_testable_requirement=True
        )

        # Mixed-case flow/action/condition/outcome values
        test_sig = ScenarioSignature(
            flow="SIGN_UP",
            action="Reject",
            condition="Weak_Password",
            expected_outcome="Rejected",
            subject="Password"
        )
        test = TestNode(
            test_id="test-1",
            title="Weak passwords are rejected during sign-up.",
            normalized_title="weak passwords are rejected during sign-up.",
            scenario_signature=test_sig
        )

        result = self.matching_service.match_requirement_to_test(req, test)
        assert result.score == 0.0, "Expected hard contradiction to trigger"
        assert "ACCEPTED vs REJECTED" in result.diagnostics.get("rejection_reason"), (
            f"Expected ACCEPTED vs REJECTED contradiction, got: {result.diagnostics.get('rejection_reason')}"
        )

        # ScenarioSignature serialized output casing must remain unchanged
        serialized = req_sig.to_dict()
        assert serialized["flow"] == "sign_up"
        assert serialized["action"] == "accept"
        assert serialized["condition"] == "weak_password"
        assert serialized["expected_outcome"] == "accepted"

    def test_junit_metadata_mismatch(self):
        """Test JUnit AC metadata mismatch constraints."""
        # JUnit AC ID without source hash is weak hint only (0.5 score on Layer 1)
        req = RequirementNode(
            requirement_id="req-03",
            readable_id="AC-03",
            title="Weak passwords are rejected during update-password.",
            flow="update_password",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            scenario_signature=ScenarioSignature(
                flow="update_password", action="reject", condition="weak_password", expected_outcome="rejected", subject="password"
            ),
            is_real_testable_requirement=True,
            source_hash="current-hash-123"
        )

        test_with_no_hash = TestNode(
            test_id="t3",
            title="Some update password test claiming AC-03",
            normalized_title="some update password test claiming ac-03",
            acceptance_criterion_metadata={
                "acceptance_criterion_id": "AC-03" # no source hash
            },
            scenario_signature=ScenarioSignature(
                flow="update_password", action="reject", condition="weak_password", expected_outcome="rejected", subject="password"
            )
        )

        id_score = self.matching_service._layer1_direct_id(req, test_with_no_hash)
        assert id_score == 0.5, f"Expected weak hint score 0.5, got {id_score}"

        # JUnit AC ID with mismatched meaning triggers JUNIT_AC_ID_MISMATCH
        # Reset-password weak test with stale AC-03 metadata does not map to current AC-03 update-password
        test_contradictory = TestNode(
            test_id="t3-stale",
            title="Weak passwords are rejected during reset-password",
            normalized_title="weak passwords are rejected during reset-password",
            acceptance_criterion_metadata={
                "acceptance_criterion_id": "AC-03"
            },
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="reject", condition="weak_password", expected_outcome="rejected", subject="password"
            )
        )

        result = self.matching_service.match_requirement_to_test(req, test_contradictory)
        assert result.score == 0.0, "Expected contradiction to return 0.0"
        assert result.diagnostics.get("JUNIT_AC_ID_MISMATCH") is True, "Expected JUNIT_AC_ID_MISMATCH diagnostic flag"

        # Same test maps by signature to reset-password weak AC
        req_reset_weak = RequirementNode(
            requirement_id="req-18",
            readable_id="AC-18",
            title="Weak passwords are rejected during reset-password.",
            flow="password_reset",
            action="reject",
            condition="weak_password",
            expected_outcome="rejected",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="reject", condition="weak_password", expected_outcome="rejected", subject="password"
            ),
            is_real_testable_requirement=True
        )

        result_reset = self.matching_service.match_requirement_to_test(req_reset_weak, test_contradictory)
        assert result_reset.score >= 0.85, f"Expected test to map to correct AC by signature, got {result_reset.score}"

    def test_scoped_token_password(self):
        """Test scoped token/password hard contradictions."""
        # token-only test cannot verify password-policy-only requirement
        req_pwd = RequirementNode(
            requirement_id="req-pwd",
            readable_id="AC-pwd",
            title="Password must contain uppercase letters",
            flow="password_reset",
            action="enforce",
            condition="password_complexity",
            expected_outcome="enforced",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="enforce", condition="password_complexity", expected_outcome="enforced", subject="password"
            ),
            is_real_testable_requirement=True
        )

        test_token = TestNode(
            test_id="t-token",
            title="Verify token is valid",
            normalized_title="verify token is valid",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="accept", condition="valid_token", expected_outcome="accepted", subject="reset_token"
            )
        )

        res1 = self.matching_service.match_requirement_to_test(req_pwd, test_token)
        assert res1.score == 0.0
        assert "SCOPED_TOKEN_PASSWORD_MISMATCH" in res1.diagnostics.get("rejection_reason")

        # password-policy-only test cannot verify token-only requirement
        req_token = RequirementNode(
            requirement_id="req-token",
            readable_id="AC-token",
            title="Reset tokens must be valid",
            flow="password_reset",
            action="enforce",
            condition="valid_token",
            expected_outcome="accepted",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="enforce", condition="valid_token", expected_outcome="accepted", subject="reset_token"
            ),
            is_real_testable_requirement=True
        )

        test_pwd = TestNode(
            test_id="t-pwd",
            title="Password must include numbers",
            normalized_title="password must include numbers",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="enforce", condition="password_complexity", expected_outcome="enforced", subject="password"
            )
        )

        res2 = self.matching_service.match_requirement_to_test(req_token, test_pwd)
        assert res2.score == 0.0
        assert "SCOPED_TOKEN_PASSWORD_MISMATCH" in res2.diagnostics.get("rejection_reason")

        # combined token + password test can verify combined token + password requirement
        req_combined = RequirementNode(
            requirement_id="req-comb",
            readable_id="AC-comb",
            title="Reset-password with a valid unexpired token succeeds when new password is strong.",
            flow="password_reset",
            action="password_reset",
            condition="strong_password",
            expected_outcome="accepted",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="password_reset", condition="strong_password", expected_outcome="accepted", subject="password"
            ),
            is_real_testable_requirement=True
        )

        test_combined = TestNode(
            test_id="t-comb",
            title="Reset password succeeds with a valid token and strong password.",
            normalized_title="reset password succeeds with a valid token and strong password.",
            scenario_signature=ScenarioSignature(
                flow="password_reset", action="password_reset", condition="strong_password", expected_outcome="accepted", subject="password"
            )
        )

        res3 = self.matching_service.match_requirement_to_test(req_combined, test_combined)
        assert res3.score >= 0.85, f"Expected combined test/req to match, got {res3.score}"

    def test_stale_input_cta(self):
        """Test stale input health and CTAs."""
        builder = RecommendationViewModelBuilder()
        
        # Simulate stale inputs
        extraction_audit = {"has_stale_inputs": True}

        view_model = builder.build_view_model(
            requirements=[],
            tests=[],
            executions=[],
            coverage_nodes=[],
            missing_tests=[],
            match_table=[],
            excluded_fragments=[],
            extraction_audit=extraction_audit
        )

        assert view_model.health == "STALE_INPUTS"
        assert view_model.can_render_recommendation is True
        assert view_model.decision_copy.primary_cta == "Regenerate Recommendation"
        assert view_model.decision_copy.secondary_cta == "Review stale evidence"
