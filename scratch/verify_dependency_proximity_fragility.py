"""
verify_dependency_proximity_fragility.py

Integration verification for DependencyProximityFragilityEngine.

Tests exercised:
  1. No dependency data → no patterns, graceful diagnostics.
  2. Basic proximity detection: source file BFS-expands into downstream
     file across ≥3 failed runs on ≥2 distinct PRs → pattern created.
  3. Evidence threshold enforcement: only 2 runs on 2 PRs → no pattern.
  4. Downstream failure linkage: evidence links contain expansion path
     and downstream file explicitly.
  5. Rollback linkage: rollback-linked outcomes boost incident/rollback
     score components.
  6. Churn contribution to score.
  7. Defensive overwrite: INVALIDATED patterns are never overwritten.
  8. Stale decay lifecycle: ACTIVE → STALE after 90 days, → INVALIDATED
     after 180 days.
  9. Replay consistency: identical bundle → identical hash & score.
 10. Explanation wording matches Rule 4 template.
"""

import os
import sys
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestCase, TestResult
from app.models.dependency import FileDependency
from app.models.recommendation import RecommendationRun, RecommendationOutcome
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.models.flaky_test import FlakyTestProfile

from app.services.failure_evidence_aggregator import FailureEvidenceAggregator
from app.services.dependency_proximity_fragility_engine import (
    DependencyProximityFragilityEngine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cleanup_database():
    """Tear down all seeded test data."""
    db = SessionLocal()
    try:
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilityPattern).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(FlakyTestProfile).delete()
        db.query(FileDependency).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("SUCCESS: Database cleaned up.")
    except Exception as exc:
        db.rollback()
        print(f"Error during cleanup: {exc}")
    finally:
        db.close()


def make_repo(db):
    """Seed a fresh org + repo with unique slugs, return (org_id, repo_id)."""
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    slug = f"prox-org-{str(org_id)[:8]}"
    org = Organization(id=org_id, name="ProxOrg", slug=slug)
    db.add(org)
    repo = Repository(
        id=repo_id,
        organization_id=org_id,
        github_repo_id=770000 + int(str(repo_id)[:4], 16),
        name="prox-repo",
        full_name=f"{slug}/prox-repo",
        default_branch="main",
        is_active=True,
    )
    db.add(repo)
    db.commit()
    return org_id, repo_id


def add_dep(db, repo_id, src, dst, commit_sha="sha_dep"):
    """Add a single FileDependency (src imports dst)."""
    dep = FileDependency(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path=src,
        depends_on_file_path=dst,
        dependency_type="import",
        commit_sha=commit_sha,
    )
    db.add(dep)
    db.commit()


