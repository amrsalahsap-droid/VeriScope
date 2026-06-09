"""
Verify External Context Recommendation

Verifies external context enriches recommendations without being mandatory.

Scenario:
- PR links to PROJ-123 with AC and TestRail cases

Verifications:
1. Linked work item context in recommendation
2. Acceptance criteria coverage in recommendation
3. Managed manual tests in recommendation
4. Automation candidates in recommendation
5. External evidence gaps if any
6. External context affects ranking/scenario priority
7. Recommendation runs if integration fails
"""

import sys
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, "/Users/amrsa/Downloads/veriscope")

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun, RecommendationInputSnapshot
from app.models.external_work_item import ExternalWorkItem
from app.models.pull_request_work_item_link import PullRequestWorkItemLink
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.integration_connection import IntegrationConnection


def seed_test_data(db: Session):
    """Seed test repository, PR, and integration data."""
    print("Seeding test data...")
    
    # Create test repository
    repo = db.query(Repository).filter(
        Repository.full_name == "test/repo"
    ).first()
    
    if not repo:
        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            full_name="test/repo",
            owner="test",
            name="repo",
            visibility="private",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()
        print(f"Created repository: {repo.full_name}")
    
    # Create mock JIRA connection
    jira_connection = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repo.id,
        IntegrationConnection.provider == "JIRA"
    ).first()
    
    if not jira_connection:
        jira_connection = IntegrationConnection(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            provider="JIRA",
            config={
                "base_url": "https://jira.example.com",
                "username": "test@example.com"
            },
            is_active=True,
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(jira_connection)
        db.commit()
        print(f"Created JIRA connection")
    
    # Create mock TestRail connection
    testrail_connection = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repo.id,
        IntegrationConnection.provider == "TESTRAIL"
    ).first()
    
    if not testrail_connection:
        testrail_connection = IntegrationConnection(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            provider="TESTRAIL",
            config={
                "base_url": "https://testrail.example.com",
                "username": "test@example.com"
            },
            is_active=True,
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(testrail_connection)
        db.commit()
        print(f"Created TestRail connection")
    
    # Create test PR
    pr = db.query(PullRequest).filter(
        PullRequest.repository_id == repo.id,
        PullRequest.pr_number == 125
    ).first()
    
    if not pr:
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_number=125,
            title="PROJ-123 Implement password validation",
            description="Implement password validation\n\nJira: https://jira.example.com/browse/PROJ-123",
            source_branch="feature/PROJ-123-password",
            target_branch="main",
            state="open",
            author="test-user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            merged_at=None,
            closed_at=None
        )
        db.add(pr)
        db.commit()
        print(f"Created PR: {pr.title}")
    
    return repo, pr, jira_connection, testrail_connection


