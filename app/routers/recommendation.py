from uuid import UUID
from typing import Optional, List
import os
import logging
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db

logger = logging.getLogger(__name__)
from app.schemas.recommendation import (
    RecommendationRunCreate,
    RecommendationRunResponse,
    OutcomeCreate,
    OutcomeResponse,
    FeedbackCreate,
    RecommendationGenerateRequest,
    RecommendationExplanationResponse,
    ChangeImpactGraphResponse,
    EvidenceGapResponse,
    MissingCoverageResponse,
    OutcomeUpdate,
    TestOutcomeUpdate,
    ScenarioOutcomeUpdate,
    OverrideCreate,
    OutcomeDetailResponse,
    TestOutcomeDetailResponse,
    ScenarioOutcomeDetailResponse,
    AttachTestRunRequest,
)
from app.schemas.regression_scope import (
    CreateTargetedScopeRequest,
    CreateTargetedScopeResponse,
    ScopeItemType,
    ScopeItem,
    RegressionScope,
    EvidenceGraphSnapshotReference,
)
from app.schemas.regression_recommendation import (
    RegressionRecommendationRequest,
    RegressionRecommendationResponse,
    RegressionSummaryResponse,
    RegressionOptimizationRequest,
    RegressionOptimizationResponse,
)
from app.services.regression_recommendation_engine import RegressionRecommendationEngine

router = APIRouter()


@router.post("/regression-recommendations", response_model=RegressionRecommendationResponse, status_code=status.HTTP_200_OK)
def generate_regression_recommendations(
    request: RegressionRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Generate regression recommendations based on evidence, risk, and change impact.
    
    Categorizes requirements into REQUIRED, RECOMMENDED, OPTIONAL, or SAFE_TO_SKIP
    based on coverage bucket, risk score, risk band, and change impact level.
    """
    # Convert request to dict format for engine
    requirements_data = [
        {
            "requirement_id": req.requirement_id,
            "coverage_bucket": req.coverage_bucket,
            "risk_score": req.risk_score,
            "risk_band": req.risk_band,
            "change_impact_level": req.change_impact_level,
            "is_verified": req.is_verified
        }
        for req in request.requirements
    ]
    
    # Generate recommendations
    recommendations = RegressionRecommendationEngine.generate_regression_recommendations(requirements_data)
    
    return recommendations


@router.get("/regression-recommendations/summary", response_model=RegressionSummaryResponse, status_code=status.HTTP_200_OK)
def get_regression_recommendation_summary(
    request: RegressionRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Get summary of regression recommendations.
    """
    # Convert request to dict format for engine
    requirements_data = [
        {
            "requirement_id": req.requirement_id,
            "coverage_bucket": req.coverage_bucket,
            "risk_score": req.risk_score,
            "risk_band": req.risk_band,
            "change_impact_level": req.change_impact_level,
            "is_verified": req.is_verified
        }
        for req in request.requirements
    ]
    
    # Generate recommendations
    recommendations = RegressionRecommendationEngine.generate_regression_recommendations(requirements_data)
    
    # Get summary
    summary = RegressionRecommendationEngine.get_recommendation_summary(recommendations)
    
    return summary


@router.post("/regression-recommendations/optimize", response_model=RegressionOptimizationResponse, status_code=status.HTTP_200_OK)
def optimize_regression_scope(
    request: RegressionOptimizationRequest,
    db: Session = Depends(get_db)
):
    """
    Optimize regression scope based on recommendations.
    
    Returns optimized scope with additions and removals.
    """
    # Convert recommendations to dict format
    recommendations_dict = {
        "requiredItems": request.recommendations.requiredItems,
        "recommendedItems": request.recommendations.recommendedItems,
        "optionalItems": request.recommendations.optionalItems,
        "safeToSkipItems": request.recommendations.safeToSkipItems
    }
    
    # Optimize scope
    optimization = RegressionRecommendationEngine.optimize_regression_scope(
        current_scope=request.currentScope,
        recommendations=recommendations_dict
    )
    
    return optimization


from app.schemas.evidence_report import (
    EvidenceReportRequest,
    EvidenceReportResponse,
    EvidenceReport,
    CoveredRequirement,
    PartiallySupportedRequirement,
    MissingCoverageRequirement,
    ExcludedPassedTest,
    UploadedEvidence,
    TargetedScopeSummary,
    EvidenceGraphSnapshotInfo,
)
from app.schemas.debugging import (
    RecommendationDebugResponse,
    RecommendationDetailedDebugResponse
)
from app.schemas.release_decision import (
    ReleaseDecisionSubmit,
    ReleaseDecisionReset,
    ReleaseDecisionHistoryResponse
)
from app.schemas.readiness import RecommendationReadinessGateResponse, ReadinessAcknowledgementCreate
from app.schemas.risk_review import RiskReviewSubmit, BulkAcceptRequest, ResetReviewRequest, RiskReviewHistoryResponse
from app.services.recommendation import RecommendationService
from app.services.analytics import RecommendationAnalyticsService
from app.services.outcome_execution_collector import OutcomeExecutionCollector
from app.dependencies.auth import require_workspace_member, get_current_workspace, get_current_user
from app.models.user import Workspace, User
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService


router = APIRouter(
    prefix="/api/recommendations", 
    tags=["Recommendations"],
    dependencies=[Depends(require_workspace_member())]
)
legacy_router = APIRouter(
    prefix="/recommendations", 
    tags=["Recommendations Legacy"],
    dependencies=[Depends(require_workspace_member())]
)

@router.get("")
def list_recommendation_runs(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """List recent recommendation runs for the current workspace. Workspace-scoped."""
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.models.pull_request import PullRequest

    # Get all repository IDs for this workspace
    repo_ids = [
        r.id for r in db.query(Repository.id).filter(Repository.workspace_id == workspace.id).all()
    ]
    if not repo_ids:
        return {"runs": []}

    runs = (
        db.query(RecommendationRun)
        .filter(RecommendationRun.repository_id.in_(repo_ids))
        .order_by(RecommendationRun.created_at.desc())
        .limit(limit)
        .all()
    )

    # Batch-load repos and PRs
    repo_map = {
        r.id: r for r in db.query(Repository).filter(Repository.id.in_(repo_ids)).all()
    }
    pr_ids = [r.pull_request_id for r in runs if r.pull_request_id]
    pr_map = {}
    if pr_ids:
        pr_map = {
            p.id: p for p in db.query(PullRequest).filter(PullRequest.id.in_(pr_ids)).all()
        }

    result = []
    for run in runs:
        repo = repo_map.get(run.repository_id)
        pr = pr_map.get(run.pull_request_id) if run.pull_request_id else None
        result.append({
            "id": str(run.id),
            "repository_id": str(run.repository_id),
            "repository_full_name": repo.full_name if repo else "unknown",
            "pull_request_number": pr.number if pr else None,
            "pull_request_title": pr.title if pr else None,
            "recommendation_mode": run.recommendation_mode or "NORMAL",
            "evidence_quality": run.evidence_quality or "UNKNOWN",
            "recommended_tests_count": len(run.tests or []),
            "estimated_runtime_seconds": run.estimated_runtime_seconds or 0.0,
            "created_at": run.created_at.isoformat() + "Z" if run.created_at else None,
        })

    return {"runs": result}


@router.post("/generate", response_model=RecommendationRunResponse, status_code=status.HTTP_201_CREATED)
def create_recommendation_run(generate_in: RecommendationGenerateRequest, db: Session = Depends(get_db)):
    """Generate and persist an immutable recommendation run."""
    service = RecommendationService(db)
    
    # Validate generation mode
    mode = generate_in.mode or "confident"
    if mode not in ["draft", "confident"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_GENERATION_MODE",
                "message": "Generation mode must be 'draft' or 'confident'",
                "allowed_modes": ["draft", "confident"]
            }
        )
    
    # Check readiness — backend enforcement, not UI-only.
    # evaluate() is called for BOTH modes so draft is also gated when Input 1 is absent.
    # Any Exception from the readiness service is treated as BLOCKED for confident mode (fail-safe).
    try:
        from app.services.input_readiness_v2_service import InputReadinessV2Service
        _readiness_svc = InputReadinessV2Service(db)
        _readiness = _readiness_svc.assess(
            repository_id=generate_in.repository_id,
            pull_request_id=generate_in.pull_request_id
        )
    except Exception as _exc:
        import logging
        logging.getLogger("veriscope.api").warning(
            f"InputReadinessV2 check raised an exception during generation gate: {_exc}"
        )
        if mode == "confident":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "CONFIDENT_GENERATION_NOT_ALLOWED",
                    "reason": "Readiness check could not be completed. Use draft mode.",
                    "allowed_modes": ["draft"],
                    "blocking_inputs": [],
                    "partial_inputs": [],
                }
            )
        _readiness = None  # allow draft to fall through

    if _readiness is not None:
        if mode == "confident" and not _readiness.can_generate_confident:
            blocking = _readiness.blocking_inputs or []
            partial = _readiness.partial_inputs or []
            primary_reason = _readiness.primary_reason or ""

            if not primary_reason:
                # inputs is a List[InputReadinessItem] — search by input_id
                _input5 = next(
                    (inp for inp in (_readiness.inputs or []) if getattr(inp, 'input_id', None) == "INPUT_5"),
                    None
                )
                if _input5 and _input5.status in ("MISSING", "PARTIAL", "REVIEW_NEEDED", "NEEDS_REVIEW"):
                    primary_reason = "AC \u2192 Test Mapping is partial and unconfirmed."
                else:
                    primary_reason = "Confident generation is not allowed with current readiness state."

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "CONFIDENT_GENERATION_NOT_ALLOWED",
                    "reason": primary_reason,
                    "allowed_modes": ["draft"] if _readiness.can_generate_draft else [],
                    "blocking_inputs": blocking,
                    "partial_inputs": partial,
                    "generation_status": getattr(_readiness, 'generation_status', None),
                }
            )

        if mode == "draft" and not _readiness.can_generate_draft:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "DRAFT_GENERATION_NOT_ALLOWED",
                    "reason": "Minimum inputs (PR package) required for draft generation are missing.",
                    "allowed_modes": [],
                    "blocking_inputs": _readiness.blocking_inputs or [],
                    "partial_inputs": [],
                }
            )
    
    try:
        run_in = RecommendationRunCreate(
            repository_id=generate_in.repository_id,
            pr_id=generate_in.pull_request_id,
            changed_files=generate_in.changed_files,
            triggered_by=generate_in.triggered_by,
            engine_version=generate_in.engine_version,
            readiness_acknowledged=generate_in.readiness_acknowledged,
            generation_mode=mode  # Pass mode to service
        )
        return service.create_recommendation_run(run_in)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND and "pull request" in exc.detail.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)
        raise
    except Exception as exc:
        import logging
        logging.getLogger("veriscope.api").exception(f"Unhandled recommendation generation failure: {exc}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "RECOMMENDATION_GENERATION_FAILED",
                "message": "Veriscope could not generate this recommendation. Please retry.",
                "detail": "Veriscope could not generate the recommendation. Please retry or check backend logs.",
                "error": "Veriscope could not generate the recommendation. Please retry or check backend logs."
            }
        )

@legacy_router.post("", response_model=RecommendationRunResponse, status_code=status.HTTP_201_CREATED)
def legacy_create_recommendation_run(generate_in: RecommendationGenerateRequest, db: Session = Depends(get_db)):
    """Legacy endpoint for generating recommendation runs without /api prefix."""
    return create_recommendation_run(generate_in, db)


