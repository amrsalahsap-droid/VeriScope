"""
AC Readiness Lifecycle Verification Script (DB-direct mode)
============================================================
Bypasses auth entirely. Calls RecommendationReadinessService directly.
This is the most trustworthy trace possible.

PASS conditions (hard):
  - AC DB count > 0
  - acceptance_criteria in available_inputs (by key)
  - acceptance_criteria NOT in missing_inputs (by key)
  - score_after >= score_before + 10 (unless score_before >= 90)
  - refresh readiness matches post-save readiness
  - no signal key in both available and missing
"""
import sys
import uuid
import json
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.models.readiness import RecommendationReadinessAssessment
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor

# ── CONFIG ────────────────────────────────────────────────────────────────────
TARGET_REPO_NAME = "trustdesk"
TARGET_PR_TITLE  = "password"

AC_TEXT = (
    "1. Password must be at least 12 characters long\n"
    "2. Password must contain at least one uppercase letter\n"
    "3. Password must contain at least one special character\n"
    "4. Old password cannot match new password\n"
    "5. System shows inline validation feedback immediately"
)
BUSINESS_CHANGE = "Password validation rules updated to enforce stronger policies."
AFFECTED_USERS  = "All users on login and account settings screens"
RISK_NOTES      = "Existing passwords may not satisfy new rules."
TESTING_NOTES   = "Test on login flow and account settings."
# ─────────────────────────────────────────────────────────────────────────────

SEP = "=" * 70

def find_repo_and_pr(db):
    repos = db.query(Repository).filter(Repository.is_active == True).all()
    repo = next((r for r in repos if TARGET_REPO_NAME.lower() in (r.name or "").lower()), None)
    if not repo:
        repo = repos[0] if repos else None
        print(f"[WARN] Using first repo: {getattr(repo, 'name', None)}")
    assert repo, "FAIL: No repository found."

    prs = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).all()
    pr  = next((p for p in prs if TARGET_PR_TITLE.lower() in (p.title or "").lower()), None)
    if not pr:
        pr = prs[0] if prs else None
        print(f"[WARN] Using first PR: {getattr(pr, 'title', None)}")
    assert pr, f"FAIL: No pull request found in repo {repo.name}"
    return repo, pr


def get_readiness(db, repo_id: str, pr_id: str, label: str):
    svc = RecommendationReadinessService(db)
    a = svc.assess_readiness(repository_id=repo_id, pull_request_id=pr_id)
    avail_keys = [s.get("key") if isinstance(s, dict) else getattr(s, "key", s)
                  for s in (a.available_inputs or [])]
    miss_keys  = [s.get("key") if isinstance(s, dict) else getattr(s, "key", s)
                  for s in (a.missing_inputs  or [])]
    score_pct  = round(a.readiness_score * 100) if a.readiness_score <= 1.0 else round(a.readiness_score)
    ics        = getattr(a, "intelligence_completeness_score", 0)
    print(f"\n  [{label}]  readiness_score={a.readiness_score:.4f}  completeness={ics}")
    print(f"    available ({len(avail_keys)}): {sorted(avail_keys)}")
    print(f"    missing   ({len(miss_keys)}): {sorted(miss_keys)}")
    overlap = set(avail_keys) & set(miss_keys)
    if overlap:
        print(f"    [BUG] SIGNAL OVERLAP: {overlap}")
    else:
        print(f"    [OK] No signal key in both lists")
    return avail_keys, miss_keys, score_pct, a


def query_db_tables(db, pr_id, label: str) -> dict:
    print(f"\n[DB:{label}]  pull_request_id={pr_id}")
    ac_rows  = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr_id
    ).all()
    bio_rows = db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.pull_request_id == pr_id,
        BusinessIntentOverride.is_active == True
    ).all()
    snap_rows = db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.pull_request_id == pr_id
    ).order_by(RecommendationReadinessAssessment.created_at.desc()).limit(5).all()

    print(f"  acceptance_criteria rows: {len(ac_rows)}")
    for r in ac_rows[:5]:
        print(f"    id={r.id}  source={r.source}  repo_id={r.repository_id}  pr_id={r.pull_request_id}  text={r.text[:50]!r}")
    print(f"  business_intent_overrides (active): {len(bio_rows)}")
    for b in bio_rows[:3]:
        ac_snip = (b.acceptance_criteria or "")[:60]
        print(f"    id={b.id}  source={b.source}  ac_snippet={ac_snip!r}")
    print(f"  readiness_snapshots (last 5): {len(snap_rows)}")
    for s in snap_rows:
        print(f"    score={s.readiness_score:.4f}  ac_in_avail={'acceptance_criteria' in (s.available_signals or [])}  created_at={s.created_at}")
    return {"ac": ac_rows, "bio": bio_rows, "snaps": snap_rows}


