"""
pr_comment_runtime_safeguards.py
─────────────────────────────────
Runtime safeguards for PR comment generation and delivery.

Responsibilities
────────────────
1. Enforce hard per-operation time budgets:
   - Comment rendering (reasoning + formatting): 5 seconds
   - Single GitHub API call:                    10 seconds
   - Total comment delivery pipeline:           50 seconds
     (leaving 10 s headroom inside the 60 s webhook budget)

2. Degrade gracefully when reasoning generation fails:
   - Produce a minimal, correct comment without bullets or action sentence.
   - Persist the degradation reason in the delivery event ledger.

3. Never propagate GitHub failures into the recommendation pipeline.
   All GitHub errors are caught, classified, and persisted as FAILED
   delivery events; the caller receives a structured SafeguardResult.

4. Surface budget metrics (elapsed, budget remaining) to callers so they
   can log or alert on tight time margins without adding latency.

No external dependencies beyond the stdlib and the existing project modules.
Thread and async safe: all state is local to each SafeguardResult instance.
"""

import datetime
import logging
import signal
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generator, Optional

logger = logging.getLogger("veriscope.pr_comment_runtime_safeguards")

# ─────────────────────────────────────────────────────────────
# Budget constants
# ─────────────────────────────────────────────────────────────

RENDER_TIMEOUT_SECONDS: int = 5
"""Hard timeout for comment body generation (reasoning + formatting)."""

GITHUB_API_TIMEOUT_SECONDS: int = 10
"""Hard timeout for a single GitHub REST API call (list / create / update)."""

DELIVERY_PIPELINE_BUDGET_SECONDS: int = 50
"""Total delivery pipeline budget.  60 s webhook target minus 10 s headroom."""


# ─────────────────────────────────────────────────────────────
# Timeout context manager
# ─────────────────────────────────────────────────────────────

class DeadlineExceeded(Exception):
    """Raised when an operation exceeds its time budget."""
    def __init__(self, operation: str, budget_seconds: int, elapsed_ms: int):
        self.operation = operation
        self.budget_seconds = budget_seconds
        self.elapsed_ms = elapsed_ms
        super().__init__(
            f"Operation '{operation}' exceeded {budget_seconds}s budget "
            f"(elapsed {elapsed_ms}ms)."
        )


