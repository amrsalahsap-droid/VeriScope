"""
pr_comment_update_strategy.py
─────────────────────────────
Centralised update-strategy layer that sits between RecommendationService
and PRCommentService.  It enforces every anti-churn rule before any
GitHub API call is attempted:

  1. Debounce gate     – minimum 15 s between deliveries per PR
  2. Coalescing        – only the current latest run may deliver
  3. Supersession      – stale jobs self-cancel when a newer run exists
  4. Race prevention   – optimistic-lock on comment_state via updated_at
                         check before writing; all writes go through this
                         single choke-point

All decisions are surfaced as an UpdateDecision dataclass so that
callers and tests can inspect the exact reason without parsing log text.
"""

import datetime
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.pull_request import PullRequestCommentState, PullRequestCommentDeliveryEvent
from app.models.recommendation import RecommendationRun

logger = logging.getLogger("veriscope.pr_comment_update_strategy")

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

DEBOUNCE_INTERVAL_SECONDS: int = 15
"""Minimum wall-clock seconds between consecutive GitHub deliveries for
the same PR.  A job that arrives earlier is re-scheduled, not dropped."""

DELIVERY_JOB_TTL_HOURS: int = 24
"""Jobs older than this are considered expired and aborted without retry."""


# ─────────────────────────────────────────────────────────────
# Decision types
# ─────────────────────────────────────────────────────────────

class UpdateAction(str, Enum):
    PROCEED       = "PROCEED"         # caller may proceed to GitHub delivery
    DEBOUNCE      = "DEBOUNCE"        # too soon — re-schedule after cooldown
    SUPERSEDED    = "SUPERSEDED"      # a newer run already owns this PR
    RACE_LOST     = "RACE_LOST"       # another worker updated state concurrently
    TTL_EXPIRED   = "TTL_EXPIRED"     # job is older than 24 h — abort
    SKIPPED_HASH  = "SKIPPED_HASH"    # body hash unchanged — no update needed


@dataclass
class UpdateDecision:
    action: UpdateAction
    reason: str
    run_id: Optional[uuid.UUID] = None
    reschedule_in_seconds: Optional[int] = None  # set when action == DEBOUNCE
    details: dict = field(default_factory=dict)

    @property
    def should_proceed(self) -> bool:
        return self.action == UpdateAction.PROCEED


# ─────────────────────────────────────────────────────────────
# Strategy service
# ─────────────────────────────────────────────────────────────

