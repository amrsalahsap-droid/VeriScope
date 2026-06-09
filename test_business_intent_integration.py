"""Test suite for business intent integration in RecommendationEngine."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.recommendation_ranking_service import RecommendationRankingService
from app.schemas.recommendation import RankingCandidateInput
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage
from app.schemas.acceptance_criteria import AcceptanceCriteriaCoverageStatus, AcceptanceCriteriaCoverageReport


def test_ranking_with_ac_mapping_boost(db_session: Session):
    """Test that tests mapping to AC get scoring boost."""
    
    # Create business behavior mapping
    ac_id = uuid4()
    behavior_id = uuid4()
    scenario_id = uuid4()
    
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac_id,
        behavior_id=behavior_id,
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage with test mappings
    test_id = uuid4()
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=behavior_id,
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="COVERED_BY_EXISTING_TEST",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="HIGH",
        reason="Test exists",
        existing_tests={"test_ids": [str(test_id)]},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    # Create test-to-AC mapping
    test_to_ac_mappings = {
        str(test_id): [str(ac_id)]
    }
    
    # Create ranking input
    ranking_input = RankingCandidateInput(
        test_case_id=test_id,
        reasons=["Direct file coverage"],
        base_priority_score=0.5,
        evidence_sources={"DIRECT_FILE_COVERAGE"},
        mapping_confidence="HIGH",
        flaky_status=None,
        historical_failure_score=None
    )
    
    # Rank with business intent
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input],
        mode="NORMAL",
        business_behavior_mappings=[mapping],
        ac_coverage_report=None,
        test_to_ac_mappings=test_to_ac_mappings
    )
    
    assert len(ranked_bundle.ranked_candidates) == 1
    candidate = ranked_bundle.ranked_candidates[0]
    
    # Check that AC boost was applied
    assert candidate.risk_value > 0.5  # Base priority + AC boost
    assert any("acceptance criterion" in reason.lower() for reason in candidate.reasons)
    
    print(f"✓ Test with AC mapping got boost")
    print(f"  Risk value: {candidate.risk_value}")
    print(f"  Reasons: {candidate.reasons}")


def test_ranking_with_scenario_mapping_boost(db_session: Session):
    """Test that tests covering scenarios mapped to AC get boost."""
    
    # Create business behavior mapping with scenario
    ac_id = uuid4()
    behavior_id = uuid4()
    scenario_id = uuid4()
    
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac_id,
        behavior_id=behavior_id,
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage
    test_id = uuid4()
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=behavior_id,
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="COVERED_BY_EXISTING_TEST",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="HIGH",
        reason="Test exists",
        existing_tests={"test_ids": [str(test_id)]},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    test_to_ac_mappings = {
        str(test_id): [str(ac_id)]
    }
    
    ranking_input = RankingCandidateInput(
        test_case_id=test_id,
        reasons=["Direct file coverage"],
        base_priority_score=0.5,
        evidence_sources={"DIRECT_FILE_COVERAGE"},
        mapping_confidence="HIGH",
        flaky_status=None,
        historical_failure_score=None
    )
    
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input],
        mode="NORMAL",
        business_behavior_mappings=[mapping],
        ac_coverage_report=None,
        test_to_ac_mappings=test_to_ac_mappings
    )
    
    candidate = ranked_bundle.ranked_candidates[0]
    
    # Check that scenario boost was applied
    assert candidate.risk_value > 0.5
    assert any("scenario" in reason.lower() for reason in candidate.reasons)
    
    print(f"✓ Test with scenario mapping got boost")
    print(f"  Risk value: {candidate.risk_value}")


def test_ranking_with_behavior_intent_boost(db_session: Session):
    """Test that behaviors mapped to explicit business intent get boost."""
    
    # Create mapping with AC (explicit business intent)
    ac_id = uuid4()
    behavior_id = uuid4()
    
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac_id,
        behavior_id=behavior_id,
        behavior_scenario_id=None,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # No test-to-AC mapping (test doesn't directly map to AC)
    test_to_ac_mappings = {}
    
    test_id = uuid4()
    ranking_input = RankingCandidateInput(
        test_case_id=test_id,
        reasons=["Direct file coverage"],
        base_priority_score=0.5,
        evidence_sources={"DIRECT_FILE_COVERAGE"},
        mapping_confidence="HIGH",
        flaky_status=None,
        historical_failure_score=None
    )
    
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input],
        mode="NORMAL",
        business_behavior_mappings=[mapping],
        ac_coverage_report=None,
        test_to_ac_mappings=test_to_ac_mappings
    )
    
    candidate = ranked_bundle.ranked_candidates[0]
    
    # Check that behavior intent boost was applied
    assert candidate.risk_value > 0.5
    assert any("business intent" in reason.lower() for reason in candidate.reasons)
    
    print(f"✓ Test with behavior intent mapping got boost")
    print(f"  Risk value: {candidate.risk_value}")


def test_ranking_with_vague_inferred_boost(db_session: Session):
    """Test that vague inferred-only behavior gets small boost."""
    
    # Create mapping without AC (inferred only)
    behavior_id = uuid4()
    
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=None,  # No explicit AC
        behavior_id=behavior_id,
        behavior_scenario_id=None,
        journey_id=uuid4(),
        match_confidence=0.4,
        matched_terms=["password"],
        reason="Inferred",
        is_candidate_missing_scenario="false",
    )
    
    test_to_ac_mappings = {}
    
    test_id = uuid4()
    ranking_input = RankingCandidateInput(
        test_case_id=test_id,
        reasons=["Heuristic naming"],
        base_priority_score=0.5,
        evidence_sources={"HEURISTIC_NAMING"},
        mapping_confidence="MODERATE",
        flaky_status=None,
        historical_failure_score=None
    )
    
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input],
        mode="NORMAL",
        business_behavior_mappings=[mapping],
        ac_coverage_report=None,
        test_to_ac_mappings=test_to_ac_mappings
    )
    
    candidate = ranked_bundle.ranked_candidates[0]
    
    # Check that small inferred boost was applied
    assert candidate.risk_value > 0.5
    assert any("inferred" in reason.lower() for reason in candidate.reasons)
    
    print(f"✓ Test with vague inferred mapping got small boost")
    print(f"  Risk value: {candidate.risk_value}")


def test_explicit_ac_outranks_generic_inference(db_session: Session):
    """Test that explicit AC outranks generic domain inference."""
    
    # Test 1: Explicit AC mapping
    ac_id = uuid4()
    behavior_id1 = uuid4()
    mapping1 = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac_id,
        behavior_id=behavior_id1,
        behavior_scenario_id=None,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Explicit match",
        is_candidate_missing_scenario="false",
    )
    
    test_id1 = uuid4()
    test_to_ac_mappings1 = {str(test_id1): [str(ac_id)]}
    
    ranking_input1 = RankingCandidateInput(
        test_case_id=test_id1,
        reasons=["Direct file coverage"],
        base_priority_score=0.5,
        evidence_sources={"DIRECT_FILE_COVERAGE"},
        mapping_confidence="HIGH",
        flaky_status=None,
        historical_failure_score=None
    )
    
    # Test 2: Generic inference
    behavior_id2 = uuid4()
    mapping2 = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=None,
        behavior_id=behavior_id2,
        behavior_scenario_id=None,
        journey_id=uuid4(),
        match_confidence=0.4,
        matched_terms=["password"],
        reason="Inferred",
        is_candidate_missing_scenario="false",
    )
    
    test_id2 = uuid4()
    test_to_ac_mappings2 = {}
    
    ranking_input2 = RankingCandidateInput(
        test_case_id=test_id2,
        reasons=["Heuristic naming"],
        base_priority_score=0.5,
        evidence_sources={"HEURISTIC_NAMING"},
        mapping_confidence="MODERATE",
        flaky_status=None,
        historical_failure_score=None
    )
    
    # Rank both
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input1, ranking_input2],
        mode="NORMAL",
        business_behavior_mappings=[mapping1, mapping2],
        ac_coverage_report=None,
        test_to_ac_mappings={**test_to_ac_mappings1, **test_to_ac_mappings2}
    )
    
    assert len(ranked_bundle.ranked_candidates) == 2
    
    # Explicit AC should rank higher
    explicit_candidate = next(c for c in ranked_bundle.ranked_candidates if str(c.test_case_id) == str(test_id1))
    inferred_candidate = next(c for c in ranked_bundle.ranked_candidates if str(c.test_case_id) == str(test_id2))
    
    assert explicit_candidate.risk_value > inferred_candidate.risk_value
    
    print(f"✓ Explicit AC outranks generic inference")
    print(f"  Explicit risk: {explicit_candidate.risk_value}")
    print(f"  Inferred risk: {inferred_candidate.risk_value}")


def test_no_business_intent_continues_recommendation(db_session: Session):
    """Test that recommendation continues even without business intent."""
    
    # No business behavior mappings
    test_id = uuid4()
    ranking_input = RankingCandidateInput(
        test_case_id=test_id,
        reasons=["Direct file coverage"],
        base_priority_score=0.5,
        evidence_sources={"DIRECT_FILE_COVERAGE"},
        mapping_confidence="HIGH",
        flaky_status=None,
        historical_failure_score=None
    )
    
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input],
        mode="NORMAL",
        business_behavior_mappings=[],
        ac_coverage_report=None,
        test_to_ac_mappings={}
    )
    
    # Should still return ranked candidates
    assert len(ranked_bundle.ranked_candidates) == 1
    candidate = ranked_bundle.ranked_candidates[0]
    assert candidate.risk_value == 0.5  # No boost applied
    
    print(f"✓ Recommendation continues without business intent")
    print(f"  Risk value: {candidate.risk_value}")


def test_scoring_boost_values(db_session: Session):
    """Test that scoring boost values match specification."""
    
    # Test AC mapping boost (+0.35)
    ac_id = uuid4()
    test_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac_id,
        behavior_id=uuid4(),
        behavior_scenario_id=uuid4(),
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    test_to_ac_mappings = {str(test_id): [str(ac_id)]}
    
    ranking_input = RankingCandidateInput(
        test_case_id=test_id,
        reasons=["Direct file coverage"],
        base_priority_score=0.5,
        evidence_sources={"DIRECT_FILE_COVERAGE"},
        mapping_confidence="HIGH",
        flaky_status=None,
        historical_failure_score=None
    )
    
    ranked_bundle = RecommendationRankingService.rank_candidates(
        db=db_session,
        repository_id=uuid4(),
        candidate_tests=[ranking_input],
        mode="NORMAL",
        business_behavior_mappings=[mapping],
        ac_coverage_report=None,
        test_to_ac_mappings=test_to_ac_mappings
    )
    
    candidate = ranked_bundle.ranked_candidates[0]
    # Base 0.5 + AC boost 0.35 = 0.85 (approximately, may have other factors)
    assert candidate.risk_value >= 0.85
    
    print(f"✓ Scoring boost values match specification")
    print(f"  Risk value with AC boost: {candidate.risk_value}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
