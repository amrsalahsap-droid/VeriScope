"""Tests for TestCase → TestNode explicit AC metadata propagation."""

import unittest
from unittest.mock import MagicMock, patch
from app.services.regression_evidence_integration import RegressionEvidenceIntegration
from app.services.regression_evidence_classifier import RequirementNode, TestNode
from app.services.evidence_graph.evidence_matching_service import EvidenceMatchingService
from app.models.test_result import TestCase


class MockTestCase:
    def __init__(
        self,
        tc_id,
        test_name,
        suite_name,
        source_metadata_json=None,
        external_ac_ref=None,
        properties=None,
    ):
        self.id = tc_id
        self.test_name = test_name
        self.stable_identity = f"{suite_name}::{test_name}"
        self.suite_name = suite_name
        self.source_metadata_json = source_metadata_json or {}
        self.external_ac_ref = external_ac_ref
        self.properties = properties or {}
        self.repository_id = "repo-1"


class TestTestNodeACMetadata(unittest.TestCase):

    def _make_integration(self, file_links=None):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = file_links or []
        return RegressionEvidenceIntegration(db)

    def test_node_reads_external_ac_ref(self):
        """test_node_reads_external_ac_ref"""
        tc = MockTestCase(
            tc_id="tc-1",
            test_name="should_validate_password",
            suite_name="auth",
            external_ac_ref="AC-10",
        )
        integr = self._make_integration()
        nodes = integr.build_test_nodes([tc])
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].declared_ac_id, "AC-10")
        self.assertEqual(
            nodes[0].acceptance_criterion_metadata["acceptance_criterion_id"], "AC-10"
        )

    def test_node_reads_declared_ac_id_from_source_metadata(self):
        """test_node_reads_declared_ac_id_from_source_metadata"""
        tc = MockTestCase(
            tc_id="tc-2",
            test_name="should_validate_password",
            suite_name="auth",
            source_metadata_json={"declared_ac_id": "AC-25"},
        )
        integr = self._make_integration()
        nodes = integr.build_test_nodes([tc])
        self.assertEqual(nodes[0].declared_ac_id, "AC-25")
        self.assertEqual(
            nodes[0].acceptance_criterion_metadata["ac_id"], "AC-25"
        )

    def test_node_reads_acceptance_criterion_metadata_from_source_metadata(self):
        """test_node_reads_acceptance_criterion_metadata_from_source_metadata"""
        tc = MockTestCase(
            tc_id="tc-3",
            test_name="should_validate_password",
            suite_name="auth",
            source_metadata_json={
                "acceptance_criterion": "AC-17",
                "acceptance_criterion_text": "UI and API validation rules are consistent",
            },
        )
        integr = self._make_integration()
        nodes = integr.build_test_nodes([tc])
        self.assertEqual(nodes[0].declared_ac_id, "AC-17")
        self.assertEqual(
            nodes[0].acceptance_criterion_metadata["acceptance_criterion_text"],
            "UI and API validation rules are consistent",
        )

    def test_exact_matching_ac_metadata_produces_direct_match(self):
        """exact_matching_ac_metadata_produces_direct_match"""
        tc = MockTestCase(
            tc_id="tc-4",
            test_name="should_reject_password_confirmation_mismatch",
            suite_name="auth",
            source_metadata_json={
                "declared_ac_id": "AC-14",
                "acceptance_criterion_text": "Password confirmation must match",
            },
        )
        integr = self._make_integration()
        test = integr.build_test_nodes([tc])[0]
        req = RequirementNode(
            requirement_id="req-14",
            readable_id="AC-14",
            title="Password confirmation must match the password field.",
            flow="",
            action="",
            condition="",
            expected_outcome="",
            polarity="positive",
            validation_layer="",
            risk_level="medium",
            source="acceptance_criteria",
            is_real_testable_requirement=True,
            scenario_signature=None,
            source_number=14,
        )
        service = EvidenceMatchingService()
        result = service.match_requirement_to_test(req, test)
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.diagnostics.get("mapping_type"), "DIRECT_AC_ID")

    def test_exact_matching_ac_metadata_outranks_fuzzy_similarity(self):
        """exact_matching_ac_metadata_outranks_fuzzy_similarity"""
        # Two tests: one with exact AC-07 metadata, one with similar title but no AC.
        exact_tc = MockTestCase(
            tc_id="tc-5",
            test_name="should_reject_weak_password_during_password_reset",
            suite_name="auth",
            source_metadata_json={"declared_ac_id": "AC-07"},
        )
        fuzzy_tc = MockTestCase(
            tc_id="tc-6",
            test_name="should_reject_weak_password_during_password_reset",
            suite_name="auth",
        )
        integr = self._make_integration()
        tests = integr.build_test_nodes([exact_tc, fuzzy_tc])
        req = RequirementNode(
            requirement_id="req-07",
            readable_id="AC-07",
            title="Weak passwords are rejected during reset-password.",
            flow="",
            action="",
            condition="",
            expected_outcome="",
            polarity="positive",
            validation_layer="",
            risk_level="medium",
            source="acceptance_criteria",
            is_real_testable_requirement=True,
            scenario_signature=None,
            source_number=7,
        )
        service = EvidenceMatchingService()
        results = [service.match_requirement_to_test(req, t) for t in tests]
        self.assertEqual(results[0].score, 1.0)
        self.assertEqual(results[0].diagnostics.get("mapping_type"), "DIRECT_AC_ID")
        # The fuzzy-only test should not beat the direct match.
        self.assertLess(results[1].score, 1.0)

    def test_without_ac_metadata_still_uses_existing_fuzzy_fallback(self):
        """test_without_ac_metadata_still_uses_existing_fuzzy_fallback"""
        tc = MockTestCase(
            tc_id="tc-7",
            test_name="should_reject_weak_password_during_signup",
            suite_name="auth",
        )
        integr = self._make_integration()
        test = integr.build_test_nodes([tc])[0]
        self.assertIsNone(test.declared_ac_id)
        self.assertIsNone(test.acceptance_criterion_metadata)

    def test_conflicting_explicit_ac_metadata_does_not_create_false_direct_match(self):
        """conflicting_explicit_ac_metadata_does_not_create_false_direct_match"""
        tc = MockTestCase(
            tc_id="tc-8",
            test_name="should_validate_password",
            suite_name="auth",
            source_metadata_json={"declared_ac_id": "AC-10"},
            external_ac_ref="AC-11",
        )
        integr = self._make_integration()
        test = integr.build_test_nodes([tc])[0]
        self.assertIsNone(test.declared_ac_id)
        self.assertIsNone(test.acceptance_criterion_metadata)

    def test_file_test_link_fallback_still_works(self):
        """FileTestLink fallback is used when no explicit test metadata is present."""
        from app.models.coverage import FileTestLink
        link = MagicMock()
        link.test_case_id = "tc-9"
        link.file_path = "AC-09"
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [link]
        integr = RegressionEvidenceIntegration(db)
        tc = MockTestCase(
            tc_id="tc-9",
            test_name="should_enforce_minimum_password_length",
            suite_name="auth",
        )
        test = integr.build_test_nodes([tc])[0]
        self.assertEqual(test.declared_ac_id, "AC-09")


class TestFixtureExactACIdentityIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings
        from app.models.recommendation import RecommendationRun
        from app.models.pull_request import PullRequest

        cls.engine = create_engine(settings.DATABASE_URL)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.run_id = "12e5e6a7-5842-4e6a-970f-da4de93dffde"

    def test_all_25_test_nodes_have_declared_ac_id(self):
        """all_25_clean_fixture_requirements_use_exact_ac_identity"""
        from app.models.recommendation import RecommendationRun
        with self.Session() as s:
            run = s.get(RecommendationRun, self.run_id)
            tcs = s.query(TestCase).filter(
                TestCase.repository_id == run.repository_id
            ).all()
            from app.services.regression_evidence_integration import RegressionEvidenceIntegration
            integr = RegressionEvidenceIntegration(s)
            nodes = integr.build_test_nodes(tcs)
            with_ids = {n.declared_ac_id for n in nodes if n.declared_ac_id}
            expected = {f"AC-{i:02d}" for i in range(1, 26)}
            self.assertTrue(expected.issubset(with_ids))


if __name__ == "__main__":
    unittest.main()
