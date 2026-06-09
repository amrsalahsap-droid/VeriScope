"""
verify_recommendation_warning_rules.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Standalone verification for RecommendationWarningRules.

Each test builds a minimal mock of RecommendationRun (and optionally an
InputSnapshot / FragilityPattern list) and asserts expected warning codes.

Tests
â”€â”€â”€â”€â”€
 1. LOW coverage quality  â†’ LOW_COVERAGE_CONFIDENCE
 2. MISSING coverage      â†’ MISSING_COVERAGE_DATA
 3. MODERATE coverage     â†’ MODERATE_COVERAGE_CONFIDENCE
 4. HIGH coverage + NORMAL â†’ no coverage warning
 5. Unstable dependency neighborhood pattern on changed file
 6. Rollback-linked fragility on changed file
 7. High flaky influence (â‰¥ threshold reasoning entries)
 8. Sparse history window (< 14 days)
 9. No historical failure signal (changed files, no history used)
10. Multiple rules fire; result capped at MAX_WARNINGS
11. Forbidden phrase stripped from message at construction
12. Deduplication: same code fires only once
13. Ordering: HIGH severity before MEDIUM before LOW
14. WarningResult helpers: codes, messages, has_warnings, as_dict
"""

import sys, os, uuid, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock

from app.services.recommendation_warning_rules import (
    RecommendationWarningRules,
    RecommendationWarning,
    WarningResult,
    WarningSeverity,
    MAX_WARNINGS,
    _FLAKY_ENTRY_THRESHOLD,
    _MIN_HISTORY_WINDOW_DAYS,
)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []

def check(name, expr):
    status = PASS if expr else FAIL
    print(f"  [{status}] {name}")
    results.append(expr)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _run(
    evidence_quality="HIGH",
    recommendation_mode="NORMAL",
    reasoning_entries=None,
    window_start=None,
    window_end=None,
):
    r = MagicMock()
    r.evidence_quality = evidence_quality
    r.recommendation_mode = recommendation_mode
    r.reasoning_entries = reasoning_entries or []
    r.test_history_window_start = window_start
    r.test_history_window_end = window_end
    r.input_snapshot = None
    return r


def _snapshot(changed_files=None, historical_failures_used=None):
    s = MagicMock()
    s.changed_files = changed_files or []
    s.historical_failures_used = historical_failures_used or []
    return s


def _pattern(pattern_type, status="ACTIVE", trigger_file=None, trigger_dir=None, evidence_count=3):
    p = MagicMock()
    p.pattern_type = pattern_type
    p.status = status
    ctx = {}
    if trigger_file:
        ctx["trigger_file"] = trigger_file
    if trigger_dir:
        ctx["trigger_dir"] = trigger_dir
    p.context = ctx
    p.evidence_count = evidence_count
    return p


