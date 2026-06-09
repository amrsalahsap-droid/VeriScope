"""
verify_recommendation_action_generator.py
──────────────────────────────────────────
Standalone verification for RecommendationActionGenerator.

Tests
-----
 1. Rollback pattern (auth domain) -> auth_validation action
 2. Rollback pattern (billing domain) -> rollback_flow_review action
 3. Rollback pattern (generic path) -> rollback_flow_review with path
 4. CO_FAILURE_PATTERN auth+billing -> "auth-billing integration tests"
 5. CO_FAILURE_PATTERN same component -> "<module> integration tests"
 6. FILE_FAILURE_FREQUENCY HIGH risk -> integration tests for that file
 7. Warning code ROLLBACK_LINKED_FRAGILITY -> rollback flow review
 8. Warning code UNSTABLE_DEPENDENCY_NEIGHBORHOOD -> smoke validation
 9. Warning code HIGH_FLAKY_INFLUENCE -> manual verification
10. LOW coverage confidence -> smoke validation
11. MODERATE coverage confidence -> manual verification
12. SAFE_FALLBACK mode -> full regression suite
13. Default (HIGH + NORMAL, no signals) -> recommended regression suite
14. Determinism: same inputs always produce same output
15. No forbidden phrases in any generated sentence
16. Exactly one sentence (no newlines, no lists)
17. ActionResult.as_dict() has required keys
18. Priority: rollback beats co-failure beats frequency beats warnings
19. ESCAPED_DEFECT_PATTERN triggers rollback rule
20. No changed_files given -> conservative fallback still works
"""

import sys, os, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock

from app.services.recommendation_action_generator import (
    RecommendationActionGenerator,
    ActionResult,
    _FORBIDDEN,
)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []

def check(name, expr):
    status = PASS if expr else FAIL
    print(f"  [{status}] {name}")
    results.append(expr)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _run(evidence_quality="HIGH", recommendation_mode="NORMAL"):
    r = MagicMock()
    r.evidence_quality = evidence_quality
    r.recommendation_mode = recommendation_mode
    r.input_snapshot = None
    r.tests = []
    r.skipped_count = 0
    r.evidence_fingerprint = None
    return r

def _pattern(pattern_type, risk_level="HIGH", status="ACTIVE",
             trigger_file=None, trigger_dir=None, failure_test=None,
             evidence_count=3):
    p = MagicMock()
    p.pattern_type = pattern_type
    p.risk_level = risk_level
    p.status = status
    ctx = {}
    if trigger_file: ctx["trigger_file"] = trigger_file
    if trigger_dir:  ctx["trigger_dir"] = trigger_dir
    if failure_test: ctx["failure_test"] = failure_test
    p.context = ctx
    p.evidence_count = evidence_count
    return p

def generate(run=None, patterns=None, codes=None, files=None):
    if run is None:
        run = _run()
    return RecommendationActionGenerator.generate(
        run=run,
        fragility_patterns=patterns or [],
        warning_codes=codes or [],
        changed_files=files,
    )


# ─────────────────────────────────────────────────────────────
# Test 1: Rollback (auth domain) -> auth_validation
# ─────────────────────────────────────────────────────────────
print("\n[1] ROLLBACK_INVOLVEMENT on auth file -> auth_validation")
pat = _pattern("ROLLBACK_INVOLVEMENT", trigger_file="src/auth/middleware.py")
r = generate(patterns=[pat], files=["src/auth/middleware.py"])
check("action_type == auth_validation", r.action_type == "auth_validation")
check("sentence mentions auth", "auth" in r.sentence.lower())
check("sentence mentions review or rollback", any(w in r.sentence.lower() for w in ("review", "rollback", "integration")))
check("signal_source contains ROLLBACK", "ROLLBACK" in r.signal_source)


# ─────────────────────────────────────────────────────────────
# Test 2: Rollback (billing domain) -> rollback_flow_review
# ─────────────────────────────────────────────────────────────
print("\n[2] ESCAPED_DEFECT_PATTERN on billing file -> rollback_flow_review")
pat = _pattern("ESCAPED_DEFECT_PATTERN", trigger_file="billing/subscriptions.py")
r = generate(patterns=[pat], files=["billing/subscriptions.py"])
check("action_type == rollback_flow_review", r.action_type == "rollback_flow_review")
check("sentence mentions billing", "billing" in r.sentence.lower())
check("sentence mentions integration or rollback", any(w in r.sentence.lower() for w in ("integration", "rollback")))


