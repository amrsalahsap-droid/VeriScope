"""
Tests for TestingStrategyGenerator.

Covers:
- Priority thresholds (HIGH / MEDIUM / LOW)
- Spec example: password validation PR
- Each type carries a non-empty reason
- Reason text is factual (no forbidden phrases)
- HIGH types appear before MEDIUM appear before LOW
- Regression always recommended when risk level > LOW
- No test cases in output (structure only)
- format_for_display() renders correct sections
- Empty ImpactProfile produces regression baseline only
- Types not triggered are omitted
"""
import pytest
from app.services.testing_strategy_generator import TestingStrategyGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(**overrides):
    base = {
        "affected_domains": [],
        "affected_features": [],
        "change_types": [],
        "risk_categories": [],
        "recommended_testing_types": ["REGRESSION"],
        "impact_summary": "test",
    }
    base.update(overrides)
    return base


def _risk(level="LOW", areas=None, reasons=None):
    return {
        "risk_level": level,
        "risk_areas": areas or [],
        "risk_reasons": reasons or [],
    }


def _types_by_priority(strategy, priority):
    return [e["type"] for e in strategy["types"] if e["priority"] == priority]


def _find(strategy, t_type):
    return next((e for e in strategy["types"] if e["type"] == t_type), None)


# ---------------------------------------------------------------------------
# Structure invariants
# ---------------------------------------------------------------------------

