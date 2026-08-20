"""Regression tests: missing optional confidence/governance boosters must not force DRAFT_ONLY."""
from unittest.mock import MagicMock

import pytest

from app.services.input_readiness_v2_service import InputReadinessV2Service
from app.schemas.input_readiness_v2 import (
    InputReadinessItem,
    INPUT_WEIGHTS,
    INPUT_LABELS,
    HARD_BLOCKER_INPUTS,
)


def _item(input_id, status, details=None, earned=None):
    w = INPUT_WEIGHTS[input_id]
    earned = earned if earned is not None else (w if status == "READY" else 0.0)
    return InputReadinessItem(
        input_id=input_id,
        label=INPUT_LABELS[input_id],
        status=status,
        weight=w,
        earned_score=earned,
        max_score=w,
        is_hard_blocker=input_id in HARD_BLOCKER_INPUTS,
        summary=f"{input_id} {status}",
        details=details or {},
        actions=[],
    )


def _svc_with_inputs(items):
    """Build a service whose input evaluators return the supplied items."""
    svc = InputReadinessV2Service(MagicMock())
    by_id = {it.input_id: it for it in items}
    for n in range(1, 13):
        key = f"_evaluate_input_{n}"
        item = by_id.get(f"INPUT_{n}", _item(f"INPUT_{n}", "MISSING"))
        setattr(svc, key, lambda repository_id, pull_request_id, it=item: it)
    return svc


# ─── Baseline happy paths ───────────────────────────────────────────────────

def _all_ready():
    return [
        _item(f"INPUT_{n}", "READY") for n in range(1, 13)
    ]


def test_all_inputs_present_unchanged_confident():
    items = _all_ready()
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.can_generate == "YES"
    assert resp.can_generate_confident is True
    assert resp.generation_status in ("HIGH_CONFIDENCE_READY", "CONFIDENT_READY")
    assert resp.primary_reason == "All core inputs are ready."
    assert "INPUT_10" not in resp.primary_reason


def test_all_optional_boosters_missing_still_allows_ready_generation():
    """All hard blockers READY, score ≈ 90, all optional boosters MISSING."""
    items = [
        _item(f"INPUT_{n}", "READY") for n in range(1, 8)
    ] + [
        _item(f"INPUT_{n}", "MISSING") for n in range(8, 13)
    ]
    # Make sure i5 has confirmed mapping count
    for it in items:
        if it.input_id == "INPUT_5":
            it.details = {"confirmed_mapping_count": 25}
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.generation_status in ("HIGH_CONFIDENCE_READY", "CONFIDENT_READY"), resp.generation_status
    assert resp.generation_status != "DRAFT_ONLY"
    assert resp.can_generate == "YES"
    assert resp.can_generate_confident is True
    assert resp.primary_reason == "All core inputs are ready."
    assert "quality_gate_profile" not in resp.primary_reason.lower()
    assert "INPUT_10" in resp.missing_confidence_boosters
    assert any(w.code == "QUALITY_GATE_MISSING" for w in resp.warnings)


# ─── Single optional booster missing ──────────────────────────────────────────

@pytest.mark.parametrize("missing_id", [f"INPUT_{n}" for n in range(8, 13)])
def test_single_optional_booster_missing_does_not_force_draft(missing_id):
    items = [_item(f"INPUT_{n}", "READY") for n in range(1, 13)]
    for it in items:
        if it.input_id == missing_id:
            it.status = "MISSING"
            it.earned_score = 0.0
    for it in items:
        if it.input_id == "INPUT_5":
            it.details = {"confirmed_mapping_count": 25}
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.generation_status != "DRAFT_ONLY", f"{missing_id} missing forced DRAFT_ONLY"
    assert resp.can_generate_confident is True
    assert missing_id in resp.missing_confidence_boosters
    assert any(w.input_id == missing_id for w in resp.warnings)


# ─── Required tests from task list ───────────────────────────────────────────

def test_missing_release_context_does_not_block_confident_generation():
    items = _all_ready()
    for it in items:
        if it.input_id == "INPUT_8":
            it.status = "MISSING"
            it.earned_score = 0.0
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.can_generate_confident is True


def test_missing_environment_matrix_does_not_block_confident_generation():
    items = _all_ready()
    for it in items:
        if it.input_id == "INPUT_9":
            it.status = "MISSING"
            it.earned_score = 0.0
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.can_generate_confident is True


def test_missing_quality_gate_profile_does_not_block_confident_generation():
    items = _all_ready()
    for it in items:
        if it.input_id == "INPUT_10":
            it.status = "MISSING"
            it.earned_score = 0.0
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.can_generate_confident is True


def test_missing_known_defects_input_does_not_block_confident_generation():
    items = _all_ready()
    for it in items:
        if it.input_id == "INPUT_11":
            it.status = "MISSING"
            it.earned_score = 0.0
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.can_generate_confident is True


def test_missing_out_of_scope_input_does_not_block_confident_generation():
    items = _all_ready()
    for it in items:
        if it.input_id == "INPUT_12":
            it.status = "MISSING"
            it.earned_score = 0.0
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.can_generate_confident is True


# ─── Confidence booster metadata still works ─────────────────────────────────

def test_optional_boosters_still_emit_warnings_and_reduce_ceiling():
    items = [
        _item(f"INPUT_{n}", "READY") for n in range(1, 8)
    ] + [
        _item(f"INPUT_{n}", "MISSING") for n in range(8, 13)
    ]
    for it in items:
        if it.input_id == "INPUT_5":
            it.details = {"confirmed_mapping_count": 25}
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    missing_ids = {w.input_id for w in resp.warnings}
    for n in range(8, 13):
        assert f"INPUT_{n}" in missing_ids
    assert all(f"INPUT_{n}" in resp.missing_confidence_boosters for n in range(8, 13))


# ─── Hard blocker preservation ───────────────────────────────────────────────

def test_hard_blocker_missing_still_blocks_generation():
    items = [_item(f"INPUT_{n}", "READY") for n in range(1, 13)]
    for it in items:
        if it.input_id == "INPUT_5":
            it.status = "MISSING"
            it.earned_score = 0.0
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.generation_status == "BLOCKED"
    assert resp.can_generate == "NO"
    assert resp.can_generate_confident is False
    assert resp.can_generate_draft is False
    assert "INPUT_5" in resp.blocking_inputs


def test_hard_blocker_partial_still_preserves_existing_draft_behavior():
    items = [_item(f"INPUT_{n}", "READY") for n in range(1, 13)]
    for it in items:
        if it.input_id == "INPUT_5":
            it.status = "PARTIAL"
            it.earned_score = INPUT_WEIGHTS["INPUT_5"] * 0.5
    svc = _svc_with_inputs(items)
    resp = svc.assess(repository_id="test-repo", pull_request_id="test-pr")
    assert resp.generation_status == "DRAFT_ONLY"
    assert resp.can_generate == "DRAFT_ONLY"
    assert resp.can_generate_confident is False
    assert resp.can_generate_draft is True
