import pytest
from app.services.recommendation_reasoning_engine import RecommendationReasoningEngine

def test_generate_explanation_all_active_signals():
    """Verify that when all signals are active, we map them correctly but strictly cap at 4 bullets."""
    signals = {
        "coverage_link": 40,
        "knowledge_graph": 30,
        "module_risk": 15,
        "historical_failure": 10,
        "manual_override_history": 20,
        "escaped_defect_learning": 30,
        "runtime_cost": -1  # Represents fast execution duration
    }

    bullets = RecommendationReasoningEngine.generate_explanation(signals)
    
    # Assert strict 4 bullets cap
    assert len(bullets) == 4

    # Assert priority order and correct factual mapping (No AI wording or confidence theater)
    assert "Escaped defect gap: This test previously missed defect coverage in the changed file area." in bullets
    assert "Manual override history: Engineers repeatedly added this test manually for the changed files." in bullets
    assert "Direct code coverage: Coverage report confirms this test executes lines in the changed file." in bullets
    assert "Knowledge graph link: Execution traces correlate this test to the modified path." in bullets

def test_generate_explanation_subset_signals():
    """Verify mapping when only a subset of signals are active."""
    signals = {
        "coverage_link": 0,
        "knowledge_graph": 0,
        "module_risk": 15,
        "historical_failure": 10,
        "manual_override_history": 0,
        "escaped_defect_learning": 0,
        "runtime_cost": -10
    }

    bullets = RecommendationReasoningEngine.generate_explanation(signals)
    
    assert len(bullets) == 2
    assert "Recent execution failure: This test has failed recently in the last 30 days." in bullets
    assert "Module risk profile: Changed file lies in a directory path with elevated defect history." in bullets
    # Should not include low runtime cost since runtime_cost = -10 (which is slow)
    assert not any("runtime" in b.lower() for b in bullets)

def test_format_explanation_empty():
    """Verify fallback string is returned when no signals are active."""
    signals = {}
    formatted = RecommendationReasoningEngine.format_explanation(signals)
    assert formatted == "Selected based on pipeline fallback optimization rules."

def test_format_explanation_multiple():
    """Verify format_explanation builds bulleted strings correctly."""
    signals = {
        "coverage_link": 40,
        "historical_failure": 10
    }
    formatted = RecommendationReasoningEngine.format_explanation(signals)
    
    assert formatted.startswith("- ")
    assert "\n- " in formatted
    assert "Direct code coverage" in formatted
    assert "Recent execution failure" in formatted

def test_forbidden_language_check():
    """Verify there is absolutely zero speculative language, fake certainty, or AI words in all signals output."""
    all_possible_signals = [
        {"escaped_defect_learning": 1},
        {"manual_override_history": 1},
        {"coverage_link": True},
        {"knowledge_graph": True},
        {"historical_failure": True},
        {"module_risk": True},
        {"runtime_cost": -1}
    ]

    for sig in all_possible_signals:
        bullets = RecommendationReasoningEngine.generate_explanation(sig)
        for b in bullets:
            b_lower = b.lower()
            assert "ai believes" not in b_lower
            assert "ai thinks" not in b_lower
            assert "likely" not in b_lower
            assert "probably" not in b_lower
            assert "guaranteed" not in b_lower
            assert "certainly" not in b_lower
            assert "safe" not in b_lower
            assert "will catch" not in b_lower
            assert "will fail" not in b_lower
