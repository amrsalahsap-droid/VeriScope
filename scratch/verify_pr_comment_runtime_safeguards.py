"""
verify_pr_comment_runtime_safeguards.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Standalone verification for PRCommentRuntimeSafeguards.

Tests
-----
 1. render_with_timeout - SUCCESS path: fast render returns full body
 2. render_with_timeout - DEGRADED: exception in render_fn produces minimal comment
 3. render_with_timeout - DEGRADED: slow render produces minimal comment (Windows timer)
 4. MinimalCommentBuilder: contains canonical marker
 5. MinimalCommentBuilder: does not contain forbidden phrases
 6. MinimalCommentBuilder: deterministic (same inputs => same output)
 7. call_github_api - SUCCESS: returns correct outcome
 8. call_github_api - FAILED: exception is captured, not raised
 9. call_github_api - TIMEOUT: exceeds budget, returns TIMEOUT outcome
10. pipeline_budget_exceeded: False immediately, True after budget consumed
11. pipeline_elapsed_ms: advances monotonically
12. SafeguardResult.succeeded: True for SUCCESS and DEGRADED, False for FAILED/TIMEOUT
13. isolated_enqueue: isolates exception from caller
14. DeliveryOutcome values cover all required states
"""

import sys, os, time, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock

from app.services.pr_comment_runtime_safeguards import (
    PRCommentRuntimeSafeguards,
    MinimalCommentBuilder,
    DeliveryOutcome,
    SafeguardResult,
    isolated_enqueue,
    RENDER_TIMEOUT_SECONDS,
    GITHUB_API_TIMEOUT_SECONDS,
    DELIVERY_PIPELINE_BUDGET_SECONDS,
)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []

def check(name, expr):
    status = PASS if expr else FAIL
    print(f"  [{status}] {name}")
    results.append(expr)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 1: render_with_timeout - SUCCESS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[1] render_with_timeout - SUCCESS: fast render returns full body")
sg = PRCommentRuntimeSafeguards()
result = sg.render_with_timeout(
    lambda: "## Veriscope Regression Intelligence\n\n* 5 tests\n<!-- veriscope-pr-comment -->",
    recommended_count=5,
    total_count=100,
    evidence_quality="HIGH",
    short_hash="abc12345",
)
check("outcome == SUCCESS", result.outcome == DeliveryOutcome.SUCCESS)
check("comment_body contains header", "Veriscope Regression Intelligence" in result.comment_body)
check("is_degraded is False", result.is_degraded is False)
check("elapsed_ms >= 0", result.elapsed_ms >= 0)
check("budget_remaining_ms > 0", result.budget_remaining_ms > 0)
check("succeeded is True", result.succeeded)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 2: render_with_timeout - DEGRADED on exception
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[2] render_with_timeout - DEGRADED: exception in render_fn")
def _failing_render():
    raise RuntimeError("DB query timed out")

sg = PRCommentRuntimeSafeguards()
result = sg.render_with_timeout(
    _failing_render,
    recommended_count=10,
    total_count=200,
    evidence_quality="LOW",
    short_hash="deadbeef",
)
check("outcome == DEGRADED", result.outcome == DeliveryOutcome.DEGRADED)
check("is_degraded is True", result.is_degraded is True)
check("degradation_reason contains error", "DB query timed out" in (result.degradation_reason or ""))
check("comment_body contains canonical marker", "<!-- veriscope-pr-comment -->" in result.comment_body)
check("comment_body mentions unavailable", "unavailable" in result.comment_body.lower())
check("succeeded is True (degraded still delivers)", result.succeeded)
check("count in body", "10" in result.comment_body)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 3: render_with_timeout - DEGRADED on very short timeout
# Uses a 1-second budget and a 3-second sleep to force timeout.
# Windows: threading.Timer cannot interrupt time.sleep mid-way, so we
# verify at-exit detection fires.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[3] render_with_timeout - DEGRADED: timeout exceeded (2s budget, 3s sleep)")
def _slow_render():
    time.sleep(3)
    return "this should never be returned"