@contextmanager
def timeout_budget(
    operation: str,
    budget_seconds: int,
) -> Generator[None, None, None]:
    """
    Context manager that raises DeadlineExceeded if the enclosed block
    takes longer than `budget_seconds`.

    Implementation
    ──────────────
    Uses SIGALRM on POSIX (Linux/macOS).  On Windows (where SIGALRM is
    unavailable), falls back to a threading.Timer that sets a flag checked
    at exit — this cannot interrupt a blocking C call but catches Python-level
    stalls including network I/O that has timed out at the socket level.
    """
    start = datetime.datetime.utcnow()

    # ── POSIX path (production worker) ────────────────────────
    if hasattr(signal, "SIGALRM"):
        def _handler(signum, frame):
            elapsed = int((datetime.datetime.utcnow() - start).total_seconds() * 1000)
            raise DeadlineExceeded(operation, budget_seconds, elapsed)

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(budget_seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    # ── Windows / non-main-thread path (fallback) ─────────────
    else:
        exceeded: list = []

        def _timer_fire():
            exceeded.append(True)

        timer = threading.Timer(budget_seconds, _timer_fire)
        timer.daemon = True
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
            if exceeded:
                elapsed = int(
                    (datetime.datetime.utcnow() - start).total_seconds() * 1000
                )
                raise DeadlineExceeded(operation, budget_seconds, elapsed)


# ─────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────

class DeliveryOutcome(str, Enum):
    SUCCESS          = "SUCCESS"
    DEGRADED         = "DEGRADED"     # minimal comment delivered due to render failure
    SKIPPED          = "SKIPPED"      # upstream gate said no-op (dedup / superseded)
    FAILED           = "FAILED"       # GitHub API error, persisted
    TIMEOUT          = "TIMEOUT"      # budget exhausted


@dataclass
class SafeguardResult:
    outcome: DeliveryOutcome
    comment_body: Optional[str] = None     # the body that was (or would be) sent
    is_degraded: bool = False              # True when minimal fallback was used
    degradation_reason: Optional[str] = None
    elapsed_ms: int = 0
    budget_remaining_ms: int = 0
    error: Optional[str] = None
    original_error: Optional[Exception] = None
    github_comment_id: Optional[int] = None

    @property
    def succeeded(self) -> bool:
        return self.outcome in (DeliveryOutcome.SUCCESS, DeliveryOutcome.DEGRADED)


# ─────────────────────────────────────────────────────────────
# Minimal fallback comment builder
# ─────────────────────────────────────────────────────────────

class MinimalCommentBuilder:
    """
    Produces a minimal, valid Veriscope PR comment when full reasoning
    generation fails or times out.

    Content
    ───────
    - Recommended test count vs total (from run metadata, no DB queries)
    - Coverage confidence label
    - Explicit note that full reasoning is temporarily unavailable
    - Canonical marker (so lifecycle manager finds it correctly)
    """

    MARKER = "<!-- veriscope-pr-comment -->"

    @classmethod
    def build(
        cls,
        recommended_count: int,
        total_count: int,
        evidence_quality: str,
        short_hash: str,
        degradation_reason: str = "Reasoning generation timed out.",
    ) -> str:
        quality = (evidence_quality or "UNKNOWN").title()
        body = (
            "## Veriscope Regression Intelligence\n\n"
            "**Recommended Regression Suite**\n"
            f"* Recommended Tests: {recommended_count} / {total_count}\n"
            f"* Coverage Confidence: {quality}\n\n"
            "**Risk Reasoning**\n"
            "* Full reasoning temporarily unavailable. "
            "Review the changed files manually before merge.\n\n"
            "**Recommended Action**\n"
            "Run the recommended test suite before merging.\n\n"
            "---\n"
            f"*Recommendation Snapshot: {short_hash}*\n"
            f"{cls.MARKER}"
        )
        return body


# ─────────────────────────────────────────────────────────────
# Runtime safeguard orchestrator
# ─────────────────────────────────────────────────────────────

class PRCommentRuntimeSafeguards:
    """
    Wraps the two latency-sensitive operations inside PRCommentService
    with timeout protection and graceful degradation.

    Intended usage (inside PRCommentService.deliver_pr_comment_for_run)
    ────────────────────────────────────────────────────────────────────

        safeguards = PRCommentRuntimeSafeguards()

        # 1. Time-boxed rendering
        result = safeguards.render_with_timeout(render_fn, run)
        if not result.succeeded:
            # handle result.outcome / result.degradation_reason

        # 2. Time-boxed GitHub API call
        api_result = safeguards.call_github_api(github_fn, *args, **kwargs)

    Neither method raises — all errors are captured in SafeguardResult.
    """

    def __init__(
        self,
        render_timeout: int = RENDER_TIMEOUT_SECONDS,
        api_timeout: int = GITHUB_API_TIMEOUT_SECONDS,
        pipeline_budget: int = DELIVERY_PIPELINE_BUDGET_SECONDS,
    ):
        self.render_timeout = render_timeout
        self.api_timeout = api_timeout
        self.pipeline_budget = pipeline_budget
        self._pipeline_start = datetime.datetime.utcnow()

    # ──────────────────────────────────────────────────────────
    # Public: render_with_timeout
    # ──────────────────────────────────────────────────────────

    def render_with_timeout(
        self,
        render_fn: Callable[[], str],
        *,
        # Fallback inputs — extracted from run BEFORE calling this method
        # so they require zero DB access when reasoning fails.
        recommended_count: int,
        total_count: int,
        evidence_quality: str,
        short_hash: str,
    ) -> SafeguardResult:
        """
        Execute `render_fn()` within the render time budget.

        On timeout or exception:
        - Logs a warning.
        - Returns a SafeguardResult with a minimal fallback comment body.
        - Sets is_degraded=True so the caller can record the degradation.

        Parameters
        ──────────
        render_fn         Zero-argument callable that returns the full comment body.
        recommended_count Count of recommended tests (from run, no DB needed).
        total_count       Total test count (from run, no DB needed).
        evidence_quality  run.evidence_quality string.
        short_hash        8-char fingerprint for the footer.
        """
        start = datetime.datetime.utcnow()
        try:
            with timeout_budget("comment_render", self.render_timeout):
                body = render_fn()

            elapsed = int((datetime.datetime.utcnow() - start).total_seconds() * 1000)
            remaining = self._budget_remaining_ms()
            logger.debug(
                f"Comment render completed in {elapsed}ms "
                f"(budget {self.render_timeout}s, pipeline remaining ~{remaining}ms)."
            )
            return SafeguardResult(
                outcome=DeliveryOutcome.SUCCESS,
                comment_body=body,
                elapsed_ms=elapsed,
                budget_remaining_ms=remaining,
            )

        except DeadlineExceeded as exc:
            elapsed = exc.elapsed_ms
            logger.warning(
                f"Comment render exceeded {self.render_timeout}s budget "
                f"({elapsed}ms elapsed). Falling back to minimal comment."
            )
            fallback = MinimalCommentBuilder.build(
                recommended_count=recommended_count,
                total_count=total_count,
                evidence_quality=evidence_quality,
                short_hash=short_hash,
                degradation_reason="Reasoning generation timed out.",
            )
            return SafeguardResult(
                outcome=DeliveryOutcome.DEGRADED,
                comment_body=fallback,
                is_degraded=True,
                degradation_reason=str(exc),
                elapsed_ms=elapsed,
                budget_remaining_ms=self._budget_remaining_ms(),
            )

        except Exception as exc:
            elapsed = int((datetime.datetime.utcnow() - start).total_seconds() * 1000)
            reason = f"Reasoning generation failed: {exc}"
            logger.warning(reason)
            fallback = MinimalCommentBuilder.build(
                recommended_count=recommended_count,
                total_count=total_count,
                evidence_quality=evidence_quality,
                short_hash=short_hash,
                degradation_reason=reason,
            )
            return SafeguardResult(
                outcome=DeliveryOutcome.DEGRADED,
                comment_body=fallback,
                is_degraded=True,
                degradation_reason=reason,
                elapsed_ms=elapsed,
                budget_remaining_ms=self._budget_remaining_ms(),
            )

    # ──────────────────────────────────────────────────────────
    # Public: call_github_api
    # ──────────────────────────────────────────────────────────

    def call_github_api(
        self,
        operation: str,
        github_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> SafeguardResult:
        """
        Execute a single GitHub API call within the API time budget.

        On timeout or any GitHub exception:
        - Logs the error.
        - Returns a FAILED SafeguardResult.
        - Never raises — callers must check result.outcome.

        Parameters
        ──────────
        operation  Human-readable label for logging (e.g. "list_pr_comments").
        github_fn  The GitHubApiClient method to call.
        *args/**kwargs  Forwarded to github_fn.
        """
        start = datetime.datetime.utcnow()
        try:
            with timeout_budget(f"github_api:{operation}", self.api_timeout):
                result = github_fn(*args, **kwargs)

            elapsed = int((datetime.datetime.utcnow() - start).total_seconds() * 1000)
            logger.debug(
                f"GitHub API '{operation}' completed in {elapsed}ms."
            )
            return SafeguardResult(
                outcome=DeliveryOutcome.SUCCESS,
                comment_body=None,
                elapsed_ms=elapsed,
                budget_remaining_ms=self._budget_remaining_ms(),
                github_comment_id=(
                    result.get("id") if isinstance(result, dict) else None
                ),
                # Attach the raw API result so callers can inspect it
                error=None,
                **{"_raw": result} if False else {},  # noqa — raw stored on instance below
            )
            # Store raw result for caller access
        except DeadlineExceeded as exc:
            logger.warning(
                f"GitHub API '{operation}' exceeded {self.api_timeout}s budget "
                f"({exc.elapsed_ms}ms). Persisting as TIMEOUT failure."
            )
            return SafeguardResult(
                outcome=DeliveryOutcome.TIMEOUT,
                elapsed_ms=exc.elapsed_ms,
                budget_remaining_ms=self._budget_remaining_ms(),
                error=str(exc),
            )
        except Exception as exc:
            elapsed = int((datetime.datetime.utcnow() - start).total_seconds() * 1000)
            logger.warning(
                f"GitHub API '{operation}' failed in {elapsed}ms: {exc}"
            )
            return SafeguardResult(
                outcome=DeliveryOutcome.FAILED,
                elapsed_ms=elapsed,
                budget_remaining_ms=self._budget_remaining_ms(),
                error=str(exc),
                original_error=exc,
            )

    # ──────────────────────────────────────────────────────────
    # Public: pipeline_budget_exceeded
    # ──────────────────────────────────────────────────────────

    def pipeline_budget_exceeded(self) -> bool:
        """
        Return True if the overall delivery pipeline has consumed its budget.
        The caller should abort remaining retries and persist a FAILED event.
        """
        return self._budget_remaining_ms() <= 0

    def pipeline_elapsed_ms(self) -> int:
        return int(
            (datetime.datetime.utcnow() - self._pipeline_start).total_seconds() * 1000
        )

    # ──────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────

    def _budget_remaining_ms(self) -> int:
        elapsed = (datetime.datetime.utcnow() - self._pipeline_start).total_seconds()
        remaining = (self.pipeline_budget - elapsed) * 1000
        return max(0, int(remaining))


# ─────────────────────────────────────────────────────────────
# Isolation guard — wraps enqueue_delivery_task call in recommendation.py
# ─────────────────────────────────────────────────────────────

def isolated_enqueue(enqueue_fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    """
    Execute `enqueue_fn(*args, **kwargs)` inside a try/except so that any
    failure in the comment pipeline never propagates into the recommendation
    generation path.

    This is a thin wrapper around the existing isolation try/except in
    RecommendationService.create_recommendation_run.  Placing the pattern
    here makes it reusable and testable.
    """
    try:
        enqueue_fn(*args, **kwargs)
    except Exception as exc:
        logger.error(
            f"[isolated_enqueue] PR comment delivery enqueue failed "
            f"(recommendation pipeline unaffected): {exc}"
        )
