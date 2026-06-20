import hashlib
import logging
import uuid
import datetime
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry, RecommendationInputSnapshot
from app.models.pull_request import PullRequestCommentState, PullRequestCommentDeliveryEvent, PullRequest
from app.models.github_installation import GitHubInstallation
from app.models.fragility_pattern import FragilitySnapshot
from app.services.github_api_client import GitHubApiClient
from app.services.comment_deduplication_engine import CommentDeduplicationEngine
from app.services.pr_comment_update_strategy import (
    PRCommentUpdateStrategy,
    UpdateAction,
)
from app.services.pr_comment_runtime_safeguards import (
    PRCommentRuntimeSafeguards,
    MinimalCommentBuilder,
    DeliveryOutcome,
    RENDER_TIMEOUT_SECONDS,
    GITHUB_API_TIMEOUT_SECONDS,
    DELIVERY_PIPELINE_BUDGET_SECONDS,
)
from app.services.recommendation_report_generator import RecommendationReportGenerator
from app.services.github_recommendation_comment_builder import GitHubRecommendationCommentBuilder

logger = logging.getLogger("veriscope.pr_comment_service")

# Hard rendering ceiling constraints
MAX_COMMENT_LINES = 120
MAX_REASONING_BULLETS = 4
MAX_BULLET_LENGTH = 160

COMMENT_TEMPLATE_VERSION = "template.v1"
COMMENT_RENDERING_RULES_VERSION = "rules.v1"
DELIVERY_JOB_TTL_HOURS = 24

FORBIDDEN_PHRASES = [
    "safe to ship",
    "unsafe to merge",
    "production failure likely",
    "high probability of outage",
    "ai believes",
    "guaranteed",
    "certified",
    "approved"
]

def escape_markdown(text: str) -> str:
    """Safely escape special markdown characters."""
    if not text:
        return ""
    escaped = ""
    for char in text:
        if char in ['\\', '_', '*', '`', '[', ']']:
            escaped += '\\' + char
        else:
            escaped += char
    return escaped

def shorten_path(path: str) -> str:
    """Shorten long file paths by keeping the last two components."""
    if not path:
        return ""
    parts = path.split('/')
    if len(parts) > 3:
        return ".../" + "/".join(parts[-2:])
    return path

def clean_bullet_text(text: str) -> str:
    """Collapse redundant phrases and clean spacing."""
    if not text:
        return ""
    text = text.replace("preceded failed executions", "failed executions")
    text = text.replace("co-failed with downstream test", "co-failed with")
    text = text.replace("Changes involving", "Changes to")
    text = " ".join(text.split())
    return text

def enforce_single_line_bullet(text: str) -> str:
    """Strip newlines and nested formatting from bullets."""
    if not text:
        return ""
    # Strip nested markdown styling
    text = text.replace("`", "").replace("*", "").replace("_", "")
    # Strip newlines
    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    return text

def format_bullet(text: str) -> str:
    """Format and constrain a bullet to single-line under 160 characters."""
    text = enforce_single_line_bullet(text)
    
    # Compress long paths in the text
    words = []
    for word in text.split(' '):
        if '/' in word:
            cleaned_word = word.strip(".,;:?!()")
            shortened = shorten_path(cleaned_word)
            prefix = word[:word.find(cleaned_word)]
            suffix = word[word.find(cleaned_word) + len(cleaned_word):]
            words.append(prefix + shortened + suffix)
        else:
            words.append(word)
    text = " ".join(words)
    
    text = clean_bullet_text(text)
    text = escape_markdown(text)
    
    if len(text) > MAX_BULLET_LENGTH:
        text = text[:MAX_BULLET_LENGTH - 3] + "..."
    return text

def sanitize_and_check_forbidden(text: str) -> str:
    """Locate and strip case-insensitive forbidden phrases from comment body."""
    text_lower = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text_lower:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            text = pattern.sub("[censored phrase]", text)
    return text