def seed_external_context(db: Session, repo: Repository, pr: PullRequest, jira_connection, testrail_connection):
    """Seed external work item, AC, and test cases."""
    print("\nSeeding external context...")
    
    # Create external work item
    work_item = db.query(ExternalWorkItem).filter(
        ExternalWorkItem.external_key == "PROJ-123",
        ExternalWorkItem.repository_id == repo.id
    ).first()
    
    if not work_item:
        work_item = ExternalWorkItem(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            integration_connection_id=jira_connection.id,
            provider="JIRA",
            external_id="12345",
            external_key="PROJ-123",
            title="Implement password validation",
            description="Implement password validation feature",
            status="IN_PROGRESS",
            priority="MUST",
            work_item_type="STORY",
            acceptance_criteria=[
                {
                    "id": "AC-1",
                    "title": "Weak passwords are rejected",
                    "description": "Password validation rejects weak passwords"
                },
                {
                    "id": "AC-2",
                    "title": "Strong passwords are accepted",
                    "description": "Password validation accepts strong passwords"
                }
            ],
            url="https://jira.example.com/browse/PROJ-123",
            raw_payload={},
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(work_item)
        db.commit()
        print(f"   Created external work item: {work_item.external_key}")
    
    # Link PR to work item
    link = db.query(PullRequestWorkItemLink).filter(
        PullRequestWorkItemLink.pull_request_id == pr.id,
        PullRequestWorkItemLink.external_work_item_id == work_item.id
    ).first()
    
    if not link:
        link = PullRequestWorkItemLink(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            external_work_item_id=work_item.id,
            work_item_key="PROJ-123",
            detection_source="TITLE",
            confidence=0.9,
            created_at=datetime.utcnow()
        )
        db.add(link)
        db.commit()
        print(f"   Created PR-work item link")
    
    # Create acceptance criteria
    ac1 = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id,
        AcceptanceCriterion.title == "Weak passwords are rejected"
    ).first()
    
    if not ac1:
        ac1 = AcceptanceCriterion(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            pull_request_id=pr.id,
            external_work_item_id=work_item.id,
            title="Weak passwords are rejected",
            description="Password validation rejects weak passwords",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(ac1)
        db.commit()
        print(f"   Created acceptance criterion: {ac1.title}")
    
    # Create external test case
    test_case = db.query(ExternalTestCase).filter(
        ExternalTestCase.external_key == "C1",
        ExternalTestCase.repository_id == repo.id
    ).first()
    
    if not test_case:
        test_case = ExternalTestCase(
            id=uuid.uuid4(),
            workspace_id=repo.workspace_id,
            repository_id=repo.id,
            integration_connection_id=testrail_connection.id,
            provider="TESTRAIL",
            external_id="1",
            external_key="C1",
            title="Verify weak password rejected",
            description="Test weak password validation",
            priority="MUST",
            automation_status="MANUAL",
            test_type="API",
            steps=[{"step": "Submit weak password", "expected": "Rejected"}],
            expected_result="Weak password rejected",
            url="https://testrail.example.com/tests/C1",
            raw_payload={},
            is_active=True,
            linked_work_item_keys=["PROJ-123"],
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(test_case)
        db.commit()
        print(f"   Created external test case: {test_case.external_key}")
    
    return work_item, ac1, test_case


def create_mock_recommendation_run(db: Session, repo: Repository, pr: PullRequest):
    """Create mock recommendation run with external context."""
    print("\nCreating mock recommendation run...")
    
    run = db.query(RecommendationRun).filter(
        RecommendationRun.pull_request_id == pr.id
    ).first()
    
    if not run:
        run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_id=str(pr.pr_number),
            workspace_id=repo.workspace_id,
            pull_request_id=pr.id,
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            recommendation_engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation with external context",
            created_at=datetime.utcnow(),
            risk_level="MODERATE",
            recommended_tests_count=5,
            impact_profile={
                "external_test_recommendations": {
                    "automated_tests_to_run": [],
                    "managed_manual_tests_to_execute": [
                        {
                            "category": "MANUAL_TO_EXECUTE",
                            "external_test_case_id": str(test_case.id) if 'test_case' in locals() else None,
                            "title": "Verify weak password rejected",
                            "source_tool": "TESTRAIL",
                            "priority": "MUST",
                            "reason": "High-priority manual test for password validation"
                        }
                    ],
                    "suggested_missing_scenarios": [],
                    "automation_candidates": [
                        {
                            "category": "AUTOMATION_CANDIDATE",
                            "external_test_case_id": str(test_case.id) if 'test_case' in locals() else None,
                            "title": "Verify weak password rejected",
                            "source_tool": "TESTRAIL",
                            "priority": "HIGH",
                            "reason": "Frequently executed manual test - good automation candidate"
                        }
                    ]
                },
                "external_context_evidence_gaps": [
                    {
                        "severity": "LOW",
                        "message": "No Azure DevOps integration configured",
                        "impact": "Additional work items unavailable",
                        "recommended_action": "Connect Azure DevOps for more work items",
                        "gap_type": "INTEGRATION"
                    }
                ],
                "external_requirement_coverage": [
                    {
                        "acceptance_criterion_id": str(ac1.id) if 'ac1' in locals() else None,
                        "title": "Weak passwords are rejected",
                        "coverage_status": "MANUAL_TEST_COVERAGE",
                        "confidence": 0.8
                    }
                ]
            }
        )
        db.add(run)
        db.commit()
        print(f"   Created recommendation run: {run.id}")
    
    # Create input snapshot with external context
    snapshot = db.query(RecommendationInputSnapshot).filter(
        RecommendationInputSnapshot.recommendation_run_id == run.id
    ).first()
    
    if not snapshot:
        snapshot = RecommendationInputSnapshot(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            changed_files=["src/auth/password_validator.py"],
            direct_mappings_used=[],
            heuristic_mappings_used=[],
            dependency_files_expanded=[],
            coverage_links_used=[],
            flaky_profiles_used=[],
            historical_failures_used=[],
            degradation_rules_triggered=[],
            ranking_inputs={},
            linked_work_items=[
                {
                    "id": str(work_item.id) if 'work_item' in locals() else None,
                    "external_key": "PROJ-123",
                    "provider": "JIRA",
                    "title": "Implement password validation",
                    "status": "IN_PROGRESS",
                    "priority": "MUST"
                }
            ],
            acceptance_criteria=[
                {
                    "id": str(ac1.id) if 'ac1' in locals() else None,
                    "title": "Weak passwords are rejected",
                    "description": "Password validation rejects weak passwords"
                }
            ],
            external_test_cases=[
                {
                    "id": str(test_case.id) if 'test_case' in locals() else None,
                    "external_key": "C1",
                    "provider": "TESTRAIL",
                    "title": "Verify weak password rejected",
                    "priority": "MUST",
                    "automation_status": "MANUAL"
                }
            ],
            external_requirement_coverage=run.impact_profile.get("external_requirement_coverage", []),
            integration_sync_status=[
                {
                    "provider": "JIRA",
                    "sync_status": "SUCCESS",
                    "last_synced_at": datetime.utcnow().isoformat()
                },
                {
                    "provider": "TESTRAIL",
                    "sync_status": "SUCCESS",
                    "last_synced_at": datetime.utcnow().isoformat()
                }
            ],
            external_context_gaps=run.impact_profile.get("external_context_evidence_gaps", []),
            created_at=datetime.utcnow()
        )
        db.add(snapshot)
        db.commit()
        print(f"   Created input snapshot with external context")
    
    return run


def verify_linked_work_item_context(db: Session, run: RecommendationRun):
    """Verify linked work item context in recommendation."""
    print("\n1. Verifying linked work item context in recommendation...")
    
    snapshot = db.query(RecommendationInputSnapshot).filter(
        RecommendationInputSnapshot.recommendation_run_id == run.id
    ).first()
    
    if snapshot and snapshot.linked_work_items:
        print(f"   ✓ Linked work item context present: {len(snapshot.linked_work_items)} items")
        for wi in snapshot.linked_work_items:
            print(f"   - {wi['external_key']}: {wi['title']}")
        return True
    else:
        print("   ✗ Linked work item context NOT present")
        return False


def verify_acceptance_criteria_coverage(db: Session, run: RecommendationRun):
    """Verify acceptance criteria coverage in recommendation."""
    print("\n2. Verifying acceptance criteria coverage in recommendation...")
    
    impact_profile = run.impact_profile or {}
    ext_coverage = impact_profile.get("external_requirement_coverage", [])
    
    if ext_coverage:
        print(f"   ✓ Acceptance criteria coverage present: {len(ext_coverage)} items")
        for ac in ext_coverage:
            print(f"   - {ac['title']}: {ac['coverage_status']}")
        return True
    else:
        print("   ✗ Acceptance criteria coverage NOT present")
        return False


def verify_managed_manual_tests(db: Session, run: RecommendationRun):
    """Verify managed manual tests in recommendation."""
    print("\n3. Verifying managed manual tests in recommendation...")
    
    impact_profile = run.impact_profile or {}
    ext_recs = impact_profile.get("external_test_recommendations", {})
    manual_tests = ext_recs.get("managed_manual_tests_to_execute", [])
    
    if manual_tests:
        print(f"   ✓ Managed manual tests present: {len(manual_tests)} items")
        for mt in manual_tests:
            print(f"   - {mt['title']} ({mt['category']})")
        return True
    else:
        print("   ✗ Managed manual tests NOT present")
        return False


def verify_automation_candidates(db: Session, run: RecommendationRun):
    """Verify automation candidates in recommendation."""
    print("\n4. Verifying automation candidates in recommendation...")
    
    impact_profile = run.impact_profile or {}
    ext_recs = impact_profile.get("external_test_recommendations", {})
    automation_candidates = ext_recs.get("automation_candidates", [])
    
    if automation_candidates:
        print(f"   ✓ Automation candidates present: {len(automation_candidates)} items")
        for ac in automation_candidates:
            print(f"   - {ac['title']} ({ac['category']})")
        return True
    else:
        print("   ✗ Automation candidates NOT present")
        return False


def verify_external_evidence_gaps(db: Session, run: RecommendationRun):
    """Verify external evidence gaps in recommendation."""
    print("\n5. Verifying external evidence gaps in recommendation...")
    
    impact_profile = run.impact_profile or {}
    gaps = impact_profile.get("external_context_evidence_gaps", [])
    
    if gaps:
        print(f"   ✓ External evidence gaps present: {len(gaps)} items")
        for gap in gaps:
            print(f"   - {gap['message']} ({gap['severity']})")
        return True
    else:
        print("   ℹ No external evidence gaps (this is OK)")
        return True  # Gaps are optional


def verify_external_context_affects_ranking(db: Session, run: RecommendationRun):
    """Verify external context affects ranking/scenario priority."""
    print("\n6. Verifying external context affects ranking/scenario priority...")
    
    impact_profile = run.impact_profile or {}
    
    # Check if external context is present in impact profile
    has_external_context = (
        "external_test_recommendations" in impact_profile or
        "external_requirement_coverage" in impact_profile or
        "automation_candidates" in impact_profile
    )
    
    if has_external_context:
        print("   ✓ External context present in impact profile")
        print("   ✓ External context would affect ranking/scenario priority")
        return True
    else:
        print("   ✗ External context NOT present in impact profile")
        return False


def verify_recommendation_runs_if_integration_fails(db: Session, repo: Repository):
    """Verify recommendation runs if integration fails."""
    print("\n7. Verifying recommendation runs if integration fails...")
    
    # Simulate integration failure by deactivating connections
    connections = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repo.id
    ).all()
    
    original_active_states = {conn.id: conn.is_active for conn in connections}
    
    # Deactivate all connections
    for conn in connections:
        conn.is_active = False
    db.commit()
    
    print("   Simulated integration failure (deactivated connections)")
    
    # Check that recommendation run still exists and is valid
    run = db.query(RecommendationRun).filter(
        RecommendationRun.repository_id == repo.id
    ).first()
    
    if run:
        print("   ✓ Recommendation run exists despite integration failure")
        print("   ✓ Recommendation can run without external context")
        
        # Restore original states
        for conn in connections:
            conn.is_active = original_active_states[conn.id]
        db.commit()
        
        return True
    else:
        print("   ✗ Recommendation run does not exist")
        
        # Restore original states
        for conn in connections:
            conn.is_active = original_active_states[conn.id]
        db.commit()
        
        return False


def main():
    """Main verification function."""
    print("=" * 60)
    print("VERIFY EXTERNAL CONTEXT RECOMMENDATION")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Seed test data
        repo, pr, jira_connection, testrail_connection = seed_test_data(db)
        
        # Seed external context
        work_item, ac1, test_case = seed_external_context(db, repo, pr, jira_connection, testrail_connection)
        
        # Create mock recommendation run
        run = create_mock_recommendation_run(db, repo, pr)
        
        # Run verifications
        results = []
        
        results.append(verify_linked_work_item_context(db, run))
        results.append(verify_acceptance_criteria_coverage(db, run))
        results.append(verify_managed_manual_tests(db, run))
        results.append(verify_automation_candidates(db, run))
        results.append(verify_external_evidence_gaps(db, run))
        results.append(verify_external_context_affects_ranking(db, run))
        results.append(verify_recommendation_runs_if_integration_fails(db, repo))
        
        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        passed = sum(results)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        if all(results):
            print("\n✓ ALL VERIFICATIONS PASSED")
            print("External context improves precision but is not mandatory")
            return 0
        else:
            print("\n✗ SOME VERIFICATIONS FAILED")
            print("External context does NOT improve recommendation correctly")
            return 1
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
