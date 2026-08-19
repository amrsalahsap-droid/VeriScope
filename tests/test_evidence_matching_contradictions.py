"""Tests for EvidenceMatchingService hard-contradiction rules."""

import unittest
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService
from app.services.regression_evidence_classifier import (
    EvidenceClassification,
    ScenarioSignatureGenerator,
    RequirementNode,
    TestNode,
)


class TestContradictionResetUpdate(unittest.TestCase):

    def _make_nodes(self, req_title, test_title, req_flow=None, test_flow=None):
        req = RequirementNode(
            requirement_id="req-1",
            readable_id="AC-X",
            title=req_title,
            flow=req_flow or "",
            action="",
            condition="",
            expected_outcome="",
            polarity="positive",
            validation_layer="",
            risk_level="medium",
            source="acceptance_criteria",
            is_real_testable_requirement=True,
            scenario_signature=None,
        )
        test = TestNode(
            test_id="tc-1",
            title=test_title,
            normalized_title=test_title,
            classname="auth",
            file_path="",
            test_type="unit",
            automation_status="existing_automated",
            mapped_requirement_ids=[],
            scenario_signature=None,
            properties={},
            declared_ac_id=None,
            acceptance_criterion_metadata=None,
        )
        req.scenario_signature = ScenarioSignatureGenerator.generate_signature(req_title)
        test.scenario_signature = ScenarioSignatureGenerator.generate_signature(test_title)
        req.scenario_signature.flow = req_flow or "account_security_validation"
        test.scenario_signature.flow = test_flow or "account_security_validation"
        return req, test

    def test_compound_update_reset_pair_is_not_contradiction(self):
        """compound_update_reset_pair_is_not_contradiction"""
        req, test = self._make_nodes(
            "Password update/reset operation is atomic",
            "should_apply_password_update_reset_atomically",
        )
        service = EvidenceMatchingService()
        result = service._check_hard_contradictions(req, test)
        self.assertFalse(result["is_contradiction"])
        self.assertNotEqual(result["rule"], "RESET_PASSWORD vs UPDATE_PASSWORD")

    def test_reset_only_vs_update_only_is_contradiction(self):
        """reset_only_vs_update_only_is_contradiction"""
        req, test = self._make_nodes(
            "should reject weak password during password reset",
            "should login with new password after successful update",
        )
        service = EvidenceMatchingService()
        result = service._check_hard_contradictions(req, test)
        self.assertTrue(result["is_contradiction"])
        self.assertIn("RESET_PASSWORD vs UPDATE_PASSWORD", result["rule"])

    def test_update_only_vs_reset_only_is_contradiction(self):
        """update_only_vs_reset_only_is_contradiction"""
        req, test = self._make_nodes(
            "should login with new password after successful update",
            "should reject weak password during password reset",
        )
        service = EvidenceMatchingService()
        result = service._check_hard_contradictions(req, test)
        self.assertTrue(result["is_contradiction"])
        self.assertIn("RESET_PASSWORD vs UPDATE_PASSWORD", result["rule"])

    def test_reset_only_vs_compound_update_reset_is_not_false_contradiction(self):
        """reset_only_vs_compound_update_reset_is_not_false_contradiction"""
        req, test = self._make_nodes(
            "reset the user password",
            "should apply password update and reset operation",
        )
        service = EvidenceMatchingService()
        result = service._check_hard_contradictions(req, test)
        self.assertFalse(result["is_contradiction"])

    def test_compound_update_reset_vs_update_only_is_not_false_contradiction(self):
        """compound_update_reset_vs_update_only_is_not_false_contradiction"""
        req, test = self._make_nodes(
            "Password update/reset operation is atomic",
            "should login with new password after successful update",
            test_flow="account_security_validation",
        )
        service = EvidenceMatchingService()
        result = service._check_hard_contradictions(req, test)
        self.assertFalse(result["is_contradiction"])

    def test_flow_based_reset_vs_update_contradiction_remains(self):
        """flow-based reset vs update contradiction remains"""
        req, test = self._make_nodes(
            "reset password",
            "update password",
            req_flow="PASSWORD_RESET",
            test_flow="UPDATE_PASSWORD",
        )
        service = EvidenceMatchingService()
        result = service._check_hard_contradictions(req, test)
        self.assertTrue(result["is_contradiction"])
        self.assertIn("RESET_PASSWORD vs UPDATE_PASSWORD", result["rule"])

    def test_genuine_non_flow_hard_contradiction_still_rejects_direct_ac_id(self):
        """genuine_non_flow_hard_contradiction_still_rejects_direct_ac_id"""
        req, test = self._make_nodes(
            "reject weak password attempts",
            "accept strong password",
        )
        test.declared_ac_id = "AC-GEN"
        test.acceptance_criterion_metadata = {
            "acceptance_criterion_id": "AC-GEN",
            "ac_id": "AC-GEN",
        }
        req.readable_id = "AC-GEN"
        service = EvidenceMatchingService()
        result = service.match_requirement_to_test(req, test)
        self.assertEqual(result.score, 0.0)
        self.assertTrue(result.diagnostics.get("JUNIT_AC_ID_MISMATCH"))


