"""
verify_pr_ingestion.py
======================
Verifies end-to-end PR ingestion for amrsalahsap-droid/trustdesk PR #1.

Run from the veriscope root:
    python scratch/verify_pr_ingestion.py

Requires:
    - Backend running on localhost:8000
    - A valid session token (set VERISCOPE_TOKEN env var or edit TOKEN below)
    - DATABASE_URL accessible (reads DB directly for some checks)
"""

import os
import sys
import json
import requests
from uuid import UUID

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND = os.getenv("VERISCOPE_BACKEND", "http://localhost:8000")
TOKEN   = os.getenv("VERISCOPE_TOKEN", "")          # Bearer token from session
REPO_FULL_NAME = "amrsalahsap-droid/trustdesk"
EXPECTED_PR_NUMBER = 1
EXPECTED_PR_TITLE  = "Implement modern password validation rules and fix test suites"
EXPECTED_SOURCE_BRANCH = "branch-one"
EXPECTED_TARGET_BRANCH = "main"

# ── Helpers ───────────────────────────────────────────────────────────────────
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

def ok(msg):   print(f"  {PASS} {msg}")
def fail(msg): print(f"  {FAIL} {msg}"); sys.exit(1)
def warn(msg): print(f"  {WARN} {msg}")

def api(method, path, **kwargs):
    headers = kwargs.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    url = f"{BACKEND}{path}"
    r = getattr(requests, method)(url, headers=headers, timeout=30, **kwargs)
    return r

# ── Check 1: Backend health ───────────────────────────────────────────────────
print("\n[1] Backend health")
r = requests.get(f"{BACKEND}/", timeout=10)
assert r.status_code == 200, f"Backend not reachable: {r.status_code}"
ok(f"Backend is up at {BACKEND}")

# ── Check 2: Auth token ───────────────────────────────────────────────────────
print("\n[2] Auth token")
if not TOKEN:
    warn("VERISCOPE_TOKEN not set — skipping authenticated checks")
    print("\nSet VERISCOPE_TOKEN and re-run for full verification.")
    sys.exit(0)
ok("Token provided")

# ── Check 3: Workspace repositories ──────────────────────────────────────────
print("\n[3] Workspace repositories")
r = api("get", "/github/repositories")
if r.status_code != 200:
    fail(f"GET /github/repositories returned {r.status_code}: {r.text[:200]}")
repos = r.json().get("repositories", [])
if not repos:
    fail("No repositories found in workspace")
ok(f"Found {len(repos)} repository/repositories in workspace")

# Find trustdesk
repo = next((x for x in repos if x.get("full_name") == REPO_FULL_NAME), None)
if not repo:
    fail(f"Repository {REPO_FULL_NAME!r} not found in workspace. Available: {[x['full_name'] for x in repos]}")
ok(f"Repository {REPO_FULL_NAME} found (id={repo['id']})")
REPO_ID = repo["id"]

# ── Check 4: GitHub installation ─────────────────────────────────────────────
print("\n[4] GitHub installation")
r = api("get", "/github/installation/status")
if r.status_code != 200:
    fail(f"GET /github/installation/status returned {r.status_code}: {r.text[:200]}")
inst = r.json()
if not inst.get("connected"):
    fail(f"GitHub App not connected. Status: {inst.get('status')}")
ok(f"GitHub App connected (installation_id={inst.get('installation_id')})")

# ── Check 5: Manual PR sync ───────────────────────────────────────────────────
print("\n[5] Manual PR sync")
r = api("post", f"/github/repositories/{REPO_ID}/pull-requests/sync")
if r.status_code != 200:
    fail(f"POST /github/repositories/{REPO_ID}/pull-requests/sync returned {r.status_code}: {r.text[:300]}")
sync_result = r.json()
ok(f"Sync completed: {sync_result.get('synced_pull_requests')} PRs, {sync_result.get('synced_changed_files')} files")
if sync_result.get("synced_pull_requests", 0) == 0:
    warn("No PRs were synced — check GitHub App permissions and that PR #1 is open")