@router.post("/{id}/outcome", response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
def record_outcome(id: UUID, outcome_in: OutcomeCreate, db: Session = Depends(get_db)):
    """Record actual execution outcomes and human overrides/feedback."""
    service = RecommendationService(db)
    return service.record_outcome(id, outcome_in)

@legacy_router.post("/{id}/outcome", response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
def legacy_record_outcome(id: UUID, outcome_in: OutcomeCreate, db: Session = Depends(get_db)):
    """Legacy endpoint for recording outcomes."""
    return record_outcome(id, outcome_in, db)


@router.post("/{id}/feedback", response_model=OutcomeResponse, status_code=status.HTTP_200_OK)
def record_feedback(id: UUID, feedback_in: FeedbackCreate, db: Session = Depends(get_db)):
    """Submit human feedback (useful, not_useful, missing_tests) for a recommendation run."""
    service = RecommendationService(db)
    return service.record_feedback(id, feedback_in)

@legacy_router.post("/{id}/feedback", response_model=OutcomeResponse, status_code=status.HTTP_200_OK)
def legacy_record_feedback(id: UUID, feedback_in: FeedbackCreate, db: Session = Depends(get_db)):
    """Legacy endpoint for recording feedback."""
    return record_feedback(id, feedback_in, db)

@router.get("/{id}/feedback/github", status_code=status.HTTP_200_OK)
def record_github_feedback(
    id: UUID,
    state: str,
    details: Optional[str] = None,
    actor: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Capture human feedback clicked directly from GitHub comment links/buttons."""
    from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
    try:
        RecommendationEngineerFeedbackCapture.capture_feedback(
            db=db,
            recommendation_run_id=id,
            feedback_type=state,
            feedback_text=details,
            created_by=actor
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    return {"status": "success", "message": f"Feedback '{state}' captured successfully. Thank you!"}


@router.post("/{id}/feedback/useful", status_code=status.HTTP_200_OK)
def record_signed_feedback_useful(
    id: UUID,
    token: str = Query(..., description="Signed token"),
    sig: str = Query(..., description="Signature"),
    db: Session = Depends(get_db)
):
    """Capture 'useful' feedback via signed URL from GitHub PR comment."""
    from app.services.signed_url_generator import signed_url_generator
    from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
    
    # Validate signature
    payload = signed_url_generator.validate_signature(token, sig)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired signature"
        )
    
    # Verify recommendation run ID matches
    if str(payload["recommendation_run_id"]) != str(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recommendation run ID mismatch"
        )
    
    # Verify feedback type
    if payload["feedback_type"] != "useful":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback type mismatch"
        )
    
    # Capture feedback
    try:
        RecommendationEngineerFeedbackCapture.capture_feedback(
            db=db,
            recommendation_run_id=id,
            feedback_type="USEFUL",
            feedback_text="Feedback from GitHub PR comment",
            created_by="github_pr_comment"
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    
    return {"status": "success", "message": "Feedback captured successfully. Thank you!"}


@router.post("/{id}/feedback/not-useful", status_code=status.HTTP_200_OK)
def record_signed_feedback_not_useful(
    id: UUID,
    token: str = Query(..., description="Signed token"),
    sig: str = Query(..., description="Signature"),
    db: Session = Depends(get_db)
):
    """Capture 'not-useful' feedback via signed URL from GitHub PR comment."""
    from app.services.signed_url_generator import signed_url_generator
    from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
    
    # Validate signature
    payload = signed_url_generator.validate_signature(token, sig)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired signature"
        )
    
    # Verify recommendation run ID matches
    if str(payload["recommendation_run_id"]) != str(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recommendation run ID mismatch"
        )
    
    # Verify feedback type
    if payload["feedback_type"] != "not-useful":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback type mismatch"
        )
    
    # Capture feedback
    try:
        RecommendationEngineerFeedbackCapture.capture_feedback(
            db=db,
            recommendation_run_id=id,
            feedback_type="NOT_USEFUL",
            feedback_text="Feedback from GitHub PR comment",
            created_by="github_pr_comment"
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    
    return {"status": "success", "message": "Feedback captured successfully. Thank you!"}


@router.post("/{id}/feedback/missing-tests", status_code=status.HTTP_200_OK)
def record_signed_feedback_missing_tests(
    id: UUID,
    token: str = Query(..., description="Signed token"),
    sig: str = Query(..., description="Signature"),
    db: Session = Depends(get_db)
):
    """Capture 'missing-tests' feedback via signed URL from GitHub PR comment."""
    from app.services.signed_url_generator import signed_url_generator
    from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
    
    # Validate signature
    payload = signed_url_generator.validate_signature(token, sig)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired signature"
        )
    
    # Verify recommendation run ID matches
    if str(payload["recommendation_run_id"]) != str(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recommendation run ID mismatch"
        )
    
    # Verify feedback type
    if payload["feedback_type"] != "missing-tests":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback type mismatch"
        )
    
    # Capture feedback
    try:
        RecommendationEngineerFeedbackCapture.capture_feedback(
            db=db,
            recommendation_run_id=id,
            feedback_type="MISSING_TESTS",
            feedback_text="Feedback from GitHub PR comment",
            created_by="github_pr_comment"
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    
    return {"status": "success", "message": "Feedback captured successfully. Thank you!"}

@legacy_router.get("/{id}/feedback/github", status_code=status.HTTP_200_OK)
def legacy_record_github_feedback(
    id: UUID,
    state: str,
    details: Optional[str] = None,
    actor: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Legacy endpoint for capturing feedback clicked from GitHub comments."""
    return record_github_feedback(id, state, details, actor, db)


@router.get("/{recommendation_run_id}")
def get_recommendation_run(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve a recommendation run with full structured detail. Workspace-scoped."""
    from app.models.recommendation import (
        RecommendationRun, RecommendationExplanation, RecommendationOutcome,
        RecommendationTestOutcome, SuggestedScenarioOutcome, RecommendationOverride
    )
    from app.models.repository import Repository
    from app.models.pull_request import PullRequest, PullRequestChangedFile
    from app.models.coverage import CoverageReport
    from app.models.test_result import TestCase
    from app.services.recommendation_reasoning_engine import RecommendationReasoningEngine

    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation run not found.")

    # Workspace scope check
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Check if the PR head SHA has changed since generation, and reset acknowledgement
    if run.pull_request and run.pr_snapshot:
        if run.pull_request.head_commit_sha != run.pr_snapshot.head_commit_sha:
            if run.readiness_acknowledged:
                run.readiness_acknowledged = False
                run.readiness_acknowledged_at = None
                run.readiness_acknowledged_missing_inputs = None
                run.readiness_decision = None
                db.add(run)
                db.commit()
                db.refresh(run)

    pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
    
    # Part 6: Evaluate staleness and build PR package response
    from app.services.recommendation_input_freshness_service import RecommendationInputFreshnessService
    staleness_result = RecommendationInputFreshnessService.evaluate_recommendation_input_freshness(
        db, run, pr
    )
    
    # Resolve current usable changed-file evidence once for the package response.
    from app.services.input_readiness_v2_service import InputReadinessV2Service
    changed_files_evidence = InputReadinessV2Service.get_changed_files_evidence(db, pr) if pr else {
        "changed_files_count": 0,
        "changed_file_paths_available": False,
        "changed_files": [],
        "changed_files_source": None,
        "head_commit_sha": None,
        "evidence_successful": False,
        "evidence_error": "Pull request is unavailable.",
    }
    changed_files_details = changed_files_evidence["changed_files"]
    
    # Build PR package readiness from snapshot or current state
    pr_package_readiness = {
        "status": "READY",
        "blockers": [],
        "warnings": []
    }
    
    if pr:
        # Fetch changed files database rows to be accurate
        changed_files_db = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).order_by(PullRequestChangedFile.file_path.asc()).all()
        
        changed_files_count = pr.changed_files_count if pr.changed_files_count is not None else len(changed_files_db)

        if not pr.head_commit_sha:
            pr_package_readiness["status"] = "BLOCKED"
            pr_package_readiness["blockers"].append("HEAD_SHA_MISSING")
        elif changed_files_count <= 0:
            pr_package_readiness["status"] = "BLOCKED"
            pr_package_readiness["blockers"].append("CHANGED_FILES_MISSING")
        elif not changed_files_evidence["changed_file_paths_available"]:
            pr_package_readiness["status"] = "PARTIAL"
            pr_package_readiness["warnings"].append("CHANGED_FILE_PATHS_UNAVAILABLE")
        else:
            pr_package_readiness["status"] = "READY"
            if changed_files_evidence["changed_files_source"] == "cached_pr_package":
                pr_package_readiness["warnings"].append("CHANGED_FILES_FROM_CACHE")

        if pr.evidence_truncated:
            pr_package_readiness["status"] = "PARTIAL"
            pr_package_readiness["warnings"].append("LARGE_DIFF_TRUNCATED")
            
        # Check for patch missing warnings
        missing_patch = [f.file_path for f in changed_files_db if not f.patch_summary]
        if missing_patch:
            pr_package_readiness["warnings"].append("PATCH_MISSING")
    
    # Generation-time readiness cannot override current missing changed-file paths.
    if (
        run.pr_package_ready_at_generation is not None
        and changed_files_evidence["changed_file_paths_available"]
    ):
        pr_package_readiness["status"] = "READY" if run.pr_package_ready_at_generation else "BLOCKED"

    # Compute recommendation_audit details
    from app.models.pull_request import PullRequestSnapshot
    audit_status = "UNKNOWN"
    has_snapshot = False
    has_direct_snapshot_json = False
    snapshot_head_sha = None
    is_stale = False
    stale_reason = None
    message = None

    if not run:
        audit_status = "NO_RECOMMENDATION_YET"
        message = "No recommendation generated yet for this pull request."
    else:
        # Check for pr_snapshot_id linked to snapshot
        snapshot = None
        if run.pr_snapshot_id:
            snapshot = db.query(PullRequestSnapshot).filter(
                PullRequestSnapshot.id == run.pr_snapshot_id
            ).first()

        if snapshot:
            has_snapshot = True
            snapshot_head_sha = snapshot.head_commit_sha
            
            if pr and pr.head_commit_sha != snapshot.head_commit_sha:
                audit_status = "OUTDATED"
                is_stale = True
                stale_reason = f"PR head commit SHA changed from {snapshot.head_commit_sha} to {pr.head_commit_sha}."
                message = f"Generated from {snapshot.head_commit_sha[:7]} (outdated), current PR head is {pr.head_commit_sha[:7]}. Regenerate before signoff."
            else:
                audit_status = "AUDITABLE"
                message = "Recommendation has an auditable PR package snapshot."
        
        # Fallback to direct snapshot JSON fields
        elif run.head_commit_sha_at_generation and run.changed_files_snapshot_json:
            has_direct_snapshot_json = True
            snapshot_head_sha = run.head_commit_sha_at_generation
            
            if pr and pr.head_commit_sha != run.head_commit_sha_at_generation:
                audit_status = "OUTDATED"
                is_stale = True
                stale_reason = f"PR head commit SHA changed from {run.head_commit_sha_at_generation} to {pr.head_commit_sha}."
                message = f"Generated from {run.head_commit_sha_at_generation[:7]} (outdated), current PR head is {pr.head_commit_sha[:7]}. Regenerate before signoff."
            else:
                audit_status = "AUDITABLE"
                message = "Recommendation has an auditable PR package snapshot."
        
        else:
            audit_status = "LEGACY_NO_SNAPSHOT"
            message = "Existing recommendation predates PR package snapshot support. Regenerate for auditability."

    recommendation_audit_obj = {
        "status": audit_status,
        "has_snapshot": has_snapshot,
        "has_direct_snapshot_json": has_direct_snapshot_json,
        "snapshot_head_sha": snapshot_head_sha,
        "current_head_sha": pr.head_commit_sha if pr else None,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "message": message
    }

    # Generate plain-English explanations
    engine = RecommendationReasoningEngine(db)
    explanation = engine.explain(run)

    # Recover changed files
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        raw = run.input_snapshot.changed_files
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    changed_files.append(item)
                elif isinstance(item, dict):
                    fp = item.get("file_path") or item.get("filename")
                    if fp:
                        changed_files.append(fp)
    if not changed_files and pr:
        changed_files = [f.file_path for f in (pr.changed_files or [])]

    # Fetch persisted explanations
    explanations = db.query(RecommendationExplanation).filter(
        RecommendationExplanation.recommendation_run_id == recommendation_run_id
    ).all()
    explanation_map = {e.test_id: e for e in explanations}

    # Fetch RecommendedTest records to map execution status
    from app.models.recommendation import RecommendedTest
    recommended_tests = db.query(RecommendedTest).filter(
        RecommendedTest.recommendation_run_id == recommendation_run_id
    ).all()
    rec_test_map = {rt.test_identifier: rt for rt in recommended_tests}

    # Candidate statuses that mean a test has already been resolved by execution evidence.
    # These must NOT appear under must_run / should_run in the UI.
    _EXECUTION_RESOLVED_STATUSES = {
        "ALREADY_PASSED_CURRENT_PR",
        "FAILED_CURRENT_PR",
        "SKIPPED_CURRENT_PR",
        "STALE_RESULT_RERUN_REQUIRED",
        "NEEDS_MAPPING_REVIEW",
        "NOT_RELEVANT",
    }

    # Build test list with priority tiers from priority_score
    tests = run.tests or []
    test_list = []
    for t in tests:
        score = t.priority_score or 0.0
        if score >= 0.80:
            tier = "must_run"
        elif score >= 0.50:
            tier = "should_run"
        else:
            tier = "fallback"

        # Shorten identity for display
        parts = t.test_case_id.split("::")
        display_name = parts[-1] if parts else t.test_case_id
        suite_name = parts[0] if len(parts) > 1 else ""

        # Dynamically infer properties for description enrichment
        id_lower = t.test_case_id.lower()
        
        # 1. Infer testing type
        types = []
        if "security" in id_lower or "auth" in id_lower or "token" in id_lower or "password" in id_lower:
            types.append("Security")
        if "api" in id_lower or "route" in id_lower:
            types.append("API")
        if "integration" in id_lower or "workflow" in id_lower:
            types.append("Integration")
        if "ui" in id_lower or "page" in id_lower or "form" in id_lower:
            types.append("UI")
        if not types:
            types.append("Unit")
        if "regression" in id_lower or len(types) > 0:
            types.append("Regression")
        testing_type = " / ".join(types)

        # 2. Infer impacted area
        if "password" in id_lower:
            impacted_area = "Password Reset"
        elif "auth" in id_lower or "token" in id_lower:
            impacted_area = "Authentication"
        elif "signup" in id_lower or "sign-up" in id_lower or "user" in id_lower:
            impacted_area = "User Registration"
        elif "security" in id_lower:
            impacted_area = "Security Validation"
        elif "billing" in id_lower or "subscription" in id_lower or "invoice" in id_lower:
            impacted_area = "Billing"
        else:
            impacted_area = "General"

        # 3. Dynamic personalized reason
        changed_areas = []
        if any("auth" in f.lower() or "token" in f.lower() for f in changed_files):
            changed_areas.append("authentication")
        if any("password" in f.lower() for f in changed_files):
            changed_areas.append("password reset")
        if any("signup" in f.lower() or "sign-up" in f.lower() for f in changed_files):
            changed_areas.append("user registration")
        
        area_str = " and ".join(changed_areas) if changed_areas else "core logic"
        clean_test_name = display_name.replace("_", " ")
        custom_reason = f"Recommended because this PR changes {area_str} flows, and this test validates {clean_test_name} behavior."

        # 4. Matched signals list
        signals = []
        if "direct_file_coverage" in t.reason_type or t.reason_type == "coverage_link":
            signals.append({"name": "Domain match", "value": "Authentication"})
        if "auth" in id_lower or "token" in id_lower:
            signals.append({"name": "Token overlap", "value": "auth/token"})
        if "failed" in id_lower or t.reason_type in ("historical_fragility", "scoped_historical_failure"):
            signals.append({"name": "Historical failure", "value": "failed recently"})
        
        if not signals:
            signals.append({"name": "Path fallback", "value": "convention matched"})

        confidence = "HIGH" if score >= 80 else "MEDIUM" if score >= 50 else "LOW"

        # Fetch explanation if exists
        explanation_record = explanation_map.get(t.test_case_id)
        if explanation_record:
            triggered_files_list = explanation_record.triggered_files or []
            domains_list = explanation_record.domains or []
            testing_types_list = explanation_record.testing_types or []
            signals_trace_list = explanation_record.signals or []
            score_breakdown_dict = explanation_record.score_breakdown or {}
            explanation_reason = explanation_record.reason or custom_reason
        else:
            triggered_files_list = []
            domains_list = []
            testing_types_list = []
            signals_trace_list = []
            score_breakdown_dict = {}
            explanation_reason = custom_reason

        rt = rec_test_map.get(t.test_case_id)
        candidate_status = rt.candidate_status if rt else None
        active_action = rt.active_action if rt else "RUN_NOW"
        included_val = rt.included if rt else True
        mapping_uncertainty_val = rt.mapping_uncertainty if rt else None

        # Execution-aware tier: override score-based tier when execution evidence is conclusive.
        # ALREADY_PASSED_CURRENT_PR -> must NOT appear under must_run/should_run.
        # FAILED_CURRENT_PR / SKIPPED_CURRENT_PR -> separate bucket, not must_run.
        # STALE_RESULT_RERUN_REQUIRED -> flagged separately, treated as must_run for urgency.
        if candidate_status == "ALREADY_PASSED_CURRENT_PR":
            execution_aware_tier = "already_verified"
        elif candidate_status == "FAILED_CURRENT_PR":
            execution_aware_tier = "failed_current_pr"
        elif candidate_status == "SKIPPED_CURRENT_PR":
            execution_aware_tier = "skipped_current_pr"
        elif candidate_status == "STALE_RESULT_RERUN_REQUIRED":
            execution_aware_tier = "stale_rerun_required"
        elif candidate_status == "NEEDS_MAPPING_REVIEW":
            execution_aware_tier = "mapping_review_needed"
        elif candidate_status in ("NOT_EXECUTED_FOR_CURRENT_PR", "MUST_RUN", "SHOULD_RUN", "OPTIONAL", None):
            execution_aware_tier = tier
        else:
            execution_aware_tier = tier

        # Use the evidence_path persisted on RecommendedTest when available;
        # fall back to live computation for runs generated before persistence was added.
        if rt and rt.evidence_path:
            evidence_path_list = rt.evidence_path
        else:
            from app.services.traceability_graph_service import TraceabilityGraphService
            evidence_path_list = TraceabilityGraphService.get_evidence_path_for_recommendation(
                db=db,
                repository_id=run.repository_id,
                pull_request_id=run.pull_request_id,
                test_id=t.test_case_id
            )
        
        would_priority = "MUST_RUN" if (score >= 80 or score >= 0.8) else "SHOULD_RUN" if (score >= 50 or score >= 0.5) else "OPTIONAL"

        test_list.append({
            "stable_identity": t.test_case_id,
            "display_name": display_name,
            "suite_name": suite_name,
            "tier": tier,
            "execution_aware_tier": execution_aware_tier,
            "priority_score": round(score, 3),
            "reason_type": t.reason_type,
            "reason": explanation_reason,
            "testing_type": " / ".join([x.title() for x in testing_types_list]) if testing_types_list else testing_type,
            "impacted_area": " / ".join([x.title() for x in domains_list]) if domains_list else impacted_area,
            "confidence": confidence,
            "signals": signals,
            "triggered_files": triggered_files_list,
            "domains": domains_list,
            "testing_types": testing_types_list,
            "signals_trace": signals_trace_list,
            "score_breakdown": score_breakdown_dict,
            "candidate_status": candidate_status,
            "active_action": active_action,
            "included": included_val,
            "mapping_uncertainty": mapping_uncertainty_val,
            "evidence_path": evidence_path_list,
            "would_have_been_priority": would_priority
        })

    # Sort: must_run first, then should_run, then fallback; within tier by priority_score desc
    tier_order = {"must_run": 0, "should_run": 1, "fallback": 2}
    test_list.sort(key=lambda x: (tier_order[x["tier"]], -x["priority_score"]))

    # Build execution-aware bucketed lists.
    # These are the canonical source of truth for UI bucketing — never use raw tier for this.
    already_verified_tests = [t for t in test_list if t["execution_aware_tier"] == "already_verified"]
    must_run_tests = [t for t in test_list if t["execution_aware_tier"] == "must_run"]
    should_run_tests = [t for t in test_list if t["execution_aware_tier"] == "should_run"]
    failed_current_pr_tests = [t for t in test_list if t["execution_aware_tier"] == "failed_current_pr"]
    skipped_current_pr_tests = [t for t in test_list if t["execution_aware_tier"] == "skipped_current_pr"]
    stale_rerun_required_tests = [t for t in test_list if t["execution_aware_tier"] == "stale_rerun_required"]
    mapping_review_needed_tests = [t for t in test_list if t["execution_aware_tier"] == "mapping_review_needed"]
    not_executed_tests = [t for t in test_list if t["execution_aware_tier"] == "fallback" and t["candidate_status"] in ("NOT_EXECUTED_FOR_CURRENT_PR", None)]

    # Evidence signals
    original_mode = run.recommendation_mode or "NORMAL"
    quality = run.evidence_quality or "UNKNOWN"

    coverage_report = None
    cr = None
    if run.coverage_report_id:
        cr = db.query(CoverageReport).filter(CoverageReport.id == run.coverage_report_id).first()
        if cr:
            coverage_report = {
                "commit_sha": cr.commit_sha,
                "confidence": cr.confidence_score,
                "files_total": cr.files_total,
                "line_coverage_ratio": round(cr.line_coverage_ratio, 3) if cr.line_coverage_ratio else None,
                "created_at": cr.created_at.isoformat() + "Z" if cr.created_at else None,
            }

    # Dynamic calculation of impact profile and testing strategy
    from app.services.pr_impact_analyzer import PRImpactAnalyzer
    from app.services.testing_strategy_generator import TestingStrategyGenerator
    
    impact_profile = run.impact_profile
    if not impact_profile and changed_files:
        impact_profile = PRImpactAnalyzer.analyze_pr_impact(
            title=pr.title if pr else "Implement modern password validation rules and fix test suites",
            description="",
            changed_files=changed_files
        )
    
    strategy = TestingStrategyGenerator.generate(impact_profile or {}, {"risk_level": run.risk_level or "LOW"})

    # Determine the recommendation mode dynamically to prevent contradictions
    selected_tests_count = len(test_list)
    full_suite_count = db.query(TestCase).filter(TestCase.repository_id == run.repository_id).count()
    
    if selected_tests_count >= full_suite_count and full_suite_count > 0:
        mode = "FULL_SUITE"
    else:
        # Check if we have strong exact mappings (DIRECT coverage or DIRECT test coverage links)
        has_strong_mapping = False
        if cr and run.coverage_report_id:
            direct_entries = [e for e in run.reasoning_entries if e.reason_type == "direct_file_coverage"]
            if direct_entries:
                has_strong_mapping = True
        
        if has_strong_mapping:
            mode = "TARGETED"
        else:
            mode = "CONSERVATIVE"

    # Derive risk level
    if mode in ("FULL_REGRESSION", "FULL_SUITE", "SAFE_FALLBACK") or quality in ("LOW", "UNKNOWN"):
        risk_level = "HIGH"
    elif mode == "WIDENED" or quality == "MODERATE":
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # Warnings
    warnings = []
    if mode in ("CONSERVATIVE", "FULL_SUITE"):
        mode_labels = {"CONSERVATIVE": "conservative fallback", "FULL_SUITE": "full regression"}
        warnings.append(f"Engine used {mode_labels.get(mode, mode)} — coverage evidence was insufficient for targeted selection.")
    if quality == "LOW":
        warnings.append("Coverage confidence is low. Test selection is broader than usual.")
    if run.unsafe_for_optimization:
        warnings.append("This PR has evidence integrity issues. Results should be treated as advisory.")

    # Detect Evidence Gaps & Analyze Missing Coverage & Generate Testing Scope
    from app.services.evidence_gap_detector import EvidenceGapDetector
    from app.services.missing_coverage_analyzer import MissingCoverageAnalyzer
    from app.services.testing_scope_generator import TestingScopeGenerator
    evidence_gaps = EvidenceGapDetector.detect_gaps(db, run, explanations)
    missing_coverage = MissingCoverageAnalyzer.analyze_missing_coverage(db, run, changed_files)
    testing_scope = TestingScopeGenerator.generate_scope(db, run, changed_files)

    from app.services.recommendation_quality_evaluator import RecommendationQualityEvaluator
    quality_assessment = RecommendationQualityEvaluator.evaluate_quality(run.recommended_tests)

    # Evaluate impacted area coverage sufficiency
    from app.services.impacted_area_coverage_sufficiency import ImpactedAreaCoverageSufficiency
    from app.models.test_coverage_link import TestCoverageLink
    from app.models.test_result import TestCase
    
    existing_tcs = db.query(TestCase).filter(TestCase.repository_id == run.repository_id).all()
    kg_links = []
    coverage_entries = []
    if cr:
        kg_links = cr.test_links
        coverage_entries = cr.file_entries
    else:
        kg_links = db.query(TestCoverageLink).filter(TestCoverageLink.repository_id == run.repository_id).all()

    sufficiency_results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=impact_profile.get("affected_domains", []) if impact_profile else [],
        changed_files=changed_files,
        existing_test_inventory=existing_tcs,
        recommended_tests=run.tests or [],
        coverage_file_entries=coverage_entries,
        knowledge_graph_links=kg_links,
        suggested_scenarios=run.suggested_scenarios or [],
        coverage_confidence=run.evidence_quality or "HIGH"
    )

    # Build scenario coverage matrix
    from app.services.scenario_coverage_matrix_builder import ScenarioCoverageMatrixBuilder
    
    scenario_coverage_matrix = None
    try:
        scenario_coverage_matrix = ScenarioCoverageMatrixBuilder.build_matrix(
            db=db,
            recommendation_run_id=recommendation_run_id
        )
        # Convert to dict for JSON response
        scenario_coverage_matrix_dict = {
            "recommendation_run_id": scenario_coverage_matrix.recommendation_run_id,
            "repository_id": scenario_coverage_matrix.repository_id,
            "pull_request_id": scenario_coverage_matrix.pull_request_id,
            "total_scenarios": scenario_coverage_matrix.total_scenarios,
            "covered_and_verified": scenario_coverage_matrix.covered_and_verified,
            "covered_not_run": scenario_coverage_matrix.covered_not_run,
            "partially_covered": scenario_coverage_matrix.partially_covered,
            "missing_automated_coverage": scenario_coverage_matrix.missing_automated_coverage,
            "suggest_manual_validation": scenario_coverage_matrix.suggest_manual_validation,
            "items": [
                {
                    "scenario_intent_key": item.scenario_intent_key,
                    "title": item.title,
                    "impacted_area": item.impacted_area,
                    "testing_type": item.testing_type,
                    "priority": item.priority,
                    "existing_tests": [
                        {
                            "test_identifier": et.test_identifier,
                            "test_name": et.test_name,
                            "suite_name": et.suite_name,
                            "class_name": et.class_name,
                            "last_execution_status": et.last_execution_status,
                            "last_execution_timestamp": et.last_execution_timestamp
                        }
                        for et in item.existing_tests
                    ],
                    "suggested_scenarios": [
                        {
                            "scenario_id": ss.scenario_id,
                            "title": ss.title,
                            "testing_type": ss.testing_type,
                            "priority": ss.priority,
                            "automation_candidate": ss.automation_candidate,
                            "preconditions": ss.preconditions,
                            "steps": ss.steps,
                            "expected_result": ss.expected_result,
                            "test_data": ss.test_data
                        }
                        for ss in item.suggested_scenarios
                    ],
                    "code_coverage_status": item.code_coverage_status,
                    "current_pr_execution_status": item.current_pr_execution_status,
                    "final_status": item.final_status,
                    "recommendation_action": item.recommendation_action.value,
                    "evidence_reason": item.evidence_reason,
                    "confidence": item.confidence,
                    "domain": item.domain,
                    "feature": item.feature,
                    "layer": item.layer,
                    "case_type": item.case_type
                }
                for item in scenario_coverage_matrix.items
            ],
            "generated_at": scenario_coverage_matrix.generated_at
        }
    except Exception as e:
        import logging
        logging.getLogger("veriscope.api").exception(f"Failed to build scenario coverage matrix: {e}")
        scenario_coverage_matrix_dict = None

    # Fetch recommended manual tests for the response
    manual_tests_response = []
    if pr:
        from app.models.external_test_case_detailed import ExternalTestCase
        # Get manual test cases for this repository
        manual_tests = db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == run.repository_id,
            ExternalTestCase.automation_status == "MANUAL",
            ExternalTestCase.is_active == True
        ).all()
        for mt in manual_tests:
            manual_tests_response.append({
                "id": str(mt.id),
                "title": mt.title
            })

    return {
        "id": str(run.id),
        "created_at": run.created_at.isoformat() + "Z" if run.created_at else None,
        "triggered_by": run.triggered_by,
        "recommendation_quality": quality_assessment,
        "manual_tests": manual_tests_response,
        "repository": {
            "id": str(repo.id),
            "full_name": repo.full_name,
        },
        "pull_request": {
            "id": str(pr.id) if pr else None,
            "number": pr.number if pr else None,
            "title": pr.title if pr else None,
            "source_branch": pr.source_branch if pr else None,
            "target_branch": pr.target_branch if pr else None,
        } if pr else None,
        # Part 6: PR Package and recommendation_audit at the root
        "pr_package": {
            "status": pr_package_readiness["status"],
            "head_commit_sha": changed_files_evidence["head_commit_sha"],
            "changed_files_count": changed_files_evidence["changed_files_count"],
            "changed_file_paths_available": changed_files_evidence["changed_file_paths_available"],
            "changed_files": changed_files_details,
            "changed_files_source": changed_files_evidence["changed_files_source"],
            "evidence_successful": changed_files_evidence["evidence_successful"],
            "evidence_error": changed_files_evidence["evidence_error"],
            "blockers": pr_package_readiness["blockers"],
            "warnings": pr_package_readiness["warnings"]
        } if pr else None,
        "recommendation_audit": recommendation_audit_obj,
        # Generation-time readiness snapshot
        "readiness_snapshot": {
            "readiness_snapshot_available": run.readiness_snapshot_available,
            "readiness_score": run.readiness_score_at_generation,
            "readiness_level": run.readiness_level_at_generation,
            "expected_confidence": run.expected_confidence_at_generation,
            "confidence_ceiling": run.confidence_ceiling_at_generation,
            "confidence_reason": run.confidence_reason_at_generation,
            "can_generate": run.can_generate_at_generation,
            "available_inputs": run.available_inputs_at_generation,
            "missing_inputs": run.missing_inputs_at_generation,
            "blocking_inputs": run.blocking_inputs_at_generation,
            "confidence_limiters": run.confidence_limiters_at_generation,
            "evidence_summary": run.evidence_summary_at_generation,
            "generated_from_repository_id": str(run.generated_from_repository_id) if run.generated_from_repository_id else None,
            "generated_from_pull_request_id": str(run.generated_from_pull_request_id) if run.generated_from_pull_request_id else None,
            "generation_context_version": run.generation_context_version,
        } if run.readiness_snapshot_available else None,
        # Section 1: Executive Summary
        "executive_summary": {
            "changed_files": changed_files,
            "changed_files_count": len(changed_files),
            "risk_level": risk_level,
            "bullets": explanation["executive_summary"],
            "impact_profile": impact_profile or {},
        },
        # Section 2: Testing Strategy
        "testing_strategy": {
            "recommendation_mode": mode,
            "evidence_quality": quality,
            "optimization_allowed": run.optimization_allowed,
            "must_run_count": len(must_run_tests),
            "should_run_count": len(should_run_tests),
            "fallback_count": sum(1 for t in test_list if t["execution_aware_tier"] == "fallback"),
            "already_verified_count": len(already_verified_tests),
            "failed_current_pr_count": len(failed_current_pr_tests),
            "stale_rerun_required_count": len(stale_rerun_required_tests),
            "mapping_review_needed_count": len(mapping_review_needed_tests),
            "estimated_runtime_seconds": run.estimated_runtime_seconds or 0.0,
            "full_suite_runtime_seconds": run.full_suite_runtime_seconds,
            "runtime_confidence": run.runtime_confidence,
            "skipped_count": run.skipped_count or 0,
            "skipped_reason_summary": run.skipped_reason_summary,
            "types": strategy.get("types", []),
            "summary": strategy.get("summary", ""),
        },
        # Section 3: Recommended Tests (tiered, full list — use execution_aware_tier for bucketing)
        "recommended_tests": test_list,
        # Section 3a: Execution-aware bucketed lists (canonical for UI classification)
        # Already-verified tests must NOT appear under must_run / should_run.
        "already_verified_tests": already_verified_tests,
        "must_run_tests": must_run_tests,
        "should_run_tests": should_run_tests,
        "failed_current_pr_tests": failed_current_pr_tests,
        "skipped_current_pr_tests": skipped_current_pr_tests,
        "stale_rerun_required_tests": stale_rerun_required_tests,
        "mapping_review_needed_tests": mapping_review_needed_tests,
        "not_executed_tests": not_executed_tests,
        # Section 4: Why (risk reasoning bullets)
        "why": explanation["executive_summary"],
        # Section 5: Evidence
        "evidence": {
            "coverage": coverage_report,
            "knowledge_graph": {
                "dependency_state_hash": run.dependency_state_hash,
                "has_dependencies": run.dependency_state_hash not in (None, "empty_dependency_state"),
            },
            "history": {
                "window_start": run.test_history_window_start.isoformat() + "Z" if run.test_history_window_start else None,
                "window_end": run.test_history_window_end.isoformat() + "Z" if run.test_history_window_end else None,
                "flakiness_profile_hash": run.flakiness_profile_hash,
                "has_flakiness_data": run.flakiness_profile_hash not in (None, "empty_flakiness_state"),
            },
            "overrides": {
                "unsafe_for_optimization": run.unsafe_for_optimization,
                "evidence_consistency_status": run.evidence_consistency_status,
                "evidence_health_status": run.evidence_health_status,
            },
        },
        # Warnings
        "warnings": warnings,
        # Section 6: Evidence Gaps
        "evidence_gaps": evidence_gaps,
        # Section 7: Potential Missing Coverage
        "missing_coverage": missing_coverage,
        # Section 8: Testing Scope Recommendations
        "testing_scope": testing_scope,
        # Suggested Test Scenarios
        "suggested_test_scenarios": [
            {
                "id": str(s.id),
                "recommendation_run_id": str(s.recommendation_run_id),
                "title": s.title,
                "testing_type": s.testing_type,
                "impacted_area": s.impacted_area,
                "priority": s.priority,
                "preconditions": s.preconditions or [],
                "test_data": s.test_data or {},
                "steps": s.steps or [],
                "expected_result": s.expected_result,
                "automation_candidate": s.automation_candidate,
                "related_changed_files": s.related_changed_files or [],
                "reason": s.reason,
                "confidence": s.confidence,
                "source_signal": s.source_signal,
                "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
            }
            for s in (run.suggested_scenarios or [])
        ],
        # Scenario Coverage Matrix
        "scenario_coverage_matrix": scenario_coverage_matrix_dict,
        # Business Intent Sections
        "business_intent": impact_profile.get("business_intent_coverage_matrix") if impact_profile else None,
        # Fragility Intelligence
        "fragility": _build_fragility_response(db, run, changed_files, impact_profile),
        # Acceptance Criteria - get from input snapshot if available, otherwise from signal breakdown
        "acceptance_criteria": _build_acceptance_criteria_response(db, run, impact_profile),
        "requirement_gaps": impact_profile.get("requirement_gap_report", {}).get("gaps", []) if impact_profile else [],
        "business_intent_coverage_matrix": impact_profile.get("business_intent_coverage_matrix") if impact_profile else None,
        "pr_description_template_suggestion": impact_profile.get("pr_description_template_suggestion") if impact_profile else None,
        # Phase 2I: Completeness Assessment
        "completeness_assessment": impact_profile.get("completeness_assessment") if impact_profile else None,
        # Readiness and acknowledgement fields
        "readiness_acknowledged": run.readiness_acknowledged,
        "readiness_acknowledged_at": run.readiness_acknowledged_at.isoformat() + "Z" if run.readiness_acknowledged_at else None,
        "readiness_acknowledged_missing_inputs": run.readiness_acknowledged_missing_inputs,
        "readiness_decision": run.readiness_decision,
        # Outcome Summary
        "outcome": _build_outcome_summary(db, recommendation_run_id),
        # Staleness fields
        "input_stale": run.input_stale,
        "stale_reason": run.stale_reason,
        "stale_since": run.stale_since.isoformat() + "Z" if run.stale_since else None,
        "stale_input_types": run.stale_input_types,
        # Generation gate fields
        "is_draft": getattr(run, 'is_draft', False) or False,
        "generation_mode": getattr(run, 'generation_mode', None) or "confident",
        "generation_blocked_reason": getattr(run, 'generation_blocked_reason', None),
    }


@legacy_router.get("/{recommendation_run_id}")
def legacy_get_recommendation_run(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Legacy endpoint for retrieving a recommendation run."""
    return get_recommendation_run(recommendation_run_id, workspace, db)


def _build_acceptance_criteria_response(
    db: Session,
    run,
    impact_profile: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """
    Build acceptance criteria response for a recommendation run.

    Prioritizes manually pasted AC from input snapshot, falls back to signal breakdown.
    """
    from app.models.recommendation import RecommendationInputSnapshot
    from app.models.acceptance_criterion import AcceptanceCriterion

    # First, try to get AC from the input snapshot (manually pasted AC)
    snapshot = db.query(RecommendationInputSnapshot).filter(
        RecommendationInputSnapshot.recommendation_run_id == run.id
    ).first()

    if snapshot and snapshot.acceptance_criteria:
        # Return manually pasted AC from snapshot
        return snapshot.acceptance_criteria

    # Fallback: Get AC from database for this PR
    if run.pull_request_id:
        ac_rows = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == run.pull_request_id
        ).all()
        if ac_rows:
            return [
                {
                    "id": str(ac.id),
                    "text": ac.text,
                    "normalized_key": ac.normalized_key,
                    "criterion_type": ac.criterion_type,
                    "source": ac.source,
                    "confidence": ac.confidence,
                    "evidence_excerpt": ac.evidence_excerpt,
                }
                for ac in ac_rows
            ]

    # Final fallback: Return from signal breakdown if available
    if impact_profile:
        return impact_profile.get("business_intent_signal_breakdown", {}).get("acceptance_criteria", [])

    return []


def _build_fragility_response(
    db: Session,
    run,
    changed_files: List[str],
    impact_profile: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Build fragility intelligence response for a recommendation run.

    Filters fragility signals to only include those relevant to the current PR.
    """
    from app.models.fragility_pattern import FragilitySnapshot
    from app.models.fragility_memory_v2 import FragilityMemoryV2
    from app.models.fragility_evidence_event import FragilityEvidenceEvent
    from app.models.behavior import Behavior
    from app.models.journey import Journey
    from app.models.behavior_scenario import BehaviorScenario
    from app.services.fragility_explanation_generator import FragilityExplanationGenerator
    
    # Default empty response
    default_response = {
        "risk_level": "LOW",
        "summary": "No fragility signals detected for this PR.",
        "behavior_signals": [],
        "journey_signals": [],
        "scenario_signals": [],
        "file_hotspots": [],
        "risky_combinations": [],
        "evidence_gaps": [],
    }
    
    # Load latest fragility snapshot
    snapshot = db.query(FragilitySnapshot).filter(
        FragilitySnapshot.repository_id == run.repository_id
    ).order_by(FragilitySnapshot.generated_at.desc()).first()
    
    if not snapshot or not snapshot.snapshot_metadata or not snapshot.snapshot_metadata.get("v2"):
        return default_response
    
    metadata = snapshot.snapshot_metadata
    
    # Get impacted behaviors/journeys from impact profile
    impacted_behavior_ids = set()
    impacted_journey_ids = set()
    if impact_profile:
        for b in impact_profile.get("impacted_behaviors", []):
            impacted_behavior_ids.add(b.get("behavior_id"))
        for j in impact_profile.get("impacted_journeys", []):
            impacted_journey_ids.add(j.get("journey_id"))
    
    # Get changed files for file hotspot filtering
    changed_files_set = set(changed_files) if changed_files else set()
    
    # Initialize explanation generator
    explanation_gen = FragilityExplanationGenerator(db)
    
    # Filter and format behavior signals
    behavior_signals = []
    for frag_data in metadata.get("behavior_fragility", []):
        # Only include if behavior is impacted
        if frag_data.get("subject_id") and frag_data["subject_id"] in impacted_behavior_ids:
            memory = db.query(FragilityMemoryV2).filter(
                FragilityMemoryV2.id == frag_data["id"]
            ).first()
            if memory:
                explanation = explanation_gen.generate_explanation(memory)
                behavior_signals.append({
                    "type": frag_data.get("memory_type"),
                    "subject": frag_data.get("subject_name"),
                    "subject_id": frag_data.get("subject_id"),
                    "score": frag_data.get("fragility_score"),
                    "confidence": frag_data.get("confidence"),
                    "risk_level": frag_data.get("risk_level"),
                    "evidence_count": _count_evidence(db, memory.id),
                    "last_seen_at": frag_data.get("last_seen_at"),
                    "reason": explanation,
                    "recommendation_effect": "boost" if frag_data.get("risk_level") in ("HIGH", "CRITICAL") else "context",
                })
    
    # Filter and format journey signals
    journey_signals = []
    for frag_data in metadata.get("journey_fragility", []):
        # Only include if journey is impacted
        if frag_data.get("subject_id") and frag_data["subject_id"] in impacted_journey_ids:
            memory = db.query(FragilityMemoryV2).filter(
                FragilityMemoryV2.id == frag_data["id"]
            ).first()
            if memory:
                explanation = explanation_gen.generate_explanation(memory)
                journey_signals.append({
                    "type": frag_data.get("memory_type"),
                    "subject": frag_data.get("subject_name"),
                    "subject_id": frag_data.get("subject_id"),
                    "score": frag_data.get("fragility_score"),
                    "confidence": frag_data.get("confidence"),
                    "risk_level": frag_data.get("risk_level"),
                    "evidence_count": _count_evidence(db, memory.id),
                    "last_seen_at": frag_data.get("last_seen_at"),
                    "reason": explanation,
                    "recommendation_effect": "boost" if frag_data.get("risk_level") in ("HIGH", "CRITICAL") else "context",
                })
    
    # Filter and format scenario signals
    scenario_signals = []
    for frag_data in metadata.get("scenario_fragility", []):
        # Only include if scenario is related to impacted behaviors
        scenario_key = frag_data.get("subject_name")
        if scenario_key:
            # Check if scenario is linked to impacted behavior
            scenario = db.query(BehaviorScenario).filter(
                BehaviorScenario.scenario_key == scenario_key
            ).first()
            if scenario and str(scenario.behavior_id) in impacted_behavior_ids:
                memory = db.query(FragilityMemoryV2).filter(
                    FragilityMemoryV2.id == frag_data["id"]
                ).first()
                if memory:
                    explanation = explanation_gen.generate_explanation(memory)
                    scenario_signals.append({
                        "type": frag_data.get("memory_type"),
                        "subject": frag_data.get("subject_name"),
                        "subject_id": frag_data.get("subject_id"),
                        "score": frag_data.get("fragility_score"),
                        "confidence": frag_data.get("confidence"),
                        "risk_level": frag_data.get("risk_level"),
                        "evidence_count": _count_evidence(db, memory.id),
                        "last_seen_at": frag_data.get("last_seen_at"),
                        "reason": explanation,
                        "recommendation_effect": "boost" if frag_data.get("risk_level") in ("HIGH", "CRITICAL") else "context",
                    })
    
    # Filter and format file hotspots
    file_hotspots = []
    for frag_data in metadata.get("file_hotspots", []):
        # Only include if file is changed or in changed files path
        file_path = frag_data.get("subject_name")
        if file_path and any(file_path in cf or cf in file_path for cf in changed_files_set):
            memory = db.query(FragilityMemoryV2).filter(
                FragilityMemoryV2.id == frag_data["id"]
            ).first()
            if memory:
                explanation = explanation_gen.generate_explanation(memory)
                file_hotspots.append({
                    "type": frag_data.get("memory_type"),
                    "subject": frag_data.get("subject_name"),
                    "subject_id": frag_data.get("subject_id"),
                    "score": frag_data.get("fragility_score"),
                    "confidence": frag_data.get("confidence"),
                    "risk_level": frag_data.get("risk_level"),
                    "evidence_count": _count_evidence(db, memory.id),
                    "last_seen_at": frag_data.get("last_seen_at"),
                    "reason": explanation,
                    "recommendation_effect": "boost" if frag_data.get("risk_level") in ("HIGH", "CRITICAL") else "context",
                })
    
    # Filter and format risky combinations
    risky_combinations = []
    for frag_data in metadata.get("risky_combinations", []):
        # Only include if combination involves changed files
        combination_subject = frag_data.get("subject_name", "")
        if any(cf in combination_subject for cf in changed_files_set):
            memory = db.query(FragilityMemoryV2).filter(
                FragilityMemoryV2.id == frag_data["id"]
            ).first()
            if memory:
                explanation = explanation_gen.generate_explanation(memory)
                risky_combinations.append({
                    "type": frag_data.get("memory_type"),
                    "subject": frag_data.get("subject_name"),
                    "subject_id": frag_data.get("subject_id"),
                    "score": frag_data.get("fragility_score"),
                    "confidence": frag_data.get("confidence"),
                    "risk_level": frag_data.get("risk_level"),
                    "evidence_count": _count_evidence(db, memory.id),
                    "last_seen_at": frag_data.get("last_seen_at"),
                    "reason": explanation,
                    "recommendation_effect": "boost" if frag_data.get("risk_level") in ("HIGH", "CRITICAL") else "context",
                })
    
    # Detect evidence gaps
    evidence_gaps = []
    if not behavior_signals and impacted_behavior_ids:
        evidence_gaps.append({
            "type": "missing_behavior_fragility",
            "description": f"No fragility signals found for {len(impacted_behavior_ids)} impacted behaviors.",
            "severity": "info",
        })
    if not file_hotspots and changed_files:
        evidence_gaps.append({
            "type": "missing_file_hotspots",
            "description": f"No file hotspot signals found for {len(changed_files)} changed files.",
            "severity": "info",
        })
    
    # Calculate overall risk level
    all_signals = behavior_signals + journey_signals + scenario_signals + file_hotspots + risky_combinations
    if all_signals:
        critical_count = sum(1 for s in all_signals if s.get("risk_level") == "CRITICAL")
        high_count = sum(1 for s in all_signals if s.get("risk_level") == "HIGH")
        if critical_count > 0:
            overall_risk = "CRITICAL"
        elif high_count > 0:
            overall_risk = "HIGH"
        else:
            overall_risk = "MODERATE"
    else:
        overall_risk = "LOW"
    
    # Generate summary
    signal_count = len(all_signals)
    if signal_count == 0:
        summary = "No fragility signals detected for this PR."
    else:
        summary = f"Detected {signal_count} fragility signal{'s' if signal_count > 1 else ''} related to this PR."
        if critical_count > 0:
            summary += f" {critical_count} critical pattern{'s' if critical_count > 1 else ''} detected."
        elif high_count > 0:
            summary += f" {high_count} high-risk pattern{'s' if high_count > 1 else ''} detected."
    
    return {
        "risk_level": overall_risk,
        "summary": summary,
        "behavior_signals": behavior_signals,
        "journey_signals": journey_signals,
        "scenario_signals": scenario_signals,
        "file_hotspots": file_hotspots,
        "risky_combinations": risky_combinations,
        "evidence_gaps": evidence_gaps,
    }


def _count_evidence(db: Session, memory_id: uuid.UUID) -> int:
    """Count evidence events for a fragility memory."""
    return db.query(FragilityEvidenceEvent).filter(
        FragilityEvidenceEvent.fragility_memory_id == memory_id
    ).count()


def _build_outcome_summary(db: Session, recommendation_run_id: UUID) -> Dict[str, Any]:
    """
    Build outcome summary for a recommendation run.
    
    Returns a structured summary of tests, scenarios, overrides, and post-merge outcomes.
    """
    from app.models.recommendation import (
        RecommendationOutcome, RecommendationTestOutcome,
        SuggestedScenarioOutcome, RecommendationOverride, RecommendedTest
    )
    
    # Load outcome
    outcome = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.recommendation_run_id == recommendation_run_id
    ).first()
    
    if not outcome:
        return {
            "status": "NOT_CAPTURED",
            "feedback": None,
            "tests": {
                "recommended_count": 0,
                "kept_count": 0,
                "removed_count": 0,
                "executed_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "not_run_count": 0,
            },
            "scenarios": {
                "suggested_count": 0,
                "accepted_count": 0,
                "dismissed_count": 0,
                "executed_count": 0,
                "important_count": 0,
            },
            "overrides": {
                "added_tests_count": 0,
                "removed_tests_count": 0,
            },
            "defect_escaped": False,
            "rollback_occurred": False,
        }
    
    # Load test outcomes
    test_outcomes = db.query(RecommendationTestOutcome).filter(
        RecommendationTestOutcome.recommendation_run_id == recommendation_run_id
    ).all()
    
    # Load scenario outcomes
    scenario_outcomes = db.query(SuggestedScenarioOutcome).filter(
        SuggestedScenarioOutcome.recommendation_run_id == recommendation_run_id
    ).all()
    
    # Load overrides
    overrides = db.query(RecommendationOverride).filter(
        RecommendationOverride.recommendation_run_id == recommendation_run_id
    ).all()
    
    # Load recommended tests
    recommended_tests = db.query(RecommendedTest).filter(
        RecommendedTest.recommendation_run_id == recommendation_run_id
    ).all()
    
    # Calculate test counts
    recommended_count = len(recommended_tests)
    kept_count = sum(1 for to in test_outcomes if to.engineer_decision == "KEPT")
    removed_count = sum(1 for to in test_outcomes if to.engineer_decision == "REMOVED")
    executed_count = sum(1 for to in test_outcomes if to.execution_status in ["PASSED", "FAILED"])
    passed_count = sum(1 for to in test_outcomes if to.execution_status == "PASSED")
    failed_count = sum(1 for to in test_outcomes if to.execution_status == "FAILED")
    skipped_count = sum(1 for to in test_outcomes if to.execution_status == "SKIPPED")
    not_run_count = sum(1 for to in test_outcomes if to.execution_status == "NOT_RUN")
    
    # Calculate scenario counts
    suggested_count = len(scenario_outcomes)
    accepted_count = sum(1 for so in scenario_outcomes if so.engineer_decision == "ACCEPTED")
    dismissed_count = sum(1 for so in scenario_outcomes if so.engineer_decision == "DISMISSED")
    executed_count_scenarios = sum(1 for so in scenario_outcomes if so.execution_status == "EXECUTED")
    important_count = sum(1 for so in scenario_outcomes if so.engineer_decision == "IMPORTANT")
    
    # Calculate override counts
    added_tests_count = sum(1 for o in overrides if o.override_type == "ADDED")
    removed_tests_count = sum(1 for o in overrides if o.override_type == "REMOVED")

    # Load the recommendation run to get snapshot data
    from app.models.recommendation import RecommendationRun
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()

    if not run:
        return {
            "status": "NOT_FOUND",
            "feedback": None,
            "tests": {
                "recommended_count": 0,
                "kept_count": 0,
                "removed_count": 0,
                "executed_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "not_run_count": 0,
            },
            "scenarios": {
                "suggested_count": 0,
                "accepted_count": 0,
                "dismissed_count": 0,
                "executed_count": 0,
                "important_count": 0,
            },
            "overrides": {
                "added_tests_count": 0,
                "removed_tests_count": 0,
            },
            "defect_escaped": False,
            "rollback_occurred": False,
        }

    # Use generation-time snapshot if available, otherwise null
    readiness_summary = None
    if run.readiness_level_at_generation:
        readiness_summary = {
            "readiness_level": run.readiness_level_at_generation,
            "expected_confidence": run.expected_confidence_at_generation,
            "readiness_score": run.readiness_score_at_generation,
            "can_generate": run.can_generate_at_generation,
            "can_generate_reason": run.confidence_reason_at_generation,
            "available_signals": run.available_inputs_at_generation,
            "missing_signals": run.missing_inputs_at_generation,
            "confidence_impact_summary": run.confidence_limiters_at_generation
        }
    
    return {
        "status": outcome.outcome_status,
        "feedback": outcome.user_feedback,
        "tests": {
            "recommended_count": recommended_count,
            "kept_count": kept_count,
            "removed_count": removed_count,
            "executed_count": executed_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "not_run_count": not_run_count,
        },
        "scenarios": {
            "suggested_count": suggested_count,
            "accepted_count": accepted_count,
            "dismissed_count": dismissed_count,
            "executed_count": executed_count_scenarios,
            "important_count": important_count,
        },
        "overrides": {
            "added_tests_count": added_tests_count,
            "removed_tests_count": removed_tests_count,
        },
        "defect_escaped": outcome.escaped_defect,
        "rollback_occurred": outcome.rollback_occurred,
        "readiness": readiness_summary,
    }


@router.get("/{recommendation_run_id}/explanations", response_model=List[RecommendationExplanationResponse])
def get_recommendation_run_explanations(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve all explanations for a recommendation run. Workspace-scoped."""
    from app.models.recommendation import RecommendationRun, RecommendationExplanation
    from app.models.repository import Repository

    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation run not found.")

    # Workspace scope check
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    explanations = db.query(RecommendationExplanation).filter(
        RecommendationExplanation.recommendation_run_id == recommendation_run_id
    ).all()

    return explanations


@router.get("/{recommendation_run_id}/impact-graph", response_model=ChangeImpactGraphResponse)
def get_recommendation_run_impact_graph(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve the ChangeImpactGraph visual relationship model. Workspace-scoped."""
    from app.models.recommendation import RecommendationRun, RecommendationExplanation
    from app.models.repository import Repository
    from app.services.change_impact_graph import ChangeImpactGraphEngine

    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation run not found.")

    # Workspace scope check
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Backward compatibility fallback
    if not run.impact_graph:
        explanations = db.query(RecommendationExplanation).filter(
            RecommendationExplanation.recommendation_run_id == recommendation_run_id
        ).all()
        graph = ChangeImpactGraphEngine.build_graph(explanations)
        run.impact_graph = graph
        db.commit()
    else:
        graph = run.impact_graph

    return graph


@legacy_router.get("/{recommendation_run_id}/impact-graph", response_model=ChangeImpactGraphResponse)
def legacy_get_recommendation_run_impact_graph(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Legacy endpoint for retrieving the ChangeImpactGraph."""
    return get_recommendation_run_impact_graph(recommendation_run_id, workspace, db)


@router.get("/{recommendation_run_id}/intelligence-report")
def get_intelligence_report(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Generate the Regression Intelligence Report for a recommendation run. Workspace-scoped."""
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.services.intelligence_report_generator import IntelligenceReportGenerator

    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation run not found.")

    # Workspace scope check
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    report = IntelligenceReportGenerator.generate_report(db, run.id)
    markdown = IntelligenceReportGenerator.render_as_markdown(report)
    html = IntelligenceReportGenerator.render_as_html(report)

    return {
        "report": report,
        "markdown": markdown,
        "html": html
    }


@legacy_router.get("/{recommendation_run_id}/intelligence-report")
def legacy_get_intelligence_report(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Legacy endpoint for generating the intelligence report."""
    return get_intelligence_report(recommendation_run_id, workspace, db)


@router.get("/{recommendation_run_id}/report")
def get_recommendation_report(
    recommendation_run_id: UUID,
    format: Optional[str] = Query("ui"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Generate the unified Regression Scoping Report for a recommendation run. Workspace-scoped.
    Supports formats: ui, markdown, and pdf.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.services.recommendation_report_generator import RecommendationReportGenerator
    from fastapi.responses import Response

    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation run not found.")

    # Workspace scope check
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    try:
        report = RecommendationReportGenerator.generate_report(db, run.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    fmt = (format or "ui").lower()
    if fmt == "pdf":
        pdf_bytes = RecommendationReportGenerator.render_as_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=veriscope_report_{run.id}.pdf"
            }
        )
    elif fmt in ("markdown", "github_comment", "github-comment"):
        md = RecommendationReportGenerator.render_as_github_comment(report)
        return Response(
            content=md,
            media_type="text/markdown"
        )
    else:  # "ui" format
        return RecommendationReportGenerator.render_as_ui(report)


@legacy_router.get("/{recommendation_run_id}/report")
def legacy_get_recommendation_report(
    recommendation_run_id: UUID,
    format: Optional[str] = Query("ui"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Legacy endpoint for generating the report."""
    return get_recommendation_report(recommendation_run_id, format, workspace, db)


internal_router = APIRouter(
    prefix="/internal/recommendations", 
    tags=["Diagnostics"],
    dependencies=[Depends(require_workspace_member())]
)

@internal_router.get("/{recommendation_run_id}/debug", response_model=RecommendationDetailedDebugResponse)
def get_debug_chain_internal(
    recommendation_run_id: UUID,
    include_input_snapshot: Optional[bool] = Query(None),
    include_reasoning: Optional[bool] = Query(None),
    include_tests: Optional[bool] = Query(None),
    reasoning_limit: int = Query(100),
    db: Session = Depends(get_db)
):
    """Retrieve detailed explainability data and forensic audit logs for a recommendation."""
    # Resolve backward compatibility defaults:
    # If no parameters are explicitly requested, default include_reasoning=True and include_tests=True, include_input_snapshot=False.
    if include_input_snapshot is None and include_reasoning is None and include_tests is None:
        include_input_snapshot = False
        include_reasoning = True
        include_tests = True
    else:
        include_input_snapshot = include_input_snapshot or False
        include_reasoning = include_reasoning or False
        include_tests = include_tests or False

    service = RecommendationService(db)
    return service.get_detailed_debug(
        recommendation_run_id,
        include_input_snapshot=include_input_snapshot,
        include_reasoning=include_reasoning,
        include_tests=include_tests,
        reasoning_limit=reasoning_limit
    )

@internal_router.get("/{recommendation_run_id}/feedback")
def get_recommendation_feedbacks(recommendation_run_id: UUID, db: Session = Depends(get_db)):
    """Retrieve the full timeline of collected human engineer feedbacks for a recommendation run."""
    from app.models.recommendation import RecommendationOutcome, RecommendationEngineerFeedback
    outcome = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.recommendation_run_id == recommendation_run_id
    ).first()
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No RecommendationOutcome found for recommendation run ID: {recommendation_run_id}."
        )
    
    feedbacks = db.query(RecommendationEngineerFeedback).filter(
        RecommendationEngineerFeedback.recommendation_outcome_id == outcome.id
    ).order_by(RecommendationEngineerFeedback.created_at.asc()).all()
    
    return [
        {
            "id": fb.id,
            "feedback_type": fb.feedback_type,
            "feedback_text": fb.feedback_text,
            "created_by": fb.created_by,
            "created_at": fb.created_at.isoformat() if fb.created_at else None
        }
        for fb in feedbacks
    ]

@internal_router.get("/{repo_id}/analytics")
def get_outcome_analytics(repo_id: UUID, db: Session = Depends(get_db)):
    """Fetch high-fidelity trust calibration index and recommendation outcomes analytics."""
    service = RecommendationAnalyticsService(db)
    return service.get_outcome_analytics(repo_id)

@router.get("/repository/{repo_id}/learning-diagnostics")
def get_learning_diagnostics(repo_id: UUID, db: Session = Depends(get_db)):
    """Retrieve evidence-backed organizational learning insights and suite expansion recommendations."""
    service = RecommendationAnalyticsService(db)
    return service.get_learning_diagnostics(repo_id)


# ----------------------------------------------------
# Administrative Drift Detection & Recovery HTTP APIs
# ----------------------------------------------------

@internal_router.get("/outcomes/{outcome_id}/drift", status_code=status.HTTP_200_OK)
def get_outcome_drift_diagnostics(outcome_id: UUID, db: Session = Depends(get_db)):
    """Retrieve detailed semantic and integrity drift diagnostics for a recommendation outcome."""
    from app.services.recommendation_outcome_drift_detector import RecommendationOutcomeDriftDetector
    try:
        return RecommendationOutcomeDriftDetector.detect_outcome_drift(db, outcome_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@internal_router.get("/repository/{repo_id}/drift", status_code=status.HTTP_200_OK)
def get_repository_drift_diagnostics(repo_id: UUID, db: Session = Depends(get_db)):
    """Scan and catalog historical lineage drift for all outcomes in a repository."""
    from app.services.recommendation_outcome_drift_detector import RecommendationOutcomeDriftDetector
    try:
        return RecommendationOutcomeDriftDetector.detect_repository_drift(db, repo_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@internal_router.post("/outcomes/{outcome_id}/replay", status_code=status.HTTP_200_OK)
def post_replay_outcome_classification(
    outcome_id: UUID, 
    apply_repair: bool = Query(False), 
    db: Session = Depends(get_db)
):
    """Manually replay chronological evidence and optionally repair stored classification status."""
    from app.services.recommendation_outcome_recovery import RecommendationOutcomeRecoveryService
    try:
        return RecommendationOutcomeRecoveryService.replay_outcome_classification(db, outcome_id, apply_repair=apply_repair)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@internal_router.post("/outcomes/{outcome_id}/rebuild-snapshot", status_code=status.HTTP_200_OK)
def post_rebuild_outcome_snapshot(
    outcome_id: UUID, 
    force: bool = Query(False), 
    db: Session = Depends(get_db)
):
    """Generate missing snapshots or rebuild existing snapshots with administrative bypass."""
    from app.services.recommendation_outcome_recovery import RecommendationOutcomeRecoveryService
    try:
        return RecommendationOutcomeRecoveryService.rebuild_outcome_snapshot(db, outcome_id, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@internal_router.post("/outcomes/{outcome_id}/repair", status_code=status.HTTP_200_OK)
def post_repair_broken_lineage(outcome_id: UUID, db: Session = Depends(get_db)):
    """Automatically repair stale references or restore missing evidence records from reasoning logs."""
    from app.services.recommendation_outcome_recovery import RecommendationOutcomeRecoveryService
    try:
        return RecommendationOutcomeRecoveryService.repair_broken_lineage(db, outcome_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@internal_router.get("/{recommendation_run_id}/behavior-debug")
def get_behavior_debug_internal(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve detailed behavior impact and coverage debug information for a recommendation run.
    
    This endpoint provides forensic diagnostics for behavior-aware recommendations including:
    - Impacted behaviors and their matching signals
    - Scenario mappings and coverage status
    - Existing test mappings
    - Coverage support mappings
    - Final coverage statuses and gaps
    - Ranking contribution from behavior intelligence
    
    Workspace-scoped and internal-only for development/debugging purposes.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    
    # Verify the recommendation run belongs to this workspace
    run = db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation run {recommendation_run_id} not found"
        )
    
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation run does not belong to your workspace"
        )
    
    # Extract behavior intelligence from impact_profile
    impact_profile = run.impact_profile or {}
    behavior_intelligence = impact_profile.get("behavior_intelligence", {})
    behavior_coverage_matrix = impact_profile.get("behavior_coverage_matrix", [])
    
    # Get behavior impact run data
    from app.models.behavior_impact import BehaviorImpactRun, BehaviorImpactItem
    behavior_impact_run = db.query(BehaviorImpactRun).filter(
        BehaviorImpactRun.recommendation_run_id == recommendation_run_id
    ).first()


@internal_router.get("/{recommendation_run_id}/business-intent-debug")
def get_business_intent_debug_internal(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve detailed business intent debug information for a recommendation run.
    
    This endpoint provides forensic diagnostics for business intent analysis including:
    - Raw PR title/body
    - Extracted business intent
    - Extracted acceptance criteria
    - Mappings to behaviors/scenarios
    - AC coverage statuses
    - Requirement gaps
    - Scoring contribution
    
    Workspace-scoped and internal-only for development/debugging purposes.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.models.pull_request import PullRequest
    
    # Verify the recommendation run belongs to this workspace
    run = db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation run {recommendation_run_id} not found"
        )
    
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation run does not belong to your workspace"
        )
    
    # Get PR data
    pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
    
    # Extract business intent debug data from impact_profile
    impact_profile = run.impact_profile or {}
    
    return {
        "recommendation_run_id": str(recommendation_run_id),
        "pr": {
            "id": str(pr.id) if pr else None,
            "number": pr.number if pr else None,
            "title": pr.title if pr else None,
            "body": pr.body if pr else None,
        },
        "business_intent_coverage_matrix": impact_profile.get("business_intent_coverage_matrix"),
        "requirement_gap_report": impact_profile.get("requirement_gap_report"),
        "business_intent_signal_breakdown": impact_profile.get("business_intent_signal_breakdown"),
        "pr_description_template_suggestion": impact_profile.get("pr_description_template_suggestion"),
        "scoring_boosts_applied": impact_profile.get("business_intent_signal_breakdown", {}).get("business_intent_signals", {}).get("scoring_boosts_applied"),
    }


@internal_router.get("/{recommendation_run_id}/behavior-debug")
def get_behavior_debug_internal(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve detailed behavior impact and coverage debug information for a recommendation run.
    
    This endpoint provides forensic diagnostics for behavior-aware recommendations including:
    - Impacted behaviors and their matching signals
    - Scenario mappings and coverage status
    - Existing test mappings
    - Coverage support mappings
    - Final coverage statuses and gaps
    - Ranking contribution from behavior intelligence
    
    Workspace-scoped and internal-only for development/debugging purposes.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    
    # Verify the recommendation run belongs to this workspace
    run = db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation run {recommendation_run_id} not found"
        )
    
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation run does not belong to your workspace"
        )
    
    # Extract behavior intelligence from impact_profile
    impact_profile = run.impact_profile or {}
    behavior_intelligence = impact_profile.get("behavior_intelligence", {})
    behavior_coverage_matrix = impact_profile.get("behavior_coverage_matrix", [])
    
    # Get behavior impact run data
    from app.models.behavior_impact import BehaviorImpactRun, BehaviorImpactItem
    behavior_impact_run = db.query(BehaviorImpactRun).filter(
        BehaviorImpactRun.recommendation_run_id == recommendation_run_id
    ).first()
    
    impacted_behaviors = []
    if behavior_impact_run:
        impact_items = db.query(BehaviorImpactItem).filter(
            BehaviorImpactItem.behavior_impact_run_id == behavior_impact_run.id
        ).all()
        
        for item in impact_items:
            impacted_behaviors.append({
                "behavior_id": str(item.behavior_id),
                "journey_id": str(item.journey_id) if item.journey_id else None,
                "impact_level": item.impact_level,
                "confidence": item.confidence,
                "impact_reason": item.impact_reason,
                "source_signals": item.source_signals,
                "impacted_files": item.impacted_files,
                "affected_scenarios": item.affected_scenarios,
            })
    
    # Get behavior scenario coverages
    from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage
    scenario_coverages = db.query(BehaviorScenarioCoverage).filter(
        BehaviorScenarioCoverage.recommendation_run_id == recommendation_run_id
    ).all()
    
    scenario_coverage_debug = []
    for sc in scenario_coverages:
        scenario_coverage_debug.append({
            "scenario_id": str(sc.scenario_id),
            "behavior_id": str(sc.behavior_id),
            "coverage_status": sc.coverage_status,
            "execution_trace": sc.execution_trace,
            "test_mappings": sc.test_mappings,
            "created_at": sc.created_at.isoformat() if sc.created_at else None,
        })
    
    # Compile debug response
    debug_response = {
        "recommendation_run_id": str(recommendation_run_id),
        "repository_id": str(run.repository_id),
        "workspace_id": str(workspace.id),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        
        # Behavior impact analysis
        "behavior_impact_summary": {
            "impact_summary": behavior_impact_run.impact_summary if behavior_impact_run else None,
            "confidence": behavior_impact_run.confidence if behavior_impact_run else None,
            "impacted_behaviors": impacted_behaviors,
        },
        
        # Behavior intelligence snapshot
        "behavior_intelligence": {
            "behavior_coverages": behavior_intelligence.get("behavior_coverages", []),
            "behavior_coverage_gaps": behavior_intelligence.get("behavior_coverage_gaps", []),
            "all_scenarios": behavior_intelligence.get("all_scenarios", []),
        },
        
        # Behavior coverage matrix (frontend-ready)
        "behavior_coverage_matrix": behavior_coverage_matrix,
    }
    
    return debug_response


# Outcome Update Endpoints
@router.get("/{recommendation_run_id}/outcome", response_model=OutcomeDetailResponse)
def get_outcome(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get outcome details for a recommendation run."""
    from app.models.recommendation import RecommendationOutcome, RecommendationRun
    
    # Verify run exists and belongs to workspace
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id,
        RecommendationRun.workspace_id == workspace.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Get or create outcome
    outcome = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.recommendation_run_id == recommendation_run_id
    ).first()
    
    if not outcome:
        # Initialize outcome if it doesn't exist
        from app.services.recommendation_outcome_initializer import RecommendationOutcomeInitializer
        RecommendationOutcomeInitializer.initialize_outcomes(
            db=db,
            recommendation_run_id=recommendation_run_id,
            repository_id=run.repository_id,
            workspace_id=workspace.id
        )
        outcome = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == recommendation_run_id
        ).first()
    
    return outcome


@router.patch("/{recommendation_run_id}/outcome", response_model=OutcomeDetailResponse)
def update_outcome(
    recommendation_run_id: UUID,
    outcome_update: OutcomeUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Update outcome details (partial update supported)."""
    from app.models.recommendation import RecommendationOutcome, RecommendationRun
    
    # Verify run exists and belongs to workspace
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id,
        RecommendationRun.workspace_id == workspace.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Get outcome
    outcome = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.recommendation_run_id == recommendation_run_id
    ).first()
    
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found"
        )
    
    # Apply partial updates
    if outcome_update.outcome_status is not None:
        outcome.outcome_status = outcome_update.outcome_status
    if outcome_update.user_feedback is not None:
        outcome.user_feedback = outcome_update.user_feedback
    if outcome_update.feedback_comment is not None:
        outcome.feedback_comment = outcome_update.feedback_comment
    if outcome_update.ignored_reason is not None:
        outcome.ignored_reason = outcome_update.ignored_reason
    if outcome_update.defect_escaped is not None:
        outcome.escaped_defect = outcome_update.defect_escaped
    if outcome_update.rollback_occurred is not None:
        outcome.rollback_occurred = outcome_update.rollback_occurred
    if outcome_update.production_incident_url is not None:
        outcome.production_incident_url = outcome_update.production_incident_url
    
    db.commit()
    db.refresh(outcome)
    return outcome


@router.patch("/{recommendation_run_id}/tests/{recommended_test_id}/outcome", response_model=TestOutcomeDetailResponse)
def update_test_outcome(
    recommendation_run_id: UUID,
    recommended_test_id: UUID,
    test_outcome_update: TestOutcomeUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Update test outcome details (partial update supported)."""
    from app.models.recommendation import RecommendationTestOutcome, RecommendationRun
    
    # Verify run exists and belongs to workspace
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id,
        RecommendationRun.workspace_id == workspace.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Get test outcome
    test_outcome = db.query(RecommendationTestOutcome).filter(
        RecommendationTestOutcome.recommendation_run_id == recommendation_run_id,
        RecommendationTestOutcome.recommended_test_id == recommended_test_id
    ).first()
    
    if not test_outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test outcome not found"
        )
    
    # Apply partial updates
    if test_outcome_update.recommendation_action is not None:
        test_outcome.recommendation_action = test_outcome_update.recommendation_action
    if test_outcome_update.execution_status is not None:
        test_outcome.execution_status = test_outcome_update.execution_status
    if test_outcome_update.engineer_decision is not None:
        test_outcome.engineer_decision = test_outcome_update.engineer_decision
    if test_outcome_update.actual_test_result_id is not None:
        test_outcome.actual_test_result_id = test_outcome_update.actual_test_result_id
    if test_outcome_update.actual_test_run_id is not None:
        test_outcome.actual_test_run_id = test_outcome_update.actual_test_run_id
    if test_outcome_update.duration_seconds is not None:
        test_outcome.duration_seconds = test_outcome_update.duration_seconds
    if test_outcome_update.failure_message is not None:
        test_outcome.failure_message = test_outcome_update.failure_message
    
    db.commit()
    db.refresh(test_outcome)
    return test_outcome


@router.patch("/{recommendation_run_id}/scenarios/{suggested_scenario_id}/outcome", response_model=ScenarioOutcomeDetailResponse)
def update_scenario_outcome(
    recommendation_run_id: UUID,
    suggested_scenario_id: UUID,
    scenario_outcome_update: ScenarioOutcomeUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Update scenario outcome details (partial update supported)."""
    from app.models.recommendation import SuggestedScenarioOutcome, RecommendationRun
    
    # Verify run exists and belongs to workspace
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id,
        RecommendationRun.workspace_id == workspace.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Get scenario outcome
    scenario_outcome = db.query(SuggestedScenarioOutcome).filter(
        SuggestedScenarioOutcome.recommendation_run_id == recommendation_run_id,
        SuggestedScenarioOutcome.suggested_scenario_id == suggested_scenario_id
    ).first()
    
    if not scenario_outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario outcome not found"
        )
    
    # Apply partial updates
    if scenario_outcome_update.engineer_decision is not None:
        scenario_outcome.engineer_decision = scenario_outcome_update.engineer_decision
    if scenario_outcome_update.execution_status is not None:
        scenario_outcome.execution_status = scenario_outcome_update.execution_status
    if scenario_outcome_update.converted_to_test is not None:
        scenario_outcome.converted_to_test = scenario_outcome_update.converted_to_test
    if scenario_outcome_update.linked_test_identifier is not None:
        scenario_outcome.linked_test_identifier = scenario_outcome_update.linked_test_identifier
    if scenario_outcome_update.comment is not None:
        scenario_outcome.comment = scenario_outcome_update.comment
    
    db.commit()
    db.refresh(scenario_outcome)
    return scenario_outcome


@router.post("/{recommendation_run_id}/overrides", status_code=status.HTTP_201_CREATED)
def create_override(
    recommendation_run_id: UUID,
    override_create: OverrideCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Create an override record for a recommendation run."""
    from app.models.recommendation import RecommendationOverride, RecommendationOutcome, RecommendationRun
    from app.services.recommendation_override_updater import RecommendationOverrideUpdater
    
    # Verify run exists and belongs to workspace
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id,
        RecommendationRun.workspace_id == workspace.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
    )
    
    # Get outcome
    outcome = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.recommendation_run_id == recommendation_run_id
    ).first()
    
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found"
        )
    
    # Create override based on type
    if override_create.override_type == "TEST_ADDED" and override_create.test_identifier:
        success = RecommendationOverrideUpdater.record_test_added(
            db=db,
            recommendation_run_id=recommendation_run_id,
            test_identifier=override_create.test_identifier,
            reason=override_create.reason,
            source=override_create.source,
            created_by=str(workspace.id)  # Use workspace as creator for now
        )
    elif override_create.override_type == "TEST_REMOVED" and override_create.test_identifier:
        success = RecommendationOverrideUpdater.record_test_removed(
            db=db,
            recommendation_run_id=recommendation_run_id,
            test_identifier=override_create.test_identifier,
            reason=override_create.reason,
            source=override_create.source,
            created_by=str(workspace.id)
        )
    elif override_create.override_type == "SCENARIO_ADDED" and override_create.scenario_intent_key:
        success = RecommendationOverrideUpdater.record_scenario_added(
            db=db,
            recommendation_run_id=recommendation_run_id,
            scenario_intent_key=override_create.scenario_intent_key,
            reason=override_create.reason,
            source=override_create.source,
            created_by=str(workspace.id)
        )
    elif override_create.override_type == "SCENARIO_REMOVED" and override_create.scenario_intent_key:
        success = RecommendationOverrideUpdater.record_scenario_removed(
            db=db,
            recommendation_run_id=recommendation_run_id,
            scenario_intent_key=override_create.scenario_intent_key,
            reason=override_create.reason,
            source=override_create.source,
            created_by=str(workspace.id)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid override type or missing required identifier"
        )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create override"
        )
    
    return {"status": "created", "message": "Override recorded successfully"}


@router.post("/{recommendation_run_id}/attach-test-run", status_code=status.HTTP_200_OK)
def attach_test_run(
    recommendation_run_id: str,
    request: AttachTestRunRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """
    Attach a TestRun to a recommendation run to map execution results to outcomes.
    
    This endpoint:
    - Verifies recommendation run belongs to workspace
    - Checks if test run matches PR head SHA (if applicable)
    - Uses OutcomeExecutionCollector to map test results
    - Updates test outcomes with execution status
    - Creates overrides for extra tests
    - Updates recommendation outcome status
    - Recalculates readiness after attachment
    """
    from app.models.recommendation import RecommendationRun
    from app.models.test_result import TestRun
    from app.models.pull_request import PullRequest
    from app.services.recommendation_readiness_gate import RecommendationReadinessGate
    
    # Verify recommendation run exists and belongs to workspace
    rec_run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    
    if not rec_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Verify workspace ownership
    from app.models.repository import Repository
    repo = db.query(Repository).filter(Repository.id == rec_run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation run does not belong to this workspace"
        )
    
    # Verify test run exists
    test_run = db.query(TestRun).filter(
        TestRun.id == str(request.test_run_id)
    ).first()
    
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found"
        )
    
    # Verify test run belongs to same repository
    if test_run.repository_id != rec_run.repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test run does not belong to the same repository as the recommendation"
        )
    
    # Check PR head SHA matching if recommendation is for a PR
    is_manual_attach = False
    matches_pr_head = True
    
    if rec_run.pull_request_id:
        pr = db.query(PullRequest).filter(
            PullRequest.id == rec_run.pull_request_id
        ).first()
        
        if pr and pr.head_commit_sha:
            if test_run.commit_sha != pr.head_commit_sha:
                is_manual_attach = True
                matches_pr_head = False
    
    # Use OutcomeExecutionCollector to map execution results
    collector = OutcomeExecutionCollector(db)
    
    try:
        results = collector.collect_execution_outcomes(
            recommendation_run_id=recommendation_run_id,
            test_run_id=str(request.test_run_id),
        )
        
        # Recalculate readiness after attachment
        readiness_gate = RecommendationReadinessGate(db)
        readiness_result = readiness_gate.assess_readiness(
            recommendation_run_id=recommendation_run_id
        )
        
        return {
            "status": "attached",
            "message": "Test run attached successfully",
            "results": results,
            "matches_pr_head": matches_pr_head,
            "is_manual_attach": is_manual_attach,
            "readiness_updated": True,
            "readiness_state": readiness_result.readiness_state if readiness_result else None
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach test run: {str(e)}"
        )


@router.get("/{recommendation_run_id}/readiness")
def get_recommendation_readiness(
    recommendation_run_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Assess readiness for an existing recommendation run using strict 12-input readiness.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.services.input_readiness_v2_service import InputReadinessV2Service

    rec_run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not rec_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )

    # Verify workspace ownership
    repo = db.query(Repository).filter(
        Repository.id == rec_run.repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation run does not belong to this workspace"
        )

    # Check if the PR head SHA has changed since generation, and reset acknowledgement
    if rec_run.pull_request and rec_run.pr_snapshot:
        if rec_run.pull_request.head_commit_sha != rec_run.pr_snapshot.head_commit_sha:
            if rec_run.readiness_acknowledged:
                rec_run.readiness_acknowledged = False
                rec_run.readiness_acknowledged_at = None
                rec_run.readiness_acknowledged_missing_inputs = None
                rec_run.readiness_decision = None
                db.add(rec_run)
                db.commit()
                db.refresh(rec_run)

    # Use strict 12-input readiness service
    v2_service = InputReadinessV2Service(db)
    strict_readiness = v2_service.assess(
        repository_id=str(rec_run.repository_id),
        pull_request_id=str(rec_run.pull_request_id) if rec_run.pull_request_id else None
    )

    # Convert to response format
    strict_dict = strict_readiness.model_dump() if hasattr(strict_readiness, "model_dump") else (strict_readiness.dict() if hasattr(strict_readiness, "dict") else strict_readiness)

    return {
        "strict_12_input_readiness": strict_dict,
        "legacy_repository_readiness": {
            "readiness_state": "LEGACY",
            "readiness_reasons": ["Using strict 12-input readiness"],
            "next_action": "See strict_12_input_readiness for details"
        }
    }


def _resolve_acceptance_criteria_text(run, pr, db) -> dict:
    import hashlib
    diagnostics = []
    
    # 1. Explicit uploaded AC artifact
    from app.models.artifact import RawArtifact
    ac_artifact = db.query(RawArtifact).filter(
        RawArtifact.repository_id == run.repository_id,
        RawArtifact.evidence_artifact_type == "acceptance_criteria"
    ).order_by(RawArtifact.created_at.desc()).first()
    
    if ac_artifact and ac_artifact.artifact_metadata and "text" in ac_artifact.artifact_metadata:
        text = ac_artifact.artifact_metadata["text"]
        return {
            "text": text,
            "source_type": "ARTIFACT",
            "source_id": str(ac_artifact.id),
            "source_hash": hashlib.md5(text.encode()).hexdigest(),
            "diagnostics": diagnostics + ["Found uploaded AC artifact"]
        }

    # 2. DB AcceptanceCriterion (clean source after PHASE 0.8)
    from app.models.acceptance_criterion import AcceptanceCriterion
    if pr:
        ac_rows = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pr.id
        ).all()
        if ac_rows:
            text = "\n".join([f"- {row.text}" for row in ac_rows])
            return {
                "text": text,
                "source_type": "DB_ACCEPTANCE_CRITERION",
                "source_id": f"pr-{pr.id}",
                "source_hash": hashlib.md5(text.encode()).hexdigest(),
                "diagnostics": diagnostics + ["Reconstructed AC text from DB rows"]
            }

    # 3. Acceptance criteria text stored in RecommendationRun.input_snapshot (fallback, may be polluted)
    if run.input_snapshot and run.input_snapshot.acceptance_criteria:
        ac_items = run.input_snapshot.acceptance_criteria
        text_lines = []
        for ac in ac_items:
            if isinstance(ac, dict) and "text" in ac:
                text_lines.append(f"- {ac['text']}")
            elif isinstance(ac, str):
                text_lines.append(f"- {ac}")
        
        if text_lines:
            text = "\n".join(text_lines)
            return {
                "text": text,
                "source_type": "INPUT_SNAPSHOT",
                "source_id": str(run.input_snapshot.id),
                "source_hash": hashlib.md5(text.encode()).hexdigest(),
                "diagnostics": diagnostics + ["Reconstructed AC text from input snapshot (may be polluted)"]
            }

    # 4. PullRequest.body
    if pr and hasattr(pr, "body") and pr.body:
        return {
            "text": pr.body,
            "source_type": "PR_BODY",
            "source_id": str(pr.id),
            "source_hash": hashlib.md5(pr.body.encode()).hexdigest(),
            "diagnostics": diagnostics + ["Using PR body"]
        }
        
    # 5. PullRequest.description
    if pr and hasattr(pr, "description") and pr.description:
        return {
            "text": pr.description,
            "source_type": "PR_DESCRIPTION",
            "source_id": str(pr.id),
            "source_hash": hashlib.md5(pr.description.encode()).hexdigest(),
            "diagnostics": diagnostics + ["Using PR description"]
        }
        
    # 6. Empty string
    diagnostics.append("No acceptance criteria source found")
    return {
        "text": "",
        "source_type": "NONE",
        "source_id": "NONE",
        "source_hash": "NONE",
        "diagnostics": diagnostics
    }

def _map_classification_to_group(classification: str) -> str:
    """Map evidence classification to scope group."""
    mapping = {
        "VERIFIED_BY_CURRENT_PR_EXECUTION": "EXCLUDED_ALREADY_VERIFIED",
        "PARTIALLY_COVERED": "RECOMMENDED",
        "MISSING_AUTOMATED_COVERAGE": "REQUIRED",
        "FAILED_IN_CURRENT_PR_EXECUTION": "REQUIRED",
        "SKIPPED_IN_CURRENT_PR_EXECUTION": "REQUIRED",
        "EXISTING_TEST_NOT_RUN_IN_CURRENT_PR": "REQUIRED",
        "NOT_MAPPED_TRACEABILITY_RISK": "REQUIRED",
    }
    return mapping.get(classification, "UNKNOWN")

def _map_classification_to_execution_status(classification: str) -> str:
    """Map evidence classification to execution status."""
    mapping = {
        "VERIFIED_BY_CURRENT_PR_EXECUTION": "PASSED",
        "FAILED_IN_CURRENT_PR_EXECUTION": "FAILED",
        "SKIPPED_IN_CURRENT_PR_EXECUTION": "SKIPPED",
        "EXISTING_TEST_NOT_RUN_IN_CURRENT_PR": "NOT_RUN",
        "PARTIALLY_COVERED": "NOT_RUN",
        "MISSING_AUTOMATED_COVERAGE": "NOT_RUN",
        "NOT_MAPPED_TRACEABILITY_RISK": "NOT_RUN",
    }
    return mapping.get(classification, "UNKNOWN")

def _build_file_impact_map(db: Session, run, pr, parent_reqs):
    """Build file impact map showing which ACs are affected by each changed file."""
    from app.models.pull_request import PullRequestChangedFile
    from app.models.coverage import FileTestLink
    from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
    from app.models.acceptance_criterion import AcceptanceCriterion
    from app.models.test_result import TestCase
    from collections import defaultdict
    
    # Get changed files for this PR
    changed_files = db.query(PullRequestChangedFile).filter(
        PullRequestChangedFile.pull_request_id == pr.id
    ).all()
    
    if not changed_files:
        return []
    
    # Build a map of test_case_id -> AC information
    # First, get all manual test requirement mappings for this repository
    manual_mappings = db.query(ManualTestRequirementMapping).filter(
        ManualTestRequirementMapping.repository_id == run.repository_id,
        ManualTestRequirementMapping.is_active == True
    ).all()
    
    # Build test_case_id -> AC ID mapping
    test_to_ac = {}
    for mapping in manual_mappings:
        test_to_ac[mapping.external_test_case_id] = mapping.acceptance_criterion_id
    
    # Get all ACs for this repository
    ac_ids = list(set(test_to_ac.values()))
    ac_by_id = {}
    if ac_ids:
        acs = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id.in_(ac_ids)).all()
        ac_by_id = {ac.id: ac for ac in acs}
    
    # Build a map of requirement_id -> classification for parent_reqs
    req_to_classification = {}
    for req in parent_reqs:
        req_to_classification[req.requirement_id] = req.classification.value if hasattr(req.classification, "value") else str(req.classification)
    
    # Build file impact map
    file_impact_map = []
    
    for changed_file in changed_files:
        # Find FileTestLink records for this file
        file_links = db.query(FileTestLink).filter(
            FileTestLink.file_path == changed_file.file_path
        ).all()
        
        if not file_links:
            continue
        
        # Collect affected ACs
        affected_acs = []
        seen_ac_ids = set()
        
        for link in file_links:
            test_case_id = link.test_case_id
            
            # Check if this test is mapped to an AC
            if test_case_id in test_to_ac:
                ac_id = test_to_ac[test_case_id]
                
                if ac_id in seen_ac_ids:
                    continue
                seen_ac_ids.add(ac_id)
                
                ac = ac_by_id.get(ac_id)
                if ac:
                    # Get classification from parent_reqs
                    classification = req_to_classification.get(str(ac_id), "UNKNOWN")
                    
                    affected_acs.append({
                        "acId": f"AC-{ac.source_number}" if ac.source_number else ac.normalized_key,
                        "title": ac.text,
                        "group": _map_classification_to_group(classification),
                        "executionStatus": _map_classification_to_execution_status(classification)
                    })
        
        if affected_acs:
            file_impact_map.append({
                "filePath": changed_file.file_path,
                "changeStatus": changed_file.status,
                "affectedAcs": affected_acs
            })
    
    return file_impact_map

@router.get("/{recommendation_run_id}/regression-evidence", status_code=status.HTTP_200_OK)
def get_regression_evidence_classification(
    recommendation_run_id: UUID,
    audit: bool = Query(False),
    include_business_context: bool = Query(True, description="Include business context annotations"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get regression evidence classification using the Requirement Evidence Graph Service.
    
    This endpoint provides the RecommendationEvidenceViewModel as the single source of truth
    for all UI components, distinguishing between verified tests, missing tests, and coverage gaps.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.pull_request import PullRequest
    from fastapi.responses import JSONResponse
    from app.services.regression_evidence_classifier import EvidenceClassification
    from app.config import settings
    from app.dependencies.authorization import validate_recommendation_run_access
    
    run = validate_recommendation_run_access(db, recommendation_run_id, user)
    
    # Get pull request
    pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request not found for recommendation run."
        )
    
    # Initialize requirement evidence graph service
    graph_service = RequirementEvidenceGraphService(db)
    
    # Safely extract changed files
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        raw = run.input_snapshot.changed_files
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    changed_files.append(item)
                elif isinstance(item, dict):
                    fp = item.get("file_path") or item.get("filename")
                    if fp:
                        changed_files.append(fp)
    if not changed_files:
        import logging
        logging.getLogger(__name__).warning("changed_files unavailable in recommendation input snapshot")
    
    # Resolve AC text
    ac_source = _resolve_acceptance_criteria_text(run, pr, db)
    
    # Build evidence graph and view model safely
    try:
        view_model = graph_service.build_evidence_graph(
            repository_id=str(run.repository_id),
            pull_request_id=str(pr.id),
            head_sha=pr.head_commit_sha,
            changed_files=changed_files,
            pr_description=ac_source["text"],
            recommendation_run_id=str(recommendation_run_id)
        )
        
        # Merge diagnostics info
        if "diagnostics" not in view_model.diagnostics:
            view_model.diagnostics["diagnostics"] = []
        for diag in ac_source.get("diagnostics", []):
            if diag not in view_model.diagnostics.get("diagnostics", []):
                view_model.diagnostics.setdefault("diagnostics", []).append(diag)
        view_model.diagnostics["ac_source_type"] = ac_source.get("source_type")
        view_model.diagnostics["ac_source_id"] = ac_source.get("source_id")
        view_model.diagnostics["ac_source_hash"] = ac_source.get("source_hash")

        # Persist graph snapshot
        graph_service.persist_graph_snapshot(str(recommendation_run_id), view_model)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"Regression evidence build failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "ERROR",
                "error_code": "REGRESSION_EVIDENCE_BUILD_FAILED",
                "message": str(e),
                "recommendationRunId": str(recommendation_run_id),
                "canRenderRecommendation": False
            }
        )
    
    # Filter parent requirements
    parent_reqs = [
        req for req in getattr(view_model, "requirements", [])
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    verified_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION)
    failed_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION)
    skipped_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION)
    required_not_run_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR)
    missing_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE)
    partial_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED)
    not_mapped_count = sum(1 for r in parent_reqs if r.classification == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK)
    
    health = view_model.health
    can_render_recommendation = view_model.can_render_recommendation
    
    # Resolve primary CTA and secondary CTAs
    if health in ("VALIDATION_PASSED_TRACEABILITY_INCOMPLETE", "VALIDATION_PASSED_COVERAGE_INCOMPLETE"):
        primary_cta = "Review Missing & Partial Coverage"
        secondary_ctas = ["Create Targeted Regression Scope", "Export Evidence Report"]
    else:
        primary_cta = view_model.decision_copy.primary_cta
        secondary_ctas = [view_model.decision_copy.secondary_cta] if view_model.decision_copy.secondary_cta else []
        
    decision_summary = {
        "totalCurrentPrTests": view_model.counts.get("uploadedPrTestsTotal", 0),
        "passedCurrentPrTests": view_model.counts.get("uploadedPrTestsPassed", 0),
        "failedCurrentPrTests": view_model.counts.get("uploadedPrTestsFailed", 0),
        "skippedCurrentPrTests": view_model.counts.get("uploadedPrTestsSkipped", 0),
        "totalParentRequirements": len(parent_reqs),
        "coveredByPassedPrTests": verified_count,
        "partiallySupported": partial_count,
        "missingAutomatedCoverage": missing_count,
        "traceabilityReviewNeeded": not_mapped_count,
        "health": health,
        "canRenderRecommendation": can_render_recommendation,
        "primaryCta": primary_cta,
        "secondaryCtas": secondary_ctas,
        "decisionCopy": {
            "headline": view_model.decision_copy.headline,
            "explanation": view_model.decision_copy.explanation,
            "nextAction": view_model.decision_copy.next_action,
            "primaryCta": primary_cta,
            "secondaryCta": secondary_ctas[0] if secondary_ctas else "",
        }
    }
    # Initialize business context service if enabled
    business_context_service = None
    if settings.BUSINESS_CONTEXT_ENABLED and include_business_context:
        from app.services.business_understanding.business_context_service import BusinessContextService
        business_context_service = BusinessContextService()
    
    # Load active risk reviews for this run using shared RiskReviewService
    from app.services.risk_review_service import RiskReviewService
    from app.models.risk_review import RiskReview
    from app.models.acceptance_criterion import AcceptanceCriterion
    
    # Use the shared review state method which uses build_reviewable_gap_index
    review_state = RiskReviewService.get_review_state(db, run)
    active_reviews = db.query(RiskReview).filter(
        RiskReview.recommendation_run_id == recommendation_run_id,
        RiskReview.is_active == True
    ).all()
    reviews_by_req_id = {r.source_requirement_id: r for r in active_reviews if r.source_requirement_id}
    reviews_by_ac_num = {r.source_ac_number: r for r in active_reviews if r.source_ac_number is not None}
        
    # Phase 6.1: Bulk load mappings and executions to prevent N+1 queries
    from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
    from app.models.manual_test_execution import ManualTestExecution
    from app.models.external_test_case_detailed import ExternalTestCase
    from sqlalchemy import or_

    parent_req_ids = [r.requirement_id for r in parent_reqs]
    parent_uuids = []
    for r_id in parent_req_ids:
        try:
            parent_uuids.append(UUID(r_id) if isinstance(r_id, str) else r_id)
        except ValueError:
            pass

    # Query active mappings
    active_mappings = db.query(ManualTestRequirementMapping).filter(
        ManualTestRequirementMapping.acceptance_criterion_id.in_(parent_uuids),
        ManualTestRequirementMapping.is_active == True
    ).all()

    # Bulk-load acceptance criteria for these UUIDs to prevent N+1 query
    ac_by_id = {}
    if parent_uuids:
        acs = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id.in_(parent_uuids)).all()
        ac_by_id = {ac.id: ac for ac in acs}

    mapped_test_case_ids = list({m.external_test_case_id for m in active_mappings})

    # Bulk-load external test cases
    test_cases_by_id = {}
    if mapped_test_case_ids:
        tcs = db.query(ExternalTestCase).filter(ExternalTestCase.id.in_(mapped_test_case_ids)).all()
        test_cases_by_id = {tc.id: tc for tc in tcs}

    # Bulk-load latest executions
    latest_executions_by_test_id = {}
    if mapped_test_case_ids:
        executions = db.query(ManualTestExecution).filter(
            ManualTestExecution.external_test_case_id.in_(mapped_test_case_ids),
            ManualTestExecution.is_active == True,
            or_(
                ManualTestExecution.pull_request_id == run.pull_request_id,
                ManualTestExecution.recommendation_run_id == run.id
            )
        ).all()
        for exec_rec in executions:
            test_id = exec_rec.external_test_case_id
            existing_exec = latest_executions_by_test_id.get(test_id)
            if not existing_exec or exec_rec.executed_at > existing_exec.executed_at:
                latest_executions_by_test_id[test_id] = exec_rec

    # Group mappings by AC UUID
    mappings_by_ac_id = {}
    for mapping in active_mappings:
        ac_id = mapping.acceptance_criterion_id
        if ac_id not in mappings_by_ac_id:
            mappings_by_ac_id[ac_id] = []
        mappings_by_ac_id[ac_id].append(mapping)

    def serialize_requirement(req, audit_enabled: bool):
        # Resolve acceptance_criterion UUID and manual validation channel
        req_uuid = None
        try:
            req_uuid = UUID(req.requirement_id) if isinstance(req.requirement_id, str) else req.requirement_id
        except ValueError:
            pass

        item = {
            "requirementId": req.requirement_id,
            "readableId": req.readable_id,
            "title": req.title,
            "flow": req.flow,
            "riskLevel": req.risk_level,
            "classification": req.classification.value if hasattr(req.classification, "value") else str(req.classification),
        }

        # Calculate risk score using RiskScoringService
        from app.services.risk_based_regression.risk_scoring_service import RiskScoringService

        # Map classification to coverage status
        classification_to_coverage = {
            "VERIFIED_BY_CURRENT_PR_EXECUTION": "VERIFIED",
            "PARTIALLY_COVERED": "PARTIAL",
            "MISSING_AUTOMATED_COVERAGE": "MISSING",
            "FAILED_IN_CURRENT_PR_EXECUTION": "FAILED",
            "SKIPPED_IN_CURRENT_PR_EXECUTION": "SKIPPED",
            "EXISTING_TEST_NOT_RUN_IN_CURRENT_PR": "NOT_RUN",
            "NOT_MAPPED_TRACEABILITY_RISK": "MISSING",
        }

        coverage_status = classification_to_coverage.get(
            req.classification.value if hasattr(req.classification, "value") else str(req.classification),
            "VERIFIED"
        )

        # Use effective risk level from review if available, otherwise use original
        effective_risk_level = req.risk_level

        # Calculate risk score
        risk_score_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk=effective_risk_level,
            coverage_status=coverage_status,
            criticality=effective_risk_level,  # Using risk level as criticality for now
            requirement_type="FUNCTIONAL",  # Default to functional, could be enhanced
            risk_review_adjustment=None  # Could be enhanced to use review adjustments
        )

        item["riskScore"] = risk_score_result["riskScore"]
        item["riskScoreReason"] = risk_score_result["riskScoreReason"]
        item["riskBand"] = risk_score_result["riskBand"]

        # Phase 6.4: Add manual evidence risk adjustment fields
        item["generatedRiskBand"] = risk_score_result["riskBand"]
        item["manualContributionStatus"] = None
        item["residualRiskBand"] = risk_score_result["riskBand"]
        item["riskAdjustmentReason"] = None
        item["riskAdjustmentDelta"] = 0

        # Calculate change impact using ChangeImpactService
        from app.services.change_impact_service import ChangeImpactService

        # Get linked files for this requirement if available
        linked_files = []
        if hasattr(req, 'linked_existing_tests'):
            linked_files = [t.file_path for t in req.linked_existing_tests if hasattr(t, 'file_path')]

        # Calculate change impact for this requirement
        change_impact_result = ChangeImpactService.match_file_to_requirement(
            file_path=changed_files[0] if changed_files else "",
            requirement_id=req.requirement_id,
            requirement_title=req.title,
            linked_files=linked_files if linked_files else None
        )

        item["changeImpact"] = {
            "level": change_impact_result["level"],
            "matchedFiles": change_impact_result["matchedFiles"],
            "matchedPatterns": change_impact_result["matchedPatterns"],
            "explanation": change_impact_result["explanation"]
        }

        # Add risk review information
        review_rec = reviews_by_req_id.get(req.requirement_id)
        if not review_rec:
            # Fallback to source AC number
            ac = ac_by_id.get(req_uuid)
            if ac and ac.source_number is not None:
                review_rec = reviews_by_ac_num.get(ac.source_number)
        
        if review_rec and review_rec.review_status != "UNREVIEWED":
            item["businessRiskReview"] = {
                "reviewStatus": review_rec.review_status,
                "originalRiskLevel": review_rec.original_risk_level,
                "originalPriority": review_rec.original_priority,
                "reviewedRiskLevel": review_rec.reviewed_risk_level,
                "reviewedPriority": review_rec.reviewed_priority,
                "effectiveRiskLevel": review_rec.reviewed_risk_level if review_rec.review_status == "OVERRIDDEN" else review_rec.original_risk_level,
                "effectivePriority": review_rec.reviewed_priority if review_rec.review_status == "OVERRIDDEN" else review_rec.original_priority,
                "reviewerName": review_rec.reviewer_name,
                "reviewNote": review_rec.review_note,
                "updatedAt": review_rec.updated_at.isoformat()
            }
            # Override riskLevel with effective risk for display
            item["riskLevel"] = item["businessRiskReview"]["effectiveRiskLevel"]
        else:
            item["businessRiskReview"] = {
                "reviewStatus": "UNREVIEWED",
                "originalRiskLevel": req.risk_level,
                "originalPriority": "UNKNOWN",
                "reviewedRiskLevel": req.risk_level,
                "reviewedPriority": "UNKNOWN",
                "effectiveRiskLevel": req.risk_level,
                "effectivePriority": "UNKNOWN",
                "reviewerName": None,
                "reviewNote": None,
                "updatedAt": None
            }
        
        if business_context_service:
            business_context = business_context_service.generate_business_context(
                requirement_text=req.title,
                requirement_title=req.readable_id,
                requirement_id=req.requirement_id,
                matched_tests=[t.title for t in getattr(req, "linked_existing_tests", [])],
                pr_title=pr.title if pr else "",
                pr_description=getattr(pr, "description", ""),
                changed_files=changed_files
            )
            bc_dict = business_context.to_dict()
            # Override with effective risk from review if available
            if item["businessRiskReview"]["reviewStatus"] != "UNREVIEWED":
                bc_dict["riskLevel"] = item["businessRiskReview"]["effectiveRiskLevel"]
                bc_dict["priority"] = item["businessRiskReview"]["effectivePriority"]
            item["businessContext"] = bc_dict
            
        if audit_enabled:
            # Gather rejection reasons for this requirement
            rejection_reasons = []
            for entry in getattr(view_model, "match_table", []):
                if entry.requirement_id == req.requirement_id and entry.decision != "MATCHED":
                    reason = entry.reason
                    if entry.contradiction_penalty > 0:
                        reason = f"{reason} (contradiction penalty: {entry.contradiction_penalty})"
                    rejection_reasons.append(reason)
            
            item["diagnostics"] = {
                "internalId": req.requirement_id,
                "matchScore": req.match_score,
                "sourceHash": req.source_hash,
                "rejectionReasons": rejection_reasons,
                "mismatchFlags": {
                    "JUNIT_AC_ID_MISMATCH": req.match_diagnostics.get("JUNIT_AC_ID_MISMATCH", False),
                    "contextMismatch": req.match_diagnostics.get("context_mismatch", False),
                    "countMismatch": req.match_diagnostics.get("count_mismatch", False)
                }
            }

        ac_mappings = mappings_by_ac_id.get(req_uuid, [])
        mapped_count = len(ac_mappings)
        
        executed_count = 0
        passed_count = 0
        failed_count = 0
        blocked_count = 0
        skipped_count = 0
        evidence_urls = []
        manual_tests_list = []
        newest_exec = None
        latest_outcome = None
        latest_executed_at = None
        latest_test_title = None

        for mapping in ac_mappings:
            tc = test_cases_by_id.get(mapping.external_test_case_id)
            tc_title = tc.title if tc else "Unknown Test"
            exec_rec = latest_executions_by_test_id.get(mapping.external_test_case_id)
            
            test_info = {
                "id": str(mapping.external_test_case_id),
                "title": tc_title,
                "outcome": "NOT_EXECUTED",
                "executedAt": None,
                "executedByName": None,
                "evidenceUrl": None,
                "mappingSource": mapping.mapping_source
            }
            
            if exec_rec:
                executed_count += 1
                outcome = exec_rec.outcome.upper() if exec_rec.outcome else "NOT_EXECUTED"
                if outcome == "PASSED":
                    passed_count += 1
                elif outcome == "FAILED":
                    failed_count += 1
                elif outcome == "BLOCKED":
                    blocked_count += 1
                elif outcome == "SKIPPED":
                    skipped_count += 1
                    
                test_info["outcome"] = outcome
                test_info["executedAt"] = exec_rec.executed_at.isoformat() + "Z" if exec_rec.executed_at else None
                test_info["executedByName"] = exec_rec.executed_by_name
                test_info["evidenceUrl"] = exec_rec.evidence_url
                
                if exec_rec.evidence_url:
                    evidence_urls.append(exec_rec.evidence_url)
                    
                if not newest_exec or exec_rec.executed_at > newest_exec.executed_at:
                    newest_exec = exec_rec
                    
            manual_tests_list.append(test_info)
            
        if newest_exec:
            latest_outcome = newest_exec.outcome
            latest_executed_at = newest_exec.executed_at.isoformat() + "Z" if newest_exec.executed_at else None
            tc = test_cases_by_id.get(newest_exec.external_test_case_id)
            if tc:
                latest_test_title = tc.title
            
        if mapped_count == 0:
            manual_status = "NOT_MAPPED"
        elif executed_count == 0:
            manual_status = "NOT_EXECUTED"
        elif failed_count > 0:
            manual_status = "FAILED"
        elif blocked_count > 0:
            manual_status = "BLOCKED"
        elif passed_count > 0:
            manual_status = "PASSED"
        else:
            manual_status = "SKIPPED"
            
        status_to_support_status = {
            "PASSED": "MANUALLY_SUPPORTED",
            "FAILED": "MANUAL_FAILED",
            "BLOCKED": "MANUAL_BLOCKED",
            "SKIPPED": "MANUAL_SKIPPED",
            "NOT_EXECUTED": "MANUAL_NOT_EXECUTED",
            "NOT_MAPPED": "MANUAL_NOT_MAPPED"
        }
        manual_support_status = status_to_support_status[manual_status]
        
        item["manualSupportStatus"] = manual_support_status
        item["manualValidation"] = {
            "status": manual_status,
            "supportStatus": manual_support_status,
            "mappedManualTestsCount": mapped_count,
            "executedManualTestsCount": executed_count,
            "passedManualTestsCount": passed_count,
            "failedManualTestsCount": failed_count,
            "blockedManualTestsCount": blocked_count,
            "skippedManualTestsCount": skipped_count,
            "latestOutcome": newest_exec.outcome.upper() if newest_exec and newest_exec.outcome else None,
            "latestExecutedAt": newest_exec.executed_at.isoformat() + "Z" if newest_exec and newest_exec.executed_at else None,
            "latestExecutedByName": newest_exec.executed_by_name if newest_exec else None,
            "evidenceUrls": evidence_urls,
            "manualTests": manual_tests_list
        }

        item["manualTraceabilitySignals"] = {
            "mappedManualTestsCount": mapped_count,
            "latestManualExecutionOutcome": latest_outcome,
            "latestManualExecutionAt": latest_executed_at,
            "latestManualTestTitle": latest_test_title
        }

        return item



    buckets = {
        "coveredByPassedPrTests": [serialize_requirement(r, audit) for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION],
        "partiallySupported": [serialize_requirement(r, audit) for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED],
        "missingAutomatedCoverage": [serialize_requirement(r, audit) for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE],
        "traceabilityReviewNeeded": [serialize_requirement(r, audit) for r in parent_reqs if r.classification == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK],
    }

    scope_recommendation = {
        "requiredItems": [serialize_requirement(r, audit) for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE],
        "reviewItems": [
            {**serialize_requirement(r, audit), "reviewReason": "needs review or stronger assertion coverage", "notes": "needs review or stronger assertion coverage"}
            for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED
        ],
        "optionalSafetyNetItems": [serialize_requirement(r, audit) for r in parent_reqs if r.classification == EvidenceClassification.OPTIONAL_IMPROVEMENT],
        "excludedAlreadyVerifiedRequirements": [
            {
                "type": "requirement",
                "requirementId": r.requirement_id,
                "readableId": r.readable_id,
                "title": r.title
            }
            for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
        ],
        "excludedAlreadyPassedTests": [
            {
                "type": "test",
                "testId": t.id,
                "title": t.title,
                "classname": t.classname
            }
            for t in view_model.verified_by_current_pr
        ],
        "generationRulesApplied": [
            "Exclude passed current PR tests from regression scope",
            "Include missing automated coverage in required scope",
            "Include partially covered items in review scope"
        ]
    }

    # Phase 5.8: Use V2 regression scope as source of truth for release decision
    # Get V2 regression scope to determine release decision state
    from app.services.regression_scope_v2_service import RegressionScopeV2Service
    from app.schemas.regression_scope_v2 import ScopeMode
    
    try:
        v2_scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(run.id),
            mode=ScopeMode.TARGETED,
            include_safe_to_skip=False,
            include_diagnostics=False,
            audit=False
        )
        
        # Convert to dictionary representation for easy querying
        v2_scope_dict = v2_scope.model_dump() if hasattr(v2_scope, 'model_dump') else v2_scope.dict()
        groups_dict = v2_scope_dict.get("groups", {})
        
        # Extract counts from V2 scope for release decision
        required_count = len(groups_dict.get("REQUIRED", {}).get("items", []))
        review_needed_count = len(groups_dict.get("REVIEW_NEEDED", {}).get("items", []))
        already_verified_count = len(groups_dict.get("EXCLUDED_ALREADY_VERIFIED", {}).get("items", []))
        
        # Determine release decision state based on V2 scope
        if required_count > 0:
            release_decision_state = "BLOCKED"
            release_decision_reason = f"{required_count} required items need action before release"
        elif review_needed_count > 0:
            release_decision_state = "NEEDS_REVIEW"
            release_decision_reason = f"{review_needed_count} items need review"
        else:
            release_decision_state = "READY"
            release_decision_reason = f"All {already_verified_count} items verified"
        
        # Update decision_summary to use V2 scope counts
        decision_summary.update({
            "totalItems": sum(len(group.get("items", [])) for group in groups_dict.values()),
            "requiredCount": required_count,
            "reviewNeededCount": review_needed_count,
            "alreadyVerifiedCount": already_verified_count,
            "recommendedCount": len(groups_dict.get("RECOMMENDED", {}).get("items", [])),
            "optionalCount": len(groups_dict.get("OPTIONAL", {}).get("items", [])),
            "safeToSkipCount": len(groups_dict.get("SAFE_TO_SKIP", {}).get("items", [])),
            "state": release_decision_state,
            "reason": release_decision_reason,
            "source": "V2_REGRESSION_SCOPE"
        })
        
        # Update scopeRecommendation to use V2 scope
        scope_recommendation = {
            "requiredItems": groups_dict.get("REQUIRED", {}).get("items", []),
            "reviewItems": groups_dict.get("REVIEW_NEEDED", {}).get("items", []),
            "recommendedItems": groups_dict.get("RECOMMENDED", {}).get("items", []),
            "optionalItems": groups_dict.get("OPTIONAL", {}).get("items", []),
            "excludedAlreadyVerifiedItems": groups_dict.get("EXCLUDED_ALREADY_VERIFIED", {}).get("items", []),
            "safeToSkipItems": groups_dict.get("SAFE_TO_SKIP", {}).get("items", []),
            "generationRulesApplied": [
                "Phase 5: Change Impact Engine v1",
                "Candidate selection based on impact type (DIRECT, INDIRECT, CROSS_LAYER, SECURITY_SENSITIVE)",
                "Evidence overlay applied after candidate selection",
                "Mode-specific selection strategies (targeted, risk_based, full_suite)"
            ]
        }
        
    except Exception as e:
        logger.error(f"[Phase5.8] Failed to get V2 scope for release decision: {e}")
        # Fallback to legacy logic if V2 fails
        decision_summary = {
            "state": "UNKNOWN",
            "reason": f"V2 scope generation failed: {str(e)}",
            "source": "LEGACY_FALLBACK"
        }
        scope_recommendation = {}

    # Add release decision to response
    from app.models.release_decision import ReleaseDecision
    release_decision = db.query(ReleaseDecision).filter(
        ReleaseDecision.recommendation_run_id == run.id,
        ReleaseDecision.is_active == True
    ).first()

    release_decision_data = None
    if release_decision:
        release_decision_data = {
            "decisionStatus": release_decision.decision_status,
            "approverName": release_decision.approver_name,
            "snapshotHash": release_decision.snapshot_hash,
            "decisionNote": release_decision.decision_note,
            "createdAt": release_decision.created_at.isoformat() + "Z" if release_decision.created_at else None,
            "updatedAt": release_decision.updated_at.isoformat() + "Z" if release_decision.updated_at else None
        }

    # Build file impact map
    file_impact_map = _build_file_impact_map(db, run, pr, parent_reqs)

    return {
        "decisionSummary": decision_summary,
        "buckets": buckets,  # Keep legacy buckets for backward compatibility
        "scopeRecommendation": scope_recommendation,
        "releaseDecision": release_decision_data,
        "fileImpactMap": file_impact_map,
        "v2ScopeSource": "Phase 5 Change Impact Engine v1"  # Indicate source
    }


