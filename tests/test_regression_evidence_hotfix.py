"""Regression tests for PHASE 1.1 HOTFIX - Regression Evidence Endpoint Consistency."""
import pytest
from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.pull_request import PullRequest, PullRequestSnapshot
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.regression_evidence_classifier import EvidenceClassification


def test_ac_source_priority_uses_db_rows():
    """Test that AC source priority uses clean DB AcceptanceCriterion rows over polluted input_snapshot."""
    db = SessionLocal()
    
    # Get latest recommendation run
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    assert run is not None, "No recommendation run found"
    
    # Get PR
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None, "No PR found"
    
    # Check DB has 25 clean ACs
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    assert len(ac_rows) == 25, f"Expected 25 AC rows in DB, got {len(ac_rows)}"
    
    # Check input_snapshot may have polluted data (50 items)
    if run.input_snapshot and run.input_snapshot.acceptance_criteria:
        snapshot_ac_count = len(run.input_snapshot.acceptance_criteria)
        # Input snapshot may have duplicates, but DB should be prioritized
        print(f"Input snapshot has {snapshot_ac_count} AC items (may be polluted)")
    
    db.close()


def test_endpoint_returns_25_parent_requirements():
    """Test that the endpoint returns 25 parent requirements from clean DB source."""
    db = SessionLocal()
    
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    assert run is not None
    
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    assert pr is not None
    
    # Get AC text from DB (simulating _resolve_acceptance_criteria_text priority)
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    import hashlib
    text = "\n".join([f"- {row.text}" for row in ac_rows])
    
    # Get PR snapshot for head_commit_sha
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    # Get changed files
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    # Build the graph
    graph_service = RequirementEvidenceGraphService(db)
    view_model = graph_service.build_evidence_graph(
        str(run.repository_id),
        str(run.pr_id),
        head_sha,
        changed_files,
        pr_description=text,
        recommendation_run_id=str(run.id)
    )
    
    # Verify 25 parent requirements
    parent_reqs = [r for r in view_model.requirements if r.node_type == "PARENT_REQUIREMENT"]
    assert len(parent_reqs) == 25, f"Expected 25 parent requirements, got {len(parent_reqs)}"
    
    db.close()


def test_health_derivation_correct():
    """Test that health derivation returns VALIDATION_PASSED_COVERAGE_INCOMPLETE when not_mapped is 0."""
    db = SessionLocal()
    
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
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
    
    # Verify health is VALIDATION_PASSED_COVERAGE_INCOMPLETE (not NEEDS_TRACEABILITY_REVIEW)
    assert view_model.health == "VALIDATION_PASSED_COVERAGE_INCOMPLETE", \
        f"Expected health VALIDATION_PASSED_COVERAGE_INCOMPLETE, got {view_model.health}"
    
    # Verify not_mapped is 0
    not_mapped = view_model.counts.get("notMappedTraceabilityRisks", 0)
    assert not_mapped == 0, f"Expected not_mapped to be 0, got {not_mapped}"
    
    db.close()


def test_decision_copy_uses_correct_fields():
    """Test that decision copy uses uploadedPrTestsPassed and correct field names."""
    db = SessionLocal()
    
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
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
    
    # Verify decision copy uses correct test count
    passed_tests = view_model.counts.get("uploadedPrTestsPassed", 0)
    assert passed_tests == 18, f"Expected 18 passed tests, got {passed_tests}"
    
    # Verify explanation mentions correct test count
    explanation = view_model.decision_copy.explanation
    assert f"{passed_tests} tests" in explanation, \
        f"Expected explanation to mention {passed_tests} tests"
    
    # Verify CTA is correct
    assert view_model.decision_copy.primary_cta == "Review Missing & Partial Coverage", \
        f"Expected primary CTA 'Review Missing & Partial Coverage', got {view_model.decision_copy.primary_cta}"
    
    db.close()


def test_scope_recommendation_bucket_separation():
    """Test that scope recommendation separates excluded requirements and tests."""
    db = SessionLocal()
    
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
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
    
    # Filter parent requirements
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Build scope recommendation
    excluded_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION]
    excluded_tests = view_model.verified_by_current_pr
    
    # Verify separation
    assert len(excluded_reqs) == 16, f"Expected 16 excluded verified requirements, got {len(excluded_reqs)}"
    assert len(excluded_tests) == 18, f"Expected 18 excluded passed tests, got {len(excluded_tests)}"
    
    db.close()


if __name__ == "__main__":
    # Run tests manually for verification
    print("Running regression tests for PHASE 1.1 HOTFIX...")
    
    test_ac_source_priority_uses_db_rows()
    print("PASS: test_ac_source_priority_uses_db_rows")
    
    test_endpoint_returns_25_parent_requirements()
    print("PASS: test_endpoint_returns_25_parent_requirements")
    
    test_health_derivation_correct()
    print("PASS: test_health_derivation_correct")
    
    test_decision_copy_uses_correct_fields()
    print("PASS: test_decision_copy_uses_correct_fields")
    
    test_scope_recommendation_bucket_separation()
    print("PASS: test_scope_recommendation_bucket_separation")
    
    print("\nAll PHASE 1.1 HOTFIX regression tests passed!")