class TestStructureInvariants:
    def test_every_entry_has_required_keys(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"], risk_categories=["AUTH"]),
            _risk("HIGH"),
        )
        for entry in s["types"]:
            assert "type"     in entry
            assert "label"    in entry
            assert "priority" in entry
            assert "reason"   in entry
            assert "score"    in entry

    def test_every_entry_has_non_empty_reason(self):
        s = TestingStrategyGenerator.generate(
            _profile(
                change_types=["AUTH_CHANGE", "API_CHANGE", "UI_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "PAYMENTS"],
            ),
            _risk("CRITICAL"),
        )
        for entry in s["types"]:
            assert entry["reason"].strip() != "", f"{entry['type']} has empty reason"

    def test_output_contains_no_test_case_keys(self):
        """The strategy must NOT enumerate individual test cases."""
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"]),
            _risk("HIGH"),
        )
        for entry in s["types"]:
            assert "test_case" not in entry
            assert "test_id" not in entry
            assert "stable_identity" not in entry

    def test_priority_order_is_high_then_medium_then_low(self):
        s = TestingStrategyGenerator.generate(
            _profile(
                change_types=["AUTH_CHANGE", "CONFIG_CHANGE"],
                risk_categories=["AUTH", "SECURITY"],
            ),
            _risk("HIGH"),
        )
        priorities = [e["priority"] for e in s["types"]]
        # Once we leave HIGH, we must not see HIGH again
        seen_medium = False
        seen_low = False
        for p in priorities:
            if p == "MEDIUM":
                seen_medium = True
            if p == "LOW":
                seen_low = True
            if p == "HIGH":
                assert not seen_medium and not seen_low, "HIGH entry appeared after MEDIUM/LOW"
            if p == "MEDIUM":
                assert not seen_low, "MEDIUM entry appeared after LOW"

    def test_no_duplicate_types(self):
        s = TestingStrategyGenerator.generate(
            _profile(
                change_types=["AUTH_CHANGE", "API_CHANGE", "DATABASE_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "DATA_INTEGRITY"],
            ),
            _risk("CRITICAL"),
        )
        types = [e["type"] for e in s["types"]]
        assert len(types) == len(set(types)), f"Duplicate types: {types}"

    def test_all_priorities_are_valid_values(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE", "UI_CHANGE"]),
            _risk("MODERATE"),
        )
        for entry in s["types"]:
            assert entry["priority"] in ("HIGH", "MEDIUM", "LOW"), \
                f"Invalid priority: {entry['priority']}"

    def test_summary_is_non_empty_string(self):
        s = TestingStrategyGenerator.generate(_profile(), _risk())
        assert isinstance(s["summary"], str)
        assert len(s["summary"]) > 0

    def test_risk_level_echoed_in_output(self):
        s = TestingStrategyGenerator.generate(_profile(), _risk("CRITICAL"))
        assert s["risk_level"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Regression baseline
# ---------------------------------------------------------------------------

class TestRegressionBaseline:
    def test_regression_always_present(self):
        """Regression must always appear, even for an empty ImpactProfile."""
        s = TestingStrategyGenerator.generate(_profile(), _risk("LOW"))
        assert _find(s, "REGRESSION") is not None

    def test_regression_priority_increases_with_risk_level(self):
        low_s  = TestingStrategyGenerator.generate(_profile(), _risk("LOW"))
        high_s = TestingStrategyGenerator.generate(_profile(), _risk("HIGH"))
        low_score  = _find(low_s,  "REGRESSION")["score"]
        high_score = _find(high_s, "REGRESSION")["score"]
        assert high_score > low_score

    def test_regression_is_high_priority_for_critical_risk(self):
        """CRITICAL risk alone must push regression to HIGH."""
        # HIGH threshold = 6, CRITICAL boost = 6
        s = TestingStrategyGenerator.generate(_profile(), _risk("CRITICAL"))
        reg = _find(s, "REGRESSION")
        assert reg["priority"] == "HIGH"

    def test_regression_reason_mentions_risk_level(self):
        s = TestingStrategyGenerator.generate(_profile(), _risk("HIGH"))
        reg = _find(s, "REGRESSION")
        assert "High" in reg["reason"] or "HIGH" in reg["reason"]


# ---------------------------------------------------------------------------
# Spec example: Password validation PR
# ---------------------------------------------------------------------------

class TestPasswordValidationSpecExample:
    """
    Input mirrors the spec example: 'Password validation change'.

    Expected HIGH:  Security, Integration, Regression
    Expected MEDIUM: API (if present)
    Expected LOW:   Performance (if triggered)
    """
    def _strategy(self):
        return TestingStrategyGenerator.generate(
            _profile(
                change_types=["AUTH_CHANGE", "VALIDATION_CHANGE", "API_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "USER_REGISTRATION"],
                affected_features=["password", "reset-password"],
            ),
            _risk("CRITICAL", areas=["Authentication", "Security"]),
        )

    def test_security_is_high_priority(self):
        s = self._strategy()
        sec = _find(s, "SECURITY")
        assert sec is not None, "SECURITY not in strategy"
        assert sec["priority"] == "HIGH"

    def test_regression_is_high_priority(self):
        s = self._strategy()
        reg = _find(s, "REGRESSION")
        assert reg is not None
        assert reg["priority"] == "HIGH"

    def test_integration_is_present(self):
        s = self._strategy()
        intg = _find(s, "INTEGRATION")
        assert intg is not None, "INTEGRATION not in strategy"

    def test_api_is_present(self):
        s = self._strategy()
        api = _find(s, "API")
        assert api is not None, "API not in strategy"

    def test_high_priority_first(self):
        s = self._strategy()
        high = _types_by_priority(s, "HIGH")
        assert len(high) >= 2, f"Expected ≥2 HIGH types, got: {high}"


# ---------------------------------------------------------------------------
# Signal-specific trigger tests
# ---------------------------------------------------------------------------

class TestSignalTriggers:
    def test_ui_change_triggers_ui_type(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["UI_CHANGE"]),
            _risk("LOW"),
        )
        ui = _find(s, "UI")
        assert ui is not None
        assert ui["priority"] == "HIGH"  # UI_CHANGE → UI score=6

    def test_database_change_triggers_database_type(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["DATABASE_CHANGE"]),
            _risk("LOW"),
        )
        db = _find(s, "DATABASE")
        assert db is not None
        assert db["priority"] == "HIGH"

    def test_api_change_triggers_api_type_high(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["API_CHANGE"]),
            _risk("LOW"),
        )
        api = _find(s, "API")
        assert api is not None
        assert api["priority"] == "HIGH"

    def test_config_change_triggers_smoke(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["CONFIG_CHANGE"]),
            _risk("LOW"),
        )
        smoke = _find(s, "SMOKE")
        assert smoke is not None

    def test_payments_triggers_e2e_high(self):
        s = TestingStrategyGenerator.generate(
            _profile(risk_categories=["PAYMENTS"]),
            _risk("HIGH"),
        )
        e2e = _find(s, "E2E")
        assert e2e is not None
        assert e2e["priority"] == "HIGH"

    def test_data_integrity_triggers_database_high(self):
        s = TestingStrategyGenerator.generate(
            _profile(risk_categories=["DATA_INTEGRITY"]),
            _risk("MODERATE"),
        )
        db = _find(s, "DATABASE")
        assert db is not None
        assert db["priority"] == "HIGH"

    def test_dependency_change_triggers_integration(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["DEPENDENCY_CHANGE"]),
            _risk("LOW"),
        )
        intg = _find(s, "INTEGRATION")
        assert intg is not None

    def test_test_change_only_adds_regression_low(self):
        """TEST_CHANGE has no code change → no UNIT baseline, only small regression boost."""
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["TEST_CHANGE"]),
            _risk("LOW"),
        )
        unit = _find(s, "UNIT")
        # UNIT baseline only fires for non-TEST_CHANGE code changes
        assert unit is None

    def test_non_test_change_adds_unit_baseline(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["VALIDATION_CHANGE"]),
            _risk("LOW"),
        )
        unit = _find(s, "UNIT")
        assert unit is not None

    def test_performance_not_recommended_without_signals(self):
        """PERFORMANCE has no trigger in the current table — must not appear unsolicited."""
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"]),
            _risk("LOW"),
        )
        perf = _find(s, "PERFORMANCE")
        assert perf is None


