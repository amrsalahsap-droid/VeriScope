import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.flaky_test import FlakyTestProfile
from app.models.recalculation_job import FlakyRecalculationJob
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.observability import SystemEvent

logger = logging.getLogger("veriscope.flaky_test_service")

class FlakyTestService:
    # Thresholds & Expiration Configs
    MIN_EXECUTIONS = 5
    INSTABILITY_THRESHOLD = 0.1
    FAILURE_RATE_THRESHOLD = 0.1
    RECENT_DECAY_FACTOR = 0.9
    FLAKY_PROFILE_MAX_AGE_DAYS = 14
    FLAKY_RECOVERY_PASSING_RUNS = 10

    def __init__(self, db: Session):
        self.db = db

    def calculate_profile(self, test_case_id: uuid.UUID) -> Optional[FlakyTestProfile]:
        """
        Fetches recent results for a test case, evaluates instability/failure rate metrics,
        determines classification and recovery status, and saves/updates the FlakyTestProfile.
        """
        # Fetch TestCase to confirm it exists
        test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not test_case:
            logger.warning(f"TestCase with ID {test_case_id} not found.")
            return None

        repository_id = test_case.repository_id

        # Fetch up to 50 recent non-skipped TestResult records ordered by created_at descending
        results = (
            self.db.query(TestResult)
            .filter(TestResult.test_case_id == test_case_id)
            .filter(TestResult.status != "skipped")
            .order_by(desc(TestResult.created_at))
            .limit(50)
            .all()
        )

        sample_size = len(results)
        confidence_level = "LOW"
        if sample_size >= 10:
            if sample_size <= 30:
                confidence_level = "MODERATE"
            else:
                confidence_level = "HIGH"

        # Initialize default metrics
        failure_rate = 0.0
        recent_failure_rate = 0.0
        instability_score = 0.0
        failures = 0
        failure_mode_distribution = {
            "assertion_failure": 0,
            "timeout": 0,
            "infra_error": 0,
            "unknown": 0
        }

        # Retrieve existing profile if any
        profile = self.db.query(FlakyTestProfile).filter(FlakyTestProfile.test_case_id == test_case_id).first()
        current_status = profile.status if profile else "stable"
        stability_recovered_at = profile.stability_recovered_at if profile else None

        if sample_size < self.MIN_EXECUTIONS:
            # Insufficient runs to perform flakiness heuristics
            status = current_status if current_status == "quarantined" else "stable"
            rationale = f"Insufficient history to analyze flakiness. Sample size: {sample_size} (minimum {self.MIN_EXECUTIONS} required)."
        else:
            # 1. Failure counts & overall failure rate
            failures = sum(1 for r in results if r.status in ("failed", "error"))
            failure_rate = failures / sample_size

            # 2. Recency-Weighted Failure Rate
            weighted_failure_sum = 0.0
            weight_sum = 0.0
            for i, r in enumerate(results):
                w_i = self.RECENT_DECAY_FACTOR ** i
                is_failed = 1.0 if r.status in ("failed", "error") else 0.0
                weighted_failure_sum += w_i * is_failed
                weight_sum += w_i
            recent_failure_rate = (weighted_failure_sum / weight_sum) if weight_sum > 0 else 0.0

            # 3. Transition Instability Metric
            chrono_results = list(reversed(results))
            transitions = 0
            if len(chrono_results) > 1:
                for i in range(len(chrono_results) - 1):
                    curr_failed = chrono_results[i].status in ("failed", "error")
                    next_failed = chrono_results[i+1].status in ("failed", "error")
                    if curr_failed != next_failed:
                        transitions += 1
                instability_score = transitions / (len(chrono_results) - 1)
            else:
                instability_score = 0.0

            # 4. Failure Mode Keywords Classification
            for r in results:
                if r.status in ("failed", "error"):
                    msg = (r.failure_message or "").lower()
                    trace = (r.stack_trace or "").lower()
                    
                    if "timeout" in msg or "timed out" in msg or "timeout" in trace or "timed out" in trace:
                        failure_mode_distribution["timeout"] += 1
                    elif any(kw in msg for kw in ["infra", "connection refused", "runner crash"]) or any(kw in trace for kw in ["infra", "connection refused", "runner crash"]):
                        failure_mode_distribution["infra_error"] += 1
                    elif any(kw in msg for kw in ["assertion", "expected", "assert", "should be"]) or any(kw in trace for kw in ["assertion", "expected", "assert", "should be"]):
                        failure_mode_distribution["assertion_failure"] += 1
                    else:
                        failure_mode_distribution["unknown"] += 1

            # 5. Stability & Recovery logic
            is_unstable_by_thresholds = (
                instability_score >= self.INSTABILITY_THRESHOLD or
                recent_failure_rate >= self.FAILURE_RATE_THRESHOLD
            )

            last_fail_res = next((r for r in results if r.status in ("failed", "error")), None)
            if current_status == "stable" and stability_recovered_at is not None:
                if last_fail_res is None or last_fail_res.created_at <= stability_recovered_at:
                    is_unstable_by_thresholds = False
                    instability_score = 0.0
                    recent_failure_rate = 0.0
                    failure_rate = 0.0

            if current_status == "quarantined":
                status = "quarantined"
                rationale = profile.rationale if profile else ""
            elif current_status == "unstable":
                # Check for recovery: most recent 10 consecutive runs are all passed
                if sample_size >= self.FLAKY_RECOVERY_PASSING_RUNS and all(r.status == "passed" for r in results[:self.FLAKY_RECOVERY_PASSING_RUNS]):
                    status = "stable"
                    stability_recovered_at = datetime.utcnow()
                    instability_score = 0.0
                    recent_failure_rate = 0.0
                    failure_rate = 0.0
                    rationale = f"Recovered stability: {sample_size} runs, {self.FLAKY_RECOVERY_PASSING_RUNS} consecutive passing runs, recent failure rate 0.0%, confidence {confidence_level}."
                else:
                    status = "unstable"
                    recent_fail_pct = int(recent_failure_rate * 100)
                    last_fail_res = next((r for r in results if r.status in ("failed", "error")), None)
                    last_fail = last_fail_res.created_at.isoformat() if last_fail_res else "N/A"
                    rationale = f"Marked unstable: {failures} failures in {sample_size} runs, recent failure rate {recent_fail_pct}%, instability score {instability_score:.2f}, confidence {confidence_level}. Last failure: {last_fail}."
            else:
                # Previous status was stable
                if is_unstable_by_thresholds:
                    status = "unstable"
                    recent_fail_pct = int(recent_failure_rate * 100)
                    last_fail_res = next((r for r in results if r.status in ("failed", "error")), None)
                    last_fail = last_fail_res.created_at.isoformat() if last_fail_res else "N/A"
                    rationale = f"Marked unstable: {failures} failures in {sample_size} runs, recent failure rate {recent_fail_pct}%, instability score {instability_score:.2f}, confidence {confidence_level}. Last failure: {last_fail}."
                else:
                    status = "stable"
                    rationale = f"Test case is stable: {failures} failures in {sample_size} runs, confidence {confidence_level}."

        # 6. Save or update the database profile record
        if not profile:
            profile = FlakyTestProfile(
                repository_id=repository_id,
                test_case_id=test_case_id,
            )
            self.db.add(profile)

        # Apply updates
        if profile.status != "quarantined":
            profile.status = status
            profile.rationale = rationale[:500] if rationale else None
            profile.stability_recovered_at = stability_recovered_at

        profile.failure_rate = failure_rate
        profile.recent_failure_rate = recent_failure_rate
        profile.instability_score = instability_score
        profile.sample_size = sample_size
        profile.confidence_level = confidence_level
        profile.failure_mode_distribution = failure_mode_distribution

        # Populate environment parameters from latest run if possible
        if results:
            latest_result = results[0]
            test_run = latest_result.test_run
            if test_run:
                profile.execution_environment = test_run.request_origin or "github_actions"
                profile.runner_type = "github-hosted"
                profile.ci_provider = test_run.request_origin or "github_actions"
                profile.test_framework = test_run.parser_version or "junit"

        # Record last failure timestamp
        last_fail_res = next((r for r in results if r.status in ("failed", "error")), None)
        if last_fail_res:
            profile.last_failure_at = last_fail_res.created_at

        profile.last_recalculated_at = datetime.utcnow()
        profile.stale_profile = False

        self.db.flush()
        return profile

    def trigger_recalculation_job(self, repository_id: uuid.UUID, scope: str = "FULL_REPOSITORY") -> Dict[str, Any]:
        """
        Triggers a flakiness recalculation job. Enforces recalculation storm protection:
        if a job is already RUNNING, deduplicates the trigger, logs a SystemEvent, and returns the existing job.
        """
        # Deduplication check
        active_job = (
            self.db.query(FlakyRecalculationJob)
            .filter(
                FlakyRecalculationJob.repository_id == repository_id,
                FlakyRecalculationJob.status == "RUNNING"
            )
            .first()
        )

        if active_job:
            logger.info(f"Deduplicated recalculation job trigger for repository {repository_id}. Active job {active_job.id} exists.")
            # Emit deduplicated SystemEvent
            try:
                event = SystemEvent(
                    id=uuid.uuid4(),
                    entity_type="repository",
                    entity_id=str(repository_id),
                    event_type="flaky_recalculation_deduplicated",
                    payload={
                        "message": "Flaky recalculation deduplicated. Job already running.",
                        "repository_id": str(repository_id),
                        "existing_job_id": str(active_job.id)
                    },
                    created_at=datetime.utcnow()
                )
                self.db.add(event)
                self.db.commit()
            except Exception as e:
                logger.error(f"Failed to persist flaky_recalculation_deduplicated event: {e}")
                self.db.rollback()

            return {"job_id": active_job.id, "status": "RUNNING", "newly_created": False}

        # Register a new RUNNING recalculation job
        new_job = FlakyRecalculationJob(
            id=uuid.uuid4(),
            repository_id=repository_id,
            status="RUNNING",
            recalculation_scope=scope,
            started_at=datetime.utcnow()
        )
        self.db.add(new_job)
        self.db.commit()

        return {"job_id": new_job.id, "status": "RUNNING", "newly_created": True}

    def run_recalculation(self, job_id: uuid.UUID, repository_id: uuid.UUID) -> None:
        """
        Executes the recalculation work. Finds all test cases associated with the repository,
        computes their stability profiles, and updates the recalculation job status upon completion.
        """
        logger.info(f"Starting flakiness recalculation for job {job_id}, repository {repository_id}")
        job = self.db.query(FlakyRecalculationJob).filter(FlakyRecalculationJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found in database.")
            return

        try:
            # Query all test cases in this repository
            test_cases = self.db.query(TestCase).filter(TestCase.repository_id == repository_id).all()
            logger.info(f"Found {len(test_cases)} test cases to recalculate for repository {repository_id}")
            
            for tc in test_cases:
                self.calculate_profile(tc.id)

            # Update job status to COMPLETED
            job.status = "COMPLETED"
            job.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Recalculation job {job_id} completed successfully.")
        except Exception as e:
            logger.exception(f"Error during flakiness recalculation job {job_id}: {e}")
            self.db.rollback()
            try:
                # Re-query inside rollback transaction
                job = self.db.query(FlakyRecalculationJob).filter(FlakyRecalculationJob.id == job_id).first()
                if job:
                    job.status = "FAILED"
                    job.completed_at = datetime.utcnow()
                    job.error_message = str(e)[:1000]
                    self.db.commit()
            except Exception as e2:
                logger.error(f"Failed to mark job {job_id} as FAILED: {e2}")
                self.db.rollback()

    def get_flaky_profiles(self, repository_id: uuid.UUID) -> List[FlakyTestProfile]:
        """
        Retrieves all unstable or quarantined profiles for a repository.
        Proactively applies stale expiration checks if profiles haven't been updated in 14 days.
        """
        profiles = (
            self.db.query(FlakyTestProfile)
            .filter(
                FlakyTestProfile.repository_id == repository_id,
                FlakyTestProfile.status.in_(["unstable", "quarantined"])
            )
            .all()
        )

        # Proactively check for stale status
        now = datetime.utcnow()
        any_stale_changed = False
        for p in profiles:
            if p.last_recalculated_at and (now - p.last_recalculated_at).days >= self.FLAKY_PROFILE_MAX_AGE_DAYS:
                if not p.stale_profile:
                    p.stale_profile = True
                    any_stale_changed = True

        if any_stale_changed:
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"Failed to commit stale profile updates: {e}")
                self.db.rollback()

        return profiles