@router.post("/{recommendation_run_id}/acknowledge-readiness", status_code=status.HTTP_200_OK)
def acknowledge_recommendation_readiness(
    recommendation_run_id: str,
    request: ReadinessAcknowledgementCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Store user acknowledgement of missing inputs for a recommendation run.
    """
    from datetime import datetime
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.schemas.readiness import ReadinessAcknowledgementCreate

    rec_run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    if not rec_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )

    # Verify workspace ownership
    repo = db.query(Repository).filter(
        Repository.id == rec_run.repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation run does not belong to this workspace"
        )

    # Persist acknowledgement fields
    rec_run.readiness_acknowledged = True
    rec_run.readiness_acknowledged_at = datetime.utcnow()
    rec_run.readiness_acknowledged_missing_inputs = request.acknowledged_missing_inputs
    rec_run.readiness_decision = request.decision
    
    db.commit()
    
    return {"status": "acknowledged", "recommendation_run_id": str(rec_run.id)}


@router.get("/{recommendation_run_id}/release-decision", status_code=status.HTTP_200_OK)
def get_release_decision(
    recommendation_run_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_risk_recommendations: bool = Query(False, description="Include risk-aware decision recommendations")
):
    """Get current release decision state for a recommendation run."""
    from app.services.release_decision_service import ReleaseDecisionService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, user)

    if include_risk_recommendations:
        # Get requirements with risk data from the regression evidence
        # For Phase 3.3, we'll fetch requirements from the evidence graph
        # This is a simplified implementation - in production, this would be optimized
        from app.models.recommendation import RecommendationOutcome
        
        # Fetch requirements with risk data
        outcomes = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run.id
        ).all()
        
        requirements = []
        for outcome in outcomes:
            requirements.append({
                "requirement_id": outcome.requirement_id,
                "title": outcome.title or "",
                "risk_score": getattr(outcome, 'risk_score', 0) or 0,
                "risk_band": getattr(outcome, 'risk_band', 'LOW') or 'LOW',
                "coverage_bucket": outcome.classification or 'COVERED'
            })
        
        return ReleaseDecisionService.get_risk_aware_release_state(db, run.id, requirements)
    else:
        return ReleaseDecisionService.get_release_state(db, run.id)


@router.post("/{recommendation_run_id}/release-decision", status_code=status.HTTP_201_CREATED)
def submit_release_decision(
    recommendation_run_id: UUID,
    request: ReleaseDecisionSubmit,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a release decision (APPROVED, REJECTED, CONDITIONALLY_APPROVED)."""
    from app.services.release_decision_service import ReleaseDecisionService
    from app.dependencies.authorization import validate_recommendation_run_access
    from app.models.user import WorkspaceMember

    run = validate_recommendation_run_access(db, recommendation_run_id, actor)

    # Authorization: Only OWNER and ADMIN may approve/reject releases
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == run.workspace_id,
        WorkspaceMember.user_id == actor.id
    ).first()

    if not member or member.role not in ("OWNER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="RELEASE_APPROVAL_ACCESS_DENIED: Only workspace OWNER and ADMIN roles may approve or reject releases."
        )

    try:
        decision = ReleaseDecisionService.submit_release_decision(
            db, run, request.dict(), actor,
            live_evidence_health=request.live_evidence_health
        )
        return decision
    except ValueError as e:
        error_msg = str(e)
        if "RELEASE_SNAPSHOT_MISMATCH" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        elif "RELEASE_DECISION_BLOCKED" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif "DECISION_NOTE_REQUIRED" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )


@router.post("/{recommendation_run_id}/release-decision/reset", status_code=status.HTTP_200_OK)
def reset_release_decision(
    recommendation_run_id: UUID,
    request: ReleaseDecisionReset,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset a release decision back to PENDING_REVIEW."""
    from app.services.release_decision_service import ReleaseDecisionService
    from app.dependencies.authorization import validate_recommendation_run_access
    from app.models.user import WorkspaceMember

    run = validate_recommendation_run_access(db, recommendation_run_id, actor)

    # Authorization: Only OWNER and ADMIN may reset release decisions
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == run.workspace_id,
        WorkspaceMember.user_id == actor.id
    ).first()

    if not member or member.role not in ("OWNER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="RELEASE_APPROVAL_ACCESS_DENIED: Only workspace OWNER and ADMIN roles may reset release decisions."
        )

    try:
        decision = ReleaseDecisionService.reset_release_decision(
            db, run, request.dict(), actor,
            live_evidence_health=request.live_evidence_health
        )
        return decision
    except ValueError as e:
        error_msg = str(e)
        if "RELEASE_SNAPSHOT_MISMATCH" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        elif "NO_ACTIVE_DECISION" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )


@router.get("/{recommendation_run_id}/release-decision/history", status_code=status.HTTP_200_OK)
def get_release_decision_history(
    recommendation_run_id: UUID,
    audit: bool = Query(False, description="Expose internal IDs in audit mode"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get release decision history for a recommendation run."""
    from app.services.release_decision_service import ReleaseDecisionService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, user)
    return ReleaseDecisionService.get_release_history(db, run.id, audit_mode=audit)