# ---------------------------------------------------------------------------
# Reason quality
# ---------------------------------------------------------------------------

class TestReasonQuality:
    _FORBIDDEN = [
        "confident", "likely", "probably", "might", "could be",
        "seems", "appears", "maybe", "almost certainly", "critical risk guaranteed",
        "%",
    ]

    def test_no_forbidden_phrases_in_reasons(self):
        s = TestingStrategyGenerator.generate(
            _profile(
                change_types=["AUTH_CHANGE", "API_CHANGE", "UI_CHANGE", "DATABASE_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "PAYMENTS", "DATA_INTEGRITY"],
            ),
            _risk("CRITICAL"),
        )
        for entry in s["types"]:
            for phrase in self._FORBIDDEN:
                assert phrase not in entry["reason"].lower(), (
                    f"Forbidden phrase '{phrase}' found in reason for {entry['type']}: "
                    f"{entry['reason']}"
                )

    def test_reason_is_a_single_sentence(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"]),
            _risk("HIGH"),
        )
        for entry in s["types"]:
            # Primary reason should not contain newlines
            assert "\n" not in entry["reason"], \
                f"{entry['type']} reason contains newline: {entry['reason']!r}"


# ---------------------------------------------------------------------------
# format_for_display
# ---------------------------------------------------------------------------

class TestFormatForDisplay:
    def test_output_contains_high_priority_header(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"], risk_categories=["AUTH"]),
            _risk("HIGH"),
        )
        text = TestingStrategyGenerator.format_for_display(s)
        assert "HIGH PRIORITY" in text

    def test_output_contains_recommended_testing_types_header(self):
        s = TestingStrategyGenerator.generate(_profile(), _risk())
        text = TestingStrategyGenerator.format_for_display(s)
        assert "Recommended Testing Types" in text

    def test_output_contains_each_type_label(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE", "API_CHANGE"]),
            _risk("HIGH"),
        )
        text = TestingStrategyGenerator.format_for_display(s)
        for entry in s["types"]:
            assert entry["label"] in text, f"Label '{entry['label']}' missing from display"

    def test_output_contains_reason_for_each_type(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"]),
            _risk("HIGH"),
        )
        text = TestingStrategyGenerator.format_for_display(s)
        for entry in s["types"]:
            assert entry["reason"] in text, \
                f"Reason '{entry['reason']}' for {entry['type']} missing from display"

    def test_summary_appears_in_display(self):
        s = TestingStrategyGenerator.generate(
            _profile(change_types=["AUTH_CHANGE"]),
            _risk("HIGH"),
        )
        text = TestingStrategyGenerator.format_for_display(s)
        assert s["summary"] in text
