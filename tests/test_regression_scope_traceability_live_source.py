"""Tests that RegressionScopeV2.traceability_summary uses live evidence, not stale snapshots."""

import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.recommendation import RecommendationRun
from app.schemas.regression_scope_v2 import ScopeMode
from app.services.regression_scope_v2_service import RegressionScopeV2Service
from app.services.evidence_graph.recommendation_view_model_builder import (
    ACTraceabilityRow,
    RecommendationEvidenceViewModel,
)


@pytest.fixture
def db():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        yield s


@pytest.fixture
def fixture_run_id():
    return "12e5e6a7-5842-4e6a-970f-da4de93dffde"


class TestTraceabilitySummaryUsesLiveEvidence:
    def test_traceability_summary_uses_live_requirement_evidence(self, db, fixture_run_id):
        """traceability_summary_uses_live_requirement_evidence"""
        scope = RegressionScopeV2Service.generate_scope_v2(
            db, fixture_run_id, mode=ScopeMode.TARGETED
        )
        ts = scope.traceability_summary
        # Live graph has 25 verified; snapshot has 23 covered + 1 review + 1 missing
        assert ts.total_requirements == 25
        assert ts.covered == 25
        assert ts.missing == 0
        assert ts.not_mapped == 0
        assert ts.review_required == 0
        assert ts.unknown_statuses == []

    def test_stale_snapshot_does_not_override_live_traceability(self, db, fixture_run_id):
        """stale_snapshot_does_not_override_live_traceability"""
        run = db.get(RecommendationRun, fixture_run_id)
        before = run.requirement_evidence_snapshot_json
        snapshot = json.loads(before) if isinstance(before, str) else before
        assert snapshot["acTraceability"][0].get("coverageStatus") != "VERIFIED_BY_CURRENT_PR_EXECUTION"

        scope = RegressionScopeV2Service.generate_scope_v2(
            db, fixture_run_id, mode=ScopeMode.TARGETED
        )
        # Result must reflect live evidence, not stale snapshot
        assert scope.traceability_summary.covered == 25

    def test_clean_fixture_returns_25_covered(self, db, fixture_run_id):
        """clean_fixture_returns_25_covered"""
        scope = RegressionScopeV2Service.generate_scope_v2(
            db, fixture_run_id, mode=ScopeMode.TARGETED
        )
        ts = scope.traceability_summary
        assert ts.total_requirements == 25
        assert ts.covered == 25
        assert ts.missing == 0
        assert ts.not_mapped == 0
        assert ts.review_required == 0

    def test_historical_requirement_evidence_snapshot_is_not_mutated(self, db, fixture_run_id):
        """historical_requirement_evidence_snapshot_is_not_mutated"""
        run = db.get(RecommendationRun, fixture_run_id)
        before = run.requirement_evidence_snapshot_json
        RegressionScopeV2Service.generate_scope_v2(
            db, fixture_run_id, mode=ScopeMode.TARGETED
        )
        db.refresh(run)
        after = run.requirement_evidence_snapshot_json
        assert json.dumps(before, sort_keys=True, default=str) == json.dumps(after, sort_keys=True, default=str)

    def test_traceability_total_equals_all_buckets(self, db, fixture_run_id):
        """traceability_total_equals_all_buckets"""
        scope = RegressionScopeV2Service.generate_scope_v2(
            db, fixture_run_id, mode=ScopeMode.TARGETED
        )
        ts = scope.traceability_summary
        assert ts.total_requirements == (
            ts.covered + ts.missing + ts.not_mapped + ts.review_required
        )


class TestTraceabilitySummaryBucketsFromLiveRows:
    @staticmethod
    def _make_view_model(statuses):
        view_model = RecommendationEvidenceViewModel()
        for i, status in enumerate(statuses):
            view_model.ac_traceability.append(
                ACTraceabilityRow(
                    requirement_id=f"req-{i}",
                    readable_id=f"AC-{i+1:02d}",
                    title=f"Requirement {i+1}",
                    full_text=f"Full text {i+1}",
                    coverage_status=status,
                    linked_existing_tests=[],
                    linked_missing_test=None,
                    priority="Recommended",
                    notes="",
                    database_ac_id=f"db-ac-{i}" if status != "NOT_MAPPED_TRACEABILITY_RISK" else None,
                )
            )
        return view_model

    def _run_with_patched_evidence(self, db, fixture_run_id, statuses):
        view_model = self._make_view_model(statuses)
        with patch(
            "app.services.evidence_graph.requirement_evidence_graph_service.RequirementEvidenceGraphService.build_evidence_graph",
            return_value=view_model,
        ):
            return RegressionScopeV2Service.generate_scope_v2(
                db, fixture_run_id, mode=ScopeMode.TARGETED
            )

    def test_live_partial_requirement_counts_as_review_required(self, db, fixture_run_id):
        """live_partial_requirement_counts_as_review_required"""
        statuses = ["Covered"] * 24 + ["Coverage Recommendation"]
        scope = self._run_with_patched_evidence(db, fixture_run_id, statuses)
        ts = scope.traceability_summary
        assert ts.covered == 24
        assert ts.review_required == 1
        assert ts.missing == 0
        assert ts.not_mapped == 0

    def test_live_missing_coverage_counts_as_missing(self, db, fixture_run_id):
        """live_missing_coverage_counts_as_missing"""
        statuses = ["Covered"] * 24 + ["Evidence Gap"]
        scope = self._run_with_patched_evidence(db, fixture_run_id, statuses)
        ts = scope.traceability_summary
        assert ts.covered == 24
        assert ts.missing == 1
        assert ts.review_required == 0
        assert ts.not_mapped == 0

    def test_live_not_mapped_counts_as_not_mapped(self, db, fixture_run_id):
        """live_not_mapped_counts_as_not_mapped"""
        statuses = ["Covered"] * 24 + ["NOT_MAPPED_TRACEABILITY_RISK"]
        scope = self._run_with_patched_evidence(db, fixture_run_id, statuses)
        ts = scope.traceability_summary
        assert ts.covered == 24
        assert ts.not_mapped == 1
        assert ts.missing == 0
        assert ts.review_required == 0

    def test_mixed_live_fixture_buckets_correctly(self, db, fixture_run_id):
        """mixed_live_fixture_buckets_correctly"""
        statuses = (
            ["Covered"] * 20
            + ["Coverage Recommendation", "Coverage Recommendation"]
            + ["Evidence Gap"]
            + ["NOT_MAPPED_TRACEABILITY_RISK"]
            + ["Review Needed"]
        )
        scope = self._run_with_patched_evidence(db, fixture_run_id, statuses)
        ts = scope.traceability_summary
        assert ts.total_requirements == 25
        assert ts.covered == 20
        assert ts.missing == 1
        assert ts.not_mapped == 1
        assert ts.review_required == 3
        assert ts.total_requirements == (
            ts.covered + ts.missing + ts.not_mapped + ts.review_required
        )

    def test_build_scope_does_not_create_duplicate_evidence_state(self, db, fixture_run_id):
        """build_scope_does_not_create_duplicate_evidence_state"""
        run_before = db.get(RecommendationRun, fixture_run_id)
        snapshot_before = run_before.requirement_evidence_snapshot_json
        scope = RegressionScopeV2Service.generate_scope_v2(
            db, fixture_run_id, mode=ScopeMode.TARGETED
        )
        db.refresh(run_before)
        snapshot_after = run_before.requirement_evidence_snapshot_json
        # Snapshot unchanged and no new persisted evidence rows appear
        assert snapshot_before == snapshot_after
        assert scope.traceability_summary.covered == 25