@router.get("/{recommendation_run_id}/regression-scope", status_code=status.HTTP_200_OK)
def get_regression_scope_v2(
    recommendation_run_id: UUID,
    mode: str = Query("targeted", description="Scope generation mode: targeted, risk_based, full"),
    include_safe_to_skip: bool = Query(False, description="Include safe-to-skip items"),
    include_diagnostics: bool = Query(False, description="Include diagnostic information"),
    audit: bool = Query(False, description="Include audit information"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unified regression scope V2 for a recommendation run."""
    from app.services.regression_scope_v2_service import RegressionScopeV2Service
    from app.schemas.regression_scope_v2 import (
        RegressionScopeV2Response,
        ScopeMode
    )
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, user)

    logger.info(
        "REGRESSION_SCOPE_MODE_RECEIVED",
        extra={
            "recommendation_run_id": str(recommendation_run_id),
            "mode": mode,
        },
    )

    try:
        # Validate mode
        try:
            scope_mode = ScopeMode(mode)
        except ValueError:
            return RegressionScopeV2Response(
                status="ERROR",
                scope=None,
                error_code="INVALID_MODE",
                message=f"Invalid mode: {mode}. Must be one of: targeted, risk_based, full_suite"
            )

        # Generate scope
        try:
            logger.info(f"[ScopeGen] Starting scope generation for run_id={run.id}, mode={scope_mode}")
            scope = RegressionScopeV2Service.generate_scope_v2(
                db=db,
                run_id=str(run.id),
                mode=scope_mode,
                include_safe_to_skip=include_safe_to_skip,
                include_diagnostics=include_diagnostics,
                audit=audit
            )
            logger.info(f"[ScopeGen] Scope generation completed successfully for run_id={run.id}")
            
            response = RegressionScopeV2Response(
                status="SUCCESS",
                scope=scope,
                mode=scope_mode
            )
            logger.info(f"[ScopeGen] Response object created with mode={scope_mode}, attempting to serialize")
            return response
        except AttributeError as e:
            logger.error(
                f"[ScopeGen] AttributeError during scope generation: {e}"
            )
            return RegressionScopeV2Response(
                status="ERROR",
                scope=None,
                error_code="ATTRIBUTE_ERROR",
                message=f"Scope generation failed: {str(e)}"
            )
    except ValueError as e:
        return RegressionScopeV2Response(
            status="ERROR",
            scope=None,
            error_code="VALIDATION_ERROR",
            message=str(e)
        )
    except Exception as e:
        import traceback
        logger.error(f"[ScopeGen] Full traceback:\n{traceback.format_exc()}")
        return RegressionScopeV2Response(
            status="ERROR",
            scope=None,
            error_code="INTERNAL_ERROR",
            message=str(e)
        )


@router.get("/{recommendation_run_id}/risk-reviews", status_code=status.HTTP_200_OK)
def get_recommendation_risk_reviews(
    recommendation_run_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get risk review state for all missing and partial items."""
    from app.services.risk_review_service import RiskReviewService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, user)
    return RiskReviewService.get_review_state(db, run)


@router.post("/{recommendation_run_id}/risk-reviews", status_code=status.HTTP_201_CREATED)
def submit_recommendation_risk_review(
    recommendation_run_id: UUID,
    request: RiskReviewSubmit,
    reviewer: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit one risk review."""
    from app.services.risk_review_service import RiskReviewService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, reviewer)
    review = RiskReviewService.submit_review(db, run, request.dict(), reviewer)
    return review


@router.post("/{recommendation_run_id}/risk-reviews/bulk-accept", status_code=status.HTTP_200_OK)
def bulk_accept_recommendation_risk(
    recommendation_run_id: UUID,
    request: BulkAcceptRequest,
    reviewer: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk accept all generated risks for missing/partial items."""
    from app.services.risk_review_service import RiskReviewService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, reviewer)
    result = RiskReviewService.bulk_accept(db, run, request.dict(), reviewer)
    return result


@router.delete("/{recommendation_run_id}/risk-reviews/{review_id}", status_code=status.HTTP_200_OK)
def delete_recommendation_risk_review(
    recommendation_run_id: UUID,
    review_id: UUID,
    snapshotHash: Optional[str] = Query(None),
    reviewer: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate a specific review override."""
    from app.services.risk_review_service import RiskReviewService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, reviewer)
    RiskReviewService.reset_review(db, run, review_id, {"snapshotHash": snapshotHash}, reviewer)
    return {"status": "SUCCESS"}


@router.post("/{recommendation_run_id}/risk-reviews/reset", status_code=status.HTTP_200_OK)
def reset_recommendation_risk_review(
    recommendation_run_id: UUID,
    request: ResetReviewRequest,
    reviewer: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate review override for a specific item."""
    from app.services.risk_review_service import RiskReviewService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, reviewer)
    RiskReviewService.reset_review_by_item(db, run, request.dict(), reviewer)
    return {"status": "SUCCESS"}


@router.get("/{recommendation_run_id}/risk-reviews/history", response_model=RiskReviewHistoryResponse, status_code=status.HTTP_200_OK)
def get_recommendation_risk_review_history(
    recommendation_run_id: UUID,
    sourceAcNumber: Optional[int] = Query(None, description="Filter by source AC number"),
    readableId: Optional[str] = Query(None, description="Filter by readable ID"),
    sourceRequirementId: Optional[str] = Query(None, description="Filter by source requirement ID"),
    includeInactive: bool = Query(True, description="Include inactive history events"),
    limit: Optional[int] = Query(None, description="Limit result size"),
    offset: Optional[int] = Query(None, description="Offset result size"),
    audit: bool = Query(False, description="Expose internal UUIDs and snapshot hash"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete, user-friendly audit trail for risk review decisions."""
    from app.services.risk_review_service import RiskReviewService
    from app.dependencies.authorization import validate_recommendation_run_access

    run = validate_recommendation_run_access(db, recommendation_run_id, user)
    return RiskReviewService.get_review_history(
        db=db,
        run=run,
        source_ac_number=sourceAcNumber,
        readable_id=readableId,
        source_requirement_id=sourceRequirementId,
        include_inactive=includeInactive,
        limit=limit,
        offset=offset,
        audit=audit
    )



@router.post("/{recommendation_run_id}/create-targeted-scope", status_code=status.HTTP_200_OK)
def create_targeted_regression_scope(
    recommendation_run_id: str,
    request: CreateTargetedScopeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a targeted regression scope from the evidence graph.
    
    This endpoint generates a scope based on the final backend evidence buckets,
    excluding already verified requirements and already passed tests.
    """
    import uuid
    from datetime import datetime
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.models.pull_request import PullRequest, PullRequestSnapshot
    from app.models.acceptance_criterion import AcceptanceCriterion
    from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
    from app.services.regression_evidence_classifier import EvidenceClassification
    from app.config import settings
    from app.dependencies.authorization import validate_recommendation_run_access
    
    run_uuid = uuid.UUID(recommendation_run_id) if isinstance(recommendation_run_id, str) else recommendation_run_id
    run = validate_recommendation_run_access(db, run_uuid, user)
    
    # Check if evidence graph is stale
    if run.input_snapshot and run.input_snapshot.is_stale:
        return CreateTargetedScopeResponse(
            status="REQUIRES_REGENERATION",
            error_code="STALE_EVIDENCE_GRAPH",
            message="Evidence graph is stale. Regenerate recommendation before creating scope."
        )
    
    # Validate snapshot freshness against canonical sources
    if run.requirement_evidence_snapshot_json:
        import json
        snapshot_data = json.loads(run.requirement_evidence_snapshot_json)
        snapshot_parent_count = snapshot_data.get("counts", {}).get("totalRequirements", 0)
        
        # Get canonical AC count
        canonical_parent_count = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == run.pr_id
        ).count()
        
        if snapshot_parent_count != canonical_parent_count:
            return CreateTargetedScopeResponse(
                status="REQUIRES_REGENERATION",
                error_code="SNAPSHOT_PARENT_REQUIREMENT_COUNT_MISMATCH",
                message=f"Snapshot is stale: contains {snapshot_parent_count} parent requirements, but canonical source has {canonical_parent_count}. Regenerate recommendation before creating scope."
            )
    
    # Resolve AC text using the same priority as regression-evidence endpoint
    ac_source = _resolve_acceptance_criteria_text(run, None, db)
    
    if not ac_source["text"]:
        return CreateTargetedScopeResponse(
            status="ERROR",
            error_code="EVIDENCE_GRAPH_UNAVAILABLE",
            message="No acceptance criteria source available. Cannot create scope."
        )
    
    # Get PR snapshot for head_commit_sha
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    
    # Get changed files
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    # Build the evidence graph
    try:
        graph_service = RequirementEvidenceGraphService(db)
        view_model = graph_service.build_evidence_graph(
            str(run.repository_id),
            str(run.pr_id),
            head_sha,
            changed_files,
            pr_description=ac_source["text"],
            recommendation_run_id=str(run.id)
        )
    except Exception as e:
        return CreateTargetedScopeResponse(
            status="ERROR",
            error_code="INTERNAL_EVIDENCE_MODEL_INCONSISTENT",
            message=f"Evidence graph build failed: {str(e)}"
        )
    
    # Check for graph invariant failure
    if view_model.health == "INTERNAL_EVIDENCE_MODEL_INCONSISTENT":
        return CreateTargetedScopeResponse(
            status="ERROR",
            error_code="INTERNAL_EVIDENCE_MODEL_INCONSISTENT",
            message="Evidence graph invariant failed. Cannot create scope."
        )
    
    # Filter parent requirements
    parent_reqs = [
        req for req in view_model.requirements
        if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
    ]
    
    # Build scope items from evidence buckets
    generation_rules = []
    diagnostics = []
    
    # Generate business context if enabled
    business_contexts = {}
    if settings.BUSINESS_CONTEXT_ENABLED and request.include_business_context:
        from app.services.business_understanding.business_context_service import BusinessContextService
        from app.services.risk_review_service import RiskReviewService
        business_context_service = BusinessContextService()
        
        # Use the shared review state method which uses build_reviewable_gap_index
        review_state = RiskReviewService.get_review_state(db, run)
        
        # Load active risk reviews
        from app.models.risk_review import RiskReview
        active_reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run.id,
            RiskReview.is_active == True
        ).all()
        reviews_by_req_id = {r.source_requirement_id: r for r in active_reviews if r.source_requirement_id}
        
        for req in parent_reqs:
            business_context = business_context_service.generate_business_context(
                requirement_text=req.title,
                requirement_title=req.readable_id,
                requirement_id=req.requirement_id,
                matched_tests=[t.title for t in getattr(req, "linked_existing_tests", [])],
                pr_title=pr.title if pr else "",
                pr_description=getattr(pr, "description", ""),
                changed_files=changed_files
            )
            bc_dict = business_context.to_dict()
            
            # Override with effective risk from review if available
            review_rec = reviews_by_req_id.get(req.requirement_id)
            if review_rec and review_rec.review_status != "UNREVIEWED":
                # Use effective risk based on review status
                if review_rec.review_status == "OVERRIDDEN":
                    bc_dict["riskLevel"] = review_rec.reviewed_risk_level
                    bc_dict["priority"] = review_rec.reviewed_priority
                else:
                    bc_dict["riskLevel"] = review_rec.original_risk_level
                    bc_dict["priority"] = review_rec.original_priority
            
            business_contexts[req.requirement_id] = bc_dict
    
    # Required items from MISSING_AUTOMATED_COVERAGE
    required_items = []
    missing_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE]
    for req in missing_reqs:
        # Get source AC number from DB if available
        ac_row = None
        if pr:
            ac_row = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.pull_request_id == pr.id,
                AcceptanceCriterion.text == req.title
            ).first()
        
        source_ac_number = ac_row.source_number if ac_row else None
        
        # Get business context if available
        business_context = business_contexts.get(req.requirement_id)
        
        required_items.append(ScopeItem(
            id=str(uuid.uuid4()),
            item_type=ScopeItemType.REQUIRED_MISSING_COVERAGE,
            source_requirement_id=req.requirement_id,
            readable_id=req.readable_id,
            source_ac_number=source_ac_number,
            title=req.title,
            flow=req.flow,
            classification=req.classification.value if hasattr(req.classification, "value") else str(req.classification),
            suggested_action="Create test to cover this acceptance criterion",
            suggested_test_title=f"Test {req.readable_id}: {req.title[:50]}",
            suggested_layer="backend",
            risk_if_skipped="HIGH" if req.risk_level == "CRITICAL" else "MEDIUM",
            evidence_summary={"classification": "MISSING_AUTOMATED_COVERAGE"},
            matched_tests=[],
            diagnostics={},
            businessContext=business_context
        ))
    
    if missing_reqs:
        generation_rules.append("INCLUDED_MISSING_AUTOMATED_COVERAGE")
    
    # Review items from PARTIALLY_COVERED
    review_items = []
    partial_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.PARTIALLY_COVERED]
    for req in partial_reqs:
        ac_row = None
        if pr:
            ac_row = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.pull_request_id == pr.id,
                AcceptanceCriterion.text == req.title
            ).first()
        
        source_ac_number = ac_row.source_number if ac_row else None
        
        # Get business context if available
        business_context = business_contexts.get(req.requirement_id)
        
        review_items.append(ScopeItem(
            id=str(uuid.uuid4()),
            item_type=ScopeItemType.REVIEW_PARTIAL_COVERAGE,
            source_requirement_id=req.requirement_id,
            readable_id=req.readable_id,
            source_ac_number=source_ac_number,
            title=req.title,
            flow=req.flow,
            classification=req.classification.value if hasattr(req.classification, "value") else str(req.classification),
            suggested_action="Review and strengthen test coverage",
            suggested_test_title=f"Strengthen {req.readable_id}: {req.title[:50]}",
            suggested_layer="backend",
            risk_if_skipped="MEDIUM",
            evidence_summary={"classification": "PARTIALLY_COVERED"},
            matched_tests=[],
            diagnostics={},
            businessContext=business_context
        ))
    
    if partial_reqs:
        generation_rules.append("INCLUDED_PARTIAL_COVERAGE_FOR_REVIEW")
    
    # Excluded verified requirements
    excluded_verified_reqs = []
    verified_reqs = [r for r in parent_reqs if r.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION]
    for req in verified_reqs:
        ac_row = None
        if pr:
            ac_row = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.pull_request_id == pr.id,
                AcceptanceCriterion.text == req.title
            ).first()
        
        source_ac_number = ac_row.source_number if ac_row else None
        
        excluded_verified_reqs.append(ScopeItem(
            id=str(uuid.uuid4()),
            item_type=ScopeItemType.EXCLUDED_ALREADY_VERIFIED_REQUIREMENT,
            source_requirement_id=req.requirement_id,
            readable_id=req.readable_id,
            source_ac_number=source_ac_number,
            title=req.title,
            flow=req.flow,
            classification=req.classification.value if hasattr(req.classification, "value") else str(req.classification),
            reason_excluded="Already covered by passed current PR execution",
            evidence_summary={"classification": "VERIFIED_BY_CURRENT_PR_EXECUTION"},
            matched_tests=[],
            diagnostics={}
        ))
    
    if verified_reqs:
        generation_rules.append("EXCLUDED_VERIFIED_REQUIREMENTS")
    
    # Excluded passed tests
    excluded_passed_tests = []
    if not request.include_already_passed_tests:
        for test in view_model.verified_by_current_pr:
            excluded_passed_tests.append(ScopeItem(
                id=str(uuid.uuid4()),
                item_type=ScopeItemType.EXCLUDED_ALREADY_PASSED_TEST,
                test_id=test.id,
                title=test.title,
                class_name=test.classname,
                reason_excluded="Already passed in current PR execution",
                evidence_summary={"status": "passed"},
                matched_tests=[],
                diagnostics={}
            ))
        generation_rules.append("EXCLUDED_ALREADY_PASSED_CURRENT_PR_TESTS")
    
    # Generation rules
    generation_rules.extend([
        "EXCLUDED_COVERAGE_ONLY_SUGGESTIONS",
        "EXCLUDED_OPTIONAL_HARDENING_FROM_REQUIRED_SCOPE"
    ])
    
    # Build summary
    summary = (
        f"Veriscope created a targeted regression scope from the current evidence graph. "
        f"The scope includes {len(required_items)} missing automated coverage items and "
        f"{len(review_items)} partially supported requirements for review. "
        f"It excludes {len(excluded_verified_reqs)} acceptance criteria already covered by passed PR tests "
        f"and excludes {len(excluded_passed_tests)} tests that already passed in the current PR execution."
    )
    
    # Add audit diagnostics if requested
    if request.include_audit_diagnostics:
        diagnostics.append("Audit mode enabled")
        diagnostics.append(f"Source type: {ac_source['source_type']}")
        diagnostics.append(f"Source hash: {ac_source['source_hash']}")
    
    # Create snapshot reference with hash based on persisted graph body
    import hashlib
    import json
    
    # Get persisted snapshot for canonical hash
    if run.requirement_evidence_snapshot_json:
        snapshot_json = run.requirement_evidence_snapshot_json
        if isinstance(snapshot_json, str):
            snapshot_data_for_hash = json.loads(snapshot_json)
        else:
            snapshot_data_for_hash = snapshot_json
        
        # Create canonical JSON for hashing (sorted keys)
        canonical_snapshot = json.dumps(snapshot_data_for_hash, sort_keys=True)
        snapshot_hash = hashlib.md5(canonical_snapshot.encode()).hexdigest()
    else:
        # Fallback if no snapshot exists (should not happen in normal flow)
        snapshot_data = f"{run.id}:{view_model.health}:{ac_source['source_hash']}"
        snapshot_hash = hashlib.md5(snapshot_data.encode()).hexdigest()
    
    snapshot_reference = EvidenceGraphSnapshotReference(
        recommendation_run_id=str(run.id),
        snapshot_hash=snapshot_hash,
        generated_at=datetime.utcnow(),
        source_hash=ac_source.get('source_hash'),
        evidence_version="1.0"
    )
    
    diagnostics.append("SCOPE_CREATED_FROM_EVIDENCE_GRAPH_SNAPSHOT")
    diagnostics.append(f"snapshotHash: {snapshot_hash}")
    diagnostics.append(f"generatedAt: {datetime.utcnow().isoformat()}")
    
    # Build scope response
    scope = RegressionScope(
        id=str(uuid.uuid4()),
        recommendation_run_id=str(run.id),
        source_evidence_graph_snapshot=snapshot_reference,
        created_at=datetime.utcnow(),
        scope_type=request.scope_type,
        health_at_creation=view_model.health,
        summary=summary,
        required_items=required_items,
        review_items=review_items,
        optional_safety_net_items=[],
        excluded_already_verified_requirements=excluded_verified_reqs,
        excluded_already_passed_tests=excluded_passed_tests,
        generation_rules_applied=generation_rules,
        diagnostics=diagnostics
    )
    
    return CreateTargetedScopeResponse(
        status="SUCCESS",
        scope=scope
    )