def classify_github_error(error: Exception) -> bool:
    """Classify a GitHub API exception.
    
    Returns:
        True if the error is retryable (transient/network/rate limit).
        False if the error is non-retryable (permission/validation/deleted/not found).
    """
    from app.services.github_api_client import (
        GitHubRateLimitExceededError,
        GitHubServiceUnavailableError,
        GitHubAuthPermissionError,
        GitHubNotFoundError,
        GitHubValidationError
    )
    
    # Classify custom veriscope exceptions
    if isinstance(error, (GitHubRateLimitExceededError, GitHubServiceUnavailableError)):
        return True
    if isinstance(error, (GitHubAuthPermissionError, GitHubNotFoundError, GitHubValidationError)):
        return False
        
    # Check exception string for both custom exception class names and generic transient keywords
    err_str = str(error).lower()
    
    if "ratelimit" in err_str or "rate limit" in err_str or "too many requests" in err_str:
        return True
    if "serviceunavailable" in err_str or "service unavailable" in err_str or "503" in err_str or "502" in err_str or "504" in err_str:
        return True
    if "authpermission" in err_str or "permission" in err_str or "401" in err_str or "403" in err_str:
        return False
    if "notfound" in err_str or "not found" in err_str or "404" in err_str:
        return False
    if "validation" in err_str or "422" in err_str:
        return False
        
    # Fallback checking string representations for network issues or timeout hints
    if any(hint in err_str for hint in ("timeout", "network", "connect", "secondary rate limit")):
        return True
        
    return False