# ─────────────────────────────────────────────────────────────
# Test 3: Rollback on generic path -> rollback_flow_review with path
# ─────────────────────────────────────────────────────────────
print("\n[3] ROLLBACK_INVOLVEMENT on generic path -> rollback_flow_review with path or domain")
pat = _pattern("ROLLBACK_INVOLVEMENT", trigger_file="services/payments/gateway.py")
r = generate(patterns=[pat], files=["services/payments/gateway.py"])
check("action_type == rollback_flow_review or auth_validation",
      r.action_type in ("rollback_flow_review", "auth_validation"))
# payments/ hits _BILLING_KEYWORDS, so sentence mentions billing or the path
check("sentence mentions billing or gateway or review",
      any(w in r.sentence.lower() for w in ("billing", "gateway.py", "payments", "review", "rollback")))


# ─────────────────────────────────────────────────────────────
# Test 4: CO_FAILURE_PATTERN auth+billing -> "auth-billing integration tests"
# ─────────────────────────────────────────────────────────────
print('\n[4] CO_FAILURE_PATTERN auth+billing -> "Run auth-billing integration tests"')
pat = _pattern(
    "CO_FAILURE_PATTERN",
    trigger_file="src/auth/middleware.py",
    failure_test="src/billing/subscriptions.py",
)
r = generate(patterns=[pat], files=["src/auth/middleware.py"])
check("action_type == integration_tests", r.action_type == "integration_tests")
check("sentence mentions auth", "auth" in r.sentence.lower())
check("sentence mentions billing or integration", any(w in r.sentence.lower() for w in ("billing", "integration")))
check("sentence ends with 'before merging.'", r.sentence.strip().endswith("before merging."))
# Spec example: "Run auth-billing integration tests before merge."
check("matches spec example pattern", "integration" in r.sentence.lower() and "before merging" in r.sentence.lower())


# ─────────────────────────────────────────────────────────────
# Test 5: CO_FAILURE_PATTERN same component -> "<module> integration tests"
# ─────────────────────────────────────────────────────────────
print("\n[5] CO_FAILURE_PATTERN within same component")
pat = _pattern(
    "CO_FAILURE_PATTERN",
    trigger_file="api/payments/handler.py",
    failure_test="api/payments/validation.py",
)
r = generate(patterns=[pat], files=["api/payments/handler.py"])
check("action_type == integration_tests", r.action_type == "integration_tests")
check("sentence mentions module", "payments" in r.sentence.lower() or "integration" in r.sentence.lower())


# ─────────────────────────────────────────────────────────────
# Test 6: FILE_FAILURE_FREQUENCY HIGH -> integration tests for that file
# ─────────────────────────────────────────────────────────────
print("\n[6] FILE_FAILURE_FREQUENCY HIGH on changed file -> integration tests")
pat = _pattern("FILE_FAILURE_FREQUENCY", risk_level="HIGH",
               trigger_file="core/auth/token_service.py", evidence_count=8)
r = generate(patterns=[pat], files=["core/auth/token_service.py"])
check("action_type == integration_tests", r.action_type == "integration_tests")
check("sentence mentions auth or token_service", any(w in r.sentence.lower() for w in ("auth", "token_service.py", "token")))
check("signal_source contains FILE_FAILURE", "FILE_FAILURE" in r.signal_source)


# ─────────────────────────────────────────────────────────────
# Test 7: Warning ROLLBACK_LINKED_FRAGILITY -> rollback flow review
# ─────────────────────────────────────────────────────────────
print("\n[7] Warning ROLLBACK_LINKED_FRAGILITY -> rollback flow review")
r = generate(codes=["ROLLBACK_LINKED_FRAGILITY"], files=["src/checkout/flow.py"])
check("action_type == rollback_flow_review", r.action_type == "rollback_flow_review")
check("sentence mentions review or integration", any(w in r.sentence.lower() for w in ("review", "integration")))
check("signal_source contains WARNING", "WARNING" in r.signal_source)


# ─────────────────────────────────────────────────────────────
# Test 8: Warning UNSTABLE_DEPENDENCY_NEIGHBORHOOD -> smoke validation
# ─────────────────────────────────────────────────────────────
print("\n[8] Warning UNSTABLE_DEPENDENCY_NEIGHBORHOOD -> smoke validation")
r = generate(codes=["UNSTABLE_DEPENDENCY_NEIGHBORHOOD"], files=["api/auth/routes.py"])
check("action_type == smoke_validation", r.action_type == "smoke_validation")
check("sentence mentions smoke validation", "smoke" in r.sentence.lower())
check("sentence mentions auth", "auth" in r.sentence.lower())


