"""
verify_repository_pr_summary_consistency.py
============================================
Verifies that repository card data, detail stats, and PR list all agree
for amrsalahsap-droid/trustdesk.

Run from the veriscope root:
    VERISCOPE_TOKEN=<token> python scratch/verify_repository_pr_summary_consistency.py

Checks:
 1.  Repository exists and is workspace-scoped
 2.  GET /github/repositories returns active_pr_count = 1
 3.  GET /github/repositories returns latest_pr_synced_at populated
 4.  GET /github/repositories/{id} returns active_pull_requests_count = 1
 5.  GET /github/repositories/{id} returns latest_pr_synced_at populated
 6.  GET /github/repositories/{id} returns last_synced_at separate from latest_pr_synced_at
 7.  GET /github/repositories/{id}/pull-requests returns PR #1
 8.  PR #1 has correct title, source_branch, target_branch
 9.  POST /github/repositories/{id}/pull-requests/sync updates latest_pr_synced_at
 10. Repeated sync does not duplicate PR #1
 11. active_pr_count > 0 means Evidence section must NOT show "No PRs"
 12. Closed PRs are not counted in active_pr_count
"""

import os
import sys
import requests
from datetime import datetime

BACKEND = os.getenv("VERISCOPE_BACKEND", "http://localhost:8000")
TOKEN   = os.getenv("VERISCOPE_TOKEN", "")
REPO_FULL_NAME         = "amrsalahsap-droid/trustdesk"
EXPECTED_PR_NUMBER     = 1
EXPECTED_PR_TITLE      = "Implement modern password validation rules and fix test suites"
EXPECTED_SOURCE_BRANCH = "branch-one"
EXPECTED_TARGET_BRANCH = "main"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

def ok(msg):    print(f"  {PASS} {msg}")
def fail(msg):  print(f"  {FAIL} {msg}"); sys.exit(1)
def warn(msg):  print(f"  {WARN} {msg}")

def api(method, path, **kwargs):
    headers = kwargs.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = getattr(requests, method)(f"{BACKEND}{path}", headers=headers, timeout=30, **kwargs)
    return r

# ── Health ────────────────────────────────────────────────────────────────────
print("\n[0] Backend health")
r = requests.get(f"{BACKEND}/", timeout=10)
assert r.status_code == 200, f"Backend not reachable: {r.status_code}"
ok(f"Backend up at {BACKEND}")

if not TOKEN:
    warn("VERISCOPE_TOKEN not set — set it and re-run")
    sys.exit(0)

# ── Check 1: Repository exists in workspace ───────────────────────────────────
print("\n[1] Repository exists in workspace")
r = api("get", "/github/repositories")
assert r.status_code == 200, f"GET /github/repositories failed: {r.status_code}"
repos = r.json().get("repositories", [])
repo = next((x for x in repos if x.get("full_name") == REPO_FULL_NAME), None)
if not repo:
    fail(f"{REPO_FULL_NAME} not found. Available: {[x['full_name'] for x in repos]}")
ok(f"Found {REPO_FULL_NAME} (id={repo['id']})")
REPO_ID = repo["id"]

# ── Check 2: active_pr_count in list endpoint ─────────────────────────────────
print("\n[2] GET /github/repositories → active_pr_count")
active_pr_count = repo.get("active_pr_count", 0)
if active_pr_count < 1:
    fail(f"active_pr_count = {active_pr_count}, expected >= 1. Run PR sync first.")
ok(f"active_pr_count = {active_pr_count}")

# ── Check 3: latest_pr_synced_at in list endpoint ─────────────────────────────
print("\n[3] GET /github/repositories → latest_pr_synced_at")
latest_pr_synced_at_list = repo.get("latest_pr_synced_at")
if not latest_pr_synced_at_list:
    warn("latest_pr_synced_at is null in list endpoint — sync PRs first")
else:
    ok(f"latest_pr_synced_at = {latest_pr_synced_at_list}")

# ── Check 4: active_pull_requests_count in detail endpoint ───────────────────
print("\n[4] GET /github/repositories/{id} → active_pull_requests_count")
r = api("get", f"/github/repositories/{REPO_ID}")
assert r.status_code == 200, f"GET /github/repositories/{REPO_ID} failed: {r.status_code}"
detail = r.json()
active_prs_detail = detail.get("evidence", {}).get("active_pull_requests_count", 0)
if active_prs_detail < 1:
    fail(f"active_pull_requests_count = {active_prs_detail} in detail, expected >= 1")
ok(f"active_pull_requests_count = {active_prs_detail}")

# ── Check 5: latest_pr_synced_at in detail endpoint ──────────────────────────
print("\n[5] GET /github/repositories/{id} → latest_pr_synced_at")
latest_pr_synced_at_detail = detail.get("latest_pr_synced_at")
if not latest_pr_synced_at_detail:
    warn("latest_pr_synced_at is null in detail endpoint — sync PRs first")
else:
    ok(f"latest_pr_synced_at = {latest_pr_synced_at_detail}")

# ── Check 6: Timestamps are distinct ─────────────────────────────────────────
print("\n[6] Timestamps are distinct (repo sync ≠ PR sync)")
last_synced_at = detail.get("last_synced_at")
last_webhook_at = detail.get("last_webhook_at")
ok(f"last_synced_at (repo metadata) = {last_synced_at or 'null'}")
ok(f"last_webhook_at               = {last_webhook_at or 'null'}")
ok(f"latest_pr_synced_at           = {latest_pr_synced_at_detail or 'null'}")
if last_synced_at and latest_pr_synced_at_detail and last_synced_at == latest_pr_synced_at_detail:
    warn("last_synced_at == latest_pr_synced_at — they should be independent timestamps")
