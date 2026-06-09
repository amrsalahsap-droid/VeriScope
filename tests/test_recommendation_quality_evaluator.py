import pytest
from app.services.recommendation_quality_evaluator import RecommendationQualityEvaluator
from app.models.recommendation import RecommendedTest

def test_empty_recommendations():
    """Test quality evaluation with an empty list of recommendations."""
    res = RecommendationQualityEvaluator.evaluate_quality([])
    assert res["score"] == 0
    assert res["tier"] == "POOR"
    assert res["is_weak"] is True
    assert res["breakdown"]["coverage_contribution"] == 0.0
    assert res["breakdown"]["graph_contribution"] == 0.0
    assert res["breakdown"]["domain_contribution"] == 0.0
    assert res["breakdown"]["fallback_ratio"] == 0.0
    assert res["breakdown"]["evidence_completeness"] == 0.0

def test_strong_quality_direct_coverage():
    """Test 100% direct coverage recommendations result in STRONG quality."""
    recs = [
        {"source_signal": "DIRECT_COVERAGE"},
        {"source_signal": "DIRECT_COVERAGE"},
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    assert res["score"] == 100
    assert res["tier"] == "STRONG"
    assert res["is_weak"] is False
    assert res["breakdown"]["coverage_contribution"] == 1.0
    assert res["breakdown"]["evidence_completeness"] == 1.0
    assert res["breakdown"]["fallback_ratio"] == 0.0

def test_graph_quality():
    """Test 100% graph coverage recommendations."""
    recs = [
        {"source_signal": "TEST_COVERAGE_GRAPH"},
        {"source_signal": "TEST_COVERAGE_GRAPH"},
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    assert res["score"] == 85
    assert res["tier"] == "STRONG"
    assert res["is_weak"] is False
    assert res["breakdown"]["graph_contribution"] == 1.0
    assert res["breakdown"]["evidence_completeness"] == 1.0

def test_domain_match_quality():
    """Test 100% domain match recommendations."""
    recs = [
        {"source_signal": "DOMAIN_MATCH"},
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    assert res["score"] == 70
    assert res["tier"] == "GOOD"
    assert res["is_weak"] is False
    assert res["breakdown"]["domain_contribution"] == 1.0
    assert res["breakdown"]["evidence_completeness"] == 1.0

def test_fallback_quality():
    """Test 100% fallback recommendations result in POOR quality."""
    recs = [
        {"source_signal": "HISTORICAL_FAILURE_FALLBACK"},
        {"source_signal": "HISTORICAL_FAILURE_FALLBACK"},
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    assert res["score"] == 0
    assert res["tier"] == "POOR"
    assert res["is_weak"] is True
    assert res["breakdown"]["fallback_ratio"] == 1.0
    assert res["breakdown"]["evidence_completeness"] == 0.0

def test_mixed_quality_fair():
    """Test mixed fallback and domain match results in FAIR quality."""
    # 50% DOMAIN_MATCH, 50% HISTORICAL_FAILURE_FALLBACK
    recs = [
        {"source_signal": "DOMAIN_MATCH"},
        {"source_signal": "HISTORICAL_FAILURE_FALLBACK"},
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    # math:
    # cov_contrib = 0, graph_contrib = 0, domain_contrib = 0.5, fallback_ratio = 0.5, evidence_completeness = 0.5, other_ratio = 0
    # evidence_sum = 0.5
    # evidence_score = (0.5 * 70.0) / 0.5 = 70.0
    # score = round(0.5 * 70.0) = 35
    assert res["score"] == 35
    assert res["tier"] == "FAIR"
    assert res["is_weak"] is True
    assert res["breakdown"]["domain_contribution"] == 0.5
    assert res["breakdown"]["fallback_ratio"] == 0.5
    assert res["breakdown"]["evidence_completeness"] == 0.5

def test_other_signals():
    """Test signals that are categorized as 'other'."""
    recs = [
        {"source_signal": "INDIRECT_DEPENDENCY_IMPACT"},
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    # math:
    # other_ratio = 1.0
    # evidence_sum = 1.0
    # evidence_score = 80.0
    # score = 80
    assert res["score"] == 80
    assert res["tier"] == "STRONG"
    assert res["is_weak"] is False
    assert res["breakdown"]["evidence_completeness"] == 1.0

def test_db_model_instances():
    """Test that the evaluator successfully handles ORM model instances."""
    recs = [
        RecommendedTest(source_signal="DIRECT_COVERAGE", priority=1.0, confidence="HIGH", reason="", test_identifier="t1", test_name="t1"),
        RecommendedTest(source_signal="HISTORICAL_FAILURE_FALLBACK", priority=1.0, confidence="LOW", reason="", test_identifier="t2", test_name="t2"),
    ]
    res = RecommendationQualityEvaluator.evaluate_quality(recs)
    # math:
    # cov_contrib = 0.5, fallback_ratio = 0.5, evidence_completeness = 0.5
    # evidence_sum = 0.5
    # evidence_score = (0.5 * 100.0) / 0.5 = 100.0
    # score = round(0.5 * 100.0) = 50
    assert res["score"] == 50
    assert res["tier"] == "GOOD"
    assert res["is_weak"] is False
    assert res["breakdown"]["coverage_contribution"] == 0.5
    assert res["breakdown"]["fallback_ratio"] == 0.5
    assert res["breakdown"]["evidence_completeness"] == 0.5