@router.post("/{recommendation_run_id}/regenerate-evidence-graph", status_code=status.HTTP_200_OK)
def regenerate_evidence_graph(
    recommendation_run_id: UUID,
    db: Session = Depends(get_db)
):
    """Regenerate the evidence graph snapshot from canonical sources."""
    import hashlib
    from datetime import datetime
    from app.models.recommendation import RecommendationRun
    from app.models.pull_request import PullRequest, PullRequestSnapshot
    from app.models.acceptance_criterion import AcceptanceCriterion
    
    # Get recommendation run
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Get PR
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Resolve AC rows from DB (canonical source)
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    # Get PR snapshot
    pr_snapshot = db.query(PullRequestSnapshot).filter(
        PullRequestSnapshot.pull_request_id == run.pr_id
    ).order_by(PullRequestSnapshot.created_at.desc()).first()
    
    head_sha = pr_snapshot.head_commit_sha if pr_snapshot else None
    changed_files = []
    if run.input_snapshot and run.input_snapshot.changed_files:
        changed_files = run.input_snapshot.changed_files
    
    # Build evidence graph from canonical sources
    # Use canonical AC DB rows directly if they exist, bypassing AC extraction
    graph_service = RequirementEvidenceGraphService(db)
    if ac_rows:
        # Use canonical DB rows directly to prevent re-extraction dropping valid requirements
        view_model = graph_service.build_evidence_graph(
            str(run.repository_id),
            str(run.pr_id),
            head_sha,
            changed_files,
            pr_description=None,  # Not needed when using canonical rows
            recommendation_run_id=str(run.id),
            canonical_ac_rows=ac_rows
        )
    else:
        # Fallback to AC extraction if no DB rows exist
        ac_text = "\n".join([f"- {row.text}" for row in ac_rows]) if ac_rows else None
        view_model = graph_service.build_evidence_graph(
            str(run.repository_id),
            str(run.pr_id),
            head_sha,
            changed_files,
            pr_description=ac_text,
            recommendation_run_id=str(run.id)
        )
    
    # Persist new snapshot
    graph_service.persist_graph_snapshot(str(run.id), view_model)
    
    # Clear stale flag
    run.input_stale = False
    run.stale_reason = None
    run.stale_since = None
    run.stale_input_types = None
    db.commit()
    
    # Generate snapshot hash from persisted graph body
    import json
    snapshot_json = run.requirement_evidence_snapshot_json
    if isinstance(snapshot_json, str):
        snapshot_data = json.loads(snapshot_json)
    else:
        snapshot_data = snapshot_json
    
    # Create canonical JSON for hashing (sorted keys)
    canonical_snapshot = json.dumps(snapshot_data, sort_keys=True)
    snapshot_hash = hashlib.md5(canonical_snapshot.encode()).hexdigest()
    
    # Return decision summary from new snapshot
    return {
        "status": "SUCCESS",
        "message": "Evidence graph regenerated successfully",
        "snapshot_hash": snapshot_hash,
        "decision_summary": {
            "health": view_model.health,
            "counts": view_model.counts,
            "decision_copy": {
                "headline": view_model.decision_copy.headline,
                "explanation": view_model.decision_copy.explanation,
                "next_action": view_model.decision_copy.next_action
            }
        }
    }