class TestFixtureAC25Verified(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings

        cls.engine = create_engine(settings.DATABASE_URL)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.run_id = "12e5e6a7-5842-4e6a-970f-da4de93dffde"

    def _build_graph(self):
        from app.models.recommendation import RecommendationRun
        from app.models.pull_request import PullRequest
        from app.routers.recommendation import _resolve_acceptance_criteria_text
        from app.services.evidence_graph.requirement_evidence_graph_service import (
            RequirementEvidenceGraphService,
        )

        with self.Session() as s:
            run = s.get(RecommendationRun, self.run_id)
            pr = s.get(PullRequest, run.pull_request_id)
            ac_source = _resolve_acceptance_criteria_text(run, pr, s)
            service = RequirementEvidenceGraphService(s)
            return service.build_evidence_graph(
                repository_id=str(run.repository_id),
                pull_request_id=str(pr.id),
                head_sha=pr.head_commit_sha,
                changed_files=[],
                pr_description=ac_source["text"],
                recommendation_run_id=str(run.id),
            )

    def test_ac_25_direct_match_not_rejected(self):
        """ac_25_direct_match_not_rejected"""
        view_model = self._build_graph()
        req = next((r for r in view_model.requirements if r.readable_id == "AC-25"), None)
        self.assertIsNotNone(req)
        self.assertEqual(req.match_score, 1.0)
        diag = req.match_diagnostics or {}
        md = diag.get("matching_dimensions", {})
        self.assertEqual(diag.get("mapping_type"), "DIRECT_AC_ID")
        self.assertEqual(md.get("test_title"), "should_apply_password_update_reset_atomically")

    def test_ac_25_classified_verified_by_current_pr_execution(self):
        """ac_25_classified_verified_by_current_pr_execution"""
        view_model = self._build_graph()
        req = next((r for r in view_model.requirements if r.readable_id == "AC-25"), None)
        self.assertIsNotNone(req)
        self.assertEqual(req.classification, EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION)
        self.assertIn("score: 1.00", req.classification_reason.lower())

    def test_all_25_clean_fixture_requirements_verified(self):
        """all_25_clean_fixture_requirements_verified"""
        view_model = self._build_graph()
        from collections import Counter
        counts = Counter(r.classification for r in view_model.requirements if r.node_type == "PARENT_REQUIREMENT")
        self.assertEqual(counts.get(EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION, 0), 25)
        self.assertEqual(counts.get(EvidenceClassification.PARTIALLY_COVERED, 0), 0)
        self.assertEqual(counts.get(EvidenceClassification.MISSING_AUTOMATED_COVERAGE, 0), 0)


if __name__ == "__main__":
    unittest.main()