def save_ac_manually(db, repo_id, pr_id):
    """Replicate exactly what the manual AC endpoint does."""
    import uuid as _uuid
    from datetime import datetime as _dt

    # 1. Invalidate readiness cache
    db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.pull_request_id == pr_id
    ).delete(synchronize_session=False)
    db.flush()

    # 2. Delete old manual ACs for this PR
    old_acs = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr_id,
        AcceptanceCriterion.source == "MANUAL_USER_INPUT"
    ).all()
    old_ids = [ac.id for ac in old_acs]
    if old_ids:
        db.query(BusinessBehaviorMapping).filter(
            BusinessBehaviorMapping.acceptance_criterion_id.in_(old_ids)
        ).delete(synchronize_session=False)
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.id.in_(old_ids)
        ).delete(synchronize_session=False)
        db.flush()
    print(f"  [SAVE] Removed {len(old_ids)} old MANUAL_USER_INPUT AC rows")

    # 3. Deactivate existing BIOs
    db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.pull_request_id == pr_id,
        BusinessIntentOverride.is_active == True
    ).update({"is_active": False})

    # 4. Create BIO
    bio = BusinessIntentOverride(
        id=_uuid.uuid4(),
        repository_id=repo_id,
        pull_request_id=pr_id,
        business_change_summary=BUSINESS_CHANGE,
        affected_users_journeys=AFFECTED_USERS,
        risk_notes=RISK_NOTES,
        testing_notes=TESTING_NOTES,
        acceptance_criteria=AC_TEXT,
        source="MANUAL_USER_INPUT",
        is_active=True,
        is_processed=True,
        created_at=_dt.utcnow(),
        updated_at=_dt.utcnow()
    )
    db.add(bio)
    db.flush()
    print(f"  [SAVE] Created BusinessIntentOverride id={bio.id}")

    # 5. Extract and persist AcceptanceCriterion rows
    extractor = AcceptanceCriteriaExtractor(db=db)
    criteria = extractor._extract_criteria_from_text(AC_TEXT, "MANUAL_USER_INPUT")
    if not criteria:
        raw_lines = AC_TEXT.split("\n")
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            clean_text = re.sub(r"^(\s*[-*\d\.]+\s+)", "", line)
            if clean_text:
                criteria.append({
                    "text": clean_text,
                    "source": "MANUAL_USER_INPUT",
                    "confidence": 1.0,
                    "evidence_excerpt": line
                })
    criteria = extractor._normalize_and_deduplicate(criteria)
    for c in criteria:
        c["criterion_type"] = extractor._classify_criterion_type(c["text"])

    persisted = []
    if criteria:
        persisted = extractor.persist_criteria(criteria, str(repo_id), str(pr_id), db)
    print(f"  [SAVE] Persisted {len(persisted)} AcceptanceCriterion rows")

    # 6. Commit
    db.commit()
    print(f"  [SAVE] COMMITTED")
    return persisted


