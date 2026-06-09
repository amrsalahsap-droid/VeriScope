"""
verify_pr_comment_update_strategy.py
─────────────────────────────────────
Standalone verification for PRCommentUpdateStrategy.

Tests:
  1. PROCEED — clean state, no prior delivery
  2. DEBOUNCE — next_allowed_delivery_at in the future
  3. SUPERSEDED — a newer run is pinned on the state
  4. SKIPPED_HASH — body hash unchanged, status=DELIVERED
  5. TTL_EXPIRED — run created > 24 h ago
  6. claim_delivery succeeds for correct run
  7. claim_delivery fails (returns False) when another run has taken over
  8. coalesce_pending_runs creates state on first call
  9. coalesce_pending_runs updates + supersedes on second call
 10. mark_delivered persists debounce window and resets attempt count
"""

import sys, os, uuid, datetime, hashlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch, PropertyMock

from app.services.pr_comment_update_strategy import (
    PRCommentUpdateStrategy,
    UpdateAction,
    DEBOUNCE_INTERVAL_SECONDS,
    DELIVERY_JOB_TTL_HOURS,
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

def _make_run(pull_request=None, created_at=None):
    run = MagicMock()
    run.id = uuid.uuid4()
    run.pull_request = pull_request or _make_pr()
    run.repository_id = uuid.uuid4()
    run.created_at = created_at or datetime.datetime.utcnow()
    return run

def _make_pr(repository_id=None):
    pr = MagicMock()
    pr.id = uuid.uuid4()
    pr.repository_id = repository_id or uuid.uuid4()
    pr.number = 42
    return pr

def _make_state(
    latest_run_id=None,
    comment_status="PENDING",
    next_allowed=None,
    body_hash=None,
):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.latest_recommendation_run_id = latest_run_id
    s.comment_status = comment_status
    s.next_allowed_delivery_at = next_allowed
    s.latest_comment_body_hash = body_hash
    s.delivery_attempt_count = 0
    s.last_delivery_attempt_at = None
    return s

def _make_strategy(run, state):
    """Build a strategy with a mock DB that returns the given run and state."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [run, state]
    return PRCommentUpdateStrategy(db)


# ─────────────────────────────────────────────────────────────
# Test 1: PROCEED — clean state, no prior delivery
# ─────────────────────────────────────────────────────────────
print("\n[1] PROCEED — clean state")
run = _make_run()
state = _make_state(latest_run_id=run.id, comment_status="PENDING")
strategy = _make_strategy(run, state)
d = strategy.evaluate(run_id=run.id)
check("action == PROCEED", d.action == UpdateAction.PROCEED)
check("should_proceed is True", d.should_proceed)


# ─────────────────────────────────────────────────────────────
# Test 2: DEBOUNCE — next_allowed_delivery_at in the future
# ─────────────────────────────────────────────────────────────
print("\n[2] DEBOUNCE — cooldown window active")
run = _make_run()
future = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
state = _make_state(latest_run_id=run.id, next_allowed=future)
strategy = _make_strategy(run, state)
d = strategy.evaluate(run_id=run.id)
check("action == DEBOUNCE", d.action == UpdateAction.DEBOUNCE)
check("reschedule_in_seconds > 0", (d.reschedule_in_seconds or 0) > 0)
check("should_proceed is False", not d.should_proceed)


# ─────────────────────────────────────────────────────────────
# Test 3: SUPERSEDED — newer run pinned
# ─────────────────────────────────────────────────────────────
print("\n[3] SUPERSEDED — a newer run owns this PR")
older_run_id = uuid.uuid4()
newer_run_id = uuid.uuid4()
run = MagicMock()
run.id = older_run_id
run.pull_request = _make_pr()
run.repository_id = uuid.uuid4()
run.created_at = datetime.datetime.utcnow()
state = _make_state(latest_run_id=newer_run_id)

db = MagicMock()
db.query.return_value.filter.return_value.first.side_effect = [run, state]
strategy = PRCommentUpdateStrategy(db)
d = strategy.evaluate(run_id=older_run_id)
check("action == SUPERSEDED", d.action == UpdateAction.SUPERSEDED)
check("details contains latest_run_id", "latest_run_id" in d.details)


# ─────────────────────────────────────────────────────────────
# Test 4: SKIPPED_HASH — body hash unchanged, status=DELIVERED
# ─────────────────────────────────────────────────────────────
print("\n[4] SKIPPED_HASH — normalized body hash unchanged")
run = _make_run()
body_hash = hashlib.sha256(b"same body").hexdigest()
state = _make_state(
    latest_run_id=run.id,
    comment_status="DELIVERED",
    body_hash=body_hash,
)
strategy = _make_strategy(run, state)
d = strategy.evaluate(run_id=run.id, new_body_hash=body_hash)
check("action == SKIPPED_HASH", d.action == UpdateAction.SKIPPED_HASH)
check("should_proceed is False", not d.should_proceed)


# ─────────────────────────────────────────────────────────────
# Test 5: TTL_EXPIRED — run created > 24 h ago
# ─────────────────────────────────────────────────────────────
print("\n[5] TTL_EXPIRED — job older than 24 h")
old_created = datetime.datetime.utcnow() - datetime.timedelta(hours=DELIVERY_JOB_TTL_HOURS + 1)
run = _make_run(created_at=old_created)
state = _make_state(latest_run_id=run.id)
strategy = _make_strategy(run, state)
d = strategy.evaluate(run_id=run.id)
check("action == TTL_EXPIRED", d.action == UpdateAction.TTL_EXPIRED)
check("details.age_hours > 24", d.details.get("age_hours", 0) > 24)


# ─────────────────────────────────────────────────────────────
# Test 6: claim_delivery succeeds for correct run
# ─────────────────────────────────────────────────────────────
print("\n[6] claim_delivery — succeeds for correct run")
run = _make_run()
state = _make_state(latest_run_id=run.id)
db = MagicMock()
# scalar() returns the same run_id (optimistic lock passes)
db.query.return_value.filter.return_value.scalar.return_value = run.id
strategy = PRCommentUpdateStrategy(db)
result = strategy.claim_delivery(state, run_id=run.id)
check("returns True", result is True)
check("delivery_attempt_count incremented", state.delivery_attempt_count == 1)


# ─────────────────────────────────────────────────────────────
# Test 7: claim_delivery fails when another run has taken over
# ─────────────────────────────────────────────────────────────
print("\n[7] claim_delivery — race detected, returns False")
run_id = uuid.uuid4()
concurrent_run_id = uuid.uuid4()
state = _make_state(latest_run_id=run_id)
db = MagicMock()
# scalar() returns a *different* run_id — another worker raced
db.query.return_value.filter.return_value.scalar.return_value = concurrent_run_id
strategy = PRCommentUpdateStrategy(db)
result = strategy.claim_delivery(state, run_id=run_id)
check("returns False", result is False)


# ─────────────────────────────────────────────────────────────
# Test 8: coalesce_pending_runs creates state on first call
# ─────────────────────────────────────────────────────────────
print("\n[8] coalesce_pending_runs — creates new state")
repo_id = uuid.uuid4()
pr_id = uuid.uuid4()
run_id = uuid.uuid4()

db = MagicMock()
db.query.return_value.filter.return_value.first.return_value = None  # no existing state

added = []
db.add.side_effect = lambda obj: added.append(obj)

strategy = PRCommentUpdateStrategy(db)
created = strategy.coalesce_pending_runs(
    repository_id=repo_id,
    pull_request_id=pr_id,
    new_run_id=run_id,
)
check("returns False (new state created)", created is False)
check("db.add was called", len(added) == 1)
check("new state has correct run_id", added[0].latest_recommendation_run_id == run_id)
check("new state is PENDING", added[0].comment_status == "PENDING")


# ─────────────────────────────────────────────────────────────
# Test 9: coalesce_pending_runs updates existing state
# ─────────────────────────────────────────────────────────────
print("\n[9] coalesce_pending_runs — updates existing state (coalescing)")
existing_state = _make_state(latest_run_id=uuid.uuid4())  # old run
new_run_id = uuid.uuid4()

db = MagicMock()
db.query.return_value.filter.return_value.first.return_value = existing_state
strategy = PRCommentUpdateStrategy(db)
updated = strategy.coalesce_pending_runs(
    repository_id=uuid.uuid4(),
    pull_request_id=uuid.uuid4(),
    new_run_id=new_run_id,
)
check("returns True (existing updated)", updated is True)
check("state pinned to new run", existing_state.latest_recommendation_run_id == new_run_id)
check("status reset to PENDING", existing_state.comment_status == "PENDING")


# ─────────────────────────────────────────────────────────────
# Test 10: mark_delivered persists debounce and resets attempts
# ─────────────────────────────────────────────────────────────
print("\n[10] mark_delivered — debounce window set, attempt count reset")
state = _make_state()
state.delivery_attempt_count = 3
composite = "abc123"
norm_hash = "def456"

db = MagicMock()
strategy = PRCommentUpdateStrategy(db)
before = datetime.datetime.utcnow()
strategy.mark_delivered(
    state,
    composite_hash=composite,
    normalized_body_hash=norm_hash,
    github_comment_id=999,
    integrity_status="VALID",
)
check("status == DELIVERED", state.comment_status == "DELIVERED")
check("composite hash stored", state.latest_comment_hash == composite)
check("normalized body hash stored", state.latest_comment_body_hash == norm_hash)
check("delivery_attempt_count reset to 0", state.delivery_attempt_count == 0)
check("github_comment_id set", state.github_comment_id == 999)
check(
    "next_allowed_delivery_at is in the future",
    state.next_allowed_delivery_at > before,
)
check(
    "debounce window >= DEBOUNCE_INTERVAL_SECONDS",
    (state.next_allowed_delivery_at - before).total_seconds() >= DEBOUNCE_INTERVAL_SECONDS - 1,
)


# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
total = len(results)
passed = sum(results)
failed = total - passed
print(f"Results: {passed}/{total} passed" + (f"  ({failed} FAILED)" if failed else "  — all assertions passed"))
sys.exit(0 if failed == 0 else 1)