# ─────────────────────────────────────────────────────────────
# Test 9: Warning HIGH_FLAKY_INFLUENCE -> manual verification
# ─────────────────────────────────────────────────────────────
print("\n[9] Warning HIGH_FLAKY_INFLUENCE -> manual verification")
r = generate(codes=["HIGH_FLAKY_INFLUENCE"])
check("action_type == manual_verification", r.action_type == "manual_verification")
check("sentence mentions manual or verify", any(w in r.sentence.lower() for w in ("manual", "verify")))


# ─────────────────────────────────────────────────────────────
# Test 10: LOW coverage -> smoke validation
# ─────────────────────────────────────────────────────────────
print("\n[10] LOW coverage confidence -> smoke validation")
r = generate(run=_run(evidence_quality="LOW"), files=["src/new_feature.py"])
check("action_type == smoke_validation", r.action_type == "smoke_validation")
check("sentence mentions smoke", "smoke" in r.sentence.lower())
check("signal_source == LOW_COVERAGE_CONFIDENCE", r.signal_source == "LOW_COVERAGE_CONFIDENCE")


# ─────────────────────────────────────────────────────────────
# Test 11: MODERATE coverage -> manual verification
# ─────────────────────────────────────────────────────────────
print("\n[11] MODERATE coverage confidence -> manual verification")
r = generate(run=_run(evidence_quality="MODERATE"))
check("action_type == manual_verification", r.action_type == "manual_verification")
check("sentence mentions critical paths or manually", any(w in r.sentence.lower() for w in ("manually", "critical")))


# ─────────────────────────────────────────────────────────────
# Test 12: SAFE_FALLBACK mode -> full regression
# ─────────────────────────────────────────────────────────────
print("\n[12] SAFE_FALLBACK recommendation_mode -> full regression suite")
r = generate(run=_run(evidence_quality="HIGH", recommendation_mode="SAFE_FALLBACK"))
check("action_type == full_regression", r.action_type == "full_regression")
check("sentence mentions full regression", "full regression" in r.sentence.lower())


# ─────────────────────────────────────────────────────────────
# Test 13: Default (HIGH + NORMAL, no signals) -> recommended regression
# ─────────────────────────────────────────────────────────────
print("\n[13] Default: HIGH + NORMAL, no patterns -> recommended regression suite")
r = generate(run=_run(evidence_quality="HIGH", recommendation_mode="NORMAL"))
check("action_type == regression_suite", r.action_type == "regression_suite")
check("signal_source == DEFAULT", r.signal_source == "DEFAULT")
check("sentence mentions regression", "regression" in r.sentence.lower())


# ─────────────────────────────────────────────────────────────
# Test 14: Determinism
# ─────────────────────────────────────────────────────────────
print("\n[14] Determinism: same inputs produce identical output")
pat = _pattern("CO_FAILURE_PATTERN",
               trigger_file="auth/middleware.py",
               failure_test="billing/subscriptions.py")
run = _run()
files = ["auth/middleware.py"]
r1 = RecommendationActionGenerator.generate(run=run, fragility_patterns=[pat], changed_files=files)
r2 = RecommendationActionGenerator.generate(run=run, fragility_patterns=[pat], changed_files=files)
check("sentence identical", r1.sentence == r2.sentence)
check("action_type identical", r1.action_type == r2.action_type)
check("signal_source identical", r1.signal_source == r2.signal_source)


# ─────────────────────────────────────────────────────────────
# Test 15: No forbidden phrases in any generated sentence
# ─────────────────────────────────────────────────────────────
print("\n[15] No forbidden phrases in any output sentence")
scenarios = [
    generate(run=_run(evidence_quality="LOW")),
    generate(run=_run(evidence_quality="MODERATE")),
    generate(run=_run(evidence_quality="HIGH", recommendation_mode="SAFE_FALLBACK")),
    generate(run=_run(evidence_quality="HIGH", recommendation_mode="NORMAL")),
    generate(codes=["ROLLBACK_LINKED_FRAGILITY"]),
    generate(codes=["HIGH_FLAKY_INFLUENCE"]),
    generate(patterns=[_pattern("ROLLBACK_INVOLVEMENT", trigger_file="auth/session.py")],
             files=["auth/session.py"]),
]
for r in scenarios:
    lower = r.sentence.lower()
    for phrase in _FORBIDDEN:
        check(f"no '{phrase}' in: {r.sentence[:60]}", phrase not in lower)


