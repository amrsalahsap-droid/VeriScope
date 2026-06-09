"""
RepositoryReadinessService

Deterministic, backend-only service for computing per-repository readiness state.

Priority order (first match wins):
  UNKNOWN            — no installation or insufficient metadata
  REMOVED_OR_INACTIVE — repository removed from GitHub or installation removed
  NOT_SELECTED       — installation exists but repo not selected_for_analysis
  SYNC_FAILED        — latest_sync_status == FAILED
  NEEDS_TEST_HISTORY — no test runs ingested
  NEEDS_COVERAGE     — test runs exist but no coverage reports
  READY              — all conditions met
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.coverage import CoverageReport
from app.models.github_installation import GitHubInstallation
from app.models.recommendation import RecommendationRun
from app.models.repository import Repository
from app.models.test_result import TestRun
from app.models.webhook_event import WebhookEvent
from app.models.pull_request import PullRequest

logger = logging.getLogger("veriscope.repository_readiness")

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

NEXT_ACTION: Dict[str, Optional[str]] = {
    "READY":            "Open Intelligence",
    "NEEDS_TEST_HISTORY": "Upload Test Results",
    "NEEDS_COVERAGE":   "Upload Coverage Report",
    "SYNC_FAILED":      "Retry Sync",
    "NOT_SELECTED":     "Enable Repository",
    "REMOVED_OR_INACTIVE": "Check GitHub Installation",
    "UNKNOWN":          "Inspect Setup",
}


@dataclass
class RepositoryReadinessResult:
    readiness_state: str
    readiness_reasons: List[str]
    next_action: Optional[str]

    @classmethod
    def make(cls, state: str, reasons: List[str]) -> "RepositoryReadinessResult":
        return cls(
            readiness_state=state,
            readiness_reasons=reasons,
            next_action=NEXT_ACTION.get(state),
        )


# ---------------------------------------------------------------------------
# Bulk pre-fetch container (avoids N+1 queries in list endpoint)
# ---------------------------------------------------------------------------

@dataclass
class _RepoBulkData:
    installation: Optional[GitHubInstallation]
    test_run_count: int
    coverage_count: int
    recommendation_count: int
    pr_count: int
    recent_webhook: bool          # any webhook in last 24 h for this repo's installation
    github_repo_id: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class RepositoryReadinessService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public: single-repo calculation
    # ------------------------------------------------------------------

    def calculate_readiness(
        self, repository_id: UUID, workspace_id: UUID
    ) -> RepositoryReadinessResult:
        """Calculate readiness for a single repository, verified against workspace_id."""
        repo = (
            self.db.query(Repository)
            .filter(
                Repository.id == repository_id,
                Repository.workspace_id == workspace_id,
            )
            .first()
        )
        if repo is None:
            return RepositoryReadinessResult.make(
                "UNKNOWN", ["Repository not found in workspace."]
            )

        installation = (
            self.db.query(GitHubInstallation)
            .filter(GitHubInstallation.workspace_id == workspace_id)
            .first()
        )

        test_run_count = (
            self.db.query(func.count(TestRun.id))
            .filter(TestRun.repository_id == repository_id)
            .scalar() or 0
        )
        coverage_count = (
            self.db.query(func.count(CoverageReport.id))
            .filter(CoverageReport.repository_id == repository_id)
            .scalar() or 0
        )
        recommendation_count = (
            self.db.query(func.count(RecommendationRun.id))
            .filter(RecommendationRun.repository_id == repository_id)
            .scalar() or 0
        )
        pr_count = (
            self.db.query(func.count(PullRequest.id))
            .filter(PullRequest.repository_id == repository_id)
            .scalar() or 0
        )

        data = _RepoBulkData(
            installation=installation,
            test_run_count=test_run_count,
            coverage_count=coverage_count,
            recommendation_count=recommendation_count,
            pr_count=pr_count,
            recent_webhook=False,  # Not used after removing WEBHOOK_INACTIVE state
            github_repo_id=repo.github_repo_id,
        )

        return self._evaluate(repo, data)

    # ------------------------------------------------------------------
    # Public: bulk calculation (one batch of queries for N repos)
    # ------------------------------------------------------------------

    def calculate_readiness_bulk(
        self, repos: List[Repository], workspace_id: UUID
    ) -> Dict[UUID, RepositoryReadinessResult]:
        """
        Compute readiness for all repos in one pass.
        Returns a dict keyed by repository UUID.
        """
        if not repos:
            return {}

        repo_ids = [r.id for r in repos]
        github_repo_ids = [r.github_repo_id for r in repos]

        # One installation per workspace
        installation = (
            self.db.query(GitHubInstallation)
            .filter(GitHubInstallation.workspace_id == workspace_id)
            .first()
        )

        # Batch counts
        test_run_counts: Dict[UUID, int] = dict(
            self.db.query(TestRun.repository_id, func.count(TestRun.id))
            .filter(TestRun.repository_id.in_(repo_ids))
            .group_by(TestRun.repository_id)
            .all()
        )
        coverage_counts: Dict[UUID, int] = dict(
            self.db.query(CoverageReport.repository_id, func.count(CoverageReport.id))
            .filter(CoverageReport.repository_id.in_(repo_ids))
            .group_by(CoverageReport.repository_id)
            .all()
        )
        recommendation_counts: Dict[UUID, int] = dict(
            self.db.query(RecommendationRun.repository_id, func.count(RecommendationRun.id))
            .filter(RecommendationRun.repository_id.in_(repo_ids))
            .group_by(RecommendationRun.repository_id)
            .all()
        )
        pr_counts: Dict[UUID, int] = dict(
            self.db.query(PullRequest.repository_id, func.count(PullRequest.id))
            .filter(PullRequest.repository_id.in_(repo_ids))
            .group_by(PullRequest.repository_id)
            .all()
        )

        results: Dict[UUID, RepositoryReadinessResult] = {}
        for repo in repos:
            data = _RepoBulkData(
                installation=installation,
                test_run_count=test_run_counts.get(repo.id, 0),
                coverage_count=coverage_counts.get(repo.id, 0),
                recommendation_count=recommendation_counts.get(repo.id, 0),
                pr_count=pr_counts.get(repo.id, 0),
                recent_webhook=False,  # Not used after removing WEBHOOK_INACTIVE state
                github_repo_id=repo.github_repo_id,
            )
            results[repo.id] = self._evaluate(repo, data)

        return results

    # ------------------------------------------------------------------
    # Private: deterministic state machine
    # ------------------------------------------------------------------

    def _evaluate(self, repo: Repository, data: _RepoBulkData) -> RepositoryReadinessResult:
        make = RepositoryReadinessResult.make

        # 1. UNKNOWN — no installation linked to workspace
        if data.installation is None:
            return make("UNKNOWN", [
                "Complete GitHub App setup to begin."
            ])

        # 2. REMOVED_OR_INACTIVE — repository removed from GitHub or installation removed
        if not repo.is_active:
            return make("REMOVED_OR_INACTIVE", [
                "Repository no longer available from GitHub installation."
            ])

        # 3. NOT_SELECTED — repo was synced but not opted in for analysis
        if not repo.selected_for_analysis:
            return make("NOT_SELECTED", [
                "Enable this repository to start regression intelligence."
            ])

        # 4. SYNC_FAILED — last sync attempt failed
        if repo.latest_sync_status == "FAILED":
            reason = repo.sync_error or "The last repository sync failed."
            return make("SYNC_FAILED", [reason])

        # 5. NEEDS_TEST_HISTORY — repo synced, no test runs uploaded
        if data.test_run_count == 0:
            return make("NEEDS_TEST_HISTORY", [
                "Upload test results to start regression intelligence."
            ])

        # 6. NEEDS_COVERAGE — test runs exist, no coverage data
        if data.coverage_count == 0:
            return make("NEEDS_COVERAGE", [
                "Upload coverage reports to improve recommendation confidence."
            ])

        # 7. READY — all conditions satisfied
        return make("READY", [
            "Repository ready for regression intelligence."
        ])