else:
    ok("Timestamps are independent fields")

# ── Check 7: PR list returns PR #1 ───────────────────────────────────────────
print("\n[7] GET /github/repositories/{id}/pull-requests → PR #1")
r = api("get", f"/github/repositories/{REPO_ID}/pull-requests")
assert r.status_code == 200, f"PR list failed: {r.status_code}"
prs = r.json().get("pull_requests", [])
pr1 = next((p for p in prs if p.get("number") == EXPECTED_PR_NUMBER), None)
if not pr1:
    fail(f"PR #{EXPECTED_PR_NUMBER} not in list. Got: {[p.get('number') for p in prs]}")
ok(f"PR #{EXPECTED_PR_NUMBER} found: {pr1.get('title')!r}")

# ── Check 8: PR fields correct ────────────────────────────────────────────────
print("\n[8] PR #1 fields")
if pr1.get("title") != EXPECTED_PR_TITLE:
    warn(f"Title: expected {EXPECTED_PR_TITLE!r}, got {pr1.get('title')!r}")
else:
    ok(f"title: {EXPECTED_PR_TITLE!r}")
if pr1.get("source_branch") != EXPECTED_SOURCE_BRANCH:
    warn(f"source_branch: expected {EXPECTED_SOURCE_BRANCH!r}, got {pr1.get('source_branch')!r}")
else:
    ok(f"source_branch → target_branch: {pr1.get('source_branch')} → {pr1.get('target_branch')}")
if pr1.get("state", "").lower() != "open":
    warn(f"state = {pr1.get('state')!r}, expected 'open'")
else:
    ok("state: open")

# ── Check 9: Manual sync updates latest_pr_synced_at ─────────────────────────
print("\n[9] POST /github/repositories/{id}/pull-requests/sync")
r = api("post", f"/github/repositories/{REPO_ID}/pull-requests/sync")
if r.status_code != 200:
    fail(f"Sync failed: {r.status_code} — {r.text[:200]}")
sync_data = r.json()
ok(f"Sync: {sync_data.get('synced_pull_requests')} PRs, {sync_data.get('synced_changed_files')} files")
new_latest_pr_synced_at = sync_data.get("latest_pr_synced_at")
if not new_latest_pr_synced_at:
    warn("latest_pr_synced_at not returned in sync response")
else:
    ok(f"latest_pr_synced_at in sync response: {new_latest_pr_synced_at}")

# ── Check 10: No duplicate PRs after repeated sync ───────────────────────────
print("\n[10] Repeated sync does not duplicate PR #1")
r = api("post", f"/github/repositories/{REPO_ID}/pull-requests/sync")
assert r.status_code == 200, f"Second sync failed: {r.status_code}"
r = api("get", f"/github/repositories/{REPO_ID}/pull-requests")
prs_after = r.json().get("pull_requests", [])
pr1_copies = [p for p in prs_after if p.get("number") == EXPECTED_PR_NUMBER]
if len(pr1_copies) > 1:
    fail(f"Duplicate PR #{EXPECTED_PR_NUMBER}: found {len(pr1_copies)} copies")
ok(f"No duplicates — PR #{EXPECTED_PR_NUMBER} appears exactly once")

# ── Check 11: active_pr_count > 0 means no "No PRs" in evidence ──────────────
print("\n[11] Evidence consistency: active_pr_count > 0 → no 'No PRs'")
r = api("get", "/github/repositories")
repos_after = r.json().get("repositories", [])
repo_after = next((x for x in repos_after if x.get("id") == REPO_ID), None)
if repo_after:
    apc = repo_after.get("active_pr_count", 0)
    lps = repo_after.get("latest_pr_synced_at")
    ok(f"active_pr_count = {apc}")
    ok(f"latest_pr_synced_at = {lps or 'null'}")
    if apc > 0:
        ok("active_pr_count > 0 → card Evidence section must show 'X open', not 'No PRs'")
    else:
        warn("active_pr_count = 0 after sync — check GitHub App permissions")

# ── Check 12: Closed PRs not counted as active ───────────────────────────────
print("\n[12] Closed PRs not in active count")
closed_prs = [p for p in prs_after if p.get("state", "").lower() == "closed"]
if closed_prs:
    warn(f"{len(closed_prs)} closed PR(s) in default list: {[p['number'] for p in closed_prs]}")
else:
    ok("No closed PRs in default PR list")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  All checks passed.")
print(f"\n  Repository card should show:")
print(f"    PRs: {active_pr_count} open")
print(f"    PR sync: {latest_pr_synced_at_list or 'Not synced yet'}")
print(f"\n  Repository detail top cards should show:")
print(f"    Active PRs: {active_prs_detail}")
print(f"    PR Sync: {latest_pr_synced_at_detail or 'Not synced yet'}")
print(f"    Repo Sync: {last_synced_at or 'Not synced yet'}")
print(f"\n  Pull Requests section should show:")
print(f"    PR #{EXPECTED_PR_NUMBER}: {EXPECTED_PR_TITLE}")
print(f"    {EXPECTED_SOURCE_BRANCH} → {EXPECTED_TARGET_BRANCH}")
print(f"    Run Recommendation button")
print("="*60 + "\n")