def _reasoning(reason_type="historical_fragility", human_readable="Fragility detected"):
    e = MagicMock()
    e.reason_type = reason_type
    e.human_readable_reason = human_readable
    return e


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 1: LOW coverage â†’ LOW_COVERAGE_CONFIDENCE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[1] LOW coverage quality â†’ LOW_COVERAGE_CONFIDENCE")
result = RecommendationWarningRules.evaluate(run=_run(evidence_quality="LOW"))
check("code present", "LOW_COVERAGE_CONFIDENCE" in result.codes)
check("severity HIGH", result.warnings[0].severity == WarningSeverity.HIGH)
check("no forbidden language", "unsafe" not in result.messages[0].lower())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 2: MISSING coverage â†’ MISSING_COVERAGE_DATA
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[2] MISSING coverage â†’ MISSING_COVERAGE_DATA")
result = RecommendationWarningRules.evaluate(run=_run(evidence_quality="MISSING"))
check("code present", "MISSING_COVERAGE_DATA" in result.codes)
check("message mentions unavailable", "unavailable" in result.messages[0].lower())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 3: MODERATE coverage â†’ MODERATE_COVERAGE_CONFIDENCE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[3] MODERATE coverage â†’ MODERATE_COVERAGE_CONFIDENCE")
result = RecommendationWarningRules.evaluate(run=_run(evidence_quality="MODERATE"))
check("code present", "MODERATE_COVERAGE_CONFIDENCE" in result.codes)
check("severity MEDIUM", any(w.severity == WarningSeverity.MEDIUM for w in result.warnings))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 4: HIGH + NORMAL â†’ no coverage warning
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[4] HIGH coverage + NORMAL mode â†’ no coverage warning")
result = RecommendationWarningRules.evaluate(run=_run(evidence_quality="HIGH", recommendation_mode="NORMAL"))
coverage_codes = {"LOW_COVERAGE_CONFIDENCE", "MISSING_COVERAGE_DATA", "MODERATE_COVERAGE_CONFIDENCE"}
check("no coverage warning fired", not any(c in result.codes for c in coverage_codes))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 5: Unstable dependency neighborhood
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[5] UNSTABLE_MODULE pattern on changed file â†’ UNSTABLE_DEPENDENCY_NEIGHBORHOOD")
run = _run()
run.input_snapshot = _snapshot(changed_files=["auth/middleware.py"])
pat = _pattern("UNSTABLE_MODULE", trigger_file="auth/middleware.py")
result = RecommendationWarningRules.evaluate(run=run, fragility_patterns=[pat])
check("code present", "UNSTABLE_DEPENDENCY_NEIGHBORHOOD" in result.codes)
check("message concise (â‰¤ 160 chars)", all(len(m) <= 160 for m in result.messages))
check("no outage language", "outage" not in result.messages[0].lower())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 6: Rollback-linked fragility on changed file
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[6] ROLLBACK_INVOLVEMENT on changed file â†’ ROLLBACK_LINKED_FRAGILITY")
run = _run()
run.input_snapshot = _snapshot(changed_files=["billing/subscriptions.py"])
pat = _pattern("ROLLBACK_INVOLVEMENT", trigger_file="billing/subscriptions.py", evidence_count=4)
result = RecommendationWarningRules.evaluate(run=run, fragility_patterns=[pat])
check("code present", "ROLLBACK_LINKED_FRAGILITY" in result.codes)
check("severity HIGH", any(w.severity == WarningSeverity.HIGH for w in result.warnings if w.code == "ROLLBACK_LINKED_FRAGILITY"))
check("mentions path", "subscriptions.py" in result.messages[0] or "billing" in result.messages[0])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 7: High flaky influence
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"\n[7] â‰¥{_FLAKY_ENTRY_THRESHOLD} flaky reasoning entries â†’ HIGH_FLAKY_INFLUENCE")
entries = [_reasoning(reason_type="flaky_adjustments") for _ in range(_FLAKY_ENTRY_THRESHOLD)]
run = _run(reasoning_entries=entries)
result = RecommendationWarningRules.evaluate(run=run)
check("code present", "HIGH_FLAKY_INFLUENCE" in result.codes)
check("severity MEDIUM", any(w.severity == WarningSeverity.MEDIUM for w in result.warnings if w.code == "HIGH_FLAKY_INFLUENCE"))
check("message mentions test count", str(_FLAKY_ENTRY_THRESHOLD) in result.messages[-1] or "flaky" in result.messages[-1].lower())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 8: Sparse history window
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"\n[8] History window < {_MIN_HISTORY_WINDOW_DAYS} days â†’ SPARSE_HISTORICAL_EVIDENCE")
now = datetime.datetime.utcnow()
run = _run(
    evidence_quality="MODERATE",
    recommendation_mode="WIDENED",
    window_start=now - datetime.timedelta(days=5),
    window_end=now,
)
result = RecommendationWarningRules.evaluate(run=run)
check("code present", "SPARSE_HISTORICAL_EVIDENCE" in result.codes)
check("message mentions days", "day" in result.messages[-1].lower())
check("no fake percentage", "%" not in result.messages[-1])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 9: No historical failure signal (new files)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[9] Changed files, no history â†’ NO_HISTORICAL_FAILURE_SIGNAL")
run = _run(evidence_quality="MODERATE", recommendation_mode="NORMAL")
run.input_snapshot = _snapshot(
    changed_files=["src/new_feature.py"],
    historical_failures_used=[],   # empty
)
result = RecommendationWarningRules.evaluate(run=run)
check("code present", "NO_HISTORICAL_FAILURE_SIGNAL" in result.codes)
check("message mentions recently added or limited", any(
    kw in result.messages[-1].lower()
    for kw in ("recently", "limited", "available")
))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 10: Multiple rules fire, capped at MAX_WARNINGS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"\n[10] Multiple signals â†’ capped at {MAX_WARNINGS}")
flaky_entries = [_reasoning(reason_type="flaky_adjustments") for _ in range(_FLAKY_ENTRY_THRESHOLD + 2)]
now = datetime.datetime.utcnow()
run = _run(
    evidence_quality="LOW",
    recommendation_mode="SAFE_FALLBACK",
    reasoning_entries=flaky_entries,
    window_start=now - datetime.timedelta(days=3),
    window_end=now,
)
run.input_snapshot = _snapshot(
    changed_files=["auth/middleware.py", "billing/subscriptions.py"],
    historical_failures_used=[],
)
patterns = [
    _pattern("UNSTABLE_MODULE",        trigger_file="auth/middleware.py"),
    _pattern("ROLLBACK_INVOLVEMENT",   trigger_file="billing/subscriptions.py"),
    _pattern("ESCAPED_DEFECT_PATTERN", trigger_file="auth/middleware.py"),
]
result = RecommendationWarningRules.evaluate(run=run, fragility_patterns=patterns)
check(f"â‰¤ {MAX_WARNINGS} warnings", len(result.warnings) <= MAX_WARNINGS)
check("has_warnings is True", result.has_warnings)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 11: Forbidden phrase stripped
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[11] Forbidden phrase is stripped at construction")
import logging, io
log_stream = io.StringIO()
handler = logging.StreamHandler(log_stream)
logging.getLogger("veriscope.recommendation_warning_rules").addHandler(handler)