sg = PRCommentRuntimeSafeguards(render_timeout=2)
t_start = time.monotonic()
result = sg.render_with_timeout(
    _slow_render,
    recommended_count=7,
    total_count=50,
    evidence_quality="MODERATE",
    short_hash="feed1234",
)
elapsed_s = time.monotonic() - t_start
# On Windows with threading.Timer, the timer fires AFTER the sleep completes
# (can't interrupt blocking C call), so elapsed may be ~3s.
# POSIX SIGALRM would interrupt at 2s exactly.
# Either way, the result MUST be DEGRADED.
check("outcome == DEGRADED", result.outcome == DeliveryOutcome.DEGRADED)
check("is_degraded is True", result.is_degraded is True)
check("fallback body present", "<!-- veriscope-pr-comment -->" in result.comment_body)
check("succeeded is True", result.succeeded)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 4: MinimalCommentBuilder - canonical marker present
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[4] MinimalCommentBuilder: canonical marker always present")
body = MinimalCommentBuilder.build(
    recommended_count=3,
    total_count=99,
    evidence_quality="LOW",
    short_hash="cafe0001",
)
check("marker present", "<!-- veriscope-pr-comment -->" in body)
check("header present", "Veriscope Regression Intelligence" in body)
check("test counts present", "3 / 99" in body)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 5: MinimalCommentBuilder - no forbidden phrases
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[5] MinimalCommentBuilder: no forbidden phrases")
body = MinimalCommentBuilder.build(
    recommended_count=5,
    total_count=100,
    evidence_quality="MODERATE",
    short_hash="babe0002",
)
forbidden = ["unsafe to merge", "production failure", "guaranteed", "outage", "catastrophic"]
for phrase in forbidden:
    check(f"no '{phrase}'", phrase not in body.lower())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 6: MinimalCommentBuilder - deterministic
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[6] MinimalCommentBuilder: deterministic output")
kwargs = dict(recommended_count=5, total_count=50, evidence_quality="HIGH", short_hash="aabb1122")
b1 = MinimalCommentBuilder.build(**kwargs)
b2 = MinimalCommentBuilder.build(**kwargs)
check("identical outputs", b1 == b2)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 7: call_github_api - SUCCESS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[7] call_github_api - SUCCESS")
sg = PRCommentRuntimeSafeguards()
result = sg.call_github_api(
    "create_pr_comment",
    lambda **kw: {"id": 42, "html_url": "https://github.com/example/pr/1"},
    body_text="hello",
)
check("outcome == SUCCESS", result.outcome == DeliveryOutcome.SUCCESS)
check("github_comment_id == 42", result.github_comment_id == 42)
check("no error", result.error is None)
check("succeeded is True", result.succeeded)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 8: call_github_api - FAILED (exception captured)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[8] call_github_api - FAILED: exception captured, not raised")
class FakeGitHubError(Exception):
    pass

def _always_fail(**kwargs):
    raise FakeGitHubError("503 Service Unavailable")

sg = PRCommentRuntimeSafeguards()
result = sg.call_github_api("create_pr_comment", _always_fail)
check("outcome == FAILED", result.outcome == DeliveryOutcome.FAILED)
check("error message captured", "503" in (result.error or ""))
check("succeeded is False", not result.succeeded)
# Most importantly: no exception propagated to here


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 9: call_github_api - TIMEOUT
# Uses a 1s api_timeout with a 3s sleeping function.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[9] call_github_api - TIMEOUT: budget exceeded")
def _slow_api(**kwargs):
    time.sleep(3)
    return {"id": 999}

sg = PRCommentRuntimeSafeguards(api_timeout=1)
result = sg.call_github_api("create_pr_comment", _slow_api)
# On Windows: TIMEOUT detected at exit of sleep (timer fires, checked at exit)
check("outcome == TIMEOUT or FAILED", result.outcome in (DeliveryOutcome.TIMEOUT, DeliveryOutcome.FAILED))
check("succeeded is False", not result.succeeded)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 10: pipeline_budget_exceeded
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[10] pipeline_budget_exceeded: False initially, True after budget consumed")
sg = PRCommentRuntimeSafeguards(pipeline_budget=1)
check("not exceeded immediately", not sg.pipeline_budget_exceeded())
time.sleep(1.1)
check("exceeded after budget elapsed", sg.pipeline_budget_exceeded())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 11: pipeline_elapsed_ms monotonically increases
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[11] pipeline_elapsed_ms: monotonically increasing")
sg = PRCommentRuntimeSafeguards()
t0 = sg.pipeline_elapsed_ms()
time.sleep(0.1)
t1 = sg.pipeline_elapsed_ms()
check("t1 > t0", t1 > t0)
check("t0 >= 0", t0 >= 0)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 12: SafeguardResult.succeeded
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[12] SafeguardResult.succeeded: True for SUCCESS/DEGRADED, False for FAILED/TIMEOUT")
check("SUCCESS -> True",  SafeguardResult(outcome=DeliveryOutcome.SUCCESS).succeeded)
check("DEGRADED -> True", SafeguardResult(outcome=DeliveryOutcome.DEGRADED).succeeded)
check("FAILED -> False",  not SafeguardResult(outcome=DeliveryOutcome.FAILED).succeeded)
check("TIMEOUT -> False", not SafeguardResult(outcome=DeliveryOutcome.TIMEOUT).succeeded)
check("SKIPPED -> False", not SafeguardResult(outcome=DeliveryOutcome.SKIPPED).succeeded)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 13: isolated_enqueue - isolates exception
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[13] isolated_enqueue: exception does not propagate to caller")
calls = []

def _failing_enqueue(run_id):
    calls.append(run_id)
    raise RuntimeError("RQ connection refused")

try:
    isolated_enqueue(_failing_enqueue, "run-001")
    check("no exception raised", True)
except Exception:
    check("no exception raised", False)

check("enqueue was called", "run-001" in calls)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Test 14: DeliveryOutcome values
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("\n[14] DeliveryOutcome: all required states present")
required = {"SUCCESS", "DEGRADED", "SKIPPED", "FAILED", "TIMEOUT"}
actual = {e.value for e in DeliveryOutcome}
check("all required states exist", required.issubset(actual))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Summary
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"\n{'â”€'*55}")
total = len(results)
passed = sum(results)
failed = total - passed
print(f"Results: {passed}/{total} passed" + (f"  ({failed} FAILED)" if failed else "  -- all assertions passed"))
sys.exit(0 if failed == 0 else 1)