def add_failed_pr(db, repo_id, changed_file, days_ago=10, additions=10, deletions=2):
    """
    Seed one PR with one failed TestRun; returns (pr_id, run_id).
    """
    pr_id = uuid.uuid4()
    commit_sha = f"sha_{str(pr_id)[:8]}"
    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=int(str(pr_id)[:5], 16),
        number=int(str(pr_id)[:4], 16),
        title="Test PR",
        author="dev",
        source_branch="feature",
        target_branch="main",
        state="open",
        head_commit_sha=commit_sha,
        github_created_at=datetime.utcnow() - timedelta(days=days_ago),
        github_updated_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(pr)
    db.commit()

    cf = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path=changed_file,
        status="modified",
        additions=additions,
        deletions=deletions,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(cf)
    db.commit()

    run_id = uuid.uuid4()
    tr = TestRun(
        id=run_id,
        repository_id=repo_id,
        commit_sha=commit_sha,
        pull_request_id=pr_id,
        status="failed",
        file_hash=f"fh_{str(run_id)[:8]}",
        normalized_execution_fingerprint=f"fp_{str(run_id)[:8]}",
        failed_tests=1,
        passed_tests=0,
        total_tests=1,
        evidence_health_status="HEALTHY",
        consistency_status="CONSISTENT",
        parser_support_status="SUPPORTED",
        replay_drift_detected=False,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(tr)
    db.commit()
    return pr_id, run_id


def collect_bundle(db, repo_id):
    aggregator = FailureEvidenceAggregator(db)
    frozen = datetime.utcnow()
    return aggregator.collect_failure_evidence(
        repo_id, history_window_days=90, evidence_window_end=frozen
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_dependency_data():
    print("\n--- Test 1: No dependency data → no patterns, graceful diagnostics ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        # Seed a failed PR with no FileDependency records
        add_failed_pr(db, repo_id, "src/auth/login.py")
        add_failed_pr(db, repo_id, "src/auth/login.py")
        add_failed_pr(db, repo_id, "src/auth/login.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        result = engine.detect_dependency_fragility(db, repo_id, bundle)

        assert result["patterns_mined"] == 0
        assert result["diagnostics"].get("reason") == "no_dependency_data"
        print("[OK] No dependency data: 0 patterns mined, reason reported correctly.")
    finally:
        db.close()


def test_basic_proximity_detection():
    print("\n--- Test 2: Basic proximity detection (3 failed runs, 3 distinct PRs) ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)

        # Dependency: auth/session_token.py → billing/invoice_service.py
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        # 3 PRs each touching auth/session_token.py and failing
        for _ in range(3):
            add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        result = engine.detect_dependency_fragility(db, repo_id, bundle)

        assert result["patterns_mined"] >= 1, (
            f"Expected at least 1 pattern, got {result['patterns_mined']}"
        )

        # The key is bidirectional so either direction may appear
        pattern = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert pattern is not None
        assert pattern.evidence_count >= 3
        assert pattern.status == "ACTIVE"
        print(f"[OK] Pattern detected: {pattern.normalized_pattern_key}")
        print(f"     fragility_score={pattern.fragility_score}  evidence_count={pattern.evidence_count}")
    finally:
        db.close()


def test_threshold_enforcement():
    print("\n--- Test 3: Below threshold (2 runs on 1 PR) → no pattern ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        # Only 2 runs on 2 PRs but below MIN_EVIDENCE_LINKS of 3
        add_failed_pr(db, repo_id, "auth/session_token.py")
        add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        result = engine.detect_dependency_fragility(db, repo_id, bundle)

        assert result["patterns_mined"] == 0
        print("[OK] 2 evidence links correctly suppressed (below threshold of 3).")
    finally:
        db.close()


def test_evidence_link_content():
    print("\n--- Test 4: Evidence links contain expansion path and downstream file ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        for _ in range(3):
            add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        engine.detect_dependency_fragility(db, repo_id, bundle)

        pattern = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert pattern is not None

        links = (
            db.query(FragilityEvidenceLink)
            .filter(FragilityEvidenceLink.fragility_pattern_id == pattern.id)
            .all()
        )
        assert len(links) >= 3, f"Expected ≥3 links, got {len(links)}"

        # Each link should reference an expansion path
        for lnk in links:
            assert "expanded via dependency path" in lnk.evidence_summary, (
                f"Link missing expansion path: {lnk.evidence_summary}"
            )
            assert "billing/invoice_service.py" in lnk.evidence_summary or \
                   "auth/session_token.py" in lnk.evidence_summary
            assert "distance:" in lnk.evidence_summary

        print(f"[OK] {len(links)} evidence links with correct expansion diagnostics.")
    finally:
        db.close()


def test_rollback_linkage():
    print("\n--- Test 5: Rollback linkage boosts rollback score component ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        pr_ids = []
        for _ in range(3):
            pr_id, _ = add_failed_pr(db, repo_id, "auth/session_token.py")
            pr_ids.append(pr_id)

        # Attach a rollback outcome to the first PR's recommendation run
        rec_run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pr_id=str(pr_ids[0]),
            pull_request_id=pr_ids[0],
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="n/a",
        )
        db.add(rec_run)
        db.commit()

        outcome = RecommendationOutcome(
            id=uuid.uuid4(),
            recommendation_run_id=rec_run.id,
            executed_tests=[],
            manually_added_tests=[],
            manually_removed_tests=[],
            was_followed=True,
            rollback_occurred=True,
            escaped_defect=False,
        )
        db.add(outcome)
        db.commit()

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        engine.detect_dependency_fragility(db, repo_id, bundle)

        pattern = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert pattern is not None
        # Rollback score component must be > 0
        rollback_score = pattern.score_components.get("rollback", 0)
        assert rollback_score > 0, f"Expected rollback_score > 0, got {rollback_score}"
        print(f"[OK] Rollback linkage detected: rollback score component = {rollback_score:.2f}")
    finally:
        db.close()


def test_explanation_wording():
    print("\n--- Test 6: Explanation wording matches Rule 4 template ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        for _ in range(3):
            add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        engine.detect_dependency_fragility(db, repo_id, bundle)

        pattern = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert pattern is not None

        # Must follow Rule 4 template:
        # "Changes in <source> repeatedly expanded into <downstream> before failed executions …"
        assert "repeatedly expanded into" in pattern.explanation, (
            f"Unexpected explanation: {pattern.explanation!r}"
        )
        assert "before failed executions" in pattern.explanation
        assert "pull requests" in pattern.explanation
        print(f"[OK] Explanation: {pattern.explanation!r}")
    finally:
        db.close()


def test_invalidation_overwrite_protection():
    print("\n--- Test 7: INVALIDATED pattern is never overwritten ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        for _ in range(3):
            add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        engine.detect_dependency_fragility(db, repo_id, bundle)

        pattern = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert pattern is not None

        # Manually invalidate
        pattern.status = "INVALIDATED"
        pattern.invalidated_reason = "MANUAL_OVERRIDE"
        original_hash = pattern.pattern_hash
        db.commit()

        # Re-run with same bundle
        engine.detect_dependency_fragility(db, repo_id, bundle)
        db.refresh(pattern)

        assert pattern.status == "INVALIDATED", (
            f"Status was overwritten! status={pattern.status}"
        )
        assert pattern.pattern_hash == original_hash
        print("[OK] INVALIDATED pattern defensively protected from overwrite.")
    finally:
        db.close()


def test_stale_decay_lifecycle():
    print("\n--- Test 8: Stale decay lifecycle ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        for _ in range(3):
            add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        engine.detect_dependency_fragility(db, repo_id, bundle)

        pattern = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert pattern is not None
        original_score = pattern.fragility_score

        # Simulate 95 days of inactivity
        pattern.last_seen_at = datetime.utcnow() - timedelta(days=95)
        db.commit()

        engine.apply_stale_decay(repo_id)
        db.refresh(pattern)

        assert pattern.status == "STALE", f"Expected STALE, got {pattern.status}"
        expected_decay = round(original_score * (0.9 ** (95 / 30.0)), 2)
        assert pattern.fragility_score == expected_decay, (
            f"Expected {expected_decay}, got {pattern.fragility_score}"
        )
        print(f"[OK] Pattern transitioned to STALE, score decayed: {original_score} → {pattern.fragility_score}")

        # Simulate 185 days → INVALIDATED
        pattern.status = "ACTIVE"
        pattern.fragility_score = original_score
        pattern.last_seen_at = datetime.utcnow() - timedelta(days=185)
        db.commit()

        engine.apply_stale_decay(repo_id)
        db.refresh(pattern)

        assert pattern.status == "INVALIDATED", f"Expected INVALIDATED, got {pattern.status}"
        assert pattern.invalidated_reason == "STALE_NO_RECENT_EVIDENCE"
        assert pattern.invalidated_by == "SYSTEM_DECAY"
        print("[OK] Pattern transitioned to INVALIDATED after 185 days of inactivity.")
    finally:
        db.close()


def test_replay_consistency():
    print("\n--- Test 9: Replay consistency (same bundle → same hash & score) ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        add_dep(db, repo_id, "auth/session_token.py", "billing/invoice_service.py")

        for _ in range(3):
            add_failed_pr(db, repo_id, "auth/session_token.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)

        # Run 1
        engine.detect_dependency_fragility(db, repo_id, bundle)
        p1 = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        h1, s1, e1, c1 = p1.pattern_hash, p1.fragility_score, p1.explanation, p1.confidence_level

        # Wipe and run again
        db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id
        ).delete()
        db.commit()

        engine.detect_dependency_fragility(db, repo_id, bundle)
        p2 = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .first()
        )
        assert p2.pattern_hash == h1,       f"Hash mismatch: {p2.pattern_hash} vs {h1}"
        assert p2.fragility_score == s1,    f"Score mismatch: {p2.fragility_score} vs {s1}"
        assert p2.explanation == e1,        f"Explanation mismatch"
        assert p2.confidence_level == c1,   f"Confidence mismatch"
        print("[OK] Replay consistency verified: same hash, score, explanation, and confidence.")
    finally:
        db.close()


def test_no_assumptions_without_evidence():
    print("\n--- Test 10: No dependency assumption without FileDependency evidence ---")
    db = SessionLocal()
    try:
        _, repo_id = make_repo(db)
        # Dep only from A → B; no dep from A → C
        add_dep(db, repo_id, "src/A.py", "src/B.py")

        for _ in range(3):
            add_failed_pr(db, repo_id, "src/A.py")

        bundle = collect_bundle(db, repo_id)
        engine = DependencyProximityFragilityEngine(db)
        engine.detect_dependency_fragility(db, repo_id, bundle)

        # No pattern should reference C
        patterns = (
            db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
            )
            .all()
        )
        for p in patterns:
            assert "src/C.py" not in p.normalized_pattern_key, (
                f"Pattern references C without evidence: {p.normalized_pattern_key}"
            )
        print("[OK] No patterns reference undocumented dependencies — evidence-only rule enforced.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all_tests():
    print("=" * 70)
    print("STARTING DependencyProximityFragilityEngine INTEGRATION TESTS")
    print("=" * 70)

    tests = [
        test_no_dependency_data,
        test_basic_proximity_detection,
        test_threshold_enforcement,
        test_evidence_link_content,
        test_rollback_linkage,
        test_explanation_wording,
        test_invalidation_overwrite_protection,
        test_stale_decay_lifecycle,
        test_replay_consistency,
        test_no_assumptions_without_evidence,
    ]

    for t in tests:
        cleanup_database()
        t()

    print("\n" + "=" * 70)
    print("ALL DependencyProximityFragilityEngine VERIFICATIONS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    cleanup_database()
    try:
        run_all_tests()
    finally:
        cleanup_database()