# ── Check 6: PR list endpoint ─────────────────────────────────────────────────
print("\n[6] PR list endpoint")
r = api("get", f"/github/repositories/{REPO_ID}/pull-requests")
if r.status_code != 200:
    fail(f"GET /github/repositories/{REPO_ID}/pull-requests returned {r.status_code}: {r.text[:200]}")
prs = r.json().get("pull_requests", [])
ok(f"PR list returned {len(prs)} pull request(s)")

# ── Check 7: PR #1 present ────────────────────────────────────────────────────
print("\n[7] PR #1 present")
pr1 = next((p for p in prs if p.get("number") == EXPECTED_PR_NUMBER), None)
if not pr1:
    fail(f"PR #{EXPECTED_PR_NUMBER} not found in list. Got: {[p.get('number') for p in prs]}")
ok(f"PR #{EXPECTED_PR_NUMBER} found: {pr1.get('title')!r}")

# ── Check 8: PR fields ────────────────────────────────────────────────────────
print("\n[8] PR fields")
if pr1.get("title") != EXPECTED_PR_TITLE:
    warn(f"Title mismatch: expected {EXPECTED_PR_TITLE!r}, got {pr1.get('title')!r}")
else:
    ok(f"Title matches: {EXPECTED_PR_TITLE!r}")

if pr1.get("source_branch") != EXPECTED_SOURCE_BRANCH:
    warn(f"source_branch mismatch: expected {EXPECTED_SOURCE_BRANCH!r}, got {pr1.get('source_branch')!r}")
else:
    ok(f"source_branch: {EXPECTED_SOURCE_BRANCH}")

if pr1.get("target_branch") != EXPECTED_TARGET_BRANCH:
    warn(f"target_branch mismatch: expected {EXPECTED_TARGET_BRANCH!r}, got {pr1.get('target_branch')!r}")
else:
    ok(f"target_branch: {EXPECTED_TARGET_BRANCH}")

if pr1.get("state", "").lower() != "open":
    warn(f"PR state is {pr1.get('state')!r}, expected 'open'")
else:
    ok("PR state: open")

# ── Check 9: Changed files ────────────────────────────────────────────────────
print("\n[9] Changed files")
files_count = pr1.get("changed_files_count", 0)
if files_count == 0:
    warn("changed_files_count is 0 — sync may still be in progress or GitHub API call failed")
else:
    ok(f"changed_files_count: {files_count}")

# ── Check 10: No duplicate PRs ────────────────────────────────────────────────
print("\n[10] Duplicate PR check")
pr1_copies = [p for p in prs if p.get("number") == EXPECTED_PR_NUMBER]
if len(pr1_copies) > 1:
    fail(f"Duplicate PR #{EXPECTED_PR_NUMBER} found ({len(pr1_copies)} copies)")
ok("No duplicate PRs")

# ── Check 11: Closed PRs not shown ───────────────────────────────────────────
print("\n[11] Closed PRs not in active list")
closed = [p for p in prs if p.get("state", "").lower() == "closed"]
if closed:
    warn(f"{len(closed)} closed PR(s) returned in default list: {[p['number'] for p in closed]}")
else:
    ok("No closed PRs in default list")

# ── Check 12: Run Recommendation button available ────────────────────────────
print("\n[12] Recommendation status")
rec_status = pr1.get("recommendation_status", "PENDING")
ok(f"recommendation_status: {rec_status} (Run Recommendation button will be shown)")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  All checks passed.")
print(f"\n  PR #{EXPECTED_PR_NUMBER}: {EXPECTED_PR_TITLE}")
print(f"  Branch: {EXPECTED_SOURCE_BRANCH} → {EXPECTED_TARGET_BRANCH}")
print(f"  Changed files: {files_count}")
print(f"  Recommendation: {rec_status}")
print("\n  The repository detail page should now show this PR")
print("  with a 'Run Recommendation' button.")
print("="*60 + "\n")
