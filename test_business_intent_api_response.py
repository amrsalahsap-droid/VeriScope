"""Test suite for business intent API response structure."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.main import app
from app.models.recommendation import RecommendationRun
from app.models.repository import Repository
from app.models.user import Workspace, WorkspaceMember, User
from app.models.pull_request import PullRequest


def test_business_intent_api_response_structure(db_session: Session):
    """Test that business intent sections are present in API response."""
    
    # Create workspace, user, and repository
    workspace = Workspace(id=uuid4(), name="test", slug="test")
    db_session.add(workspace)
    db_session.commit()
    
    user = User(id=uuid4(), email="test@example.com", name="Test User")
    db_session.add(user)
    db_session.commit()
    
    member = WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=user.id, role="OWNER")
    db_session.add(member)
    db_session.commit()
    
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        url="https://github.com/test/repo",
        workspace_id=workspace.id,
        github_repo_id=12345,
    )
    db_session.add(repo)
    db_session.commit()
    
    # Create a recommendation run with business intent data in impact_profile
    run = RecommendationRun(
        id=uuid4(),
        repository_id=repo.id,
        pr_id="123",
        triggered_by="test",
        evidence_quality="HIGH",
        engine_version="v3.0.0",
        recommendation_engine_version="v3.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        fallback_policy_version="policy-v1",
        dependency_expansion_strategy_version="expansion-strategy-v1",
        recommendation_reasoning_summary="Test recommendation",
        pull_request_id=uuid4(),
        pr_snapshot_id=uuid4(),
        pr_sync_job_id=uuid4(),
        evidence_health_status="HEALTHY",
        recommendation_readiness_state="READY",
        evidence_consistency_status="CONSISTENT",
        readiness_dimensions={},
        evidence_fingerprint="test-fingerprint",
        coverage_report_id=None,
        dependency_state_hash="test-hash",
        test_history_window_start=None,
        test_history_window_end=None,
        flakiness_profile_hash="test-flaky",
        recommendation_mode="NORMAL",
        optimization_allowed=True,
        unsafe_for_optimization=False,
        evidence_quality_reasons=[],
        estimated_runtime_seconds=100.0,
        full_suite_runtime_seconds=500.0,
        runtime_confidence="HIGH",
        runtime_source="historical_average",
        skipped_reason_summary=None,
        skipped_count=0,
        top_skipped_examples=[],
        workspace_id=workspace.id,
        input_snapshot_hash="input-hash",
        recommendation_snapshot_hash="rec-hash",
        risk_level="LOW",
        recommended_tests_count=10,
        impact_profile={
            "business_intent_coverage_matrix": {
                "rows": [
                    {
                        "acceptance_criterion_id": str(uuid4()),
                        "business_intent_text": "User must be able to reset password",
                        "affected_behavior_name": "Password Reset",
                        "status": "COVERED",
                        "recommended_action": "RUN_EXISTING_TEST",
                        "confidence": 0.8,
                    }
                ],
                "total_intents": 1,
                "covered": 1,
                "partially_covered": 0,
                "missing": 0,
                "verified": 0,
                "unknown": 0,
                "has_business_intent": True,
                "confidence_impact": "NONE",
            },
            "requirement_gap_report": {
                "gaps": [],
                "total_gaps": 0,
                "critical_gaps": 0,
                "high_gaps": 0,
                "medium_gaps": 0,
                "low_gaps": 0,
                "has_critical_gaps": False,
                "overall_trust_level": "HIGH",
            },
            "business_intent_signal_breakdown": {
                "business_intent_signals": {
                    "has_acceptance_criteria": True,
                    "acceptance_criteria_count": 1,
                    "business_behavior_mappings_count": 1,
                    "expected_scenarios_count": 1,
                }
            }
        },
    )
    db_session.add(run)
    db_session.commit()
    
    # Make API request
    client = TestClient(app)
    response = client.get(f"/api/recommendations/{run.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify business intent sections are present
    assert "business_intent" in data
    assert "acceptance_criteria" in data
    assert "requirement_gaps" in data
    assert "business_intent_coverage_matrix" in data
    
    # Verify business intent structure
    business_intent = data["business_intent"]
    if business_intent:
        assert "rows" in business_intent
        assert "total_intents" in business_intent
        assert "has_business_intent" in business_intent
    
    # Verify requirement gaps structure
    requirement_gaps = data["requirement_gaps"]
    assert isinstance(requirement_gaps, list)
    
    # Verify business intent coverage matrix structure
    coverage_matrix = data["business_intent_coverage_matrix"]
    if coverage_matrix:
        assert "rows" in coverage_matrix
        assert "total_intents" in coverage_matrix
    
    print(f"✓ Business intent API response structure verified")
    print(f"  Business intent present: {business_intent is not None}")
    print(f"  Acceptance criteria present: {len(data['acceptance_criteria']) if data['acceptance_criteria'] else 0}")
    print(f"  Requirement gaps: {len(requirement_gaps)}")


def test_empty_business_intent_explicit_in_api(db_session: Session):
    """Test that empty business intent is explicit in API response."""
    
    # Create workspace, user, and repository
    workspace = Workspace(id=uuid4(), name="test", slug="test")
    db_session.add(workspace)
    db_session.commit()
    
    user = User(id=uuid4(), email="test@example.com", name="Test User")
    db_session.add(user)
    db_session.commit()
    
    member = WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=user.id, role="OWNER")
    db_session.add(member)
    db_session.commit()
    
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        url="https://github.com/test/repo",
        workspace_id=workspace.id,
        github_repo_id=12345,
    )
    db_session.add(repo)
    db_session.commit()
    
    # Create a recommendation run with empty business intent
    run = RecommendationRun(
        id=uuid4(),
        repository_id=repo.id,
        pr_id="123",
        triggered_by="test",
        evidence_quality="HIGH",
        engine_version="v3.0.0",
        recommendation_engine_version="v3.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        fallback_policy_version="policy-v1",
        dependency_expansion_strategy_version="expansion-strategy-v1",
        recommendation_reasoning_summary="Test recommendation",
        pull_request_id=uuid4(),
        pr_snapshot_id=uuid4(),
        pr_sync_job_id=uuid4(),
        evidence_health_status="HEALTHY",
        recommendation_readiness_state="READY",
        evidence_consistency_status="CONSISTENT",
        readiness_dimensions={},
        evidence_fingerprint="test-fingerprint",
        coverage_report_id=None,
        dependency_state_hash="test-hash",
        test_history_window_start=None,
        test_history_window_end=None,
        flakiness_profile_hash="test-flaky",
        recommendation_mode="NORMAL",
        optimization_allowed=True,
        unsafe_for_optimization=False,
        evidence_quality_reasons=[],
        estimated_runtime_seconds=100.0,
        full_suite_runtime_seconds=500.0,
        runtime_confidence="HIGH",
        runtime_source="historical_average",
        skipped_reason_summary=None,
        skipped_count=0,
        top_skipped_examples=[],
        workspace_id=workspace.id,
        input_snapshot_hash="input-hash",
        recommendation_snapshot_hash="rec-hash",
        risk_level="LOW",
        recommended_tests_count=10,
        impact_profile={
            "business_intent_coverage_matrix": {
                "rows": [
                    {
                        "business_intent_text": "No business intent or acceptance criteria found",
                        "status": "UNKNOWN",
                        "recommended_action": "CLARIFY_REQUIREMENT",
                        "confidence": 0.0,
                    }
                ],
                "total_intents": 0,
                "covered": 0,
                "partially_covered": 0,
                "missing": 0,
                "verified": 0,
                "unknown": 1,
                "has_business_intent": False,
                "confidence_impact": "REDUCED",
            },
            "requirement_gap_report": {
                "gaps": [
                    {
                        "severity": "HIGH",
                        "gap_type": "MISSING_ACCEPTANCE_CRITERIA",
                        "message": "No acceptance criteria found in PR",
                        "impact": "Cannot validate business intent",
                        "recommended_action": "Add acceptance criteria"
                    }
                ],
                "total_gaps": 1,
                "critical_gaps": 0,
                "high_gaps": 1,
                "medium_gaps": 0,
                "low_gaps": 0,
                "has_critical_gaps": False,
                "overall_trust_level": "MEDIUM",
            },
            "business_intent_signal_breakdown": {
                "business_intent_signals": {
                    "has_acceptance_criteria": False,
                    "acceptance_criteria_count": 0,
                    "business_behavior_mappings_count": 0,
                    "expected_scenarios_count": 0,
                }
            }
        },
    )
    db_session.add(run)
    db_session.commit()
    
    # Make API request
    client = TestClient(app)
    response = client.get(f"/api/recommendations/{run.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify empty business intent is explicit
    business_intent = data["business_intent"]
    assert business_intent is not None
    assert business_intent.get("has_business_intent") == False
    assert business_intent.get("confidence_impact") == "REDUCED"
    
    # Verify requirement gaps are present
    requirement_gaps = data["requirement_gaps"]
    assert len(requirement_gaps) > 0
    assert any(gap["gap_type"] == "MISSING_ACCEPTANCE_CRITERIA" for gap in requirement_gaps)
    
    print(f"✓ Empty business intent is explicit in API response")
    print(f"  Has business intent: {business_intent.get('has_business_intent')}")
    print(f"  Confidence impact: {business_intent.get('confidence_impact')}")
    print(f"  Requirement gaps: {len(requirement_gaps)}")


def test_backend_is_source_of_truth(db_session: Session):
    """Test that backend is source of truth for coverage status."""
    
    # Create workspace, user, and repository
    workspace = Workspace(id=uuid4(), name="test", slug="test")
    db_session.add(workspace)
    db_session.commit()
    
    user = User(id=uuid4(), email="test@example.com", name="Test User")
    db_session.add(user)
    db_session.commit()
    
    member = WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=user.id, role="OWNER")
    db_session.add(member)
    db_session.commit()
    
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        url="https://github.com/test/repo",
        workspace_id=workspace.id,
        github_repo_id=12345,
    )
    db_session.add(repo)
    db_session.commit()
    
    # Create a recommendation run with specific coverage status from backend
    run = RecommendationRun(
        id=uuid4(),
        repository_id=repo.id,
        pr_id="123",
        triggered_by="test",
        evidence_quality="HIGH",
        engine_version="v3.0.0",
        recommendation_engine_version="v3.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        fallback_policy_version="policy-v1",
        dependency_expansion_strategy_version="expansion-strategy-v1",
        recommendation_reasoning_summary="Test recommendation",
        pull_request_id=uuid4(),
        pr_snapshot_id=uuid4(),
        pr_sync_job_id=uuid4(),
        evidence_health_status="HEALTHY",
        recommendation_readiness_state="READY",
        evidence_consistency_status="CONSISTENT",
        readiness_dimensions={},
        evidence_fingerprint="test-fingerprint",
        coverage_report_id=None,
        dependency_state_hash="test-hash",
        test_history_window_start=None,
        test_history_window_end=None,
        flakiness_profile_hash="test-flaky",
        recommendation_mode="NORMAL",
        optimization_allowed=True,
        unsafe_for_optimization=False,
        evidence_quality_reasons=[],
        estimated_runtime_seconds=100.0,
        full_suite_runtime_seconds=500.0,
        runtime_confidence="HIGH",
        runtime_source="historical_average",
        skipped_reason_summary=None,
        skipped_count=0,
        top_skipped_examples=[],
        workspace_id=workspace.id,
        input_snapshot_hash="input-hash",
        recommendation_snapshot_hash="rec-hash",
        risk_level="LOW",
        recommended_tests_count=10,
        impact_profile={
            "business_intent_coverage_matrix": {
                "rows": [
                    {
                        "acceptance_criterion_id": str(uuid4()),
                        "business_intent_text": "User must be able to reset password",
                        "affected_behavior_name": "Password Reset",
                        "status": "VERIFIED_ON_CURRENT_PR",  # Backend-calculated status
                        "recommended_action": "ALREADY_VERIFIED",
                        "confidence": 0.95,
                    }
                ],
                "total_intents": 1,
                "covered": 0,
                "partially_covered": 0,
                "missing": 0,
                "verified": 1,
                "unknown": 0,
                "has_business_intent": True,
                "confidence_impact": "NONE",
            },
            "requirement_gap_report": {
                "gaps": [],
                "total_gaps": 0,
                "critical_gaps": 0,
                "high_gaps": 0,
                "medium_gaps": 0,
                "low_gaps": 0,
                "has_critical_gaps": False,
                "overall_trust_level": "HIGH",
            },
            "business_intent_signal_breakdown": {
                "business_intent_signals": {
                    "has_acceptance_criteria": True,
                    "acceptance_criteria_count": 1,
                    "business_behavior_mappings_count": 1,
                    "expected_scenarios_count": 1,
                }
            }
        },
    )
    db_session.add(run)
    db_session.commit()
    
    # Make API request
    client = TestClient(app)
    response = client.get(f"/api/recommendations/{run.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify backend-calculated status is returned
    business_intent = data["business_intent"]
    rows = business_intent.get("rows", [])
    assert len(rows) > 0
    assert rows[0]["status"] == "VERIFIED_ON_CURRENT_PR"
    assert rows[0]["recommended_action"] == "ALREADY_VERIFIED"
    
    print(f"✓ Backend is source of truth for coverage status")
    print(f"  Status from backend: {rows[0]['status']}")
    print(f"  Action from backend: {rows[0]['recommended_action']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
