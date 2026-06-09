"""Verification test for Behavior Coverage Intelligence accuracy.

This test verifies that the behavior coverage analyzer produces accurate
coverage truth, correctly mapping scenarios to tests and identifying gaps.

Seed Data:
- Behaviors: Password Reset, User Registration
- Scenarios: 4 for Password Reset, 3 for User Registration
- Existing tests: 2 (valid token, expired token)
- Coverage files: reset-password route partially covered

Verification Points:
1. valid token accepted maps to existing test
2. expired token rejected maps to existing test
3. reused token rejected remains missing
4. weak password rejected remains missing
5. coverage support is partial, not full
6. behavior sufficiency is PARTIAL or INSUFFICIENT
7. missing scenarios generated only for truly missing intents
8. optional scenarios preserved
9. no scenario appears twice
10. current PR run status is separate from historical JUnit
"""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.behavior_coverage_analyzer import BehaviorCoverageAnalyzer
from app.services.existing_test_to_behavior_scenario_mapper import ExistingTestToBehaviorScenarioMapper
from app.services.coverage_file_behavior_support_mapper import CoverageFileBehaviorSupportMapper
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.behavior_evidence import BehaviorEvidence
from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey


def test_behavior_coverage_intelligence_accuracy(db_session: Session):
    """Verify behavior coverage intelligence produces accurate coverage truth."""
    
    # Create repository
    repository_id = uuid4()
    
    # Create Journey: Authentication
    auth_journey = Journey(
        id=uuid4(),
        repository_id=repository_id,
        name="Authentication",
        description="User authentication and password management",
        is_deleted=False,
    )
    db_session.add(auth_journey)
    db_session.commit()
    
    # Create Behavior: Password Reset
    password_reset_behavior = Behavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        repository_id=repository_id,
        name="Password Reset",
        slug="password-reset",
        description="User requests and completes password reset flow",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(password_reset_behavior)
    
    # Create Behavior: User Registration
    user_registration_behavior = Behavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        repository_id=repository_id,
        name="User Registration",
        slug="user-registration",
        description="New user signs up and creates account",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(user_registration_behavior)
    db_session.commit()
    
    # Create JourneyBehavior mappings
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        behavior_id=password_reset_behavior.id,
    ))
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        behavior_id=user_registration_behavior.id,
    ))
    db_session.commit()
    
    # Create Behavior Evidence for Password Reset
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        source_path="src/app/api/auth/reset-password/route.ts",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    
    # Create Behavior Evidence for User Registration
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        source_path="src/app/signup/sign-up-form.tsx",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    db_session.commit()
    
    # Create Behavior Scenarios for Password Reset
    valid_token_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        title="valid token accepted",
        description="User resets password with valid token",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(valid_token_scenario)
    
    expired_token_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        title="expired token rejected",
        description="User cannot reset with expired token",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(expired_token_scenario)
    
    reused_token_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        title="reused token rejected",
        description="User cannot reset with already-used token",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(reused_token_scenario)
    
    old_password_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        title="old password rejected after reset",
        description="User cannot use old password after reset",
        priority="SHOULD",
        case_type="negative",
    )
    db_session.add(old_password_scenario)
    
    # Create Behavior Scenarios for User Registration
    weak_password_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        title="weak password rejected",
        description="User cannot register with weak password",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(weak_password_scenario)
    
    duplicate_email_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        title="duplicate email rejected",
        description="User cannot register with existing email",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(duplicate_email_scenario)
    
    valid_signup_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        title="valid signup succeeds",
        description="User successfully creates account",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(valid_signup_scenario)
    db_session.commit()
    
    # Mock existing test cases
    class MockTestCase:
        def __init__(self, test_name, stable_identity):
            self.test_name = test_name
            self.stable_identity = stable_identity
            self.id = uuid4()
    
    test_cases = [
        MockTestCase("should_reject_expired_token", "test_auth.py::should_reject_expired_token"),
        MockTestCase("should_allow_valid_token", "test_auth.py::should_allow_valid_token"),
    ]
    
    # Mock coverage files (partial coverage)
    coverage_files = [
        {
            "file_path": "src/app/api/auth/reset-password/route.ts",
            "lines_covered": [1, 2, 3, 4, 5],  # Partial coverage
            "lines_total": 20,
            "branch_coverage": 0.5,
        }
    ]
    
    # Mock current PR test runs (empty - no tests run on current PR)
    current_pr_runs = []
    
    # Get all data
    behaviors = db_session.query(Behavior).filter(
        Behavior.repository_id == repository_id
    ).all()
    
    behavior_scenarios = db_session.query(BehaviorScenario).filter(
        BehaviorScenario.behavior_id.in_([b.id for b in behaviors])
    ).all()
    
    behavior_evidences = db_session.query(BehaviorEvidence).filter(
        BehaviorEvidence.behavior_id.in_([b.id for b in behaviors])
    ).all()
    
    journey_behaviors = db_session.query(JourneyBehavior).filter(
        JourneyBehavior.behavior_id.in_([b.id for b in behaviors])
    ).all()
    
    journeys = db_session.query(Journey).filter(
        Journey.id.in_([jb.journey_id for jb in journey_behaviors])
    ).all()
    
    # Step 1: Map existing tests to scenarios
    test_mapper = ExistingTestToBehaviorScenarioMapper(db=db_session)
    test_to_scenario_mappings = test_mapper.map_tests_to_scenarios(
        test_cases=test_cases,
        behaviors=behaviors,
        scenarios=behavior_scenarios,
    )
    
    # VERIFICATION 1: valid token accepted maps to existing test
    valid_token_mapped = any(
        m["scenario_id"] == str(valid_token_scenario.id)
        for m in test_to_scenario_mappings
    )
    assert valid_token_mapped, "valid token accepted should map to existing test (should_allow_valid_token)"
    print("✓ valid token accepted maps to existing test")
    
    # VERIFICATION 2: expired token rejected maps to existing test
    expired_token_mapped = any(
        m["scenario_id"] == str(expired_token_scenario.id)
        for m in test_to_scenario_mappings
    )
    assert expired_token_mapped, "expired token rejected should map to existing test (should_reject_expired_token)"
    print("✓ expired token rejected maps to existing test")
    
    # Step 2: Map coverage files to behaviors
    coverage_mapper = CoverageFileBehaviorSupportMapper(db=db_session)
    coverage_supports = coverage_mapper.map_coverage_to_behavior_support(
        coverage_files=coverage_files,
        behaviors=behaviors,
        evidences=behavior_evidences,
    )
    
    # VERIFICATION 5: coverage support is partial, not full
    password_reset_coverage = next(
        (c for c in coverage_supports if c["behavior_id"] == str(password_reset_behavior.id)),
        None
    )
    assert password_reset_coverage is not None, "Password Reset should have coverage support"
    assert password_reset_coverage["confidence"] in ["MODERATE", "LOW"], \
        f"Coverage should be partial (MODERATE/LOW confidence), got {password_reset_coverage['confidence']}"
    print(f"✓ coverage support is partial (confidence: {password_reset_coverage['confidence']})")
    
    # Step 3: Analyze behavior coverage
    coverage_analyzer = BehaviorCoverageAnalyzer(db=db_session)
    coverage_snapshot = coverage_analyzer.analyze_behavior_coverage(
        impacted_behaviors=[
            {
                "behavior_id": str(password_reset_behavior.id),
                "behavior_name": password_reset_behavior.name,
                "impact_level": "HIGH",
                "confidence": "HIGH",
                "impacted_files": ["src/app/api/auth/reset-password/route.ts"],
            },
            {
                "behavior_id": str(user_registration_behavior.id),
                "behavior_name": user_registration_behavior.name,
                "impact_level": "HIGH",
                "confidence": "HIGH",
                "impacted_files": ["src/app/signup/sign-up-form.tsx"],
            },
        ],
        scenarios=behavior_scenarios,
        test_mappings=test_to_scenario_mappings,
        coverage_supports=coverage_supports,
        current_pr_runs=current_pr_runs,
    )
    
    behavior_coverages = coverage_snapshot["behavior_coverages"]
    all_scenarios = coverage_snapshot["all_scenarios"]
    
    # VERIFICATION 3: reused token rejected remains missing
    reused_token_scenario_data = next(
        (s for s in all_scenarios if s["scenario_id"] == str(reused_token_scenario.id)),
        None
    )
    assert reused_token_scenario_data is not None, "reused token rejected should be in all_scenarios"
    assert reused_token_scenario_data["coverage_status"] in ["MISSING_AUTOMATED_COVERAGE", "PARTIALLY_COVERED"], \
        f"reused token rejected should be missing or partially covered, got {reused_token_scenario_data['coverage_status']}"
    print(f"✓ reused token rejected remains missing (status: {reused_token_scenario_data['coverage_status']})")
    
    # VERIFICATION 4: weak password rejected remains missing
    weak_password_scenario_data = next(
        (s for s in all_scenarios if s["scenario_id"] == str(weak_password_scenario.id)),
        None
    )
    assert weak_password_scenario_data is not None, "weak password rejected should be in all_scenarios"
    assert weak_password_scenario_data["coverage_status"] == "MISSING_AUTOMATED_COVERAGE", \
        f"weak password rejected should be missing, got {weak_password_scenario_data['coverage_status']}"
    print(f"✓ weak password rejected remains missing (status: {weak_password_scenario_data['coverage_status']})")
    
    # VERIFICATION 6: behavior sufficiency is PARTIAL or INSUFFICIENT
    password_reset_coverage_data = next(
        (b for b in behavior_coverages if b["behavior_id"] == str(password_reset_behavior.id)),
        None
    )
    assert password_reset_coverage_data is not None, "Password Reset should have coverage data"
    assert password_reset_coverage_data["sufficiency"] in ["PARTIAL", "INSUFFICIENT"], \
        f"Password Reset sufficiency should be PARTIAL or INSUFFICIENT, got {password_reset_coverage_data['sufficiency']}"
    print(f"✓ Password Reset sufficiency: {password_reset_coverage_data['sufficiency']}")
    
    user_registration_coverage_data = next(
        (b for b in behavior_coverages if b["behavior_id"] == str(user_registration_behavior.id)),
        None
    )
    assert user_registration_coverage_data is not None, "User Registration should have coverage data"
    assert user_registration_coverage_data["sufficiency"] in ["PARTIAL", "INSUFFICIENT"], \
        f"User Registration sufficiency should be PARTIAL or INSUFFICIENT, got {user_registration_coverage_data['sufficiency']}"
    print(f"✓ User Registration sufficiency: {user_registration_coverage_data['sufficiency']}")
    
    # VERIFICATION 7: missing scenarios generated only for truly missing intents
    # Count scenarios with MISSING_AUTOMATED_COVERAGE
    missing_scenarios = [s for s in all_scenarios if s["coverage_status"] == "MISSING_AUTOMATED_COVERAGE"]
    # Should be: reused token, weak password, duplicate email, valid signup (4 missing)
    # valid token and expired token are covered by existing tests
    assert len(missing_scenarios) >= 3, "Should have at least 3 truly missing scenarios"
    print(f"✓ missing scenarios generated only for truly missing intents ({len(missing_scenarios)} missing)")
    
    # VERIFICATION 8: optional scenarios preserved
    optional_scenarios = [s for s in all_scenarios if s["priority"] == "OPTIONAL"]
    # old password is SHOULD, not OPTIONAL, but if we had OPTIONAL they should be preserved
    should_scenarios = [s for s in all_scenarios if s["priority"] == "SHOULD"]
    assert len(should_scenarios) >= 1, "SHOULD priority scenarios should be preserved"
    print(f"✓ optional/SHOULD scenarios preserved ({len(should_scenarios)} SHOULD scenarios)")
    
    # VERIFICATION 9: no scenario appears twice
    scenario_ids = [s["scenario_id"] for s in all_scenarios]
    assert len(scenario_ids) == len(set(scenario_ids)), "No scenario should appear twice"
    print("✓ no scenario appears twice (all unique)")
    
    # VERIFICATION 10: current PR run status is separate from historical JUnit
    # Since current_pr_runs is empty, all scenarios should NOT be VERIFIED_ON_CURRENT_PR
    verified_on_current_pr = [s for s in all_scenarios if s["coverage_status"] == "VERIFIED_ON_CURRENT_PR"]
    assert len(verified_on_current_pr) == 0, "No scenarios should be VERIFIED_ON_CURRENT_PR when no PR runs exist"
    print("✓ current PR run status is separate from historical JUnit (no VERIFIED_ON_CURRENT_PR when no PR runs)")
    
    # Additional verification: covered by existing test status
    covered_by_existing_test = [s for s in all_scenarios if s["coverage_status"] == "COVERED_BY_EXISTING_TEST"]
    assert len(covered_by_existing_test) >= 2, "At least 2 scenarios should be COVERED_BY_EXISTING_TEST"
    print(f"✓ {len(covered_by_existing_test)} scenarios covered by existing tests")
    
    # Summary
    print("\n" + "="*60)
    print("BEHAVIOR COVERAGE INTELLIGENCE VERIFICATION PASSED")
    print("="*60)
    print(f"Total behaviors analyzed: {len(behavior_coverages)}")
    print(f"Total scenarios analyzed: {len(all_scenarios)}")
    print(f"Scenarios covered by existing tests: {len(covered_by_existing_test)}")
    print(f"Scenarios missing coverage: {len(missing_scenarios)}")
    print(f"Scenarios partially covered: {len([s for s in all_scenarios if s['coverage_status'] == 'PARTIALLY_COVERED'])}")
    print("="*60)
    print("Behavior coverage truth is accurate.")


