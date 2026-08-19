"""Tests for Acceptance Criterion identity preservation through the regression-evidence pipeline."""

import unittest
from unittest.mock import MagicMock
from app.routers.recommendation import _resolve_acceptance_criteria_text
from app.services.evidence_graph.ac_extraction_service import ACExtractionService
from app.models.acceptance_criterion import AcceptanceCriterion


class MockAC:
    def __init__(self, source_number, text):
        self.source_number = source_number
        self.text = text


class TestResolveAcceptanceCriteriaText(unittest.TestCase):

    def test_db_acceptance_criteria_are_ordered_by_source_number(self):
        """db_acceptance_criteria_are_ordered_by_source_number"""
        run = MagicMock()
        run.input_snapshot = None
        pr = MagicMock()

        # Query chain mock
        db = MagicMock()
        query = MagicMock()
        filter_result = MagicMock()
        order_result = MagicMock()
        db.query.return_value = query
        query.filter.return_value = filter_result
        filter_result.order_by.return_value = order_result
        order_result.all.return_value = [
            MockAC(1, "First"),
            MockAC(2, "Second"),
            MockAC(3, "Third"),
        ]

        from app.models.artifact import RawArtifact

        result = _resolve_acceptance_criteria_text(run, pr, db)

        # The function should order AcceptanceCriterion by source_number.
        # (order_by may also be called for the RawArtifact query.)
        filter_result.order_by.assert_any_call(AcceptanceCriterion.source_number)
        # Verify the returned text preserves numbered source identity.
        expected = "1. First\n2. Second\n3. Third"
        self.assertEqual(result["text"], expected)

    def test_db_acceptance_criteria_preserve_source_number_in_reconstructed_text(self):
        """db_acceptance_criteria_preserve_source_number_in_reconstructed_text"""
        run = MagicMock()
        run.input_snapshot = None
        pr = MagicMock()

        db = MagicMock()
        query = MagicMock()
        filter_result = MagicMock()
        order_result = MagicMock()
        db.query.return_value = query
        query.filter.return_value = filter_result
        filter_result.order_by.return_value = order_result
        order_result.all.return_value = [
            MockAC(13, "Leading and trailing spaces"),
            MockAC(14, "Password confirmation"),
            MockAC(25, "Atomic operation"),
        ]

        result = _resolve_acceptance_criteria_text(run, pr, db)

        expected = "13. Leading and trailing spaces\n14. Password confirmation\n25. Atomic operation"
        self.assertEqual(result["text"], expected)
        self.assertEqual(result["source_type"], "DB_ACCEPTANCE_CRITERION")

    def test_legacy_null_source_number_uses_existing_fallback(self):
        """legacy_null_source_number_uses_existing_fallback"""
        run = MagicMock()
        run.input_snapshot = None
        pr = MagicMock()

        db = MagicMock()
        query = MagicMock()
        filter_result = MagicMock()
        order_result = MagicMock()
        db.query.return_value = query
        query.filter.return_value = filter_result
        filter_result.order_by.return_value = order_result
        order_result.all.return_value = [
            MockAC(1, "Numbered one"),
            MockAC(None, "Legacy unnumbered"),
            MockAC(2, "Numbered two"),
        ]

        result = _resolve_acceptance_criteria_text(run, pr, db)

        self.assertIn("1. Numbered one", result["text"])
        self.assertIn("- Legacy unnumbered", result["text"])
        self.assertIn("2. Numbered two", result["text"])


class TestACExtractionIdentity(unittest.TestCase):

    def test_ac_extraction_uses_original_source_number(self):
        """ac_extraction_uses_original_source_number"""
        text = "13. Leading and trailing spaces are handled.\n14. Password confirmation must match."
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        ids = [node.readable_id for node in result.requirement_nodes]
        self.assertIn("AC-13", ids)
        self.assertIn("AC-14", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_unordered_db_insert_order_does_not_change_ac_identity(self):
        """unordered_db_insert_order_does_not_change_ac_identity"""
        # Text is already numbered, so shuffled lines still retain identity.
        text = (
            "14. Password confirmation must match the password field.\n"
            "25. Password update/reset operation is atomic: either the full update succeeds or nothing changes.\n"
            "13. Leading and trailing spaces are handled consistently according to the defined policy."
        )
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        by_id = {node.readable_id: node.title for node in result.requirement_nodes}
        self.assertIn("AC-13", by_id)
        self.assertIn("AC-14", by_id)
        self.assertIn("AC-25", by_id)
        self.assertIn("Leading and trailing spaces", by_id["AC-13"])
        self.assertIn("Password confirmation", by_id["AC-14"])
        self.assertIn("atomic", by_id["AC-25"])

    def test_ac_13_identity_matches_source_text(self):
        """ac_13_identity_matches_source_text"""
        text = "13. Leading and trailing spaces are handled consistently."
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        node = result.requirement_nodes[0]
        self.assertEqual(node.readable_id, "AC-13")
        self.assertIn("Leading and trailing spaces", node.title)

    def test_ac_14_identity_matches_source_text(self):
        """ac_14_identity_matches_source_text"""
        text = "14. Password confirmation must match the password field."
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        node = result.requirement_nodes[0]
        self.assertEqual(node.readable_id, "AC-14")
        self.assertIn("Password confirmation", node.title)

    def test_ac_25_identity_matches_source_text(self):
        """ac_25_identity_matches_source_text"""
        text = "25. Password update/reset operation is atomic: either the full update succeeds or nothing changes."
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        node = result.requirement_nodes[0]
        self.assertEqual(node.readable_id, "AC-25")
        self.assertIn("atomic", node.title)

    def test_all_25_fixture_ac_identities_match_source_number(self):
        """all_25_fixture_ac_identities_match_source_number"""
        # Build text with explicit numbers 1-25.
        lines = [f"{i}. Requirement number {i}" for i in range(1, 26)]
        text = "\n".join(lines)
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        readable_ids = [node.readable_id for node in result.requirement_nodes]
        expected = [f"AC-{i:02d}" for i in range(1, 26)]
        self.assertEqual(sorted(readable_ids), sorted(expected))
        self.assertEqual(len(readable_ids), len(set(readable_ids)))

        for i, node in enumerate(result.requirement_nodes, start=1):
            self.assertEqual(node.readable_id, f"AC-{i:02d}")

    def test_no_duplicate_or_missing_readable_ids(self):
        """no_duplicate_or_missing_readable_ids"""
        text = (
            "1. Weak passwords are rejected during sign-up.\n"
            "2. Strong passwords are accepted during sign-up.\n"
            "3. Weak passwords are rejected during update-password.\n"
            "4. Strong passwords are accepted during update-password.\n"
            "5. Minimum password length is enforced: at least 12 characters."
        )
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        ids = [node.readable_id for node in result.requirement_nodes]
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(set(ids)), 5)
        for i in range(1, 6):
            self.assertIn(f"AC-{i:02d}", ids)

    def test_unnumbered_text_uses_existing_fallback(self):
        """legacy unnumbered text falls back to positional counter"""
        text = (
            "- Weak passwords are rejected during sign-up.\n"
            "- Strong passwords are accepted during sign-up.\n"
            "- Minimum password length is enforced: at least 12 characters."
        )
        service = ACExtractionService()
        result = service.extract_acceptance_criteria(text)

        ids = [node.readable_id for node in result.requirement_nodes]
        self.assertEqual(ids, ["AC-01", "AC-02", "AC-03"])


if __name__ == "__main__":
    unittest.main()
