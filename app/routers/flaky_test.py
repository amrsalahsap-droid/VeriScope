import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, BackgroundTasks, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.flaky_test import FlakyTestProfile
from app.models.recalculation_job import FlakyRecalculationJob
from app.schemas.debugging import FlakyRegistryDebugResponse
from app.services.flaky_test_service import FlakyTestService

internal_router = APIRouter(prefix="/internal/flaky-tests", tags=["Flaky Test Diagnostics"])

@internal_router.get("/{repo_id}")
def get_flaky_tests(
    repo_id: UUID,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Diagnostics endpoint to retrieve all flaky, unstable, or quarantined test profiles for a repository.
    Includes pagination, staleness calculations, quarantine details, and failure distributions.
    """
    service = FlakyTestService(db)

    # Calculate total matching count
    total_count = (
        db.query(FlakyTestProfile)
        .filter(
            FlakyTestProfile.repository_id == repo_id,
            FlakyTestProfile.status.in_(["unstable", "quarantined"])
        )
        .count()
    )

    # Fetch paginated collection
    profiles = (
        db.query(FlakyTestProfile)
        .filter(
            FlakyTestProfile.repository_id == repo_id,
            FlakyTestProfile.status.in_(["unstable", "quarantined"])
        )
        .order_by(FlakyTestProfile.test_case_id)
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Proactively check and update staleness metadata
    now = datetime.datetime.utcnow()
    any_stale_changed = False
    for p in profiles:
        if p.last_recalculated_at and (now - p.last_recalculated_at).days >= service.FLAKY_PROFILE_MAX_AGE_DAYS:
            if not p.stale_profile:
                p.stale_profile = True
                any_stale_changed = True

    if any_stale_changed:
        try:
            db.commit()
        except Exception as e:
            db.rollback()

    serialized_profiles = []
    for p in profiles:
        serialized_profiles.append({
            "id": str(p.id),
            "repository_id": str(p.repository_id),
            "test_case_id": str(p.test_case_id),
            "test_name": p.test_case.test_name if p.test_case else "Unknown Test",
            "execution_environment": p.execution_environment,
            "runner_type": p.runner_type,
            "ci_provider": p.ci_provider,
            "test_framework": p.test_framework,
            "failure_rate": p.failure_rate,
            "recent_failure_rate": p.recent_failure_rate,
            "instability_score": p.instability_score,
            "sample_size": p.sample_size,
            "confidence_level": p.confidence_level,
            "status": p.status,
            "last_failure_at": p.last_failure_at.isoformat() if p.last_failure_at else None,
            "stability_recovered_at": p.stability_recovered_at.isoformat() if p.stability_recovered_at else None,
            "last_recalculated_at": p.last_recalculated_at.isoformat() if p.last_recalculated_at else None,
            "stale_profile": p.stale_profile,
            "failure_mode_distribution": p.failure_mode_distribution,
            "quarantined_at": p.quarantined_at.isoformat() if p.quarantined_at else None,
            "quarantine_reason": p.quarantine_reason,
            "quarantine_review_due_at": p.quarantine_review_due_at.isoformat() if p.quarantine_review_due_at else None,
            "quarantined_by": p.quarantined_by,
            "flakiness_calculation_version": p.flakiness_calculation_version,
            "rationale": p.rationale
        })

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "profiles": serialized_profiles
    }

@internal_router.post("/{repo_id}/recalculate", status_code=status.HTTP_202_ACCEPTED)
def recalculate_flaky_tests(
    repo_id: UUID,
    scope: str = Query("FULL_REPOSITORY"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Triggers flakiness recalculations for a repository.
    Enforces storm protection to deduplicate requests, and processes calculations asynchronously.
    """
    # Enforce safe fallback for unsupported scope metrics
    if scope not in ("FULL_REPOSITORY", "RECENT_TESTS", "UNSTABLE_ONLY"):
        scope = "FULL_REPOSITORY"

    service = FlakyTestService(db)
    res = service.trigger_recalculation_job(repo_id, scope=scope)

    # Spawn async processing thread if newly created job
    if res.get("newly_created") and background_tasks:
        background_tasks.add_task(service.run_recalculation, res["job_id"], repo_id)

    return {
        "job_id": str(res["job_id"]),
        "status": res["status"]
    }

@internal_router.get("/{repo_id}/debug", response_model=FlakyRegistryDebugResponse)
def get_flaky_registry_debug(
    repo_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieve forensic explainability data for the Flaky Test Registry of a repository.
    """
    profiles = db.query(FlakyTestProfile).filter(FlakyTestProfile.repository_id == repo_id).all()
    jobs = db.query(FlakyRecalculationJob).filter(FlakyRecalculationJob.repository_id == repo_id).order_by(FlakyRecalculationJob.started_at.desc()).all()

    jobs_list = [
        {
            "job_id": str(job.id),
            "status": job.status,
            "scope": job.recalculation_scope,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message
        }
        for job in jobs
    ]

    telemetry = {
        "recalculation_jobs": jobs_list
    }

    if not profiles:
        return FlakyRegistryDebugResponse(
            raw_inputs={
                "repository_id": str(repo_id),
                "total_profiles": 0,
                "environment_variables": [],
                "runner_specs": [],
                "test_frameworks": [],
                "sample_sizes": []
            },
            derived_relationships={
                "transitions": []
            },
            fallback_heuristics_used=[],
            warnings=["No flaky profiles registered for this repository"],
            confidence_issues=[],
            telemetry=telemetry
        )

    # Extract raw inputs
    env_vars = sorted(list({p.execution_environment for p in profiles if p.execution_environment}))
    runners = sorted(list({p.runner_type for p in profiles if p.runner_type}))
    frameworks = sorted(list({p.test_framework for p in profiles if p.test_framework}))
    sample_sizes = [p.sample_size for p in profiles]

    raw_inputs = {
        "repository_id": str(repo_id),
        "total_profiles": len(profiles),
        "environment_variables": env_vars,
        "runner_specs": runners,
        "test_frameworks": frameworks,
        "sample_sizes": sample_sizes
    }

    # Derived relationships
    transitions = [
        {
            "test_case_id": str(p.test_case_id),
            "test_name": p.test_case.test_name if p.test_case else "Unknown Test",
            "status": p.status,
            "failure_rate": p.failure_rate,
            "recent_failure_rate": p.recent_failure_rate,
            "instability_score": p.instability_score,
            "quarantined_at": p.quarantined_at.isoformat() if p.quarantined_at else None,
            "quarantine_reason": p.quarantine_reason
        }
        for p in profiles
    ]

    derived_relationships = {
        "transitions": transitions
    }

    # Fallback heuristics
    fallback_heuristics_used = []
    if any(p.sample_size < 10 for p in profiles):
        fallback_heuristics_used.append("sparse_history_sample_size_math_fallback")

    # Warnings
    warnings = []
    if any(p.stale_profile for p in profiles):
        warnings.append("stale_profiles_detected")
    if any(p.status == "quarantined" for p in profiles):
        warnings.append("quarantine_preservation_active")

    # Confidence issues
    confidence_issues = []
    if any(p.confidence_level == "LOW" for p in profiles):
        confidence_issues.append("low_confidence_math_ratings")
    if any(p.instability_score > 0.5 for p in profiles):
        confidence_issues.append("high_instability_ratings")

    return FlakyRegistryDebugResponse(
        raw_inputs=raw_inputs,
        derived_relationships=derived_relationships,
        fallback_heuristics_used=fallback_heuristics_used,
        warnings=warnings,
        confidence_issues=confidence_issues,
        telemetry=telemetry
    )