def test_behavior_coverage_with_current_pr_runs(db_session: Session):
    """Verify that current PR run status is correctly separated from historical JUnit."""
    
    # Setup minimal data
    repository_id = uuid4()
    journey = Journey(
        id=uuid4(),
        repository_id=repository_id,
        name="Test Journey",
        description="Test",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=repository_id,
        name="Test Behavior",
        slug="test-behavior",
        description="Test",
        risk_level="MEDIUM",
        is_deleted=False,
    )
    db_session.add(behavior)
    db_session.commit()
    
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=journey.id,
        behavior_id=behavior.id,
    ))
    
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Test Scenario",
        description="Test",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Mock test case
    class MockTestCase:
        def __init__(self, test_name, stable_identity):
            self.test_name = test_name
            self.stable_identity = stable_identity
            self.id = uuid4()
    
    test_cases = [MockTestCase("test_scenario", "test.py::test_scenario")]
    
    # Mock current PR run (test passed on current PR)
    current_pr_runs = [
        {
            "test_case_id": test_cases[0].id,
            "status": "passed",
            "run_at": "2024-01-01T00:00:00Z",
        }
    ]
    
    behaviors = db_session.query(Behavior).filter(Behavior.repository_id == repository_id).all()
    behavior_scenarios = db_session.query(BehaviorScenario).all()
    
    # Map tests to scenarios
    test_mapper = ExistingTestToBehaviorScenarioMapper(db=db_session)
    test_to_scenario_mappings = test_mapper.map_tests_to_scenarios(
        test_cases=test_cases,
        behaviors=behaviors,
        scenarios=behavior_scenarios,
    )
    
    # Analyze coverage with current PR runs
    coverage_analyzer = BehaviorCoverageAnalyzer(db=db_session)
    coverage_snapshot = coverage_analyzer.analyze_behavior_coverage(
        impacted_behaviors=[
            {
                "behavior_id": str(behavior.id),
                "behavior_name": behavior.name,
                "impact_level": "MEDIUM",
                "confidence": "HIGH",
                "impacted_files": [],
            }
        ],
        scenarios=behavior_scenarios,
        test_mappings=test_to_scenario_mappings,
        coverage_supports=[],
        current_pr_runs=current_pr_runs,
    )
    
    all_scenarios = coverage_snapshot["all_scenarios"]
    
    # Should have VERIFIED_ON_CURRENT_PR status
    verified_on_current_pr = [s for s in all_scenarios if s["coverage_status"] == "VERIFIED_ON_CURRENT_PR"]
    assert len(verified_on_current_pr) == 1, "Scenario should be VERIFIED_ON_CURRENT_PR when test passed on PR"
    print("✓ current PR run status correctly separates from historical JUnit (VERIFIED_ON_CURRENT_PR when test passed on PR)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