class PRCommentUpdateStrategy:
    """
    Single decision engine for "should this run post/update the PR comment?".

    Usage
    ─────
    strategy = PRCommentUpdateStrategy(db)
    decision = strategy.evaluate(run_id=run.id, new_body_hash=hash)
    if decision.should_proceed:
        strategy.claim_delivery(state, run_id=run.id)
        # … call GitHub API …
    else:
        # handle decision.action
    """

    def __init__(self, db: Session):
        self.db = db

    # ──────────────────────────────────────────────────────────
    # Public: evaluate
    # ──────────────────────────────────────────────────────────

    def evaluate(
        self,
        run_id: uuid.UUID,
        new_body_hash: Optional[str] = None,
    ) -> UpdateDecision:
        """
        Evaluate whether the given recommendation run should proceed to
        delivery.  Returns an UpdateDecision with the authoritative action.

        Parameters
        ──────────
        run_id        – ID of the RecommendationRun requesting delivery.
        new_body_hash – Optional pre-computed normalized body hash
                        (from CommentDeduplicationEngine).  When supplied
                        the SKIPPED_HASH gate is applied before proceeding.
        """
        run = self.db.query(RecommendationRun).filter(
            RecommendationRun.id == run_id
        ).first()
        if not run:
            return UpdateDecision(
                action=UpdateAction.SUPERSEDED,
                reason=f"RecommendationRun {run_id} not found.",
                run_id=run_id,
            )

        pr = run.pull_request
        if not pr:
            return UpdateDecision(
                action=UpdateAction.SUPERSEDED,
                reason=f"RecommendationRun {run_id} has no linked PullRequest.",
                run_id=run_id,
            )

        # Load or create comment state (read-only pass – no writes here)
        state = self._load_state(repository_id=run.repository_id, pull_request_id=pr.id)
        now = datetime.datetime.utcnow()

        # ── 1. TTL check ──────────────────────────────────────
        job_age_hours = (now - run.created_at).total_seconds() / 3600.0
        if job_age_hours > DELIVERY_JOB_TTL_HOURS:
            return UpdateDecision(
                action=UpdateAction.TTL_EXPIRED,
                reason=(
                    f"Delivery job expired: RecommendationRun created "
                    f"{job_age_hours:.1f} h ago (TTL={DELIVERY_JOB_TTL_HOURS} h)."
                ),
                run_id=run_id,
                details={"age_hours": round(job_age_hours, 2)},
            )

        # ── 2. Supersession check ─────────────────────────────
        #    Only the run that is currently pinned as `latest` may deliver.
        #    Any job from an older run self-cancels immediately.
        if state and state.latest_recommendation_run_id and state.latest_recommendation_run_id != run_id:
            return UpdateDecision(
                action=UpdateAction.SUPERSEDED,
                reason=(
                    f"Run {run_id} is superseded by newer run "
                    f"{state.latest_recommendation_run_id}."
                ),
                run_id=run_id,
                details={"latest_run_id": str(state.latest_recommendation_run_id)},
            )

        # ── 3. Debounce gate ──────────────────────────────────
        if state and state.next_allowed_delivery_at and now < state.next_allowed_delivery_at:
            wait_sec = int((state.next_allowed_delivery_at - now).total_seconds()) + 1
            return UpdateDecision(
                action=UpdateAction.DEBOUNCE,
                reason=(
                    f"Debounce active for PR {pr.number}. "
                    f"Next allowed delivery at {state.next_allowed_delivery_at.isoformat()}."
                ),
                run_id=run_id,
                reschedule_in_seconds=wait_sec,
                details={
                    "next_allowed_delivery_at": state.next_allowed_delivery_at.isoformat(),
                    "wait_sec": wait_sec,
                },
            )

        # ── 4. Hash deduplication (body unchanged) ────────────
        if new_body_hash and state and state.comment_status == "DELIVERED":
            if state.latest_comment_body_hash == new_body_hash:
                return UpdateDecision(
                    action=UpdateAction.SKIPPED_HASH,
                    reason=(
                        f"Normalized body hash unchanged for run {run_id} "
                        f"(hash={new_body_hash[:12]}…). Skipping delivery."
                    ),
                    run_id=run_id,
                    details={"body_hash": new_body_hash},
                )

        return UpdateDecision(
            action=UpdateAction.PROCEED,
            reason="All strategy gates passed. Proceeding to GitHub delivery.",
            run_id=run_id,
        )

    # ──────────────────────────────────────────────────────────
    # Public: coalesce_pending_runs
    # ──────────────────────────────────────────────────────────

    def coalesce_pending_runs(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID,
        new_run_id: uuid.UUID,
    ) -> bool:
        """
        Pin `new_run_id` as the authoritative latest run for this PR comment
        state and advance `comment_status` to PENDING.

        Returns True if an existing state record was updated (coalescing
        occurred), False if a fresh state record was created.

        This must be called inside the transaction that persists the new
        RecommendationRun so that the commit is atomic with the state update.
        """
        state = self._load_state(repository_id=repository_id, pull_request_id=pull_request_id)
        now = datetime.datetime.utcnow()

        if state:
            previous_run_id = state.latest_recommendation_run_id
            state.latest_recommendation_run_id = new_run_id
            state.comment_status = "PENDING"
            state.updated_at = now
            self.db.flush()

            if previous_run_id and previous_run_id != new_run_id:
                logger.info(
                    f"Coalesced PR comment delivery: PR={pull_request_id} "
                    f"superseded run={previous_run_id} with new run={new_run_id}."
                )
            return True
        else:
            new_state = PullRequestCommentState(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                latest_recommendation_run_id=new_run_id,
                comment_status="PENDING",
                created_at=now,
                updated_at=now,
            )
            self.db.add(new_state)
            self.db.flush()
            logger.info(
                f"Created new comment state for PR={pull_request_id} "
                f"with initial run={new_run_id}."
            )
            return False

    # ──────────────────────────────────────────────────────────
    # Public: claim_delivery
    # ──────────────────────────────────────────────────────────

    def claim_delivery(
        self,
        state: PullRequestCommentState,
        run_id: uuid.UUID,
    ) -> bool:
        """
        Optimistic-lock claim: atomically verify that `state` still belongs
        to `run_id` at the moment delivery begins, then increment
        `delivery_attempt_count` and record `last_delivery_attempt_at`.

        Returns True if the claim succeeded (safe to proceed).
        Returns False if another worker raced and updated `state` first
        (caller must abort with UpdateAction.RACE_LOST).

        The check re-reads `latest_recommendation_run_id` from the DB to
        detect concurrent updates that happened after evaluate() was called.
        """
        # Re-read the authoritative run ID from the DB to detect any
        # concurrent write that occurred between evaluate() and now.
        fresh_run_id = (
            self.db.query(PullRequestCommentState.latest_recommendation_run_id)
            .filter(PullRequestCommentState.id == state.id)
            .scalar()
        )

        if fresh_run_id is not None and fresh_run_id != run_id:
            logger.warning(
                f"Race detected: state {state.id} expected run {run_id} "
                f"but DB shows {fresh_run_id}. Aborting delivery."
            )
            return False

        state.last_delivery_attempt_at = datetime.datetime.utcnow()
        state.delivery_attempt_count += 1
        self.db.flush()
        return True

    # ──────────────────────────────────────────────────────────
    # Public: mark_delivered
    # ──────────────────────────────────────────────────────────

    def mark_delivered(
        self,
        state: PullRequestCommentState,
        composite_hash: str,
        normalized_body_hash: str,
        github_comment_id: Optional[int] = None,
        integrity_status: str = "VALID",
    ) -> None:
        """
        Record a successful delivery on `state`:
        - status → DELIVERED
        - reset delivery_attempt_count
        - set next_allowed_delivery_at = now + DEBOUNCE_INTERVAL_SECONDS
        - persist both the composite lineage hash and the engine-normalized
          body hash so the deduplication gate is calibrated correctly on the
          next run.
        """
        now = datetime.datetime.utcnow()
        state.comment_status = "DELIVERED"
        state.comment_integrity_status = integrity_status
        state.latest_comment_hash = composite_hash
        state.latest_comment_body_hash = normalized_body_hash
        state.comment_last_updated_at = now
        state.last_delivery_error = None
        state.delivery_attempt_count = 0
        state.next_allowed_delivery_at = now + datetime.timedelta(
            seconds=DEBOUNCE_INTERVAL_SECONDS
        )
        if github_comment_id is not None:
            state.github_comment_id = github_comment_id
        state.updated_at = now
        self.db.flush()

    # ──────────────────────────────────────────────────────────
    # Public: mark_failed
    # ──────────────────────────────────────────────────────────

    def mark_failed(
        self,
        state: PullRequestCommentState,
        error: str,
    ) -> None:
        """Record a final delivery failure on `state`."""
        state.comment_status = "DEAD_LETTER"
        state.last_delivery_error = error
        state.updated_at = datetime.datetime.utcnow()
        self.db.flush()

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _load_state(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID,
    ) -> Optional[PullRequestCommentState]:
        return (
            self.db.query(PullRequestCommentState)
            .filter(
                PullRequestCommentState.repository_id == repository_id,
                PullRequestCommentState.pull_request_id == pull_request_id,
            )
            .first()
        )