@router.get("/{recommendation_run_id}/evidence-report", status_code=status.HTTP_200_OK)
def get_evidence_report(
    recommendation_run_id: UUID,
    format: str = Query("markdown", description="Report format: markdown or json"),
    audit: bool = Query(False, description="Include internal IDs and diagnostics"),
    include_scope: bool = Query(True, description="Include targeted regression scope"),
    include_diagnostics: bool = Query(False, description="Include diagnostic information"),
    include_stale: bool = Query(False, description="Include stale report with warning"),
    include_business_context: bool = Query(True, description="Include business context annotations"),
    include_optimization_summary: bool = Query(False, description="Include regression optimization summary"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate QA evidence report from evidence graph and targeted scope."""
    import hashlib
    from datetime import datetime
    from app.models.recommendation import RecommendationRun
    from app.models.pull_request import PullRequest, PullRequestSnapshot
    from app.models.acceptance_criterion import AcceptanceCriterion
    from app.config import settings
    from app.dependencies.authorization import validate_recommendation_run_access
    
    run = validate_recommendation_run_access(db, recommendation_run_id, user)
    
    # Check for stale inputs
    if run.input_stale and not include_stale:
        return EvidenceReportResponse(
            status="REQUIRES_REGENERATION",
            error_code="STALE_EVIDENCE_GRAPH",
            can_render_report=False,
            message="Recommendation is stale. Regenerate before creating evidence report."
        )
    
    # Get PR
    pr = db.query(PullRequest).filter(PullRequest.id == run.pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Resolve AC text from DB
    ac_rows = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr.id
    ).all()
    
    ac_text = "\n".join([f"- {row.text}" for row in ac_rows])
    ac_source_hash = hashlib.md5(ac_text.encode()).hexdigest()
    
    # Use the persisted evidence graph snapshot as the single source of truth
    # This ensures consistency with decision summary and targeted scope
    if not run.requirement_evidence_snapshot_json:
        return EvidenceReportResponse(
            status="ERROR",
            error_code="EVIDENCE_GRAPH_UNAVAILABLE",
            can_render_report=False,
            message="Evidence graph snapshot not available. Regenerate recommendation first."
        )
    
    import json
    snapshot_data = json.loads(run.requirement_evidence_snapshot_json)
    
    # Validate snapshot freshness against canonical sources
    snapshot_parent_count = snapshot_data.get("counts", {}).get("totalRequirements", 0)
    canonical_parent_count = len(ac_rows)
    
    if snapshot_parent_count != canonical_parent_count and not include_stale:
        return EvidenceReportResponse(
            status="REQUIRES_REGENERATION",
            error_code="SNAPSHOT_PARENT_REQUIREMENT_COUNT_MISMATCH",
            can_render_report=False,
            message=f"Snapshot is stale: contains {snapshot_parent_count} parent requirements, but canonical source has {canonical_parent_count}. Regenerate recommendation before exporting report."
        )
    
    # Extract counts from snapshot
    snapshot_counts = snapshot_data.get("counts", {})
    snapshot_health = snapshot_data.get("health", "UNKNOWN")
    snapshot_traceability = snapshot_data.get("acTraceability", [])
    
    # Add stale warning if include_stale=true and snapshot is stale
    is_stale = snapshot_parent_count != canonical_parent_count
    
    # Map snapshot coverage status values to report values
    # Snapshot uses: 'Covered', 'Missing', 'Partially covered'
    # Report uses: 'VERIFIED', 'MISSING', 'COVERAGE_ONLY'
    coverage_status_map = {
        'Covered': 'VERIFIED',
        'Missing': 'MISSING',
        'Partially covered': 'COVERAGE_ONLY'
    }
    
    # Build coverage items from snapshot traceability
    covered_requirements = []
    partially_supported = []
    missing_coverage = []
    
    # Generate business context if enabled
    business_contexts = {}
    if settings.BUSINESS_CONTEXT_ENABLED and include_business_context:
        from app.services.business_understanding.business_context_service import BusinessContextService
        business_context_service = BusinessContextService()
        
        for trace in snapshot_traceability:
            business_context = business_context_service.generate_business_context(
                requirement_text=trace.get('title', ''),
                requirement_title=trace.get('readableId', ''),
                requirement_id=trace.get('requirementId', ''),
                matched_tests=[],
                pr_title=pr.title if pr else "",
                pr_description=getattr(pr, "description", ""),
                changed_files=[]
            )
            business_contexts[trace.get('requirementId')] = business_context.to_dict()
    
    for trace in snapshot_traceability:
        coverage_status = trace.get('coverageStatus')
        mapped_status = coverage_status_map.get(coverage_status, 'MISSING')
        req_id = trace.get('requirementId')
        business_context = business_contexts.get(req_id)
        
        if mapped_status == 'VERIFIED':
            covered_req = CoveredRequirement(
                readable_id=trace.get('readableId', 'UNKNOWN'),
                source_ac_number=None,
                title=trace.get('title', 'Unknown'),
                matched_test_name='Test from snapshot',
                test_classname='Unknown',
                evidence_type='JUNIT_EXECUTION',
                confidence_score=0.95 if not audit else None,
                reason='Covered by passed current PR execution',
                internal_requirement_id=trace.get('requirementId') if audit else None,
                businessContext=business_context
            )
            covered_requirements.append(covered_req)
        elif mapped_status == 'COVERAGE_ONLY':
            partial_req = PartiallySupportedRequirement(
                readable_id=trace.get('readableId', 'UNKNOWN'),
                source_ac_number=None,
                title=trace.get('title', 'Unknown'),
                supporting_evidence='Coverage-only evidence available',
                why_not_fully_verified='No direct test execution evidence found',
                what_would_make_it_verified='Add test that directly validates this requirement',
                suggested_strengthening_action='Create integration test with direct assertion',
                internal_requirement_id=trace.get('requirementId') if audit else None,
                businessContext=business_context
            )
            partially_supported.append(partial_req)
        else:  # MISSING
            missing_req = MissingCoverageRequirement(
                readable_id=trace.get('readableId', 'UNKNOWN'),
                source_ac_number=None,
                title=trace.get('title', 'Unknown'),
                flow='Unknown',
                why_not_covered='No test execution or coverage evidence found',
                suggested_test_title=f'Test {trace.get("title", "Unknown")}',
                suggested_layer='Integration',
                risk_if_skipped='HIGH',
                closest_candidate=None,
                rejection_reason=None,
                internal_requirement_id=trace.get('requirementId') if audit else None,
                businessContext=business_context
            )
            missing_coverage.append(missing_req)
    
    # Use snapshot counts for report
    total_acs = snapshot_counts.get('totalRequirements', len(snapshot_traceability))
    covered_count = snapshot_counts.get('verifiedTests', len(covered_requirements))
    partial_count = snapshot_counts.get('coverageGaps', len(partially_supported))
    missing_count = snapshot_counts.get('missingAutomatedCoverage', len(missing_coverage))
    passed_tests = snapshot_counts.get('uploadedPrTestsPassed', 0)
    total_tests = snapshot_counts.get('uploadedPrTestsTotal', 0)
    
    # Create snapshot reference - use canonical hash from persisted graph body
    canonical_snapshot = json.dumps(snapshot_data, sort_keys=True)
    snapshot_hash = hashlib.md5(canonical_snapshot.encode()).hexdigest()
    
    snapshot_info = EvidenceGraphSnapshotInfo(
        recommendation_run_id=str(run.id),
        snapshot_hash=snapshot_hash,
        generated_at=datetime.utcnow(),
        source_hash=ac_source_hash,
        evidence_version="1.0"
    )
    
    # Build excluded passed tests from snapshot counts
    excluded_tests = []
    for i in range(passed_tests):
        excluded_test = ExcludedPassedTest(
            test_name=f'Test {i+1}',
            classname='Unknown',
            status='PASSED',
            reason_excluded='Already passed in current PR execution',
            internal_test_id=None
        )
        excluded_tests.append(excluded_test)
    
    # Build uploaded evidence summary
    uploaded_evidence = UploadedEvidence(
        acceptance_criteria_source=f"DB_ACCEPTANCE_CRITERION ({len(ac_rows)} ACs)",
        junit_execution_summary={
            "total": total_tests,
            "passed": passed_tests,
            "failed": snapshot_counts.get('uploadedPrTestsFailed', 0),
            "skipped": snapshot_counts.get('uploadedPrTestsSkipped', 0)
        },
        coverage_summary={
            "coverage_percentage": 0
        },
        evidence_graph_snapshot=snapshot_info
    )
    
    # Build targeted scope summary
    targeted_scope = None
    if include_scope:
        targeted_scope = TargetedScopeSummary(
            required_items_count=missing_count,
            review_items_count=partial_count,
            excluded_verified_requirements_count=covered_count,
            excluded_passed_tests_count=passed_tests,
            passed_tests_recommended_for_rerun=False,
            generation_rules_applied=[
                "INCLUDED_MISSING_AUTOMATED_COVERAGE",
                "INCLUDED_PARTIAL_COVERAGE_FOR_REVIEW",
                "EXCLUDED_VERIFIED_REQUIREMENTS",
                "EXCLUDED_ALREADY_PASSED_CURRENT_PR_TESTS",
                "EXCLUDED_COVERAGE_ONLY_SUGGESTIONS",
                "EXCLUDED_OPTIONAL_HARDENING_FROM_REQUIRED_SCOPE"
            ]
        )
    
    # Build business risk summary if enabled
    business_risk_summary = None
    risk_review_decisions = None
    if settings.BUSINESS_CONTEXT_ENABLED and include_business_context:
        from app.schemas.business_context import BusinessRiskSummary
        from app.models.risk_review import RiskReview
        from app.services.risk_review_service import RiskReviewService
        
        # Use the shared review state method which uses build_reviewable_gap_index
        review_state = RiskReviewService.get_review_state(db, run)
        
        # Load active risk reviews
        active_reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == recommendation_run_id,
            RiskReview.is_active == True
        ).all()
        reviews_by_req_id = {r.source_requirement_id: r for r in active_reviews if r.source_requirement_id}
        
        # Count risks from ALL missing and partial items (not verified)
        # Default to UNKNOWN if businessContext is missing
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        unknown_count = 0
        
        # Count effective risks (after review overrides)
        effective_critical_count = 0
        effective_high_count = 0
        effective_medium_count = 0
        effective_low_count = 0
        effective_unknown_count = 0
        
        reviewed_count = 0
        overridden_count = 0
        needs_discussion_count = 0
        
        for req in missing_coverage:
            risk_level = 'UNKNOWN'
            effective_risk = 'UNKNOWN'
            if req.businessContext:
                if isinstance(req.businessContext, dict):
                    risk_level = req.businessContext.get('riskLevel') or 'UNKNOWN'
                else:
                    risk_level = getattr(req.businessContext, 'riskLevel', 'UNKNOWN') or 'UNKNOWN'
            
            # Check for risk review override
            review = reviews_by_req_id.get(req.internal_requirement_id)
            if review and review.review_status != "UNREVIEWED":
                reviewed_count += 1
                if review.review_status == "OVERRIDDEN":
                    overridden_count += 1
                elif review.review_status == "NEEDS_DISCUSSION":
                    needs_discussion_count += 1
                effective_risk = review.reviewed_risk_level if review.review_status == "OVERRIDDEN" else review.original_risk_level
            else:
                effective_risk = risk_level
            
            if risk_level == 'CRITICAL':
                critical_count += 1
            elif risk_level == 'HIGH':
                high_count += 1
            elif risk_level == 'MEDIUM':
                medium_count += 1
            elif risk_level == 'LOW':
                low_count += 1
            else:
                unknown_count += 1
            
            if effective_risk == 'CRITICAL':
                effective_critical_count += 1
            elif effective_risk == 'HIGH':
                effective_high_count += 1
            elif effective_risk == 'MEDIUM':
                effective_medium_count += 1
            elif effective_risk == 'LOW':
                effective_low_count += 1
            else:
                effective_unknown_count += 1
        
        for req in partially_supported:
            risk_level = 'UNKNOWN'
            effective_risk = 'UNKNOWN'
            if req.businessContext:
                if isinstance(req.businessContext, dict):
                    risk_level = req.businessContext.get('riskLevel') or 'UNKNOWN'
                else:
                    risk_level = getattr(req.businessContext, 'riskLevel', 'UNKNOWN') or 'UNKNOWN'
            
            # Check for risk review override
            review = reviews_by_req_id.get(req.internal_requirement_id)
            if review and review.review_status != "UNREVIEWED":
                reviewed_count += 1
                if review.review_status == "OVERRIDDEN":
                    overridden_count += 1
                elif review.review_status == "NEEDS_DISCUSSION":
                    needs_discussion_count += 1
                effective_risk = review.reviewed_risk_level if review.review_status == "OVERRIDDEN" else review.original_risk_level
            else:
                effective_risk = risk_level
            
            if risk_level == 'CRITICAL':
                critical_count += 1
            elif risk_level == 'HIGH':
                high_count += 1
            elif risk_level == 'MEDIUM':
                medium_count += 1
            elif risk_level == 'LOW':
                low_count += 1
            else:
                unknown_count += 1
            
            if effective_risk == 'CRITICAL':
                effective_critical_count += 1
            elif effective_risk == 'HIGH':
                effective_high_count += 1
            elif effective_risk == 'MEDIUM':
                effective_medium_count += 1
            elif effective_risk == 'LOW':
                effective_low_count += 1
            else:
                effective_unknown_count += 1
        
        # Build summary text
        summary_parts = []
        if critical_count > 0:
            summary_parts.append(f"{critical_count} critical gaps")
        if high_count > 0:
            summary_parts.append(f"{high_count} high gaps")
        if medium_count > 0:
            summary_parts.append(f"{medium_count} medium gaps")
        if low_count > 0:
            summary_parts.append(f"{low_count} low gaps")
        if unknown_count > 0:
            summary_parts.append(f"{unknown_count} unknown gaps")
        
        summary_text = ""
        if summary_parts:
            summary_text = "The highest-risk remaining gaps are " + ", ".join(summary_parts) + "."
            
            # Add journey context if we have business context
            journeys = set()
            for req in missing_coverage + partially_supported:
                if req.businessContext:
                    if isinstance(req.businessContext, dict):
                        journey = req.businessContext.get('userJourney')
                    else:
                        journey = getattr(req.businessContext, 'userJourney', None)
                    if journey:
                        journeys.add(journey)
            
            if journeys:
                journey_list = list(journeys)[:2]  # Top 2 journeys
                if len(journey_list) == 1:
                    summary_text += f" These items are concentrated in the {journey_list[0]} journey."
                else:
                    summary_text += f" These items are concentrated in the {journey_list[0]} and {journey_list[1]} journeys."
            
            summary_text += " These items should be reviewed before release because they affect account access and security enforcement."
        
        business_risk_summary = BusinessRiskSummary(
            critical_gaps=critical_count,
            high_gaps=high_count,
            medium_gaps=medium_count,
            low_gaps=low_count,
            unknown_gaps=unknown_count,
            summary_text=summary_text if summary_text else None
        )
        
        # Build risk review decisions section
        all_reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == recommendation_run_id
        ).all()
        
        active_reviews = [r for r in all_reviews if r.is_active]
        review_decisions = []
        for review in active_reviews:
            review_decisions.append({
                "readableId": review.readable_id,
                "originalRiskLevel": review.original_risk_level,
                "originalPriority": review.original_priority,
                "reviewedRiskLevel": review.reviewed_risk_level,
                "reviewedPriority": review.reviewed_priority,
                "reviewStatus": review.review_status,
                "reviewerName": review.reviewer_name,
                "reviewNote": review.review_note,
                "updatedAt": review.updated_at.isoformat()
            })
        
        active_reviews_count = len(active_reviews)
        active_accepted_count = sum(1 for r in active_reviews if r.review_status == "ACCEPTED")
        active_overridden_count = sum(1 for r in active_reviews if r.review_status == "OVERRIDDEN")
        active_needs_discussion_count = sum(1 for r in active_reviews if r.review_status == "NEEDS_DISCUSSION")
        reset_events_count = sum(1 for r in all_reviews if r.review_status == "RESET")
        total_history_events_count = len(all_reviews)
        
        risk_review_decisions = {
            "advisoryNotice": "Risk review is advisory and does not change evidence buckets, test counts, AC coverage status, scope required/review counts, or release readiness status.",
            "generatedRiskDistribution": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "unknown": unknown_count
            },
            "effectiveRiskDistribution": {
                "critical": effective_critical_count,
                "high": effective_high_count,
                "medium": effective_medium_count,
                "low": effective_low_count,
                "unknown": effective_unknown_count
            },
            "reviewSummary": {
                "totalReviewableGaps": len(missing_coverage) + len(partially_supported),
                "reviewedCount": reviewed_count,
                "overriddenCount": overridden_count,
                "needsDiscussionCount": needs_discussion_count,
                "unreviewedCount": (len(missing_coverage) + len(partially_supported)) - reviewed_count
            },
            "governanceSummary": {
                "activeReviews": active_reviews_count,
                "activeAccepted": active_accepted_count,
                "activeOverridden": active_overridden_count,
                "activeNeedsDiscussion": active_needs_discussion_count,
                "resetEvents": reset_events_count,
                "totalHistoryEvents": total_history_events_count
            },
            "decisions": review_decisions
        }
    
    # Build executive summary text
    if is_stale:
        executive_summary = (
            f"STALE EVIDENCE REPORT — This report was generated from a stale evidence graph snapshot. "
            f"The snapshot contains {snapshot_parent_count} parent requirements, but the current canonical source contains {canonical_parent_count}. "
            f"Regenerate recommendation before using this report for release decisions. "
            f"Current PR execution passed {passed_tests} tests. "
            f"Veriscope mapped {covered_count} acceptance criteria to passed PR evidence. "
            f"{partial_count} acceptance criteria are partially supported and need review. "
            f"{missing_count} acceptance criteria still lack automated coverage. "
            f"0 acceptance criteria require traceability review."
        )
    else:
        executive_summary = (
            f"Current PR execution passed {passed_tests} tests. "
            f"Veriscope mapped {covered_count} acceptance criteria to passed PR evidence. "
            f"{partial_count} acceptance criteria are partially supported and need review. "
            f"{missing_count} acceptance criteria still lack automated coverage. "
            f"0 acceptance criteria require traceability review."
        )
    
    # Build release decision text
    release_decision = (
        "Validation passed for covered areas, but release evidence is incomplete. "
        f"Review the {missing_count} missing automated coverage items "
        f"and {partial_count} partially supported requirements before final release approval."
    )
    
    # Build remaining risks
    remaining_risks = []
    if missing_coverage:
        for req in missing_coverage[:3]:  # Top 3 risks
            remaining_risks.append(f"{req.title} lacks direct automated coverage (risk: {req.risk_if_skipped}).")
    if partially_supported:
        remaining_risks.append(f"{len(partially_supported)} acceptance criteria are only partially supported.")
    remaining_risks.append("Release should not be marked Ready until missing/partial items are resolved or accepted.")
    
    # Build recommended next actions
    recommended_actions = [
        f"Create the {len(missing_coverage)} missing automated tests.",
        f"Strengthen or review the {len(partially_supported)} partially supported requirements.",
        f"Do not rerun the {len(excluded_tests)} passed tests as mandatory scope unless full rerun mode is explicitly selected.",
        "Regenerate recommendation after new tests are added.",
        "Export updated evidence report before release approval."
    ]
    
    # Build audit appendix if requested
    audit_appendix = None
    if audit or include_diagnostics:
        audit_appendix = {
            "internal_requirement_ids": [trace.get('requirementId') for trace in snapshot_traceability],
            "source_hashes": {"ac_source": ac_source_hash, "snapshot": snapshot_hash},
            "graph_diagnostics": {
                "total_parent_requirements": len(snapshot_traceability),
                "total_tests": total_tests
            }
        }
    
    # Build optimization summary if requested
    optimization_summary = None
    if include_optimization_summary:
        from app.services.optimization_metrics_service import OptimizationMetricsService
        
        # Build requirements list with risk and coverage data
        requirements = []
        for req in covered_requirements:
            requirements.append({
                "requirement_id": req.internal_requirement_id,
                "title": req.title,
                "risk_band": getattr(req.businessContext, 'riskLevel', 'LOW') if req.businessContext else 'LOW',
                "coverage_bucket": "COVERED"
            })
        for req in partially_supported:
            requirements.append({
                "requirement_id": req.internal_requirement_id,
                "title": req.title,
                "risk_band": getattr(req.businessContext, 'riskLevel', 'MEDIUM') if req.businessContext else 'MEDIUM',
                "coverage_bucket": "PARTIAL"
            })
        for req in missing_coverage:
            requirements.append({
                "requirement_id": req.internal_requirement_id,
                "title": req.title,
                "risk_band": getattr(req.businessContext, 'riskLevel', 'HIGH') if req.businessContext else 'HIGH',
                "coverage_bucket": "MISSING"
            })
        
        # Build regression recommendations (simplified for Phase 3.4)
        # In a full implementation, this would use the actual regression recommendation engine
        regression_recommendations = {
            "requiredItems": [
                {"requirement_id": req.internal_requirement_id, "title": req.title}
                for req in missing_coverage
            ],
            "recommendedItems": [
                {"requirement_id": req.internal_requirement_id, "title": req.title}
                for req in partially_supported
            ],
            "optionalItems": [],
            "safeToSkipItems": [
                {"requirement_id": req.internal_requirement_id, "title": req.title}
                for req in covered_requirements
            ]
        }
        
        # Generate optimization summary
        optimization_summary = OptimizationMetricsService.generate_regression_optimization_summary(
            requirements=requirements,
            regression_recommendations=regression_recommendations,
            current_test_count=total_tests
        )
    
    # Build report
    report = EvidenceReport(
        title=f"QA Evidence Report — PR #{pr.number} {pr.title}",
        generated_at=datetime.utcnow(),
        pr_title=pr.title,
        pr_number=pr.number,
        health=snapshot_health,
        decision_status="VALIDATION_PASSED_COVERAGE_INCOMPLETE",
        current_pr_test_results={
            "total": total_tests,
            "passed": passed_tests,
            "failed": snapshot_counts.get('uploadedPrTestsFailed', 0),
            "skipped": snapshot_counts.get('uploadedPrTestsSkipped', 0)
        },
        acceptance_criteria_coverage={
            "total": total_acs,
            "covered": covered_count,
            "partially_supported": partial_count,
            "missing": missing_count,
            "traceability_review_needed": 0
        },
        executive_summary_text=executive_summary,
        release_decision_text=release_decision,
        uploaded_evidence=uploaded_evidence,
        covered_by_passed_pr_tests=covered_requirements,
        partially_supported_requirements=partially_supported,
        missing_automated_coverage=missing_coverage,
        targeted_scope=targeted_scope,
        business_risk_summary=business_risk_summary,
        risk_review_decisions=risk_review_decisions,
        remaining_risks=remaining_risks,
        recommended_next_actions=recommended_actions,
        audit_appendix=audit_appendix,
        optimization_summary=optimization_summary
    )
    
    # Generate markdown if requested
    markdown_content = None
    if format == "markdown":
        markdown_lines = [
            f"# {report.title}",
            "",
            f"**Generated:** {report.generated_at.isoformat()}",
            "",
            "## Executive Summary",
            "",
            f"**PR Title:** {report.pr_title}",
            f"**Health:** {report.health}",
            f"**Decision Status:** {report.decision_status}",
            "",
            "### Current PR Test Results",
            f"- Total: {report.current_pr_test_results['total']}",
            f"- Passed: {report.current_pr_test_results['passed']}",
            f"- Failed: {report.current_pr_test_results['failed']}",
            f"- Skipped: {report.current_pr_test_results['skipped']}",
            "",
            "### Acceptance Criteria Coverage",
            f"- Total: {report.acceptance_criteria_coverage['total']}",
            f"- Covered by passed PR tests: {report.acceptance_criteria_coverage['covered']}",
            f"- Partially supported: {report.acceptance_criteria_coverage['partially_supported']}",
            f"- Missing automated coverage: {report.acceptance_criteria_coverage['missing']}",
            f"- Traceability review needed: {report.acceptance_criteria_coverage['traceability_review_needed']}",
            "",
            report.executive_summary_text,
            "",
            "## Release Decision",
            "",
            report.release_decision_text,
            "",
        ]
        
        if report.business_risk_summary:
            total_remaining_gaps = report.business_risk_summary.critical_gaps + report.business_risk_summary.high_gaps + report.business_risk_summary.medium_gaps + report.business_risk_summary.low_gaps + report.business_risk_summary.unknown_gaps
            
            # Identify top critical gaps from missing coverage and partially supported
            critical_items = [
                req for req in (report.missing_automated_coverage + report.partially_supported_requirements)
                if req.businessContext and (
                    req.businessContext.get('riskLevel') == 'CRITICAL' if isinstance(req.businessContext, dict)
                    else getattr(req.businessContext, 'riskLevel', None) == 'CRITICAL'
                )
            ]
            top_gaps_md = []
            for item in critical_items[:3]:
                top_gaps_md.append(f"- **{item.readable_id}**: {item.title}")
            if not top_gaps_md:
                top_gaps_md.append("- No critical gaps remaining.")
                
            markdown_lines.extend([
                "## Business Risk Review",
                "",
                f"- Total Remaining Business Gaps: {total_remaining_gaps}",
                f"- Risk Distribution: {report.business_risk_summary.critical_gaps} Critical, {report.business_risk_summary.high_gaps} High, {report.business_risk_summary.medium_gaps} Medium, {report.business_risk_summary.low_gaps} Low, {report.business_risk_summary.unknown_gaps} Unknown",
                "",
                "### Top Critical Gaps",
                *top_gaps_md,
                "",
                "### Why They Matter",
                "- Critical gaps relate directly to account access, credential updates, and database atomicity. Failing to cover these increases threat of session hijack, account takeover, or data corruption.",
                "",
                "### Recommended QA Action",
                "- Implement direct automated JUnit testing for atomic password updates, expired/reused token rejection, and old password invalidation on backend APIs.",
                "",
                "**Reminder:** Business risk context is advisory and does not replace actual test execution evidence.",
                ""
            ])

        if report.risk_review_decisions:
            rrd = report.risk_review_decisions
            gov = rrd["governanceSummary"]
            gen_dist = rrd["generatedRiskDistribution"]
            eff_dist = rrd["effectiveRiskDistribution"]
            
            decisions_md = []
            for d in rrd["decisions"]:
                decisions_md.append(
                    f"- **{d['readableId']}**: {d['reviewStatus']} (Original Risk: {d['originalRiskLevel']} / Reviewed Risk: {d['reviewedRiskLevel']}) "
                    f"by {d['reviewerName']} - *{d['reviewNote'] or 'No note'}*"
                )
            if not decisions_md:
                decisions_md.append("- No active decisions.")

            # Load ALL reviews to construct chronological history timeline
            sorted_reviews = sorted(all_reviews, key=lambda r: r.created_at)
            
            timeline_md = []
            for rev in sorted_reviews:
                timestamp = rev.created_at.strftime("%Y-%m-%d %H:%M:%S")
                reviewer_str = f"{rev.reviewer_name}"
                if audit:
                    reviewer_str += f" (ID: {rev.reviewer_id})"
                
                note_str = f" - Note: *{rev.review_note}*" if rev.review_note else ""
                transition_str = f" (Risk: {rev.original_risk_level} -> {rev.reviewed_risk_level})" if rev.review_status == "OVERRIDDEN" else ""
                
                uuid_str = ""
                if audit:
                    uuid_str = f" [Review ID: {rev.id}]"

                timeline_md.append(
                    f"- {timestamp}: **{rev.readable_id or 'Unknown'}** status set to **{rev.review_status}** by {reviewer_str}{transition_str}{note_str}{uuid_str}"
                )
            if not timeline_md:
                timeline_md.append("- No history events yet.")

            markdown_lines.extend([
                "## Business Risk Review Decisions",
                "",
                f"**Advisory Warning:** Risk review decisions are advisory and do not change evidence coverage, test results, or release readiness.",
                "",
                "### Governance Summary",
                f"- Active Reviews: {gov['activeReviews']}",
                f"- Accepted: {gov['activeAccepted']}",
                f"- Overridden: {gov['activeOverridden']}",
                f"- Needs Discussion: {gov['activeNeedsDiscussion']}",
                f"- Reset Events: {gov['resetEvents']}",
                f"- Total History Events: {gov['totalHistoryEvents']}",
                "",
                "### Generated Risk vs Effective Risk",
                f"- Generated Risk: {gen_dist['critical']} Critical, {gen_dist['high']} High, {gen_dist['medium']} Medium, {gen_dist['low']} Low, {gen_dist['unknown']} Unknown",
                f"- Effective Risk: {eff_dist['critical']} Critical, {eff_dist['high']} High, {eff_dist['medium']} Medium, {eff_dist['low']} Low, {eff_dist['unknown']} Unknown",
                "",
                "### Active Decisions",
                *decisions_md,
                "",
                "### History Timeline",
                *timeline_md,
                ""
            ])

        # Release Decision Summary
        from app.models.release_decision import ReleaseDecision
        from app.models.release_decision_history import ReleaseDecisionHistory
        release_decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == run.id,
            ReleaseDecision.is_active == True
        ).first()

        if release_decision:
            release_history = db.query(ReleaseDecisionHistory).filter(
                ReleaseDecisionHistory.release_decision_id == release_decision.id
            ).order_by(ReleaseDecisionHistory.created_at.asc()).all()

            release_timeline_md = []
            for event in release_history:
                timestamp = event.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if event.created_at else "Unknown"
                actor_str = event.actor_name or "Unknown"
                transition_str = f" ({event.previous_status} → {event.new_status})" if event.previous_status and event.new_status else ""
                note_str = f" - Note: {event.note}" if event.note else ""
                release_timeline_md.append(
                    f"- {timestamp}: **{event.event_type}** by {actor_str}{transition_str}{note_str}"
                )
            if not release_timeline_md:
                release_timeline_md.append("- No history events yet.")

            markdown_lines.extend([
                "## Release Decision Summary",
                "",
                f"**Advisory Warning:** Release decisions are governance actions and do not alter evidence truth, coverage status, risk reviews, readiness calculations, or regression scope generation.",
                "",
                "### Current Decision",
                f"- Decision Status: {release_decision.decision_status}",
                f"- Approver: {release_decision.approver_name or 'Not yet approved'}",
                f"- Timestamp: {release_decision.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC') if release_decision.updated_at else 'Unknown'}",
                f"- Snapshot Hash: {release_decision.snapshot_hash or 'Unknown'}",
                f"- Evidence Health: {release_decision.evidence_health_status or 'Unknown'}",
                f"- Readiness State: {release_decision.readiness_state or 'Unknown'}",
                f"- Decision Note: {release_decision.decision_note or 'None'}",
                "",
                "### Release Decision Timeline",
                *release_timeline_md,
                ""
            ])
        else:
            markdown_lines.extend([
                "## Release Decision Summary",
                "",
                "No release decision has been recorded for this recommendation run.",
                ""
            ])

        markdown_lines.extend([
            "## Uploaded Evidence",
            "",
            f"**Acceptance Criteria Source:** {report.uploaded_evidence.acceptance_criteria_source}",
            "",
            "### JUnit Execution Summary",
            f"- Total: {report.uploaded_evidence.junit_execution_summary['total']}",
            f"- Passed: {report.uploaded_evidence.junit_execution_summary['passed']}",
            f"- Failed: {report.uploaded_evidence.junit_execution_summary['failed']}",
            f"- Skipped: {report.uploaded_evidence.junit_execution_summary['skipped']}",
            "",
            "### Coverage Summary",
            f"- Coverage Percentage: {report.uploaded_evidence.coverage_summary['coverage_percentage']}%",
            "",
            "### Evidence Graph Snapshot",
            f"- Snapshot Hash: {report.uploaded_evidence.evidence_graph_snapshot.snapshot_hash}",
            f"- Generated At: {report.uploaded_evidence.evidence_graph_snapshot.generated_at.isoformat()}",
            f"- Source Hash: {report.uploaded_evidence.evidence_graph_snapshot.source_hash}",
            f"- Evidence Version: {report.uploaded_evidence.evidence_graph_snapshot.evidence_version}",
            ""
        ])

        # Manual Validation Evidence section
        manual_evidence_lines = [
            "## Manual Validation Evidence",
            "",
            "Manual validation evidence is reported separately and does not modify automated coverage or readiness calculations.",
            ""
        ]
        
        has_manual_evidence = False
        for trace in snapshot_traceability:
            mv = trace.get("manualValidation")
            if mv and mv.get("mappedManualTestsCount", 0) > 0:
                has_manual_evidence = True
                readable_id = trace.get("readableId", "UNKNOWN")
                title = trace.get("title", "Unknown")
                
                manual_evidence_lines.extend([
                    f"### {readable_id}: {title}",
                    f"- **Manual Validation Status:** {mv.get('status')}",
                    f"- **Mapped Tests Count:** {mv.get('mappedManualTestsCount')}",
                    f"- **Latest Manual Outcome:** {mv.get('latestOutcome') or 'N/A'}",
                ])
                if mv.get('latestExecutedAt'):
                    manual_evidence_lines.append(f"- **Latest Executed At:** {mv.get('latestExecutedAt')}")
                if mv.get('latestExecutedByName'):
                    manual_evidence_lines.append(f"- **Latest Executed By:** {mv.get('latestExecutedByName')}")
                if mv.get('evidenceUrls'):
                    urls_str = ", ".join(mv.get('evidenceUrls'))
                    manual_evidence_lines.append(f"- **Evidence URLs:** {urls_str}")
                
                # List the manual tests in a neat Markdown table
                manual_evidence_lines.extend([
                    "",
                    "| Test Case ID | Title | Outcome | Executed By | Date | Evidence URL |",
                    "|---|---|---|---|---|---|",
                ])
                for mt in mv.get("manualTests", []):
                    tc_id = mt.get("id")
                    t_title = mt.get("title")
                    outcome = mt.get("outcome")
                    exec_by = mt.get("executedByName") or "N/A"
                    date_str = mt.get("executedAt") or "N/A"
                    url = mt.get("evidenceUrl") or "N/A"
                    manual_evidence_lines.append(f"| {tc_id} | {t_title} | {outcome} | {exec_by} | {date_str} | {url} |")
                
                manual_evidence_lines.append("")
                
        if not has_manual_evidence:
            manual_evidence_lines.append("No manual test mappings exist for the requirements in this run.")
            manual_evidence_lines.append("")
        
        # Phase 6.5: Manual Evidence Governance section
        manual_governance_lines = [
            "## Manual Evidence Governance",
            "",
            "Manual evidence requires governance approval before it can influence residual risk calculations.",
            "",
            "**Advisory Notice:** Only approved manual evidence contributes to residual risk calculations. Manual evidence never contributes to automated coverage.",
            ""
        ]
        
        manual_nodes = snapshot_data.get("manualEvidenceNodes", [])
        governance_summary = {
            "APPROVED": 0,
            "PENDING_REVIEW": 0,
            "REJECTED": 0,
            "CHALLENGED": 0,
            "EXPIRED": 0
        }
        
        for node in manual_nodes:
            gov_status = node.get("governanceStatus", "PENDING_REVIEW")
            if gov_status in governance_summary:
                governance_summary[gov_status] += 1
        
        manual_governance_lines.extend([
            "### Governance Summary",
            f"- **Approved:** {governance_summary['APPROVED']}",
            f"- **Pending Review:** {governance_summary['PENDING_REVIEW']}",
            f"- **Rejected:** {governance_summary['REJECTED']}",
            f"- **Challenged:** {governance_summary['CHALLENGED']}",
            f"- **Expired:** {governance_summary['EXPIRED']}",
            ""
        ])
        
        # Detailed governance information for each manual evidence
        if manual_nodes:
            manual_governance_lines.extend([
                "### Manual Evidence Governance Details",
                "",
                "| Test Case | Title | Outcome | Governance Status | Reviewer | Reviewed At | Review Note |",
                "|---|---|---|---|---|---|---|",
            ])
            
            for node in manual_nodes:
                tc_id = node.get("manualTestId", "N/A")[:8] + "..."
                title = node.get("manualTestTitle", "Unknown")[:30]
                outcome = node.get("outcome", "N/A")
                gov_status = node.get("governanceStatus", "PENDING_REVIEW")
                reviewer = node.get("governanceReviewer", "N/A")
                reviewed_at = node.get("governanceReviewedAt", "N/A")
                review_note = node.get("governanceReviewNote", "")
                
                manual_governance_lines.append(
                    f"| {tc_id} | {title} | {outcome} | {gov_status} | {reviewer} | {reviewed_at} | {review_note} |"
                )
            
            manual_governance_lines.append("")
        else:
            manual_governance_lines.append("No manual evidence found in this run.")
            manual_governance_lines.append("")

        # Phase 7.1: External Test Management Synchronization section
        external_sync_lines = [
            "## External Test Management Synchronization",
            "",
            "Manual test execution results are synchronized to external test management systems (e.g., TestRail).",
            "",
            "**Advisory Notice:** External synchronization is informational only and does not contribute to automated coverage or release readiness.",
            ""
        ]
        
        # Get sync information from manual nodes
        sync_summary = {
            "SYNCED": 0,
            "PENDING": 0,
            "FAILED": 0
        }
        
        sync_details = []
        for node in manual_nodes:
            sync_status = node.get("syncStatus", "PENDING")
            if sync_status in sync_summary:
                sync_summary[sync_status] += 1
            
            # Collect sync details
            if sync_status in ["SYNCED", "FAILED"]:
                sync_details.append({
                    "test_case": node.get("manualTestTitle", "Unknown")[:30],
                    "provider": node.get("externalSystem", "N/A"),
                    "sync_status": sync_status,
                    "external_run_id": node.get("externalRunId", "N/A"),
                    "external_execution_id": node.get("externalExecutionId", "N/A"),
                    "last_synced_at": node.get("lastSyncedAt", "N/A")
                })
        
        external_sync_lines.extend([
            "### Sync Summary",
            f"- **Synced:** {sync_summary['SYNCED']}",
            f"- **Pending:** {sync_summary['PENDING']}",
            f"- **Failed:** {sync_summary['FAILED']}",
            ""
        ])
        
        # Detailed sync information
        if sync_details:
            external_sync_lines.extend([
                "### External Sync Details",
                "",
                "| Test Case | Provider | Sync Status | External Run ID | External Execution ID | Last Synced |",
                "|---|---|---|---|---|---|",
            ])
            
            for detail in sync_details:
                external_sync_lines.append(
                    f"| {detail['test_case']} | {detail['provider']} | {detail['sync_status']} | {detail['external_run_id']} | {detail['external_execution_id']} | {detail['last_synced_at']} |"
                )
            
            external_sync_lines.append("")
        else:
            external_sync_lines.append("No external sync information available for this run.")
            external_sync_lines.append("")

        markdown_lines.extend(manual_evidence_lines)
        markdown_lines.extend(manual_governance_lines)
        markdown_lines.extend(external_sync_lines)

        markdown_lines.extend([
            "## Covered by Passed PR Tests",
            ""
        ])
        
        for req in report.covered_by_passed_pr_tests:
            markdown_lines.extend([
                f"### {req.readable_id}: {req.title}",
                f"- **Source AC Number:** {req.source_ac_number}",
                f"- **Matched Test:** {req.matched_test_name}",
                f"- **Test Classname:** {req.test_classname}",
                f"- **Evidence Type:** {req.evidence_type}",
                f"- **Reason:** {req.reason}",
                ""
            ])
        
        markdown_lines.extend([
            "## Partially Supported Requirements",
            ""
        ])
        
        for req in report.partially_supported_requirements:
            markdown_lines.extend([
                f"### {req.readable_id}: {req.title}",
                f"- **Source AC Number:** {req.source_ac_number}",
                f"- **Supporting Evidence:** {req.supporting_evidence}",
                f"- **Why Not Fully Verified:** {req.why_not_fully_verified}",
                f"- **What Would Make It Verified:** {req.what_would_make_it_verified}",
                f"- **Suggested Strengthening Action:** {req.suggested_strengthening_action}",
                ""
            ])
        
        markdown_lines.extend([
            "## Missing Automated Coverage",
            ""
        ])
        
        for req in report.missing_automated_coverage:
            markdown_lines.extend([
                f"### {req.readable_id}: {req.title}",
                f"- **Source AC Number:** {req.source_ac_number}",
                f"- **Flow:** {req.flow}",
                f"- **Why Not Covered:** {req.why_not_covered}",
                f"- **Suggested Test Title:** {req.suggested_test_title}",
                f"- **Suggested Layer:** {req.suggested_layer}",
                f"- **Risk If Skipped:** {req.risk_if_skipped}",
                ""
            ])
        
        if report.targeted_scope:
            markdown_lines.extend([
                "## Regression Scope Plan",
                "",
                "### Required Before Release",
                f"- Count: {report.targeted_scope.required_items_count}",
                "",
                "### Recommended Regression",
                f"- Count: {report.targeted_scope.review_items_count}",
                "",
                "### Optional Safety Net",
                f"- Count: 0",
                "",
                "### Safe To Skip",
                f"- Count: 0",
                "",
                "### Exclusions",
                f"- Already Verified: {report.targeted_scope.excluded_verified_requirements_count}",
                f"- Already Passed Tests: {report.targeted_scope.excluded_passed_tests_count}",
                "",
                "### Generation Rules Applied",
                ""
            ])
            
            for rule in report.targeted_scope.generation_rules_applied:
                markdown_lines.append(f"- {rule}")
            
            markdown_lines.append("")
        
        if report.optimization_summary:
            markdown_lines.extend([
                "## Execution Reduction",
                "",
                "### Optimization Metrics",
                f"- Current Tests: {report.optimization_summary['optimizationMetrics']['currentTests']}",
                f"- Optimized Required: {report.optimization_summary['optimizationMetrics']['optimizedTests']['required']}",
                f"- Optimized Recommended: {report.optimization_summary['optimizationMetrics']['optimizedTests']['recommended']}",
                f"- Optimized Optional: {report.optimization_summary['optimizationMetrics']['optimizedTests']['optional']}",
                f"- Safe to Skip: {report.optimization_summary['optimizationMetrics']['optimizedTests']['safeToSkip']}",
                f"- Optimization Percentage: {report.optimization_summary['optimizationMetrics']['optimizationPercentage']}%",
                f"- Execution Reduction: {report.optimization_summary['optimizationMetrics']['executionReduction']}%",
                f"- Coverage Confidence: {report.optimization_summary['optimizationMetrics']['coverageConfidence']}%",
                "",
                "### Risk Distribution",
                ""
            ])
            
            for risk_band, data in report.optimization_summary['riskDistribution'].items():
                markdown_lines.append(f"- {risk_band}: {data['count']} ({data['percentage']}%)")
            
            markdown_lines.extend([
                "",
                "### Coverage Distribution",
                ""
            ])
            
            for coverage, data in report.optimization_summary['coverageDistribution'].items():
                markdown_lines.append(f"- {coverage}: {data['count']} ({data['percentage']}%)")
            
            markdown_lines.extend([
                "",
                "### Recommended Execution Plan",
                ""
            ])
            
            for phase in report.optimization_summary['recommendedExecutionPlan']['phases']:
                markdown_lines.extend([
                    f"#### Phase {phase['phase']}: {phase['name']}",
                    f"- Priority: {phase['priority']}",
                    f"- Test Count: {phase['testCount']}",
                    ""
                ])
            
            markdown_lines.extend([
                "### Advisory Notice",
                f"- {report.optimization_summary['advisoryNotice']['message']}",
                ""
            ])
            
            for recommendation in report.optimization_summary['advisoryNotice']['recommendations']:
                markdown_lines.append(f"- {recommendation}")
            
            markdown_lines.extend([
                "",
                "**Advisory Warning:** Regression optimization is advisory only and does not alter evidence truth, coverage status, risk reviews, readiness calculations, or release decisions.",
                ""
            ])
        
        markdown_lines.extend([
            "## Remaining Risks",
            ""
        ])
        
        for risk in report.remaining_risks:
            markdown_lines.append(f"- {risk}")
        
        markdown_lines.extend([
            "",
            "## Recommended Next Actions",
            ""
        ])
        
        for i, action in enumerate(report.recommended_next_actions, 1):
            markdown_lines.append(f"{i}. {action}")
        
        if report.audit_appendix:
            markdown_lines.extend([
                "",
                "## Audit Appendix",
                "",
                "### Internal Requirement IDs",
                ""
            ])
            
            for req_id in report.audit_appendix["internal_requirement_ids"]:
                markdown_lines.append(f"- {req_id}")
            
            markdown_lines.extend([
                "",
                "### Source Hashes",
                f"- AC Source: {report.audit_appendix['source_hashes']['ac_source']}",
                f"- Snapshot: {report.audit_appendix['source_hashes']['snapshot']}",
                "",
                "### Graph Diagnostics",
                f"- Total Parent Requirements: {report.audit_appendix['graph_diagnostics']['total_parent_requirements']}",
                f"- Total Tests: {report.audit_appendix['graph_diagnostics']['total_tests']}",
                ""
            ])
        
        markdown_content = "\n".join(markdown_lines)
    
    return EvidenceReportResponse(
        status="SUCCESS",
        report=report if format == "json" else None,
        markdown_content=markdown_content if format == "markdown" else None
    )


@router.post("/{run_id}/report-incident", status_code=status.HTTP_200_OK)
def report_post_release_incident(
    run_id: UUID,
    incident_data: dict,
    db: Session = Depends(get_db)
):
    """
    Report a post-release incident (regression, rollback, hotfix).
    Creates PatternMemoryV2 signals for affected areas.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.pattern_memory_v2 import PatternMemoryV2
    from app.models.acceptance_criterion import AcceptanceCriterion
    import uuid
    from datetime import datetime
    
    # Load the recommendation run
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == run_id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found"
        )
    
    # Validate incident type
    incident_type = incident_data.get("incident_type")
    valid_types = ["REGRESSION", "ROLLBACK", "HOTFIX"]
    if incident_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid incident_type. Must be one of: {valid_types}"
        )
    
    description = incident_data.get("description", "")
    affected_areas = incident_data.get("affected_areas", [])
    severity = incident_data.get("severity", "MEDIUM")
    
    # Map severity to strength
    severity_to_strength = {
        "CRITICAL": 0.9,
        "HIGH": 0.7,
        "MEDIUM": 0.5,
        "LOW": 0.3
    }
    strength = severity_to_strength.get(severity, 0.5)
    
    # Load regression scope if available
    signals_created = []
    
    # Load ACs for the repository
    acs = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.repository_id == run.repository_id
    ).all()
    
    # For each affected area, find matching ACs and create signals
    for area in affected_areas:
        # Try to find AC by ID or fuzzy match on text
        matched_ac = None
        for ac in acs:
            if str(ac.id) == area or area.lower() in ac.text.lower():
                matched_ac = ac
                break
        
        if matched_ac:
            # Check if signal already exists
            existing = db.query(PatternMemoryV2).filter(
                PatternMemoryV2.pattern_key == matched_ac.normalized_key,
                PatternMemoryV2.repository_id == run.repository_id
            ).first()
            
            if existing:
                existing.usage_count += 1
                existing.strength = min(1.0, existing.strength + 0.1)
                signals_created.append({
                    "pattern_key": matched_ac.normalized_key,
                    "action": "updated",
                    "signal_type": incident_type
                })
            else:
                signal = PatternMemoryV2(
                    id=uuid.uuid4(),
                    repository_id=run.repository_id,
                    workspace_id=run.workspace_id,
                    pattern_key=matched_ac.normalized_key,
                    signal_type=incident_type,
                    strength=strength,
                    confidence=0.7,
                    usage_count=1
                )
                db.add(signal)
                signals_created.append({
                    "pattern_key": matched_ac.normalized_key,
                    "action": "created",
                    "signal_type": incident_type
                })
    
    # Update recommendation run outcome status
    run.outcome_status = "REGRESSION_REPORTED"
    db.commit()
    
    return {
        "status": "SUCCESS",
        "signals_created": signals_created,
        "incident_type": incident_type,
        "severity": severity,
        "affected_areas_count": len(affected_areas)
    }


@router.get("/{run_id}/audit-report")
def get_release_audit_report(
    run_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a complete audit record for a recommendation run and its release decision.
    Returns JSON with all audit fields.
    """
    from app.services.release_audit_service import ReleaseAuditService
    
    try:
        audit_record = ReleaseAuditService.generate_release_audit_record(
            db,
            str(run_id)
        )
        return audit_record
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate audit report: {str(e)}"
        )


@router.get("/{run_id}/audit-report/pdf")
def get_release_audit_report_pdf(
    run_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a complete audit record for a recommendation run as PDF.
    Returns PDF file or JSON with warning if PDF generation fails.
    """
    from app.services.release_audit_service import ReleaseAuditService
    from fastapi.responses import JSONResponse
    
    try:
        audit_record = ReleaseAuditService.generate_release_audit_record(
            db,
            str(run_id)
        )
        
        # For now, return JSON with a warning header
        # PDF generation would require additional libraries
        return JSONResponse(
            content={
                "warning": "PDF generation not yet implemented",
                "audit_record": audit_record
            },
            headers={"X-PDF-Generation-Status": "not-implemented"}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate audit report: {str(e)}"
        )