def run():
    print(SEP)
    print("AC READINESS LIFECYCLE — DB-DIRECT VERIFICATION")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(SEP)

    db1 = SessionLocal()
    repo, pr = find_repo_and_pr(db1)
    repo_id = str(repo.id)
    pr_id   = str(pr.id)
    print(f"\n[TARGET] repo={repo.name!r} ({repo_id})")
    print(f"[TARGET] pr={pr.title!r} ({pr_id})")

    # ── Step 1: Readiness BEFORE ─────────────────────────────────────────────
    print(f"\n{SEP}")
    print("STEP 1 — READINESS BEFORE AC")
    avail_before, miss_before, score_before, _ = get_readiness(db1, repo_id, pr_id, "BEFORE")

    # ── Step 2: DB state BEFORE ──────────────────────────────────────────────
    print(f"\n{SEP}")
    print("STEP 2 — DB STATE BEFORE")
    db_before = query_db_tables(db1, pr.id, "BEFORE")
    db1.close()

    # ── Step 3: Submit AC (replicating the endpoint logic exactly) ───────────
    print(f"\n{SEP}")
    print("STEP 3 — SUBMITTING AC")
    db2 = SessionLocal()
    persisted = save_ac_manually(db2, repo_id, pr.id)
    db2.close()

    # ── Step 4: DB state AFTER (fresh session, no cache) ─────────────────────
    print(f"\n{SEP}")
    print("STEP 4 — DB STATE AFTER")
    db3 = SessionLocal()
    db_after = query_db_tables(db3, pr.id, "AFTER")

    # ── Step 5: Readiness AFTER (same fresh session, assessing from DB) ──────
    print(f"\n{SEP}")
    print("STEP 5 — READINESS AFTER AC (fresh session)")
    avail_after, miss_after, score_after, assess_after = get_readiness(db3, repo_id, pr_id, "AFTER")
    db3.close()

    # ── Step 6: Simulate page refresh (brand new session) ────────────────────
    print(f"\n{SEP}")
    print("STEP 6 — SIMULATED PAGE REFRESH (new session)")
    db4 = SessionLocal()
    avail_refresh, miss_refresh, score_refresh, _ = get_readiness(db4, repo_id, pr_id, "REFRESH")
    db4.close()

    # ── Step 7: Pass/Fail Report ──────────────────────────────────────────────
    print(f"\n{SEP}")
    print("PASS / FAIL REPORT")
    print(SEP)

    failures = []
    def check(name: str, cond: bool, detail: str = ""):
        if cond:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}   >> {detail}")
            failures.append(name)

    ac_rows = db_after["ac"]
    bio_rows = db_after["bio"]

    # DB checks
    check("AC DB count > 0", len(ac_rows) > 0,
          f"Found {len(ac_rows)} rows in acceptance_criteria")
    check("BIO created", len(bio_rows) > 0,
          f"Found {len(bio_rows)} rows in business_intent_overrides (active)")
    check("AC rows have correct pull_request_id",
          all(str(r.pull_request_id) == pr_id for r in ac_rows),
          f"PR IDs: {[str(r.pull_request_id) for r in ac_rows]}")
    check("AC rows have correct repository_id",
          all(str(r.repository_id) == repo_id for r in ac_rows),
          f"Repo IDs: {[str(r.repository_id) for r in ac_rows]}")
    check("AC rows have source=MANUAL_USER_INPUT",
          all(r.source == "MANUAL_USER_INPUT" for r in ac_rows),
          f"sources: {[r.source for r in ac_rows]}")
    check("AC rows have non-empty text",
          all(r.text and len(r.text.strip()) > 5 for r in ac_rows),
          f"texts: {[r.text[:30] for r in ac_rows]}")
    check("AC rows have normalized_key",
          all(r.normalized_key for r in ac_rows),
          f"keys: {[r.normalized_key[:20] for r in ac_rows]}")

    # Signal availability checks (AFTER)
    check("acceptance_criteria in available_inputs (AFTER)",
          "acceptance_criteria" in avail_after,
          f"available_inputs: {sorted(avail_after)}")
    check("acceptance_criteria NOT in missing_inputs (AFTER)",
          "acceptance_criteria" not in miss_after,
          f"missing_inputs: {sorted(miss_after)}")
    check("business_intent in available_inputs (AFTER)",
          "business_intent" in avail_after,
          f"available_inputs: {sorted(avail_after)}")
    check("business_intent NOT in missing_inputs (AFTER)",
          "business_intent" not in miss_after,
          f"missing_inputs: {sorted(miss_after)}")

    # Score check
    score_delta = score_after - score_before
    check(f"score increased by ≥ 10 (before={score_before}, after={score_after}, delta={score_delta})",
          score_before >= 90 or score_delta >= 10,
          "Expected +10 from acceptance_criteria signal weight")

    # Refresh stability
    check("acceptance_criteria in available_inputs (REFRESH)",
          "acceptance_criteria" in avail_refresh,
          f"available_inputs: {sorted(avail_refresh)}")
    check("score stable after refresh",
          abs(score_refresh - score_after) <= 2,
          f"after={score_after}, refresh={score_refresh}")

    # No overlap
    check("No signal overlap AFTER",
          len(set(avail_after) & set(miss_after)) == 0,
          f"Overlap: {set(avail_after) & set(miss_after)}")
    check("No signal overlap REFRESH",
          len(set(avail_refresh) & set(miss_refresh)) == 0,
          f"Overlap: {set(avail_refresh) & set(miss_refresh)}")

    print(f"\n{SEP}")
    if not failures:
        print("ALL CHECKS PASSED ✓")
    else:
        print(f"FAILED: {len(failures)} check(s):")
        for f in failures:
            print(f"  ✗  {f}")
    print(SEP)
    return len(failures) == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