class PRCommentService:
    def __init__(self, db: Session):
        self.db = db
        self.client = GitHubApiClient()

    # ----------------------------------------------------
    # Bullet Selection & Priority Logic
    # ----------------------------------------------------
    def select_prioritized_bullets(self, run: RecommendationRun) -> List[str]:
        """Prioritize and format up to 4 deterministic bullets from reasoning entries."""
        bullets_map = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
        
        # Pull reasoning entries
        entries = self.db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id
        ).all()
        
        # 3. Stale or moderate/low coverage (Check run level coverage)
        cov_conf = run.evidence_quality or "UNKNOWN"
        if cov_conf in ("LOW", "MISSING", "UNKNOWN"):
            bullets_map[3].append(
                format_bullet("Coverage: Scoped coverage reports are stale or missing for the changed files.")
            )

        for entry in entries:
            # 1. Critical/high fragility pattern
            if entry.reason_type == "historical_fragility" and ("risk level: high" in entry.human_readable_reason.lower() or "risk level: critical" in entry.human_readable_reason.lower()):
                # Pull pattern details if possible
                m = re.search(r"Pattern ID: ([a-fA-F0-9\-]+)", entry.human_readable_reason)
                pid = m.group(1) if m else "active-pattern"
                bullets_map[1].append(
                    format_bullet(f"Fragility: Active high-risk pattern detected in changed area (Pattern ID: {pid}).")
                )
            
            # 2. Co-failure pattern
            elif entry.reason_type == "historical_fragility" and "co-failed" in entry.human_readable_reason.lower():
                bullets_map[2].append(
                    format_bullet("Co-Failure: Repeated co-failures detected between changed source and test suites.")
                )
                
            # 4. Flaky/quarantined test influence
            elif entry.reason_type == "flaky_adjustments" or "flaky" in entry.human_readable_reason.lower():
                bullets_map[4].append(
                    format_bullet("Flakiness: Flaky test profiles detected in run; priority auto-calibrated.")
                )
                
            # 5. Dependency expansion warning
            elif entry.reason_type == "dependency_expansion" or "dependency" in entry.human_readable_reason.lower():
                bullets_map[5].append(
                    format_bullet("Dependencies: Transitive file dependencies expanded for regression analysis.")
                )
                
            # 6. Historical failure boost
            elif entry.reason_type == "scoped_historical_failure" or "historical failure" in entry.human_readable_reason.lower():
                bullets_map[6].append(
                    format_bullet("History: Execution priority boosted by historical failure statistics.")
                )

        # Collect sorted list of bullets
        all_bullets = []
        for i in sorted(bullets_map.keys()):
            # Deduplicate bullets in same category
            seen = set()
            for b in bullets_map[i]:
                if b not in seen:
                    all_bullets.append(b)
                    seen.add(b)

        # Strictly cap at 4 bullets
        return all_bullets[:MAX_REASONING_BULLETS]

    # ----------------------------------------------------
    # Recommended Action Sentence Generator
    # ----------------------------------------------------
    def generate_recommended_action(self, run: RecommendationRun) -> str:
        """Deterministically generate exactly one recommended action sentence."""
        mode = run.recommendation_mode or "NORMAL"
        cov_conf = run.evidence_quality or "UNKNOWN"
        
        # Check if there are critical/high fragility patterns
        has_high_risk = False
        for entry in run.reasoning_entries:
            if entry.reason_type == "historical_fragility" and ("high" in entry.human_readable_reason.lower() or "critical" in entry.human_readable_reason.lower()):
                has_high_risk = True
                break

        if mode == "FULL_REGRESSION":
            action = "Execute the full regression testing suite to ensure safety under limited coverage."
        elif mode == "SAFE_FALLBACK":
            action = "Review the coverage gaps and run the widened regression suite before merge."
        elif has_high_risk:
            action = "Run targeted integration tests for changed components to verify stability."
        elif cov_conf == "HIGH" and mode == "NORMAL":
            action = "Run the optimized regression suite to validate changes against mapped coverage."
        else:
            action = "Execute the recommended test suite to verify code correctness before merge."

        return escape_markdown(action)

    # ----------------------------------------------------
    # Core Markdown Comment Renderer
    # ----------------------------------------------------
    def render_comment(self, run: RecommendationRun) -> str:
        """Render a deterministic, professional, multi-section GitHub recommendation scoping comment."""
        # 1. Generate unified report from single source of truth report generator
        report = RecommendationReportGenerator.generate_report(self.db, run.id)

        # 2. Build the structured comment using the new builder
        comment_body = GitHubRecommendationCommentBuilder.build_comment(report, run)

        # 3. Sanitize for forbidden terminology
        comment_body = sanitize_and_check_forbidden(comment_body)

        # 4. Enforce line counting constraints strictly
        lines = comment_body.split('\n')
        if len(lines) > MAX_COMMENT_LINES:
            logger.warning(f"Comment exceeded line ceiling of {MAX_COMMENT_LINES} lines ({len(lines)} lines). Truncating.")
            lines = lines[:MAX_COMMENT_LINES - 2]
            lines.append("...")
            lines.append("<!-- veriscope-pr-comment -->")
            comment_body = "\n".join(lines)

        return comment_body

    # ----------------------------------------------------
    # Comment Hash Verification & Lineage Hashing
    # ----------------------------------------------------
    def compute_composite_hash(self, comment_body: str, run: RecommendationRun) -> str:
        """Compute strict SHA256 of comment and snapshots to prevent stale reasoning drift."""
        # 1. Normalize line endings and trim spaces on body
        normalized_body = "\n".join([line.strip() for line in comment_body.split('\n') if line.strip()])
        
        # 2. Retrieve fragility snapshot hash if exists
        frag_snap = self.db.query(FragilitySnapshot).filter(
            FragilitySnapshot.recommendation_run_id == run.id
        ).first()
        frag_hash = frag_snap.snapshot_hash if frag_snap else "empty_fragility_snapshot"
        
        # 3. Compute reasoning snapshot hash
        entries = self.db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id
        ).order_by(RecommendationReasoningEntry.id).all()
        reasoning_payload = "|".join([f"{e.reason_type}:{e.human_readable_reason}" for e in entries])
        reasoning_hash = hashlib.sha256(reasoning_payload.encode("utf-8")).hexdigest()
        
        # 4. Recommendation snapshot fingerprint
        fingerprint = run.evidence_fingerprint or "empty_fingerprint"
        
        composite_input = f"{normalized_body}|{fingerprint}|{frag_hash}|{reasoning_hash}"
        return hashlib.sha256(composite_input.encode("utf-8")).hexdigest()

    # ----------------------------------------------------
    # Async Job delivery Worker Method (RQ Wrapper Target)
    # ----------------------------------------------------
    def deliver_pr_comment_for_run(self, recommendation_run_id: uuid.UUID):
        """Execute async PR comment delivery routing all anti-churn decisions
        through PRCommentUpdateStrategy before any GitHub API call is made."""
        start_time = datetime.datetime.utcnow()

        # ── 1. Load run ───────────────────────────────────────
        run = self.db.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation_run_id
        ).first()
        if not run:
            logger.error(
                f"Cannot deliver comment: RecommendationRun {recommendation_run_id} not found."
            )
            return

        pr = run.pull_request
        if not pr:
            logger.warning(
                f"Skipping comment delivery: RecommendationRun {recommendation_run_id} "
                f"has no Pull Request."
            )
            return

        repo = pr.repository
        installation = self.db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == repo.workspace_id
        ).first()

        # ── 2. Ensure comment state exists ───────────────────
        state = self.db.query(PullRequestCommentState).filter(
            PullRequestCommentState.repository_id == pr.repository_id,
            PullRequestCommentState.pull_request_id == pr.id,
        ).first()

        if not state:
            state = PullRequestCommentState(
                repository_id=pr.repository_id,
                pull_request_id=pr.id,
                comment_status="PENDING",
                created_at=datetime.datetime.utcnow(),
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)

        # ── 3. Render body with timeout protection ───────────
        safeguards = PRCommentRuntimeSafeguards()
        recommended_count = len(run.tests)
        total_count = run.skipped_count + recommended_count
        fingerprint = run.evidence_fingerprint or str(run.id)

        render_result = safeguards.render_with_timeout(
            lambda: self.render_comment(run),
            recommended_count=recommended_count,
            total_count=total_count,
            evidence_quality=run.evidence_quality or "UNKNOWN",
            short_hash=fingerprint[:8],
        )

        body = render_result.comment_body
        is_degraded = render_result.is_degraded
        degradation_reason = render_result.degradation_reason

        if is_degraded:
            logger.warning(
                f"Degraded comment will be delivered for run {run.id}: "
                f"{degradation_reason}"
            )

        normalized_body_hash = CommentDeduplicationEngine.compute_body_hash(body)
        body_hash = self.compute_composite_hash(body, run)

        # ── 4. Strategy gate: debounce / TTL / supersession / race / hash ──
        strategy = PRCommentUpdateStrategy(self.db)
        decision = strategy.evaluate(
            run_id=recommendation_run_id,
            new_body_hash=normalized_body_hash,
        )

        if decision.action == UpdateAction.DEBOUNCE:
            logger.info(decision.reason)
            try:
                from app.services.github_app import get_rq_queue
                wait = decision.reschedule_in_seconds or 16
                get_rq_queue().enqueue_in(
                    datetime.timedelta(seconds=wait),
                    deliver_pr_comment_task_wrapper,
                    args=(str(run.id),),
                )
            except Exception as exc:
                logger.warning(f"RQ unavailable for debounce re-schedule: {exc}")
            self._record_event(
                state_id=state.id, run_id=run.id, status="RATE_LIMITED",
                payload=decision.details,
                latency_ms=int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000),
                failure_reason=decision.reason,
            )
            return

        if decision.action == UpdateAction.TTL_EXPIRED:
            logger.warning(decision.reason)
            strategy.mark_failed(state, decision.reason)
            self.db.commit()
            self._record_event(
                state_id=state.id, run_id=run.id, status="FAILED",
                payload=decision.details, latency_ms=0, failure_reason=decision.reason,
            )
            return

        if decision.action == UpdateAction.SUPERSEDED:
            logger.info(decision.reason)
            self._record_event(
                state_id=state.id, run_id=run.id, status="SKIPPED_NO_CHANGE",
                payload=decision.details, latency_ms=0, failure_reason=decision.reason,
            )
            return

        if decision.action == UpdateAction.SKIPPED_HASH:
            logger.info(decision.reason)
            self._record_event(
                state_id=state.id, run_id=run.id, status="SKIPPED_NO_CHANGE",
                payload={
                    "normalized_body_hash": normalized_body_hash,
                    "composite_hash": body_hash,
                    "version": COMMENT_TEMPLATE_VERSION,
                    "rendering_version": COMMENT_RENDERING_RULES_VERSION,
                },
                latency_ms=int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000),
            )
            return

        # decision.action == UpdateAction.PROCEED
        # Optimistic-lock claim — abort if another worker raced between evaluate() and now
        claimed = strategy.claim_delivery(state, run_id=recommendation_run_id)
        if not claimed:
            logger.warning(
                f"Race lost: another worker claimed delivery for PR {pr.number}. "
                f"Aborting run {recommendation_run_id}."
            )
            self._record_event(
                state_id=state.id, run_id=run.id, status="SKIPPED_NO_CHANGE",
                payload={"reason": "Race condition: delivery claimed by concurrent worker."},
                latency_ms=int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000),
                failure_reason="Race lost",
            )
            self.db.commit()
            return

        self.db.commit()

        # ── 5. Graceful failure if credentials missing ────────
        if not installation or not self.client.app_id or not self.client.private_key:
            err_msg = (
                "GitHub App credentials or installation mapping are not configured in settings."
            )
            logger.warning(f"Graceful failure: {err_msg}")
            strategy.mark_failed(state, err_msg)
            self.db.commit()
            self._record_event(
                state_id=state.id, run_id=run.id, status="FAILED",
                payload={"app_id_configured": self.client.app_id is not None},
                latency_ms=0, failure_reason=err_msg,
            )
            return

        # ----------------------------------------------------
        # API Comment Discovery, Integrity & Paginated Search
        # safeguards wrap each GitHub call with a 10s hard limit
        # ----------------------------------------------------
        owner, repo_name = repo.full_name.split('/')
        github_comment = None
        integrity_status = "VALID"

        try:
            # ── 1. List existing PR comments (time-boxed) ────
            list_result = safeguards.call_github_api(
                "list_pr_comments",
                self.client.list_pr_comments,
                installation_id=installation.github_installation_id,
                owner=owner,
                repo=repo_name,
                pull_number=pr.number,
            )

            if not list_result.succeeded:
                if list_result.original_error:
                    raise list_result.original_error
                err = list_result.error or "list_pr_comments failed"
                raise Exception(err)

            # Extract canonical from list result
            _comments_ref: list = []
            def _capture_comments():
                _comments_ref.extend(
                    self.client.list_pr_comments(
                        installation_id=installation.github_installation_id,
                        owner=owner,
                        repo=repo_name,
                        pull_number=pr.number,
                    )
                )

            _cap_result = safeguards.call_github_api(
                "list_pr_comments_capture", _capture_comments
            )
            
            if not _cap_result.succeeded:
                if _cap_result.original_error:
                    raise _cap_result.original_error
                err = _cap_result.error or "list_pr_comments_capture failed"
                raise Exception(err)
                
            comments = _comments_ref

            # Find all canonical comments containing the hidden marker
            canonicals = [
                c for c in comments
                if "<!-- veriscope-pr-comment -->" in c.get("body", "")
            ]

            if canonicals:
                oldest_canonical = canonicals[0]
                github_comment = oldest_canonical
                state.github_comment_id = oldest_canonical["id"]
                if len(canonicals) > 1:
                    logger.warning(
                        f"Integrity Alert: Multiple canonical Veriscope comments on PR {pr.number}. "
                        f"Cleaning up duplicates and keeping oldest {oldest_canonical['id']}."
                    )
                    integrity_status = "MALFORMED"
                    # Prune duplicate canonical comments safely
                    for duplicate in canonicals[1:]:
                        try:
                            safeguards.call_github_api(
                                f"delete_pr_comment_{duplicate['id']}",
                                self.client.delete_pr_comment,
                                installation_id=installation.github_installation_id,
                                owner=owner,
                                repo=repo_name,
                                comment_id=duplicate["id"]
                            )
                        except Exception as e:
                            logger.warning(f"Failed to delete duplicate comment {duplicate['id']}: {e}")
                    integrity_status = "VALID"
            else:
                if state.github_comment_id is not None:
                    logger.warning(
                        f"Integrity Alert: Stored comment ID {state.github_comment_id} "
                        f"not found on PR {pr.number}. Resetting to trigger recreation."
                    )
                    integrity_status = "CORRUPTED"
                    state.github_comment_id = None

            # ── 2. Create or update canonical comment (time-boxed) ──
            if github_comment and integrity_status != "CORRUPTED":
                logger.info(f"PATCHing canonical comment {github_comment['id']} on PR {pr.number}.")
                api_result = safeguards.call_github_api(
                    "update_pr_comment",
                    self.client.update_pr_comment,
                    installation_id=installation.github_installation_id,
                    owner=owner,
                    repo=repo_name,
                    comment_id=github_comment["id"],
                    body_text=body,
                )
                status_event = "UPDATED"
            else:
                status_event = "RECREATED" if integrity_status == "CORRUPTED" else "CREATED"
                logger.info(f"{status_event} new canonical comment on PR {pr.number}.")
                api_result = safeguards.call_github_api(
                    "create_pr_comment",
                    self.client.create_pr_comment,
                    installation_id=installation.github_installation_id,
                    owner=owner,
                    repo=repo_name,
                    pull_number=pr.number,
                    body_text=body,
                )

            if not api_result.succeeded:
                if api_result.original_error:
                    raise api_result.original_error
                err = api_result.error or f"{status_event.lower()} comment failed"
                raise Exception(err)

            # ── 3. Success ───────────────────────────────────
            res_dict: dict = {}
            if api_result.github_comment_id:
                res_dict = {"id": api_result.github_comment_id}
                state.github_comment_id = api_result.github_comment_id

            strategy.mark_delivered(
                state,
                composite_hash=body_hash,
                normalized_body_hash=normalized_body_hash,
                github_comment_id=api_result.github_comment_id,
                integrity_status=integrity_status,
            )
            self.db.commit()

            # Track exposure presented event after successful delivery
            try:
                from app.services.recommendation_exposure_tracker import RecommendationExposureTracker
                exposure_tracker = RecommendationExposureTracker(self.db)
                exposure_tracker.track_presented(run.id)
            except Exception as exposure_err:
                logger.error(
                    f"Failed to track exposure presented for run {run.id}: {exposure_err}"
                )

            latency = safeguards.pipeline_elapsed_ms()
            self._record_event(
                state_id=state.id,
                run_id=run.id,
                status=status_event,
                payload={
                    "version": COMMENT_TEMPLATE_VERSION,
                    "rendering_version": COMMENT_RENDERING_RULES_VERSION,
                    "degraded": is_degraded,
                    "degradation_reason": degradation_reason,
                    "pipeline_elapsed_ms": latency,
                },
                response=res_dict or None,
                latency_ms=latency,
            )
            logger.info(
                f"PR comment {'(degraded) ' if is_degraded else ''}delivered to PR {pr.number} "
                f"in {latency}ms."
            )
            return

        except Exception as e:
            self._handle_delivery_failure(state, run, e, safeguards.pipeline_elapsed_ms(), is_degraded)

    def _handle_delivery_failure(
        self,
        state: PullRequestCommentState,
        run: RecommendationRun,
        error: Exception,
        latency: int,
        is_degraded: bool
    ) -> None:
        """Classify failure, persist retry lineage, and schedule async retry if applicable."""
        err_msg = str(error)
        is_retryable = classify_github_error(error)
        
        # Check for explicit retry_after from custom exceptions or parse from error message
        retry_after = getattr(error, "retry_after", None)
        if retry_after is None:
            match = re.search(r"(?:retry-after|reset in)\s*[:\s]\s*(\d+)", err_msg.lower())
            if match:
                retry_after = int(match.group(1))

        logger.warning(
            f"PR comment delivery failed for run {run.id}: {err_msg} "
            f"(Retryable: {is_retryable}, Attempt: {state.delivery_attempt_count}, Retry-After: {retry_after})"
        )
        
        if is_retryable and state.delivery_attempt_count < 5:
            # Calculate exponential backoff or use retry_after
            if retry_after is not None:
                delay_seconds = retry_after + 2
            else:
                delay_seconds = 2 ** state.delivery_attempt_count
            
            # Set state status to PENDING so it can be picked up on retry
            state.comment_status = "PENDING"
            state.last_delivery_error = f"Retryable Failure: {err_msg}"
            self.db.commit()
            
            # Enqueue next attempt in RQ with delay
            try:
                from app.services.github_app import get_rq_queue
                import datetime
                
                queue = get_rq_queue()
                queue.enqueue_in(
                    datetime.timedelta(seconds=delay_seconds),
                    deliver_pr_comment_task_wrapper,
                    args=(str(run.id),),
                    job_id=f"deliver_comment_{run.id}_attempt_{state.delivery_attempt_count + 1}"
                )
                logger.info(
                    f"Successfully scheduled async retry attempt {state.delivery_attempt_count + 1} "
                    f"in {delay_seconds}s for run {run.id}"
                )
            except Exception as queue_err:
                logger.error(f"Failed to enqueue retry job in RQ: {queue_err}")
                
            # Persist failure event in ledger showing it will retry
            self._record_event(
                state_id=state.id,
                run_id=run.id,
                status="FAILED_RETRYING",
                payload={
                    "attempt": state.delivery_attempt_count,
                    "next_attempt": state.delivery_attempt_count + 1,
                    "backoff_seconds": delay_seconds,
                    "degraded": is_degraded,
                    "version": COMMENT_TEMPLATE_VERSION,
                },
                latency_ms=latency,
                failure_reason=err_msg
            )
        else:
            # Non-retryable error or exceeded maximum retries -> Final failure!
            strategy = PRCommentUpdateStrategy(self.db)
            strategy.mark_failed(state, err_msg)
            self.db.commit()
            
            self._record_event(
                state_id=state.id,
                run_id=run.id,
                status="DEAD_LETTER",
                payload={
                    "attempt": state.delivery_attempt_count,
                    "degraded": is_degraded,
                    "version": COMMENT_TEMPLATE_VERSION,
                    "max_retries_exceeded": state.delivery_attempt_count >= 5
                },
                latency_ms=latency,
                failure_reason=err_msg
            )

    # ----------------------------------------------------
    # Helper to create event logs
    # ----------------------------------------------------
    def _record_event(
        self,
        state_id: uuid.UUID,
        run_id: uuid.UUID,
        status: str,
        payload: Dict[str, Any],
        response: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[int] = None,
        failure_reason: Optional[str] = None
    ) -> PullRequestCommentDeliveryEvent:
        event = PullRequestCommentDeliveryEvent(
            id=uuid.uuid4(),
            comment_state_id=state_id,
            recommendation_run_id=run_id,
            github_comment_id=response.get("id") if response else None,
            delivery_status=status,
            request_payload=payload,
            response_payload=response,
            failure_reason=failure_reason,
            delivery_latency_ms=latency_ms,
            created_at=datetime.datetime.utcnow()
        )
        self.db.add(event)
        self.db.commit()
        return event

    # ----------------------------------------------------
    # Replay / Operational-recovery Methods
    # ----------------------------------------------------
    def list_dead_letter_comments(self) -> List[PullRequestCommentState]:
        """Retrieve all PR comment states currently in DEAD_LETTER status."""
        return self.db.query(PullRequestCommentState).filter(
            PullRequestCommentState.comment_status == "DEAD_LETTER"
        ).all()

    def get_delivery_metrics(self) -> Dict[str, Any]:
        """Aggregate operational observability metrics for PR comment delivery."""
        events = self.db.query(PullRequestCommentDeliveryEvent).all()
        total_attempts = len(events)
        if total_attempts == 0:
            return {
                "total_attempts": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "retry_counts": 0,
                "skipped_no_change_counts": 0,
                "latency_stats": {"min": 0, "max": 0, "avg": 0.0}
            }

        success_count = sum(1 for e in events if e.delivery_status in ("CREATED", "UPDATED", "RECREATED"))
        failure_count = sum(1 for e in events if e.delivery_status in ("FAILED", "DEAD_LETTER"))
        retry_count = sum(1 for e in events if e.delivery_status == "FAILED_RETRYING")
        skipped_count = sum(1 for e in events if e.delivery_status == "SKIPPED_NO_CHANGE")

        latencies = [e.delivery_latency_ms for e in events if e.delivery_latency_ms is not None]
        latency_stats = {
            "min": min(latencies) if latencies else 0,
            "max": max(latencies) if latencies else 0,
            "avg": sum(latencies) / len(latencies) if latencies else 0.0
        }

        return {
            "total_attempts": total_attempts,
            "success_rate": round(success_count / total_attempts, 4) if total_attempts else 0.0,
            "failure_rate": round((failure_count + retry_count) / total_attempts, 4) if total_attempts else 0.0,
            "retry_counts": retry_count,
            "skipped_no_change_counts": skipped_count,
            "latency_stats": latency_stats
        }

    def regenerate_comment_from_recommendation(self, recommendation_run_id: uuid.UUID) -> str:
        """Regenerate the comment using exclusively immutable snapshots and reasoning records."""
        run = self.db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
        if not run:
            raise ValueError(f"RecommendationRun {recommendation_run_id} not found.")

        pr = run.pull_request
        if not pr:
            raise ValueError(f"RecommendationRun {recommendation_run_id} has no Pull Request.")

        # Update PullRequestCommentState to point to this run and reset state to PENDING
        state = self.db.query(PullRequestCommentState).filter(
            PullRequestCommentState.repository_id == pr.repository_id,
            PullRequestCommentState.pull_request_id == pr.id
        ).first()

        if not state:
            state = PullRequestCommentState(
                repository_id=pr.repository_id,
                pull_request_id=pr.id,
                created_at=datetime.datetime.utcnow()
            )
            self.db.add(state)

        state.latest_recommendation_run_id = run.id
        state.comment_status = "PENDING"
        state.delivery_attempt_count = 0
        state.last_delivery_error = None
        self.db.commit()

        # Enqueue delivery in RQ
        self.enqueue_delivery_task(run.id)
        return "SUCCESS: Comment regeneration queued."

    def replay_comment_delivery(self, comment_state_id: uuid.UUID) -> str:
        """Replay comment delivery for the latest recommendation run stored in comment state."""
        state = self.db.query(PullRequestCommentState).filter(PullRequestCommentState.id == comment_state_id).first()
        if not state:
            raise ValueError(f"PullRequestCommentState {comment_state_id} not found.")
        
        if not state.latest_recommendation_run_id:
            raise ValueError(f"PullRequestCommentState {comment_state_id} has no recorded latest recommendation run.")

        state.comment_status = "PENDING"
        state.delivery_attempt_count = 0
        state.last_delivery_error = None
        self.db.commit()

        # Enqueue delivery in RQ
        self.enqueue_delivery_task(state.latest_recommendation_run_id)
        return "SUCCESS: Comment delivery replay queued."

    def repair_stale_comment_state(self, pull_request_id: uuid.UUID) -> str:
        """Repair database comment state alignment and recover from stuck PENDING/PROCESSING/DEAD_LETTER states."""
        pr = self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        if not pr:
            raise ValueError(f"PullRequest {pull_request_id} not found.")

        state = self.db.query(PullRequestCommentState).filter(
            PullRequestCommentState.pull_request_id == pr.id
        ).first()

        if not state:
            state = PullRequestCommentState(
                repository_id=pr.repository_id,
                pull_request_id=pr.id,
                comment_status="PENDING",
                created_at=datetime.datetime.utcnow()
            )
            self.db.add(state)
            self.db.flush()

        repo = pr.repository
        installation = self.db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == repo.workspace_id
        ).first()

        if not installation or not self.client.app_id or not self.client.private_key:
            raise ValueError("Credentials missing for comment state repair.")

        owner, repo_name = repo.full_name.split('/')
        comments = self.client.list_pr_comments(
            installation_id=installation.github_installation_id,
            owner=owner,
            repo=repo_name,
            pull_number=pr.number
        )

        canonicals = []
        for c in comments:
            if "<!-- veriscope-pr-comment -->" in c.get("body", ""):
                canonicals.append(c)

        if canonicals:
            oldest = canonicals[0]
            state.github_comment_id = oldest["id"]
            state.comment_status = "DELIVERED"
            state.delivery_attempt_count = 0
            state.last_delivery_error = None
            if len(canonicals) > 1:
                state.comment_integrity_status = "MALFORMED"
                # If malformed, we can prune duplicates in repair!
                for dup in canonicals[1:]:
                    try:
                        self.client.delete_pr_comment(
                            installation_id=installation.github_installation_id,
                            owner=owner,
                            repo=repo_name,
                            comment_id=dup["id"]
                        )
                    except Exception as e:
                        logger.warning(f"Failed to delete duplicate comment {dup['id']} during repair: {e}")
                state.comment_integrity_status = "VALID"
            else:
                state.comment_integrity_status = "VALID"
        else:
            state.github_comment_id = None
            state.comment_status = "PENDING"
            state.comment_integrity_status = "MISSING"

        state.updated_at = datetime.datetime.utcnow()
        self.db.commit()
        return f"SUCCESS: Comment state repaired. Status advanced to {state.comment_status}, Integrity set to {state.comment_integrity_status}."

    def repair_comment_state(self, pull_request_id: uuid.UUID) -> str:
        """Alias for repair_stale_comment_state to maintain backward compatibility."""
        return self.repair_stale_comment_state(pull_request_id)

    def enqueue_delivery_task(self, run_id: uuid.UUID):
        """Enqueue delivery task wrapper to Redis/RQ veriscope_sync queue."""
        try:
            from app.services.github_app import get_rq_queue
            queue = get_rq_queue()
            
            # Enforce idempotency protection: check if CREATED/PENDING event exists
            existing_event = self.db.query(PullRequestCommentDeliveryEvent).filter(
                PullRequestCommentDeliveryEvent.recommendation_run_id == run_id,
                PullRequestCommentDeliveryEvent.delivery_status == "CREATED"
            ).first()
            if existing_event:
                logger.info(f"Deduplication triggered: delivery event already exists for run {run_id}. Skipping enqueue.")
                return

            queue.enqueue(
                deliver_pr_comment_task_wrapper,
                args=(str(run_id),),
                job_id=f"deliver_comment_{run_id}"
            )
            logger.info(f"Successfully enqueued comment delivery job for run {run_id} in RQ veriscope_sync.")
        except Exception as e:
            logger.error(f"Failed to enqueue comment delivery task for run {run_id}: {e}")


# ----------------------------------------------------
# RQ Task Wrapper Function (Importable)
# ----------------------------------------------------
def deliver_pr_comment_task_wrapper(recommendation_run_id_str: str):
    """Background task wrapper executed by the RQ worker process."""
    from app.db.session import SessionLocal
    
    run_id = uuid.UUID(recommendation_run_id_str)
    db = SessionLocal()
    try:
        service = PRCommentService(db)
        service.deliver_pr_comment_for_run(run_id)
    except Exception as e:
        logger.exception(f"Unhandled exception running RQ PR comment delivery wrapper {run_id}: {e}")
        raise e
    finally:
        db.close()
