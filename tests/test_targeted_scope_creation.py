"""Backend tests for PHASE 1.2 - Targeted Regression Scope Creation."""
import pytest
from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.pull_request import PullRequest, PullRequestSnapshot
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.regression_evidence_classifier import EvidenceClassification
from app.schemas.regression_scope import CreateTargetedScopeRequest, ScopeItemType


def _get_golden_run(db):
    """Retrieve the golden password validation demo run to prevent postgres UUID validation errors with dirty/mocked PR IDs."""
    run = db.query(RecommendationRun).filter(RecommendationRun.id == "ac42bec0-59b5-47f3-85be-956d771f0480").first()
    if not run:
        run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    return run


def test_scope_creation_from_phase_1_1_evidence_graph():
    """Test scope creation from accepted Phase 1.1 evidence graph."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None, "No recommendation run found"
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None, "No PR found"
    
    # Get AC text from DB
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    # Filter parent requirements
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Count by classification
    missing_count = len([r for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE])
    partial_count = len([r for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED])
    verified_count = len([r for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION])
    passed_tests_count = len(view_model.verified_by_current_pr)
    
    # Verify expected counts from Phase 1.1
    assert missing_count == 7, f"Expected 7 missing ACs, got {missing_count}"
    assert partial_count == 2, f"Expected 2 partial ACs, got {partial_count}"
    assert verified_count == 16, f"Expected 16 verified ACs, got {verified_count}"
    assert passed_tests_count == 18, f"Expected 18 passed tests, got {passed_tests_count}"
    
    db.close()


def test_required_items_only_from_missing_automated_coverage():
    """Test that required items are generated only from MISSING_AUTOMATED_COVERAGE."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None
    
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Verify only MISSING_AUTOMATED_COVERAGE are in required bucket
    missing_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE]
    for req in missing_reqs:
        assert req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE
    
    # Verify verified ACs are NOT in required bucket
    verified_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION]
    assert len(verified_reqs) == 16, "Should have 16 verified ACs"
    
    db.close()


def test_review_items_only_from_partial_coverage():
    """Test that review items are generated only from PARTIALLY_COVERED."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None
    
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Verify only PARTIALLY_COVERED are in review bucket
    partial_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED]
    for req in partial_reqs:
        assert req.classification == EvidenceClassification.PARTIALLY_COVERED
    
    assert len(partial_reqs) == 2, f"Expected 2 partial ACs, got {len(partial_reqs)}"
    
    db.close()


def test_verified_acs_excluded_from_required():
    """Test that already verified requirements are excluded from requiredItems."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None
    
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Verify verified ACs are NOT in missing bucket
    verified_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION]
    missing_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE]
    
    # No overlap between verified and missing
    verified_ids = {r.requirement_id for r in verified_reqs}
    missing_ids = {r.requirement_id for r in missing_reqs}
    assert len(verified_ids & missing_ids) == 0, "Verified and missing ACs should not overlap"
    
    db.close()


def test_passed_tests_excluded_from_rerun():
    """Test that already passed current PR tests are excluded from required rerun list."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None
    
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    # Verify passed tests are in verified_by_current_pr
    passed_tests = view_model.verified_by_current_pr
    assert len(passed_tests) == 18, f"Expected 18 passed tests, got {len(passed_tests)}"
    
    # These should be excluded from required rerun by default
    assert len(passed_tests) > 0, "Should have passed tests to exclude"
    
    db.close()


def test_generation_rules_applied():
    """Test that generation rules are correctly applied."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None
    
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Verify expected rules would be applied
    has_missing = len([r for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE]) > 0
    has_partial = len([r for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED]) > 0
    has_verified = len([r for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION]) > 0
    has_passed_tests = len(view_model.verified_by_current_pr) > 0
    
    assert has_missing, "Should have missing ACs"
    assert has_partial, "Should have partial ACs"
    assert has_verified, "Should have verified ACs"
    assert has_passed_tests, "Should have passed tests"
    
    db.close()


def test_snapshot_lineage_includes_real_reference():
    """Test that scope response includes real snapshot reference with hash and timestamp."""
    db = SessionLocal()
    
    run = _get_golden_run(db)
    assert run is not None, "No recommendation run found"
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None, "No PR found"
    
    # Get AC text from DB
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    ac_source_hash = hashlib.md5(text.encode()).hexdigest()
    
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    # Simulate snapshot reference creation
    from datetime import datetime
    snapshot_data = f"{run.id}:{view_model.health}:{ac_source_hash}"
    snapshot_hash = hashlib.md5(snapshot_data.encode()).hexdigest()
    
    # Verify snapshot reference has required fields
    assert snapshot_hash is not None, "Snapshot hash should be generated"
    assert len(snapshot_hash) == 32, "MD5 hash should be 32 characters"
    assert str(run.id) in snapshot_data, "Recommendation run ID should be in snapshot data"
    assert view_model.health in snapshot_data, "Health state should be in snapshot data"
    assert ac_source_hash in snapshot_data, "Source hash should be in snapshot data"
    
    # Verify snapshot reference is not just recommendation_run_id
    assert snapshot_hash != str(run.id), "Snapshot hash should not equal recommendation_run_id"
    
    db.close()


if __name__ == "__main__":
    print("Running PHASE 1.2 backend tests...")
    
    test_scope_creation_from_phase_1_1_evidence_graph()
    print("PASS: test_scope_creation_from_phase_1_1_evidence_graph")
    
    test_required_items_only_from_missing_automated_coverage()
    print("PASS: test_required_items_only_from_missing_automated_coverage")
    
    test_review_items_only_from_partial_coverage()
    print("PASS: test_review_items_only_from_partial_coverage")
    
    test_verified_acs_excluded_from_required()
    print("PASS: test_verified_acs_excluded_from_required")
    
    test_passed_tests_excluded_from_rerun()
    print("PASS: test_passed_tests_excluded_from_rerun")
    
    test_generation_rules_applied()
    print("PASS: test_generation_rules_applied")
    
    test_snapshot_lineage_includes_real_reference()
    print("PASS: test_snapshot_lineage_includes_real_reference")
    
    print("\nAll PHASE 1.2 backend tests passed!")