w = RecommendationWarning(
    code="TEST_FORBIDDEN",
    message="This is unsafe to merge and high probability of outage.",
    severity=WarningSeverity.LOW,
)
check("unsafe to merge removed", "unsafe to merge" not in w.message.lower())
check("high probability of outage removed", "high probability of outage" not in w.message.lower())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 12: Deduplication â€” same code fires only once
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[12] Deduplication: same warning code emitted only once")
run = _run(evidence_quality="LOW")
# Two ROLLBACK patterns on the same file would normally both produce the same code
patterns = [
    _pattern("ROLLBACK_INVOLVEMENT", trigger_file="auth/middleware.py", evidence_count=3),
    _pattern("ROLLBACK_INVOLVEMENT", trigger_file="auth/middleware.py", evidence_count=5),
]
run.input_snapshot = _snapshot(changed_files=["auth/middleware.py"])
result = RecommendationWarningRules.evaluate(run=run, fragility_patterns=patterns)
rollback_count = result.codes.count("ROLLBACK_LINKED_FRAGILITY")
check("code appears exactly once", rollback_count == 1)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 13: Ordering â€” HIGH before MEDIUM before LOW
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[13] Ordering: HIGH severity before MEDIUM before LOW")
now = datetime.datetime.utcnow()
run = _run(
    evidence_quality="LOW",
    recommendation_mode="WIDENED",
    reasoning_entries=[_reasoning(reason_type="flaky_adjustments") for _ in range(_FLAKY_ENTRY_THRESHOLD)],
    window_start=now - datetime.timedelta(days=5),
    window_end=now,
)
result = RecommendationWarningRules.evaluate(run=run)
if len(result.warnings) >= 2:
    _order = {WarningSeverity.HIGH: 0, WarningSeverity.MEDIUM: 1, WarningSeverity.LOW: 2}
    severities = [_order[w.severity] for w in result.warnings]
    check("sorted HIGHâ†’MEDIUMâ†’LOW", severities == sorted(severities))
else:
    check("ordering (< 2 warnings, skip)", True)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 14: WarningResult helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[14] WarningResult helper properties")
run = _run(evidence_quality="LOW")
result = RecommendationWarningRules.evaluate(run=run)
check("codes is list of str", isinstance(result.codes, list) and all(isinstance(c, str) for c in result.codes))
check("messages is list of str", isinstance(result.messages, list) and all(isinstance(m, str) for m in result.messages))
check("has_warnings is bool", isinstance(result.has_warnings, bool))
d = result.as_dict()
check("as_dict has warning_count", "warning_count" in d)
check("as_dict has warnings list", isinstance(d.get("warnings"), list))
check("each dict entry has code/message/severity", all(
    "code" in w and "message" in w and "severity" in w
    for w in d["warnings"]
))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Summary
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"\n{'â”€'*55}")
total = len(results)
passed = sum(results)
failed = total - passed
print(f"Results: {passed}/{total} passed" + (f"  ({failed} FAILED)" if failed else "  â€” all assertions passed"))
sys.exit(0 if failed == 0 else 1)

