import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult
from app.models.recommendation import RecommendationRun, RecommendationOutcome

from app.schemas.failure_evidence import (
    FailureEvidenceTestResult,
    FailureEvidenceTestRun,
    FailureEvidencePullRequest,
    FailureEvidenceChangedFile,
    FailureEvidenceRecommendationRun,
    FailureEvidenceRecommendationOutcome,
    FailureEvidenceBundle,
)

logger = logging.getLogger(__name__)

class FailureEvidenceAggregator:
    MAX_FAILED_RUNS_LIMIT = 1000
    GENERATION_VERSION = "v1.2.0"
    NORMALIZATION_RULES_VERSION = "rules.v1"
    EVIDENCE_FILTER_POLICY_VERSION = "policy.v1"

    def __init__(self, db: Session):
        self.db = db

    def collect_failure_evidence(
        self,
        repository_id: uuid.UUID,
        history_window_days: int = 90,
        include_inactive: bool = False,
        evidence_window_end: Optional[datetime] = None
    ) -> FailureEvidenceBundle:
        """
        Gathers normalized, deterministic historical failure evidence within frozen time window.
        Enforces strict trust calibrations, exclusions, limits, and stable sorting.
        """
        # Freeze upper-bound evidence window bounds
        now = evidence_window_end or datetime.utcnow()
        window_start = now - timedelta(days=history_window_days)

        # 1. Fetch and validate repository status
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository with ID {repository_id} not found.")

        # Resolve status
        is_stale_or_inactive = not repo.is_active or repo.missing_from_github_since is not None
        repository_status = "ACTIVE"
        if is_stale_or_inactive:
            deact_reason = repo.deactivation_reason or ""
            if "stale" in deact_reason.lower() or repo.missing_from_github_since is not None:
                repository_status = "STALE"
            else:
                repository_status = "INACTIVE"

            if not include_inactive:
                raise ValueError(f"Repository {repository_id} is inactive/stale (status: {repository_status}).")

        # 2. Gather denominator metrics
        # Count all runs in window
        total_runs_in_window = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= now
        ).count()

        # Count all test results in window
        all_run_ids_q = self.db.query(TestRun.id).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= now
        )
        all_run_ids = [r[0] for r in all_run_ids_q.all()]
        if all_run_ids:
            total_test_results_in_window = self.db.query(TestResult).filter(
                TestResult.test_run_id.in_(all_run_ids)
            ).count()
        else:
            total_test_results_in_window = 0

        # 3. Gather failed test runs before quality filters
        failed_runs_query = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.status == "failed",
            TestRun.created_at >= window_start,
            TestRun.created_at <= now
        )
        all_failed_runs = failed_runs_query.all()

        # Exclude weak or invalid test evidence with backward compatibility
        unsupported_runs_cnt = 0
        insufficient_runs_cnt = 0
        broken_runs_cnt = 0
        replay_drift_runs_cnt = 0

        valid_runs = []
        for run in all_failed_runs:
            # Exclude parser unsupported status
            if run.parser_support_status == "UNSUPPORTED":
                unsupported_runs_cnt += 1
                continue

            # Exclude insufficient health status
            if run.evidence_health_status == "INSUFFICIENT":
                insufficient_runs_cnt += 1
                continue

            # Exclude broken consistency status
            if run.consistency_status == "BROKEN":
                broken_runs_cnt += 1
                continue

            # Exclude replay drift (backward compatibility: treat missing/null as UNKNOWN and do not exclude)
            replay_drift = getattr(run, "replay_drift_detected", None)
            if replay_drift is True:
                replay_drift_runs_cnt += 1
                continue

            valid_runs.append(run)

        excluded_evidence_summary = {
            "unsupported_runs": unsupported_runs_cnt,
            "insufficient_runs": insufficient_runs_cnt,
            "broken_runs": broken_runs_cnt,
            "replay_drift_runs": replay_drift_runs_cnt
        }

        # 4. Deterministic Truncation
        # Sort ASC first deterministically, then apply truncation limit
        sorted_valid_runs = sorted(valid_runs, key=lambda x: (x.created_at or datetime.min, str(x.id)))
        
        total_valid_failed_runs = len(sorted_valid_runs)
        truncated = total_valid_failed_runs > self.MAX_FAILED_RUNS_LIMIT
        truncation_reason = None
        if truncated:
            truncation_reason = f"Max limit of {self.MAX_FAILED_RUNS_LIMIT} failed runs applied."
            sorted_valid_runs = sorted_valid_runs[:self.MAX_FAILED_RUNS_LIMIT]

        final_run_ids = [run.id for run in sorted_valid_runs]

        # 5. Fetch lineage failed results
        failed_test_results = []
        if final_run_ids:
            failed_test_results = self.db.query(TestResult).filter(
                TestResult.test_run_id.in_(final_run_ids),
                TestResult.status.in_(["failed", "error"])
            ).all()

        # 6. Fetch lineage pull requests
        pr_ids = {run.pull_request_id for run in sorted_valid_runs if run.pull_request_id}
        pull_requests = []
        if pr_ids:
            pull_requests = self.db.query(PullRequest).filter(
                PullRequest.id.in_(pr_ids)
            ).all()

        # 7. Fetch changed files
        changed_files = []
        if pr_ids:
            changed_files = self.db.query(PullRequestChangedFile).filter(
                PullRequestChangedFile.pull_request_id.in_(pr_ids)
            ).all()

        # 8. Fetch recommendation runs & outcomes within window
        rec_runs = self.db.query(RecommendationRun).filter(
            RecommendationRun.repository_id == repository_id,
            RecommendationRun.created_at >= window_start,
            RecommendationRun.created_at <= now
        ).all()
        rec_run_ids = [r.id for r in rec_runs]

        outcomes = []
        if rec_run_ids:
            outcomes = self.db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id.in_(rec_run_ids),
                (RecommendationOutcome.rollback_occurred == True) | (RecommendationOutcome.escaped_defect == True)
            ).all()

        # Exclude those that are not linked to the failed test run PRs or the rollback outcomes
        linked_rec_runs_dict = {}
        for r in rec_runs:
            if r.pull_request_id in pr_ids or r.id in {o.recommendation_run_id for o in outcomes}:
                linked_rec_runs_dict[r.id] = r
        linked_recommendations = list(linked_rec_runs_dict.values())

        # 9. Deterministic Sorting
        sorted_results = sorted(failed_test_results, key=lambda x: (x.created_at or datetime.min, str(x.id)))
        sorted_runs = sorted(sorted_valid_runs, key=lambda x: (x.created_at or datetime.min, str(x.id)))
        sorted_prs = sorted(pull_requests, key=lambda x: (x.created_at or datetime.min, str(x.id)))
        sorted_files = sorted(changed_files, key=lambda x: (x.previous_filename or "", x.file_path, str(x.id)))
        sorted_outcomes = sorted(outcomes, key=lambda x: (x.created_at or datetime.min, str(x.id)))
        sorted_recs = sorted(linked_recommendations, key=lambda x: (x.created_at or datetime.min, str(x.id)))

        # 10. Map to Pydantic responses
        results_dto = [
            FailureEvidenceTestResult(
                test_result_id=r.id,
                test_run_id=r.test_run_id,
                test_case_id=r.test_case_id,
                status=r.status,
                duration=r.duration,
                created_at=r.created_at
            ) for r in sorted_results
        ]

        runs_dto = [
            FailureEvidenceTestRun(
                test_run_id=r.id,
                repository_id=r.repository_id,
                commit_sha=r.commit_sha,
                pull_request_id=r.pull_request_id,
                status=r.status,
                failed_tests=r.failed_tests,
                passed_tests=r.passed_tests,
                total_tests=r.total_tests,
                evidence_health_status=r.evidence_health_status,
                consistency_status=r.consistency_status,
                parser_version=r.parser_version,
                normalization_schema_version=r.normalization_schema_version,
                replay_verification_status=r.replay_verification_status or "NOT_VERIFIED",
                parser_support_status=r.parser_support_status or "ACTIVE",
                created_at=r.created_at
            ) for r in sorted_runs
        ]

        prs_dto = [
            FailureEvidencePullRequest(
                pull_request_id=pr.id,
                repository_id=pr.repository_id,
                github_pr_id=pr.github_pr_id,
                number=pr.number,
                title=pr.title,
                author=pr.author,
                state=pr.state,
                head_commit_sha=pr.head_commit_sha,
                created_at=pr.created_at
            ) for pr in sorted_prs
        ]

        files_dto = [
            FailureEvidenceChangedFile(
                changed_file_id=f.id,
                pull_request_id=f.pull_request_id,
                file_path=f.file_path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                previous_filename=f.previous_filename,
                created_at=f.created_at
            ) for f in sorted_files
        ]

        recs_dto = [
            FailureEvidenceRecommendationRun(
                recommendation_run_id=r.id,
                repository_id=r.repository_id,
                pr_id=r.pr_id,
                pull_request_id=r.pull_request_id,
                triggered_by=r.triggered_by,
                evidence_quality=r.evidence_quality,
                recommendation_mode=r.recommendation_mode,
                unsafe_for_optimization=r.unsafe_for_optimization,
                created_at=r.created_at
            ) for r in sorted_recs
        ]


        outcomes_dto = [
            FailureEvidenceRecommendationOutcome(
                recommendation_outcome_id=o.id,
                recommendation_run_id=o.recommendation_run_id,
                executed_tests=o.executed_tests,
                manually_added_tests=o.manually_added_tests,
                manually_removed_tests=o.manually_removed_tests,
                was_followed=o.was_followed,
                override_reason=o.override_reason,
                rollback_occurred=o.rollback_occurred,
                escaped_defect=o.escaped_defect,
                created_at=o.created_at
            ) for o in sorted_outcomes
        ]

        # Summaries
        total_failed_results = len(results_dto)
        total_failed_runs = len(runs_dto)
        distinct_pull_request_count = len(prs_dto)
        rollback_count = sum(1 for o in outcomes_dto if o.rollback_occurred)
        escaped_defect_count = sum(1 for o in outcomes_dto if o.escaped_defect)

        return FailureEvidenceBundle(
            failed_test_results=results_dto,
            related_test_runs=runs_dto,
            related_pull_requests=prs_dto,
            related_changed_files=files_dto,
            linked_incidents=outcomes_dto,
            linked_recommendations=recs_dto,
            repository_id=repository_id,
            repository_status=repository_status,
            evidence_window_start=window_start,
            evidence_window_end=now,
            history_window_days=history_window_days,
            generated_at=datetime.utcnow(),
            generation_version=self.GENERATION_VERSION,
            total_failed_results=total_failed_results,
            total_failed_runs=total_failed_runs,
            distinct_pull_request_count=distinct_pull_request_count,
            rollback_count=rollback_count,
            escaped_defect_count=escaped_defect_count,
            total_runs_in_window=total_runs_in_window,
            total_test_results_in_window=total_test_results_in_window,
            truncated=truncated,
            truncation_reason=truncation_reason,
            max_failed_runs_applied=self.MAX_FAILED_RUNS_LIMIT,
            excluded_evidence_summary=excluded_evidence_summary,
            normalization_rules_version=self.NORMALIZATION_RULES_VERSION,
            evidence_filter_policy_version=self.EVIDENCE_FILTER_POLICY_VERSION
        )