# ─────────────────────────────────────────────────────────────
# Test 16: Exactly one sentence (no newlines, no bullet lists)
# ─────────────────────────────────────────────────────────────
print("\n[16] Exactly one sentence: no newlines, no markdown lists")
all_scenarios = [
    generate(run=_run(evidence_quality="LOW")),
    generate(run=_run(evidence_quality="MODERATE")),
    generate(run=_run(evidence_quality="HIGH", recommendation_mode="FULL_REGRESSION")),
    generate(run=_run()),
    generate(codes=["UNSTABLE_DEPENDENCY_NEIGHBORHOOD"]),
    generate(patterns=[_pattern("FILE_FAILURE_FREQUENCY", trigger_file="api/orders.py")],
             files=["api/orders.py"]),
]
for r in all_scenarios:
    check(f"no newlines in: '{r.sentence[:50]}'", "\n" not in r.sentence)
    check(f"no bullet markers in: '{r.sentence[:50]}'",
          not r.sentence.strip().startswith(("*", "-", "1.", "2.")))


# ─────────────────────────────────────────────────────────────
# Test 17: ActionResult.as_dict() structure
# ─────────────────────────────────────────────────────────────
print("\n[17] ActionResult.as_dict() has required keys")
r = generate(run=_run())
d = r.as_dict()
check("has 'sentence'", "sentence" in d)
check("has 'action_type'", "action_type" in d)
check("has 'signal_source'", "signal_source" in d)
check("sentence is str", isinstance(d["sentence"], str))


# ─────────────────────────────────────────────────────────────
# Test 18: Priority: rollback beats co-failure beats frequency beats warnings
# ─────────────────────────────────────────────────────────────
print("\n[18] Priority ordering: rollback > co-failure > frequency > warning codes")
rollback_pat = _pattern("ROLLBACK_INVOLVEMENT", trigger_file="auth/middleware.py")
cofail_pat   = _pattern("CO_FAILURE_PATTERN",
                         trigger_file="auth/middleware.py",
                         failure_test="billing/subscriptions.py")
freq_pat     = _pattern("FILE_FAILURE_FREQUENCY", risk_level="HIGH",
                         trigger_file="auth/middleware.py", evidence_count=10)
files = ["auth/middleware.py"]
codes = ["ROLLBACK_LINKED_FRAGILITY", "UNSTABLE_DEPENDENCY_NEIGHBORHOOD"]

r_all = generate(patterns=[rollback_pat, cofail_pat, freq_pat], codes=codes, files=files)
check("rollback beats all others", r_all.action_type in ("auth_validation", "rollback_flow_review"))

r_no_rollback = generate(patterns=[cofail_pat, freq_pat], codes=codes, files=files)
check("co-failure beats frequency and warnings", r_no_rollback.action_type == "integration_tests")

r_freq_only = generate(patterns=[freq_pat], codes=codes, files=files)
check("frequency beats warning codes", r_freq_only.action_type == "integration_tests")


# ─────────────────────────────────────────────────────────────
# Test 19: ESCAPED_DEFECT_PATTERN also triggers rollback rule
# ─────────────────────────────────────────────────────────────
print("\n[19] ESCAPED_DEFECT_PATTERN also triggers rollback rule")
pat = _pattern("ESCAPED_DEFECT_PATTERN", trigger_file="core/payments/processor.py")
r = generate(patterns=[pat], files=["core/payments/processor.py"])
check("action_type is rollback-related",
      r.action_type in ("rollback_flow_review", "auth_validation"))
check("signal_source contains ROLLBACK", "ROLLBACK" in r.signal_source)


# ─────────────────────────────────────────────────────────────
# Test 20: No changed_files given -> still produces a valid action
# ─────────────────────────────────────────────────────────────
print("\n[20] No changed_files -> conservative fallback still works")
pat = _pattern("ROLLBACK_INVOLVEMENT", trigger_file="src/auth/session.py")
r = generate(patterns=[pat], files=None)
check("returns ActionResult", isinstance(r, ActionResult))
check("sentence is non-empty", bool(r.sentence.strip()))
check("action_type is non-empty", bool(r.action_type))


# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
print(f"\n{'-'*55}")
total = len(results)
passed = sum(results)
failed = total - passed
print(f"Results: {passed}/{total} passed" + (f"  ({failed} FAILED)" if failed else "  -- all assertions passed"))
sys.exit(0 if failed == 0 else 1)
