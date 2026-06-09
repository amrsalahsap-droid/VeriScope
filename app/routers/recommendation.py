from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
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
from app.schemas.debugging import (
    RecommendationDebugResponse,
    RecommendationDetailedDebugResponse
)
from app.schemas.readiness import RecommendationReadinessGateResponse, ReadinessAcknowledgementCreate
from app.services.recommendation import RecommendationService
from app.services.analytics import RecommendationAnalyticsService
from app.services.outcome_execution_collector import OutcomeExecutionCollector
from app.dependencies.auth import require_workspace_member, get_current_workspace
from app.models.user import Workspace


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
    try:
        run_in = RecommendationRunCreate(
            repository_id=generate_in.repository_id,
            pr_id=generate_in.pull_request_id,
            changed_files=generate_in.changed_files,
            triggered_by=generate_in.triggered_by,
            engine_version=generate_in.engine_version,
            readiness_acknowledged=generate_in.readiness_acknowledged
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

        test_list.append({
            "stable_identity": t.test_case_id,
            "display_name": display_name,
            "suite_name": suite_name,
            "tier": tier,
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
        })

    # Sort: must_run first, then should_run, then fallback; within tier by priority_score desc
    tier_order = {"must_run": 0, "should_run": 1, "fallback": 2}
    test_list.sort(key=lambda x: (tier_order[x["tier"]], -x["priority_score"]))

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

    return {
        "id": str(run.id),
        "created_at": run.created_at.isoformat() + "Z" if run.created_at else None,
        "triggered_by": run.triggered_by,
        "recommendation_quality": quality_assessment,
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
            "must_run_count": sum(1 for t in test_list if t["tier"] == "must_run"),
            "should_run_count": sum(1 for t in test_list if t["tier"] == "should_run"),
            "fallback_count": sum(1 for t in test_list if t["tier"] == "fallback"),
            "estimated_runtime_seconds": run.estimated_runtime_seconds or 0.0,
            "full_suite_runtime_seconds": run.full_suite_runtime_seconds,
            "runtime_confidence": run.runtime_confidence,
            "skipped_count": run.skipped_count or 0,
            "skipped_reason_summary": run.skipped_reason_summary,
            "types": strategy.get("types", []),
            "summary": strategy.get("summary", ""),
        },
        # Section 3: Recommended Tests (tiered)
        "recommended_tests": test_list,
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


@router.get("/{recommendation_run_id}/readiness", response_model=RecommendationReadinessGateResponse)
def get_recommendation_readiness(
    recommendation_run_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Assess readiness for an existing recommendation run.
    """
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.services.recommendation_readiness_gate import RecommendationReadinessGate
    from app.schemas.readiness import RecommendationReadinessGateResponse

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

    # Use generation-time snapshot if available for consistency
    if rec_run.readiness_level_at_generation:
        # Return snapshot data instead of live assessment
        return RecommendationReadinessGateResponse(
            can_generate=rec_run.can_generate_at_generation or False,
            readiness_level=rec_run.readiness_level_at_generation,
            expected_confidence=rec_run.expected_confidence_at_generation,
            intelligence_completeness_score=rec_run.readiness_score_at_generation or 0,
            release_confidence_ceiling=rec_run.confidence_ceiling_at_generation,
            available_inputs=rec_run.available_inputs_at_generation or [],
            missing_inputs=rec_run.missing_inputs_at_generation or [],
            blocking_inputs=rec_run.blocking_inputs_at_generation or [],
            confidence_limiters=rec_run.confidence_limiters_at_generation,
            evidence_summary=rec_run.evidence_summary_at_generation,
            confidence_reason=rec_run.confidence_reason_at_generation,
            recommended_actions=[],
            next_best_actions=[]
        )

    # Fallback to live assessment for legacy recommendations
    gate = RecommendationReadinessGate()
    result = gate.assess(db, str(rec_run.repository_id), str(rec_run.pull_request_id) if rec_run.pull_request_id else None, recommendation_run_id=str(rec_run.id))

    return RecommendationReadinessGateResponse(
        can_generate=result.can_generate,
        readiness_level=result.readiness_level,
        expected_confidence=result.expected_confidence,
        intelligence_completeness_score=result.intelligence_completeness_score,
        release_confidence_ceiling=result.release_confidence_ceiling,
        available_inputs=result.available_inputs,
        missing_inputs=result.missing_inputs,
        next_best_actions=result.next_best_actions,
        primary_message=result.user_message,
        secondary_message=result.technical_reason,
        created_at=result.created_at
    )


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
    rec_run.readiness_decision = request.decision.value
    db.commit()

    return {
        "status": "success",
        "recommendation_run_id": str(rec_run.id),
        "readiness_acknowledged": True
    }

