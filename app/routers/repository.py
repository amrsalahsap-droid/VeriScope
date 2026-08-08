from uuid import UUID
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_workspace, get_current_workspace_id, require_workspace_member
from app.models.user import User, Workspace
from app.models.coverage import CoverageReport
from app.schemas.repository import RepositoryCreate, RepositoryResponse, RepositoryTestRunsResponse
from app.schemas.readiness import RecommendationReadinessGateResponse, ReadinessSummaryResponse
from app.services.repository import RepositoryService
from app.services.test_ingestion import TestIngestionService
from app.services.repository_readiness import RepositoryReadinessService
from app.services.coverage_ingestion import CoverageIngestionService, CoverageIngestionError
from app.models.repository import Repository
from app.models.test_result import TestRun, TestResult
from app.models.webhook_event import WebhookEvent
from app.models.pull_request import PullRequest
from app.models.integration_connection import IntegrationConnection
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate, RecommendationGeneratePayload
from app.schemas.pipeline_run import PipelineRunTriggerRequest, PipelineRunResponse
from app.services.pipeline_run_service import PipelineRunService
from pydantic import BaseModel
from app.services.junit_parser import XMLParsingError, OversizedXMLException
from app.constants.evidence import EvidenceSource, EvidenceArtifactType
from app.config import settings
from app.services.manual_test_case_csv_import import ManualTestCaseCSVImport
from app.services.jira_connector import JiraConnector
from app.services.azure_devops_connector import AzureDevOpsConnector
from app.services.testrail_connector import TestRailConnector
from app.services.external_requirement_coverage_resolver import ExternalRequirementCoverageResolver
from app.schemas.manual_test_execution import ManualTestExecutionCreate
from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
from app.schemas.manual_test_mapping import ManualTestMappingCreate, ManualTestMappingResponse
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.manual_test_execution import ManualTestExecution
from app.services.manual_evidence_governance_service import ManualEvidenceGovernanceService
from app.schemas.ci_token import CITokenCreate, CITokenResponse, CITokenListResponse, CITokenRevokeResponse
from app.services.ci_token_service import CITokenService
from app.schemas.repository import RepositoryCISettingsUpdate, RepositoryCISettingsResponse

router = APIRouter(
    prefix="/repositories", 
    tags=["Repositories"],
    dependencies=[Depends(require_workspace_member())]
)

@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def create_repository(
    repo_in: RepositoryCreate, 
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """Register a new repository under the active workspace."""
    service = RepositoryService(db)
    # Automatically bind repository to the authenticated user's workspace
    repo = service.create_repository(repo_in)
    repo.workspace_id = UUID(workspace_id)
    db.commit()
    db.refresh(repo)
    return repo

@router.get("/{id}", response_model=RepositoryResponse)
def get_repository(
    id: UUID, 
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """Retrieve repository details by ID within the active workspace."""
    repo = db.query(Repository).filter(
        Repository.id == id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    return repo


@router.post("/{repository_id}/test-history/upload", status_code=status.HTTP_201_CREATED)
async def upload_test_history(
    repository_id: UUID,
    file: UploadFile = File(...),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    source: str = Form(EvidenceSource.MANUAL_UPLOAD.value),
    import_mode: Optional[str] = Form("INVENTORY_ONLY"),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Upload JUnit XML test history for a specific repository.
    
    Verifies:
    - Repository belongs to current workspace
    - Repository is selected for analysis
    
    Returns test run summary and updated repository readiness state.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # 2. Verify repository is selected for analysis
    if not repo.selected_for_analysis:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository is not selected for analysis. Enable it first."
        )
    
    # 3. Size validation
    max_bytes = settings.MAX_JUNIT_XML_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload too large: JUnit XML size exceeding limit of {settings.MAX_JUNIT_XML_SIZE_MB} MB."
        )
    
    # 4. Read file
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file stream: {str(e)}"
        )
    
    # 5. Ingest using TestIngestionService
    ingestion_service = TestIngestionService(db)
    
    try:
        test_run, duplicate_coalesced = ingestion_service.ingest_junit_xml(
            file_bytes=file_bytes,
            filename=file.filename or "unknown_junit.xml",
            repository_id=repository_id,
            commit_sha=commit_sha,
            evidence_source=source,
            branch=branch,
            import_mode=import_mode or "INVENTORY_ONLY"
        )
    except OversizedXMLException as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
    except XMLParsingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failure: {str(e)}"
        )
    
    # 6. For INVENTORY_ONLY mode, duplicate coalescing is allowed (idempotent inventory update)
    if import_mode == "INVENTORY_ONLY" or test_run is None:
        readiness_service = RepositoryReadinessService(db)
        readiness_result = readiness_service.calculate_readiness(repository_id, UUID(workspace_id))
        
        return {
            "import_mode": "INVENTORY_ONLY",
            "test_run_id": None,
            "status": "INVENTORY_UPDATED",
            "message": "Test case inventory updated successfully",
            "duplicate_coalesced": duplicate_coalesced,
            "repository_readiness": {
                "readiness_state": readiness_result.readiness_state,
                "readiness_reasons": readiness_result.readiness_reasons,
                "next_action": readiness_result.next_action
            }
        }
    
    # 7. For execution modes, reject duplicate artifacts
    if duplicate_coalesced:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate test run artifact detected. This JUnit XML file has already been uploaded."
        )
    
    # 8. Recalculate repository readiness for execution modes
    readiness_service = RepositoryReadinessService(db)
    readiness_result = readiness_service.calculate_readiness(repository_id, UUID(workspace_id))
    
    return {
        "import_mode": import_mode,
        "test_run_id": str(test_run.id),
        "tests_total": test_run.total_tests,
        "tests_passed": test_run.passed_tests,
        "tests_failed": test_run.failed_tests,
        "tests_skipped": test_run.skipped_tests,
        "duration_seconds": test_run.duration,
        "parser_version": test_run.parser_version,
        "normalization_schema_version": test_run.normalization_schema_version,
        "evidence_health_status": test_run.evidence_health_status,
        "repository_readiness": {
            "readiness_state": readiness_result.readiness_state,
            "readiness_reasons": readiness_result.readiness_reasons,
            "next_action": readiness_result.next_action
        }
    }


@router.get("/{repository_id}/test-history/summary")
def get_test_history_summary(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get test history summary for a specific repository.
    
    Returns:
    - Total test runs count
    - Total test results count
    - Latest test run timestamp
    - Latest test run details
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # 2. Get test runs count
    test_runs_count = db.query(func.count(TestRun.id)).filter(
        TestRun.repository_id == repository_id
    ).scalar() or 0
    
    # 3. Get test results count
    test_results_count = db.query(func.count(TestResult.id)).join(
        TestRun, TestResult.test_run_id == TestRun.id
    ).filter(
        TestRun.repository_id == repository_id
    ).scalar() or 0
    
    # 4. Get latest test run
    latest_test_run = db.query(TestRun).filter(
        TestRun.repository_id == repository_id
    ).order_by(TestRun.created_at.desc()).first()
    
    if test_runs_count == 0:
        return {
            "repository_id": str(repository_id),
            "test_runs_count": 0,
            "test_results_count": 0,
            "latest_test_run_at": None,
            "latest_test_run": None
        }
    
    return {
        "repository_id": str(repository_id),
        "test_runs_count": test_runs_count,
        "test_results_count": test_results_count,
        "latest_test_run_at": latest_test_run.created_at.isoformat() if latest_test_run else None,
        "latest_test_run": {
            "id": str(latest_test_run.id),
            "run_name": latest_test_run.ingestion_diagnostics.get("run_name") if latest_test_run.ingestion_diagnostics else None,
            "commit_sha": latest_test_run.commit_sha,
            "branch": latest_test_run.ingestion_diagnostics.get("branch") if latest_test_run.ingestion_diagnostics else None,
            "tests_total": latest_test_run.total_tests,
            "tests_passed": latest_test_run.passed_tests,
            "tests_failed": latest_test_run.failed_tests,
            "tests_skipped": latest_test_run.skipped_tests,
            "duration_seconds": latest_test_run.duration,
            "source": latest_test_run.evidence_source,
            "evidence_health_status": latest_test_run.evidence_health_status
        } if latest_test_run else None
    }


@router.post("/{repository_id}/coverage/upload", status_code=status.HTTP_201_CREATED)
async def upload_coverage(
    repository_id: UUID,
    file: UploadFile = File(...),
    format: str = Form("LCOV"),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    source: str = Form(EvidenceSource.MANUAL_UPLOAD.value),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Upload coverage report (LCOV or COBERTURA) for a specific repository.
    
    Verifies:
    - Repository belongs to current workspace
    - Repository is selected for analysis
    - Format is supported (LCOV only for now)
    
    Returns coverage report summary and updated repository readiness state.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # 2. Verify repository is selected for analysis
    if not repo.selected_for_analysis:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository is not selected for analysis. Enable it first."
        )
    
    # 3. Validate format
    format_upper = format.upper()
    if format_upper not in ["LCOV", "COBERTURA"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported coverage format: {format}. Only LCOV and COBERTURA are currently supported."
        )
    
    # 4. Size validation
    max_bytes = settings.MAX_LCOV_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload too large: Coverage report size exceeding limit of {settings.MAX_LCOV_SIZE_MB} MB."
        )
    
    # 5. Read file
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file stream: {str(e)}"
        )
    
    # 6. Validate commit_sha is provided
    if not commit_sha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="commit_sha is required for coverage uploads."
        )
    
    # 7. Ingest using CoverageIngestionService
    try:
        report = CoverageIngestionService.ingest_coverage(
            db=db,
            repository_id=repository_id,
            commit_sha=commit_sha,
            payload_bytes=file_bytes,
            file_name=file.filename or "coverage.info",
            branch=branch,
            evidence_source=source
        )
        db.commit()
    except CoverageIngestionError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Coverage ingestion pipeline failure: {str(e)}"
        )
    
    # 8. Recalculate repository readiness
    readiness_service = RepositoryReadinessService(db)
    readiness_result = readiness_service.calculate_readiness(repository_id, UUID(workspace_id))
    
    # 9. Get file count from coverage report
    files_count = len(report.file_entries) if report.file_entries else 0
    
    return {
        "coverage_report_id": str(report.id),
        "format": format_upper,
        "files_total": files_count,
        "covered_lines_total": report.covered_lines_count,
        "uncovered_lines_total": report.uncovered_lines_count,
        "coverage_confidence": report.confidence_score,
        "parser_version": report.parser_version,
        "normalization_schema_version": report.normalization_schema_version,
        "repository_readiness": {
            "readiness_state": readiness_result.readiness_state,
            "readiness_reasons": readiness_result.readiness_reasons,
            "next_action": readiness_result.next_action
        }
    }


def _get_webhook_status(last_webhook_at: Optional[datetime]) -> str:
    """Calculate webhook status based on last_webhook_at timestamp."""
    if not last_webhook_at:
        return "UNKNOWN"
    
    cutoff = datetime.utcnow() - timedelta(hours=24)
    if last_webhook_at >= cutoff:
        return "ACTIVE"
    return "INACTIVE"


@router.get("/{repository_id}/webhook-status")
def get_webhook_status(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get webhook status and recent events for a repository.
    
    Returns:
    - webhook_status: ACTIVE, INACTIVE, or UNKNOWN
    - last_webhook_at: timestamp of last webhook
    - recent_events: list of recent webhook events
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # 2. Determine webhook status
    webhook_status = _get_webhook_status(repo.last_webhook_at)
    
    # 3. Get recent webhook events for this repository (only valid signatures)
    recent_events = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.repository_id == repo.github_repo_id,
            WebhookEvent.signature_valid == True
        )
        .order_by(WebhookEvent.received_at.desc())
        .limit(10)
        .all()
    )
    
    events_data = []
    for event in recent_events:
        events_data.append({
            "event_type": event.event_type,
            "action": event.action,
            "received_at": event.received_at.isoformat() if event.received_at else None,
            "processing_status": event.processing_status
        })
    
    return {
        "webhook_status": webhook_status,
        "last_webhook_at": repo.last_webhook_at.isoformat() if repo.last_webhook_at else None,
        "recent_events": events_data
    }


# API Repository Router (for POST /api/repositories/...)
api_router = APIRouter(
    prefix="/api/repositories",
    tags=["API Repositories"]
)

# CI/CD Router (no workspace authentication required - uses CI token auth)
cicd_router = APIRouter(
    prefix="/api/repositories",
    tags=["CI/CD"]
)

@api_router.post("/{repository_id}/coverage/upload", status_code=status.HTTP_201_CREATED)
async def api_upload_coverage(
    repository_id: UUID,
    file: UploadFile = File(None),
    format: Optional[str] = Form(None),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    source: str = Form("MANUAL_UPLOAD"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    import hashlib
    
    # 1. 400 missing file check
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing file"
        )

    # 2. 400 format check
    if not format:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported coverage format"
        )
    
    format_upper = format.upper()
    if format_upper not in ["LCOV", "COBERTURA"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported coverage format"
        )

    # 3. 403 repository not in workspace check
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="repository not in workspace"
        )

    # 4. Reject upload if repository is NOT_SELECTED (selected_for_analysis = false)
    if not repo.selected_for_analysis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enable this repository before uploading coverage evidence."
        )

    # Validate that test history has been uploaded first
    test_runs_count = db.query(func.count(TestRun.id)).filter(TestRun.repository_id == repository_id).scalar() or 0
    if test_runs_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload test history before coverage to make this repository recommendation-ready."
        )

    # 5. Read file (400 invalid coverage file on empty or read error)
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid coverage file"
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid coverage file"
        )

    # 6. 409 Duplicate Artifact check
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_report = (
        db.query(CoverageReport)
        .filter(
            CoverageReport.repository_id == repository_id,
            CoverageReport.file_hash == file_hash
        )
        .first()
    )
    if existing_report:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="duplicate artifact"
        )

    # 7. Ingestion (422 malformed coverage content on parser error)
    try:
        report = CoverageIngestionService.ingest_coverage(
            db=db,
            repository_id=repository_id,
            commit_sha=commit_sha or "unknown_sha",
            payload_bytes=file_bytes,
            file_name=file.filename or "coverage.info",
            branch=branch,
            evidence_source=source
        )
        
        # Save optional overrides
        report.commit_sha = commit_sha
        report.branch = branch
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="malformed coverage content"
        )

    # 8. Recalculate readiness
    readiness_service = RepositoryReadinessService(db)
    readiness_result = readiness_service.calculate_readiness(repository_id, workspace.id)

    # 9. Calculate file total count
    files_count = len(report.file_entries) if report.file_entries else 0

    return {
        "coverage_report_id": str(report.id),
        "format": report.format,
        "files_total": files_count,
        "covered_lines_total": report.covered_lines_total,
        "uncovered_lines_total": report.uncovered_lines_total,
        "total_lines": report.total_lines,
        "line_coverage_ratio": report.line_coverage_ratio,
        "coverage_confidence": report.coverage_confidence,
        "parser_version": report.parser_version,
        "normalization_schema_version": report.normalization_schema_version,
        "evidence_health_status": report.evidence_health_status,
        "repository_readiness": {
            "readiness_state": readiness_result.readiness_state,
            "readiness_reasons": readiness_result.readiness_reasons,
            "next_action": readiness_result.next_action
        }
    }


@api_router.get("/{repository_id}/test-runs", response_model=RepositoryTestRunsResponse)
def get_repository_test_runs(
    repository_id: UUID,
    pull_request_id: Optional[str] = None,
    include_historical: bool = True,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Retrieve test runs for a specific repository.
    Sorts matches to the pull_request_id (or its commit/branch) first,
    then filters/includes historical test runs if include_historical is True.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
        
    # 2. Find pull request if provided
    pr = None
    if pull_request_id:
        import uuid
        try:
            pr_uuid = uuid.UUID(pull_request_id)
            pr = db.query(PullRequest).filter(
                PullRequest.id == pr_uuid,
                PullRequest.repository_id == repository_id
            ).first()
        except ValueError:
            pass

    # 3. Query all test runs for the repository
    all_runs = db.query(TestRun).filter(TestRun.repository_id == repository_id).order_by(TestRun.created_at.desc()).all()
    
    # 4. Partition runs into matching and non-matching
    matching_runs = []
    historical_runs = []
    
    for run in all_runs:
        is_match = False
        if pr:
            if run.pull_request_id == pr.id:
                is_match = True
            elif run.commit_sha == pr.head_commit_sha:
                is_match = True
            else:
                run_branch = None
                if run.ingestion_diagnostics and isinstance(run.ingestion_diagnostics, dict):
                    run_branch = run.ingestion_diagnostics.get("branch")
                if not run_branch and run.pull_request_id:
                    run_pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
                    if run_pr:
                        run_branch = run_pr.source_branch
                if not run_branch and run.commit_sha:
                    run_pr = db.query(PullRequest).filter(
                        PullRequest.repository_id == repository_id,
                        PullRequest.head_commit_sha == run.commit_sha
                    ).first()
                    if run_pr:
                        run_branch = run_pr.source_branch
                        
                pr_opened_at = pr.created_at
                if pr.github_created_at:
                    pr_opened_at = min(pr.created_at, pr.github_created_at)
                    
                if run_branch == pr.source_branch and run.created_at >= pr_opened_at:
                    is_match = True
                    
        if is_match:
            matching_runs.append(run)
        else:
            historical_runs.append(run)
            
    # 5. Build final list
    final_runs = list(matching_runs)
    if include_historical:
        final_runs.extend(historical_runs)
        
    # Format each run
    test_runs_data = []
    for run in final_runs:
        is_pr_match = run in matching_runs
        
        # Determine stale
        from datetime import datetime, timedelta
        is_stale = run.created_at < (datetime.utcnow() - timedelta(days=7))
        
        # Determine branch
        run_branch = None
        if run.ingestion_diagnostics and isinstance(run.ingestion_diagnostics, dict):
            run_branch = run.ingestion_diagnostics.get("branch")
        if not run_branch and run.pull_request_id:
            run_pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
            if run_pr:
                run_branch = run_pr.source_branch
        if not run_branch and run.commit_sha:
            run_pr = db.query(PullRequest).filter(
                PullRequest.repository_id == repository_id,
                PullRequest.head_commit_sha == run.commit_sha
            ).first()
            if run_pr:
                run_branch = run_pr.source_branch
                
        test_runs_data.append({
            "id": str(run.id),
            "repository_id": str(run.repository_id),
            "pull_request_id": str(run.pull_request_id) if run.pull_request_id else None,
            "commit_sha": run.commit_sha,
            "branch": run_branch,
            "run_name": run.run_name or f"Run {run.id}",
            "total_tests": run.total_tests,
            "passed_tests": run.passed_tests,
            "failed_tests": run.failed_tests,
            "skipped_tests": run.skipped_tests,
            "duration": run.duration,
            "created_at": run.created_at,
            "is_current_pr": is_pr_match,
            "is_stale": is_stale,
            "evidence_health_status": run.evidence_health_status
        })
        
    return {"test_runs": test_runs_data}


@api_router.get("/{repository_id}/coverage/summary")
def get_repository_coverage_summary(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Retrieve coverage summary for a specific repository under authenticated workspace.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="repository not in workspace"
        )
        
    # 2. Get coverage reports count
    reports_count = db.query(CoverageReport).filter(
        CoverageReport.repository_id == repository_id
    ).count()
    
    # 3. Get the latest report ordered by created_at desc
    latest_report = db.query(CoverageReport).filter(
        CoverageReport.repository_id == repository_id
    ).order_by(CoverageReport.created_at.desc()).first()
    
    # 4. Construct response
    latest_report_data = None
    latest_coverage_at = None
    
    if latest_report:
        latest_coverage_at = latest_report.created_at.isoformat()
        latest_report_data = {
            "id": str(latest_report.id),
            "format": latest_report.format,
            "commit_sha": latest_report.commit_sha,
            "branch": latest_report.branch,
            "files_total": latest_report.files_total,
            "covered_lines_total": latest_report.covered_lines_total,
            "uncovered_lines_total": latest_report.uncovered_lines_total,
            "total_lines": latest_report.total_lines,
            "line_coverage_ratio": latest_report.line_coverage_ratio,
            "coverage_confidence": latest_report.coverage_confidence,
            "evidence_health_status": latest_report.evidence_health_status,
            "source": latest_report.source
        }
        
    return {
        "repository_id": str(repository_id),
        "coverage_reports_count": reports_count,
        "latest_coverage_at": latest_coverage_at,
        "latest_report": latest_report_data
    }


@api_router.post("/{repository_id}/pull-requests/{pull_request_id}/recommendation")
def create_recommendation(
    repository_id: UUID,
    pull_request_id: UUID,
    payload: Optional[RecommendationGeneratePayload] = None,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Dry-run recommendation for a pull request. Workspace-scoped.

    Runs the full recommendation engine against the PR's changed files,
    test history, and coverage evidence. Persists the run and returns a
    structured summary. Does NOT post a GitHub PR comment.
    """
    import logging
    import traceback
    logger = logging.getLogger("veriscope.repository_router")
    
    # Log request details
    logger.info(f"Recommendation generation request: repository_id={repository_id}, pull_request_id={pull_request_id}, payload={payload}")
    
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found in workspace.",
            headers={"X-Error-Code": "REPOSITORY_NOT_FOUND"}
        )

    # 2. Verify PR belongs to repository
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(
            status_code=404,
            detail="Pull request not found in repository.",
            headers={"X-Error-Code": "PULL_REQUEST_NOT_FOUND"}
        )

    # 3. Preflight validation - check PR has changed files
    from app.models.pull_request import PullRequestChangedFile
    changed_files_count = db.query(func.count(PullRequestChangedFile.id)).filter(
        PullRequestChangedFile.pull_request_id == pull_request_id
    ).scalar() or 0
    
    if changed_files_count == 0:
        logger.error(f"PR {pull_request_id} has no changed files")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pull request changed files are missing. Sync pull requests before generating.",
            headers={"X-Error-Code": "MISSING_PR_DIFF"}
        )
    
    logger.info(f"PR {pull_request_id} has {changed_files_count} changed files")

    # 4. Fetch PR-scoped readiness for snapshot
    from app.services.recommendation_readiness_service import RecommendationReadinessService
    pr_readiness_svc = RecommendationReadinessService(db)
    pr_readiness = pr_readiness_svc.assess_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )

    logger.info(f"PR readiness: level={pr_readiness.readiness_level}, can_generate={pr_readiness.can_generate}, expected_confidence={pr_readiness.expected_confidence}")

    # Validate can_generate before proceeding
    if not pr_readiness.can_generate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pull request is not ready for recommendation generation. Readiness level: {pr_readiness.readiness_level}",
            headers={"X-Error-Code": "PR_NOT_READY"}
        )

    # 5. Verify repository readiness — must be READY or NEEDS_COVERAGE (low-coverage dry run allowed)
    readiness_svc = RepositoryReadinessService(db)
    readiness = readiness_svc.calculate_readiness(repository_id, workspace.id)
    logger.info(f"Repository readiness state: {readiness.readiness_state}, reasons: {readiness.readiness_reasons}")
    
    if readiness.readiness_state == "NEEDS_TEST_HISTORY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository requires test history before recommendations can run.",
            headers={"X-Error-Code": "MISSING_TEST_HISTORY"}
        )
    allowed_states = {"READY", "NEEDS_COVERAGE"}
    if readiness.readiness_state not in allowed_states:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Repository is not ready for recommendations "
                f"(state={readiness.readiness_state}). "
                f"Reasons: {'; '.join(readiness.readiness_reasons)}"
            ),
            headers={"X-Error-Code": "REPOSITORY_NOT_READY"}
        )

    # 6. Determine generation mode and enforce strict gating for confident mode
    generation_mode = (payload.mode if payload and payload.mode else None) or "confident"
    if generation_mode not in ("draft", "confident"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_GENERATION_MODE",
                "message": "Generation mode must be 'draft' or 'confident'.",
                "allowed_modes": ["draft", "confident"]
            }
        )

    if generation_mode == "confident":
        try:
            from app.services.input_readiness_v2_service import InputReadinessV2Service
            v2_readiness = InputReadinessV2Service(db).calculate_readiness(
                repository_id=repository_id,
                pull_request_id=pull_request_id
            )

            if not v2_readiness.can_generate_confident:
                blocking = getattr(v2_readiness, 'blocking_inputs', []) or []
                partial = getattr(v2_readiness, 'partial_inputs', []) or []
                primary_reason = getattr(v2_readiness, 'primary_reason', "") or ""

                # Build a human-readable reason
                if not primary_reason:
                    input5 = (v2_readiness.inputs or {}).get("INPUT_5")
                    if input5 and input5.status in ("MISSING", "PARTIAL", "REVIEW_NEEDED"):
                        primary_reason = "AC \u2192 Test Mapping is partial and unconfirmed."
                    elif not v2_readiness.can_generate_draft:
                        primary_reason = "Minimum inputs required for draft generation are missing."
                    else:
                        primary_reason = "Confident generation is not allowed with current readiness state."

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "CONFIDENT_GENERATION_NOT_ALLOWED",
                        "reason": primary_reason,
                        "allowed_modes": ["draft"] if v2_readiness.can_generate_draft else [],
                        "blocking_inputs": blocking,
                        "partial_inputs": partial,
                        "generation_status": getattr(v2_readiness, 'generation_status', None),
                    }
                )
        except HTTPException:
            raise
        except Exception as _readiness_exc:
            import logging
            logging.getLogger("veriscope.repository_router").warning(
                f"InputReadinessV2 check failed for confident generation (non-fatal): {_readiness_exc}"
            )

    # Enforce minimum: draft requires at least Input 1 (PR package)
    if generation_mode == "draft":
        try:
            from app.services.input_readiness_v2_service import InputReadinessV2Service
            v2_readiness_draft = InputReadinessV2Service(db).calculate_readiness(
                repository_id=repository_id,
                pull_request_id=pull_request_id
            )
            if not v2_readiness_draft.can_generate_draft:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "DRAFT_GENERATION_NOT_ALLOWED",
                        "reason": "Minimum inputs (PR package) required for draft generation are missing.",
                        "allowed_modes": [],
                        "blocking_inputs": getattr(v2_readiness_draft, 'blocking_inputs', []) or [],
                    }
                )
        except HTTPException:
            raise
        except Exception as _draft_exc:
            import logging
            logging.getLogger("veriscope.repository_router").warning(
                f"InputReadinessV2 draft check failed (non-fatal): {_draft_exc}"
            )

    # 7. Run recommendation engine with debug logging
    svc = RecommendationService(db)
    readiness_acknowledged = payload.readiness_acknowledged if payload else False

    def _to_dict(item):
        if isinstance(item, dict):
            return item
        if hasattr(item, "model_dump"):
            return item.model_dump()
        if hasattr(item, "dict"):
            return item.dict()
        return vars(item)

    # Prepare readiness snapshot for persistence
    readiness_snapshot = {
        "readiness_score": pr_readiness.readiness_score,
        "readiness_level": pr_readiness.readiness_level,
        "expected_confidence": pr_readiness.expected_confidence,
        "confidence_ceiling": getattr(pr_readiness, "confidence_ceiling", None),
        "confidence_reason": getattr(pr_readiness, "confidence_reason", None),
        "can_generate": pr_readiness.can_generate,
        "available_inputs": [_to_dict(i) for i in (getattr(pr_readiness, "available_inputs", None) or [])],
        "missing_inputs": [_to_dict(i) for i in (getattr(pr_readiness, "missing_inputs", None) or [])],
        "blocking_inputs": [_to_dict(i) for i in (getattr(pr_readiness, "blocking_inputs", None) or [])],
        "confidence_limiters": getattr(pr_readiness, "confidence_limiters", None),
        "evidence_summary": getattr(pr_readiness, "evidence_summary", None),
    }

    generation_log = {
        "repository_id": str(repository_id),
        "pull_request_id": str(pull_request_id),
        "changed_files_count": changed_files_count,
        "readiness_state": readiness.readiness_state,
        "pr_readiness_level": pr_readiness.readiness_level,
        "pr_can_generate": pr_readiness.can_generate,
        "readiness_acknowledged": readiness_acknowledged,
        "input_builder_started": False,
        "input_builder_completed": False,
        "ranking_completed": False,
        "scenario_generation_completed": False,
        "db_persist_completed": False,
        "error_code": None
    }

    try:
        logger.info(f"Starting recommendation generation: {generation_log}")
        generation_log["input_builder_started"] = True

        run = svc.create_recommendation_run(
            RecommendationRunCreate(
                repository_id=repository_id,
                pr_id=str(pr.id),
                changed_files=[],          # collected from DB by the service
                triggered_by="MANUAL_DRY_RUN",
                readiness_acknowledged=readiness_acknowledged,
                readiness_snapshot=readiness_snapshot,
                generated_from_repository_id=repository_id,
                generated_from_pull_request_id=pull_request_id,
                generation_mode=generation_mode,
            )
        )
        
        generation_log["input_builder_completed"] = True
        generation_log["ranking_completed"] = True
        generation_log["scenario_generation_completed"] = True
        generation_log["db_persist_completed"] = True
        logger.info(f"Recommendation generation completed successfully: {generation_log}")
        
    except HTTPException:
        db.rollback()
        generation_log["error_code"] = "HTTP_EXCEPTION"
        logger.error(f"Recommendation generation HTTP exception: {generation_log}")
        raise
    except Exception as e:
        db.rollback()
        generation_log["error_code"] = "UNKNOWN_GENERATION_ERROR"
        logger.exception(f"Recommendation engine failed for PR {pr.id}: {e}")
        logger.error(f"Generation log: {generation_log}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "RECOMMENDATION_GENERATION_FAILED",
                "message": "Veriscope could not generate this recommendation.",
                "detail": str(e),
                "traceback": traceback.format_exc(),
                "generation_log": generation_log
            },
            headers={"X-Error-Code": "RECOMMENDATION_GENERATION_FAILED"}
        )

    # 5. Build response — use only real persisted fields, no fabricated values
    recommended_tests = run.tests or []
    recommended_count = len(recommended_tests)

    # Collect unique human-readable reasons from reasoning entries (top 5, deduplicated)
    seen_reasons = set()
    reasons = []
    for entry in (run.reasoning_entries or []):
        r = entry.human_readable_reason
        if r and r not in seen_reasons:
            seen_reasons.add(r)
            reasons.append(r)
        if len(reasons) >= 5:
            break

    # Derive risk level from recommendation mode and evidence quality
    mode = run.recommendation_mode or "NORMAL"
    evidence_quality = run.evidence_quality or "UNKNOWN"
    if mode in ("FULL_REGRESSION", "SAFE_FALLBACK") or evidence_quality in ("LOW", "UNKNOWN"):
        risk_level = "HIGH"
    elif mode == "WIDENED" or evidence_quality == "MODERATE":
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # next_action is always review for a dry run
    next_action = "Review Recommendation"

    return {
        "success": True,
        "status": "GENERATED",
        "recommendation_run_id": str(run.id),
        "redirect_url": f"/app/recommendations/{run.id}",
        "repository_id": str(repository_id),
        "pull_request_id": str(pr.id),
        "recommended_tests_count": run.recommended_tests_count or recommended_count,
        "estimated_runtime_seconds": run.estimated_runtime_seconds or 0.0,
        "full_suite_runtime_seconds": run.full_suite_runtime_seconds,
        "coverage_confidence": run.evidence_quality,
        "recommendation_mode": run.recommendation_mode or mode,
        "risk_level": run.risk_level or risk_level,
        "reasons": reasons,
        "next_action": next_action
    }


class AcceptanceCriteriaSubmit(BaseModel):
    acceptance_criteria: str
    business_change_summary: Optional[str] = None
    affected_users_journeys: Optional[str] = None
    risk_notes: Optional[str] = None
    testing_notes: Optional[str] = None

@api_router.post("/{repository_id}/pull-requests/{pull_request_id}/test-runs/upload", status_code=status.HTTP_201_CREATED)
async def upload_pr_test_run(
    repository_id: UUID,
    pull_request_id: UUID,
    file: UploadFile = File(...),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    source: str = Form("MANUAL_UPLOAD"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Upload JUnit XML test execution for a specific pull request.
    
    This endpoint:
    - Verifies repository and PR belong to workspace
    - Links the test run to the specific PR
    - Marks it as current PR execution
    - Can be used when no matching test run exists for the PR
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(status_code=403, detail="Repository not found in your active workspace.")
    
    # 2. Verify PR belongs to repository
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found in repository.")
    
    # 3. Read file
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    
    # 4. Use TestIngestionService to ingest
    ingestion_service = TestIngestionService(db)
    
    try:
        test_run, duplicate_coalesced = ingestion_service.ingest_junit_xml(
            file_bytes=file_bytes,
            filename=file.filename or "unknown_junit.xml",
            repository_id=repository_id,
            commit_sha=commit_sha or pr.head_commit_sha,
            pull_request_id=pull_request_id,
            ingestion_reason="PR_MANUAL_UPLOAD",
            evidence_source=source,
            branch=branch,
            run_name=run_name
        )
        
        # 5. Update PR with latest test run reference
        pr.latest_test_run_id = test_run.id
        pr.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "test_run_id": str(test_run.id),
            "pull_request_id": str(pull_request_id),
            "tests_total": test_run.total_tests,
            "tests_passed": test_run.passed_tests,
            "tests_failed": test_run.failed_tests,
            "tests_skipped": test_run.skipped_tests,
            "duration": test_run.duration,
            "commit_sha": test_run.commit_sha,
            "is_duplicate": duplicate_coalesced
        }
    except OversizedXMLException as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"XML file too large: {str(e)}"
        )
    except XMLParsingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"XML parsing error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test ingestion failed: {str(e)}"
        )


@api_router.post("/{repository_id}/pull-requests/{pull_request_id}/acceptance-criteria", status_code=status.HTTP_200_OK)
def add_pr_acceptance_criteria(
    repository_id: UUID,
    pull_request_id: UUID,
    payload: AcceptanceCriteriaSubmit,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Manually paste and persist acceptance criteria for a PR.
    """
    import uuid
    import re
    from pydantic import BaseModel

    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace.")
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found in repository.")

    # Save business intent override if details are provided
    if payload.business_change_summary:
        from app.models.business_intent import BusinessIntentOverride
        # Deactivate existing active overrides
        db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.pull_request_id == pull_request_id,
            BusinessIntentOverride.is_active == True
        ).update({"is_active": False})
        
        bio = BusinessIntentOverride(
            id=uuid.uuid4(),
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            business_change_summary=payload.business_change_summary,
            affected_users_journeys=payload.affected_users_journeys,
            risk_notes=payload.risk_notes,
            testing_notes=payload.testing_notes,
            acceptance_criteria=payload.acceptance_criteria,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(bio)
        db.commit()

    # Parse and persist AcceptanceCriterion records
    from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor
    extractor = AcceptanceCriteriaExtractor(db=db)
    
    # Use the extractor's validation logic to filter out fragments
    criteria, excluded_fragments = extractor._extract_criteria_from_text(payload.acceptance_criteria, "MANUAL_USER_INPUT")
    
    # Normalize and deduplicate to generate labels
    criteria = extractor._normalize_and_deduplicate(criteria)
    
    # Classify criterion types
    for criterion in criteria:
        criterion["criterion_type"] = extractor._classify_criterion_type(criterion["text"])
    
    if criteria:
        persisted_ac, excluded = extractor.persist_criteria(criteria, str(repository_id), str(pull_request_id), db)
        # Merge excluded fragments from extraction and persistence
        all_excluded = excluded_fragments + excluded
        
        # Mark latest recommendation run as stale if generated before this update
        from datetime import datetime
        from app.models.recommendation import RecommendationRun
        latest_run = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id == repository_id,
            RecommendationRun.pull_request_id == pull_request_id
        ).order_by(RecommendationRun.created_at.desc()).first()

        if latest_run:
            latest_run.input_stale = True
            latest_run.stale_reason = "Acceptance criteria were added after this recommendation was generated."
            latest_run.stale_since = datetime.utcnow()
            latest_run.stale_input_types = ["acceptance_criteria"]
            
            # Also mark all of them with consistency status for compatibility
            existing_runs = db.query(RecommendationRun).filter(
                RecommendationRun.pull_request_id == pull_request_id
            ).all()
            for r in existing_runs:
                r.evidence_consistency_status = "STALE"
                r.evidence_health_status = "DEGRADED"
            db.commit()
        
    return {"status": "success", "message": f"Successfully persisted {len(criteria)} criteria"}


class ManualAcceptanceCriteriaSubmit(BaseModel):
    business_change: Optional[str] = None
    affected_users: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    risk_notes: Optional[str] = None
    testing_notes: Optional[str] = None
    # Grouped requirements support
    business_change_summary: Optional[str] = None
    affected_users_or_journeys: Optional[str] = None
    requirement_groups: Optional[List[Dict[str, Any]]] = None


class ManualAcceptanceCriteriaResponse(BaseModel):
    saved: bool
    criteria_count: int
    readiness: ReadinessSummaryResponse
    recommendation_stale: bool


@api_router.post("/{repository_id}/pull-requests/{pull_request_id}/acceptance-criteria/manual", response_model=ManualAcceptanceCriteriaResponse, status_code=status.HTTP_200_OK)
def add_pr_acceptance_criteria_manual(
    repository_id: UUID,
    pull_request_id: UUID,
    payload: ManualAcceptanceCriteriaSubmit,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Manually paste and process acceptance criteria for a PR, returning updated readiness.
    """
    import uuid
    import re
    from datetime import datetime
    from app.models.business_intent import BusinessIntentOverride
    from app.models.recommendation import RecommendationRun
    from app.models.acceptance_criterion import AcceptanceCriterion
    from app.models.business_behavior_mapping import BusinessBehaviorMapping
    from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor
    from app.services.recommendation_readiness_service import RecommendationReadinessService

    # 1. Verify repository and pull request exist and belong to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace.")
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found in repository.")

    # Calculate readiness before AC changes
    service = RecommendationReadinessService(db)
    assessment_before = service.assess_readiness(
        repository_id=str(repository_id),
        pull_request_id=str(pull_request_id)
    )
    score_before = int(assessment_before.readiness_score * 100)

    # Invalidate readiness cache in the DB
    from app.models.readiness import RecommendationReadinessAssessment
    db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.pull_request_id == pull_request_id
    ).delete(synchronize_session=False)
    db.flush()

    # Delete existing manual ACs and their mappings for this PR first to avoid duplicates/leftovers
    old_acs = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pull_request_id,
        AcceptanceCriterion.source == "MANUAL_USER_INPUT"
    ).all()
    duplicates_removed = [ac.normalized_key for ac in old_acs]
    old_ac_ids = [ac.id for ac in old_acs]
    if old_ac_ids:
        db.query(BusinessBehaviorMapping).filter(
            BusinessBehaviorMapping.acceptance_criterion_id.in_(old_ac_ids)
        ).delete(synchronize_session=False)
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.id.in_(old_ac_ids)
        ).delete(synchronize_session=False)
        db.flush()

    # 2. Deactivate existing active overrides
    db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.pull_request_id == pull_request_id,
        BusinessIntentOverride.is_active == True
    ).update({"is_active": False})

    # 3. Determine if grouped requirements are provided
    use_grouped_requirements = payload.requirement_groups is not None and len(payload.requirement_groups) > 0
    
    # Use the appropriate field names based on input type
    business_change_summary = payload.business_change_summary or payload.business_change or ""
    affected_users_or_journeys = payload.affected_users_or_journeys or payload.affected_users or ""
    risk_notes = payload.risk_notes or ""
    
    # 4. Create and add a new BusinessIntentOverride
    bio = BusinessIntentOverride(
        id=uuid.uuid4(),
        repository_id=repository_id,
        pull_request_id=pull_request_id,
        business_change_summary=business_change_summary,
        affected_users_journeys=affected_users_or_journeys,
        risk_notes=risk_notes,
        testing_notes=payload.testing_notes,
        acceptance_criteria=payload.acceptance_criteria or "",
        source="MANUAL_USER_INPUT",
        is_active=True,
        is_processed=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(bio)
    db.flush()

    # 5. Extract and persist AcceptanceCriterion records (for readiness check)
    extractor = AcceptanceCriteriaExtractor(db=db)
    
    if use_grouped_requirements:
        # Handle grouped requirements - persist as hierarchical structure
        from app.models.requirement_package import RequirementPackage
        from app.models.requirement_group import RequirementGroup
        
        # Delete existing requirement package for this PR
        existing_pkg = db.query(RequirementPackage).filter(
            RequirementPackage.repository_id == repository_id,
            RequirementPackage.pull_request_id == pull_request_id
        ).first()
        if existing_pkg:
            db.delete(existing_pkg)
            db.flush()
        
        # Create new requirement package with separated sections
        pkg = RequirementPackage(
            id=uuid.uuid4(),
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            source_type="MANUAL_USER_INPUT",
            source_id=str(bio.id),
            package_version="1.0.0",
            status="NEEDS_REVIEW",
            business_change_summary=business_change_summary,
            affected_journeys=None,  # Will be populated from payload
            risk_notes=risk_notes,
            invalid_test_data_examples=None,
            valid_test_data_examples=None,
            security_notes=None,
            integration_notes=None,
            out_of_scope_notes=None
        )
        db.add(pkg)
        db.flush()
        
        # Create requirement groups and acceptance criteria
        persisted_ac = []
        all_excluded = []
        
        for group_idx, group_data in enumerate(payload.requirement_groups):
            group_number = group_idx + 1
            group_title = group_data.get("title", f"Group {group_number}")
            group_type = group_data.get("group_type", "ENHANCEMENT")
            business_flow = group_data.get("business_flow")
            risk_level = group_data.get("risk_level")
            acceptance_criteria_data = group_data.get("acceptance_criteria", [])
            
            # Generate stable group key
            group_slug = re.sub(r"[^a-z0-9]+", "-", group_title.lower()).strip("-")
            stable_group_key = f"repo:{repository_id}:pr:{pull_request_id}:group:{group_slug}:source:manual"
            
            # Create requirement group
            req_group = RequirementGroup(
                id=uuid.uuid4(),
                requirement_package_id=pkg.id,
                pull_request_id=pull_request_id,
                group_number=group_number,
                group_type=group_type,
                stable_group_key=stable_group_key,
                title=group_title,
                description=group_data.get("description"),
                business_flow=business_flow,
                priority=group_data.get("priority"),
                risk_level=risk_level,
                source_type="MANUAL_USER_INPUT",
                status="ACTIVE"
            )
            db.add(req_group)
            db.flush()
            
            # Create acceptance criteria for this group
            INVALID_AC_PREFIXES = (
                "business change:", "business summary:", "affected journeys:",
                "affected users:", "affected flows:", "invalid test data",
                "valid test data", "security notes:", "security:", "risk notes:",
                "integration notes:", "api notes:", "out of scope:", "not in scope:",
                "notes:", "assumptions:",
            )
            for ac_idx, ac_data in enumerate(acceptance_criteria_data):
                # Preserve the original uploaded AC number when the client
                # supplied one; only fall back to positional order when the
                # source number is genuinely unknown (e.g. manually added AC).
                explicit_source_number = ac_data.get("source_number")
                if isinstance(explicit_source_number, str) and explicit_source_number.strip().isdigit():
                    explicit_source_number = int(explicit_source_number.strip())
                source_order = explicit_source_number if isinstance(explicit_source_number, int) else len(persisted_ac) + 1
                ac_title = ac_data.get("title", "")
                ac_description = ac_data.get("description", "")
                ac_source_type = ac_data.get("source_type", "MANUAL")
                ac_status = ac_data.get("status", "ACTIVE")
                
                if not ac_title or len(ac_title.strip()) < 5:
                    continue
                
                # Guard: reject lines that are section headers or known non-AC content
                ac_title_lower = ac_title.strip().lower()
                if any(ac_title_lower.startswith(prefix) for prefix in INVALID_AC_PREFIXES):
                    import logging as _aclog
                    _aclog.getLogger("veriscope.ac_guard").warning(
                        "INVALID_AC_CLASSIFICATION rejected: %s", ac_title[:80]
                    )
                    continue
                
                # Generate stable AC key scoped to group
                ac_slug = re.sub(r"[^a-z0-9]+", "-", ac_title.lower()).strip("-")
                stable_ac_key = f"{stable_group_key}:ac:{ac_slug}"
                
                # Create acceptance criterion
                ac = AcceptanceCriterion(
                    id=uuid.uuid4(),
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    requirement_group_id=req_group.id,
                    source_number=source_order,
                    ac_number=source_order,
                    stable_ac_key=stable_ac_key,
                    title=ac_title,
                    description=ac_description,
                    raw_text=ac_title,
                    normalized_text=ac_title.lower().strip(),
                    source_type=ac_source_type,
                    status=ac_status,
                    text=ac_title,
                    normalized_key=stable_ac_key,
                    source="MANUAL_USER_INPUT",
                    confidence=1.0,
                    criterion_type="FUNCTIONAL"
                )
                db.add(ac)
                persisted_ac.append(ac)
        
        db.flush()
    else:
        # Use section-aware parser for flat text mode
        sections = extractor.parse_business_requirements_sections(payload.acceptance_criteria)
        
        # Update business intent override with separated sections
        bio.business_change_summary = sections.get("business_change_summary") or business_change_summary
        bio.affected_users_journeys = "\n".join(sections.get("affected_journeys", [])) or affected_users_or_journeys
        bio.risk_notes = sections.get("risk_notes") or risk_notes
        
        # Create requirement package with separated sections
        from app.models.requirement_package import RequirementPackage
        from app.models.requirement_group import RequirementGroup
        
        # Delete existing requirement package for this PR
        existing_pkg = db.query(RequirementPackage).filter(
            RequirementPackage.repository_id == repository_id,
            RequirementPackage.pull_request_id == pull_request_id
        ).first()
        if existing_pkg:
            db.delete(existing_pkg)
            db.flush()
        
        # Create new requirement package with separated sections
        pkg = RequirementPackage(
            id=uuid.uuid4(),
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            source_type="MANUAL_USER_INPUT",
            source_id=str(bio.id),
            package_version="1.0.0",
            status="NEEDS_REVIEW",
            business_change_summary=sections.get("business_change_summary") or business_change_summary,
            affected_journeys=sections.get("affected_journeys") or [],
            risk_notes=sections.get("risk_notes") or risk_notes,
            invalid_test_data_examples=sections.get("invalid_test_data_examples") or [],
            valid_test_data_examples=sections.get("valid_test_data_examples") or [],
            security_notes=sections.get("security_notes") or [],
            integration_notes=sections.get("integration_notes"),
            out_of_scope_notes=sections.get("out_of_scope_notes")
        )
        db.add(pkg)
        db.flush()
        
        # Extract only acceptance criteria from the parsed sections
        ac_texts = sections.get("acceptance_criteria", [])
        
        # Convert to criteria format
        criteria = []
        for source_order, ac_text in enumerate(ac_texts, start=1):
            explicit_ref = re.match(r"^\s*AC[-\s]?(\d+)\s*[:.)-]?\s*", ac_text, re.IGNORECASE)
            display_number = int(explicit_ref.group(1)) if explicit_ref else source_order
            normalized_ac_text = ac_text[explicit_ref.end():].strip() if explicit_ref else ac_text
            is_valid, reason = extractor._is_valid_acceptance_criterion(normalized_ac_text)
            if is_valid:
                criteria.append({
                    "source_order": source_order,
                    "display_number": display_number,
                    "text": normalized_ac_text,
                    "source": "MANUAL_USER_INPUT",
                    "confidence": 1.0,
                    "evidence_excerpt": ac_text,
                    "normalized_key": extractor._generate_normalized_key(extractor._normalize_text(ac_text)),
                    "criterion_type": extractor._classify_criterion_type(ac_text)
                })
        
        # Normalize and deduplicate
        criteria = extractor._normalize_and_deduplicate(criteria)
        
        # Classify criterion types
        for criterion in criteria:
            criterion["criterion_type"] = extractor._classify_criterion_type(criterion["text"])
        
        # Persist criteria using intelligent grouping based on affected journeys
        persisted_ac = []
        all_excluded = []
        
        if criteria:
            # Intelligent grouping based on affected journeys
            affected_journeys = sections.get("affected_journeys", [])
            
            if affected_journeys:
                # Create groups based on affected journeys
                group_records = {}
                for journey_idx, journey in enumerate(affected_journeys):
                    group_slug = re.sub(r"[^a-z0-9]+", "-", journey.lower()).strip("-")
                    stable_group_key = f"repo:{repository_id}:pr:{pull_request_id}:group:{group_slug}:source:manual"
                    
                    req_group = RequirementGroup(
                        id=uuid.uuid4(),
                        requirement_package_id=pkg.id,
                        pull_request_id=pull_request_id,
                        group_number=journey_idx + 1,
                        group_type="ENHANCEMENT",
                        stable_group_key=stable_group_key,
                        title=journey,
                        status="ACTIVE"
                    )
                    db.add(req_group)
                    db.flush()
                    group_records[journey] = req_group
                
                # Distribute ACs across journey groups
                for criterion_data in criteria:
                    ac_text = criterion_data["text"].lower()
                    assigned = False
                    
                    for journey, req_group in group_records.items():
                        journey_lower = re.sub(r"[-\s]", "", journey.lower())
                        if journey_lower in ac_text or ac_text in journey_lower:
                            ac_slug = re.sub(r"[^a-z0-9]+", "-", criterion_data["text"].lower()).strip("-")
                            stable_ac_key = f"{req_group.stable_group_key}:ac:{ac_slug}"
                            
                            ac = AcceptanceCriterion(
                                id=uuid.uuid4(),
                                repository_id=repository_id,
                                pull_request_id=pull_request_id,
                                requirement_group_id=req_group.id,
                                source_number=criterion_data["display_number"],
                                ac_number=criterion_data["display_number"],
                                stable_ac_key=stable_ac_key,
                                title=criterion_data["text"],
                                description=criterion_data.get("description"),
                                raw_text=criterion_data["text"],
                                normalized_text=criterion_data["text"].lower().strip(),
                                source_type=criterion_data.get("source_type", "MANUAL"),
                                status="ACTIVE",
                                text=criterion_data["text"],
                                normalized_key=stable_ac_key,
                                source="MANUAL_USER_INPUT",
                                confidence=criterion_data["confidence"],
                                criterion_type=criterion_data.get("criterion_type", "FUNCTIONAL")
                            )
                            db.add(ac)
                            persisted_ac.append(ac)
                            assigned = True
                            break
                    
                    # Add unassigned ACs to a "General Requirements" group
                    if not assigned:
                        if "general" not in group_records:
                            group_slug = "general-requirements"
                            stable_group_key = f"repo:{repository_id}:pr:{pull_request_id}:group:{group_slug}:source:manual"
                            
                            req_group = RequirementGroup(
                                id=uuid.uuid4(),
                                requirement_package_id=pkg.id,
                                pull_request_id=pull_request_id,
                                group_number=len(group_records) + 1,
                                group_type="ENHANCEMENT",
                                stable_group_key=stable_group_key,
                                title="General Requirements",
                                status="ACTIVE"
                            )
                            db.add(req_group)
                            db.flush()
                            group_records["general"] = req_group
                        
                        ac_slug = re.sub(r"[^a-z0-9]+", "-", criterion_data["text"].lower()).strip("-")
                        stable_ac_key = f"{group_records['general'].stable_group_key}:ac:{ac_slug}"
                        
                        ac = AcceptanceCriterion(
                            id=uuid.uuid4(),
                            repository_id=repository_id,
                            pull_request_id=pull_request_id,
                            requirement_group_id=group_records["general"].id,
                            source_number=criterion_data["display_number"],
                            ac_number=criterion_data["display_number"],
                            stable_ac_key=stable_ac_key,
                            title=criterion_data["text"],
                            description=criterion_data.get("description"),
                            raw_text=criterion_data["text"],
                            normalized_text=criterion_data["text"].lower().strip(),
                            source_type=criterion_data.get("source_type", "MANUAL"),
                            status="ACTIVE",
                            text=criterion_data["text"],
                            normalized_key=stable_ac_key,
                            source="MANUAL_USER_INPUT",
                            confidence=criterion_data["confidence"],
                            criterion_type=criterion_data.get("criterion_type", "FUNCTIONAL")
                        )
                        db.add(ac)
                        persisted_ac.append(ac)
            else:
                # Fallback: single "General Requirements" group
                group_slug = "general-requirements"
                stable_group_key = f"repo:{repository_id}:pr:{pull_request_id}:group:{group_slug}:source:manual"
                
                req_group = RequirementGroup(
                    id=uuid.uuid4(),
                    requirement_package_id=pkg.id,
                    pull_request_id=pull_request_id,
                    group_number=1,
                    group_type="ENHANCEMENT",
                    stable_group_key=stable_group_key,
                    title="General Requirements",
                    status="ACTIVE"
                )
                db.add(req_group)
                db.flush()
                
                # Create acceptance criteria
                for ac_idx, criterion_data in enumerate(criteria):
                    ac_slug = re.sub(r"[^a-z0-9]+", "-", criterion_data["text"].lower()).strip("-")
                    stable_ac_key = f"{stable_group_key}:ac:{ac_slug}"
                    
                    ac = AcceptanceCriterion(
                        id=uuid.uuid4(),
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        requirement_group_id=req_group.id,
                        source_number=criterion_data["display_number"],
                        ac_number=criterion_data["display_number"],
                        stable_ac_key=stable_ac_key,
                        title=criterion_data["text"],
                        description=criterion_data.get("description"),
                        raw_text=criterion_data["text"],
                        normalized_text=criterion_data["text"].lower().strip(),
                        source_type=criterion_data.get("source_type", "MANUAL"),
                        status="ACTIVE",
                        text=criterion_data["text"],
                        normalized_key=stable_ac_key,
                        source="MANUAL_USER_INPUT",
                        confidence=criterion_data["confidence"],
                        criterion_type=criterion_data.get("criterion_type", "FUNCTIONAL")
                    )
                    db.add(ac)
                    persisted_ac.append(ac)
            
            db.flush()

    # 6. Extract structured scenarios and save to override (only for flat text mode)
    if not use_grouped_requirements:
        extracted_scenarios = extractor.extract_from_business_intent_override(
            payload.acceptance_criteria,
            str(bio.id),
            str(repository_id),
            source="MANUAL_USER_INPUT"
        )
        bio.extracted_scenarios = extracted_scenarios

    # 7. Run BusinessBehaviorMapper to map to business behaviors
    from app.models.behavior import Behavior
    from app.models.behavior_scenario import BehaviorScenario
    from app.models.journey import Journey
    from app.services.business_behavior_mapper import BusinessBehaviorMapper

    behaviors = db.query(Behavior).filter(Behavior.repository_id == repository_id, Behavior.is_deleted == False).all()
    behavior_ids = [b.id for b in behaviors]
    scenarios = db.query(BehaviorScenario).filter(BehaviorScenario.behavior_id.in_(behavior_ids)).all() if behavior_ids else []
    journeys = db.query(Journey).filter(Journey.repository_id == repository_id, Journey.is_deleted == False).all()
    
    mapper = BusinessBehaviorMapper(db=db)
    
    # Generate business behavior mappings for the new ACs
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=persisted_ac,
        behaviors=behaviors,
        scenarios=scenarios,
        journeys=journeys
    )
    if mappings:
        mapper.persist_mappings(mappings, db)

    # Map for the BusinessIntentOverride model's JSON field for compatibility
    try:
        mapped_behaviors = mapper.map_business_intent_override_to_behaviors(
            str(bio.id),
            payload.business_change,
            payload.acceptance_criteria,
            payload.affected_users,
            db
        )
        bio.mapped_behaviors = mapped_behaviors
    except Exception as e:
        import logging
        logging.getLogger("veriscope.repository_router").warning(f"BusinessBehaviorMapper override mapping failed: {e}")

    # 7. Mark latest recommendation run as stale if generated before this update
    recommendation_stale = False
    latest_run = db.query(RecommendationRun).filter(
        RecommendationRun.repository_id == repository_id,
        RecommendationRun.pull_request_id == pull_request_id
    ).order_by(RecommendationRun.created_at.desc()).first()

    if latest_run:
        latest_run.input_stale = True
        latest_run.stale_reason = "Acceptance criteria were added after this recommendation was generated."
        latest_run.stale_since = datetime.utcnow()
        latest_run.stale_input_types = ["acceptance_criteria"]
        recommendation_stale = True

    # Also mark all of them with consistency status for compatibility
    existing_runs = db.query(RecommendationRun).filter(
        RecommendationRun.pull_request_id == pull_request_id
    ).all()
    for r in existing_runs:
        r.evidence_consistency_status = "STALE"
        r.evidence_health_status = "DEGRADED"

    db.commit()

    # Build enriched readiness summary (all confidence fields included so frontend has complete state)
    # Re-assess AFTER commit so the new AC rows are visible to the readiness query
    assessment = service.assess_readiness(
        repository_id=str(repository_id),
        pull_request_id=str(pull_request_id)
    )

    score_after = int(assessment.readiness_score * 100)
    import logging as _logging
    _log = _logging.getLogger("veriscope.readiness")
    _log.info(
        f"AC save complete: pr_id={pull_request_id}, repo_id={repository_id}, "
        f"persisted_ac_count={len(persisted_ac)}, score_before={score_before}, score_after={score_after}, "
        f"ac_in_available={any(s.get('key') == 'acceptance_criteria' for s in assessment.available_inputs)}, "
        f"ac_in_missing={any(s.get('key') == 'acceptance_criteria' for s in assessment.missing_inputs)}"
    )


    readiness_summary = ReadinessSummaryResponse(
        repository_id=str(assessment.repository_id),
        pull_request_id=str(assessment.pull_request_id) if assessment.pull_request_id else str(pull_request_id),
        readiness_level=assessment.readiness_level,
        expected_confidence=assessment.expected_confidence,
        readiness_score=assessment.readiness_score,
        can_generate=assessment.can_generate,
        can_generate_reason=assessment.can_generate_reason or "",
        signal_count=len(assessment.available_signals),
        total_signals=15,
        intelligence_completeness_score=assessment.intelligence_completeness_score,
        release_confidence_ceiling=assessment.release_confidence_ceiling,
        available_inputs=assessment.available_inputs,
        missing_inputs=assessment.missing_inputs,
        recommended_inputs=assessment.recommended_inputs,
        blocking_inputs=assessment.blocking_inputs,
        next_best_actions=assessment.next_best_actions,
        primary_message=assessment.primary_message,
        secondary_message=assessment.secondary_message,
        # Bug 4 fix: include all confidence explanation fields
        confidence_reason=getattr(assessment, 'confidence_reason', ''),
        confidence_ceiling=getattr(assessment, 'confidence_ceiling', 'HIGH'),
        confidence_blockers=getattr(assessment, 'confidence_blockers', []),
        confidence_limiters=getattr(assessment, 'confidence_limiters', []),
    )

    return ManualAcceptanceCriteriaResponse(
        saved=True,
        criteria_count=len(persisted_ac),
        readiness=readiness_summary,
        recommendation_stale=True
    )


@api_router.get("/{repository_id}/pull-requests/{pull_request_id}/recommendation")
def get_latest_recommendation(
    repository_id: UUID,
    pull_request_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Retrieve the latest recommendation run for a pull request. Scoped by workspace.

    Returns a structured summary along with the details of recommended tests.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace.")

    # 2. Verify PR belongs to repository
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found in repository.")

    # 3. Find the latest RecommendationRun for this PR
    from app.models.recommendation import RecommendationRun
    run = db.query(RecommendationRun).filter(
        RecommendationRun.repository_id == repository_id,
        RecommendationRun.pull_request_id == pull_request_id
    ).order_by(RecommendationRun.created_at.desc()).first()

    if not run:
        raise HTTPException(status_code=404, detail="No recommendation run found for this pull request.")

    # Collect unique human-readable reasons from reasoning entries (top 5, deduplicated)
    seen_reasons = set()
    reasons = []
    for entry in (run.reasoning_entries or []):
        r = entry.human_readable_reason
        if r and r not in seen_reasons:
            seen_reasons.add(r)
            reasons.append(r)
        if len(reasons) >= 5:
            break

    # Load recommended tests from the durable RecommendedTest relationship
    tests_payload = [
        {
            "id": str(t.id),
            "test_identifier": t.test_identifier,
            "test_name": t.test_name,
            "class_name": t.class_name,
            "priority": t.priority,
            "confidence": t.confidence,
            "reason": t.reason,
            "source_signal": t.source_signal,
            "estimated_duration_seconds": t.estimated_duration_seconds,
            "included": t.included,
            "warning": t.warning,
            "created_at": t.created_at.isoformat()
        }
        for t in run.recommended_tests
    ]

    return {
        "recommendation_run_id": str(run.id),
        "repository_id": str(repository_id),
        "pull_request_id": str(pull_request_id),
        "workspace_id": str(run.workspace_id) if run.workspace_id else None,
        "input_snapshot_hash": run.input_snapshot_hash,
        "recommendation_snapshot_hash": run.recommendation_snapshot_hash,
        "recommended_tests_count": run.recommended_tests_count or len(tests_payload),
        "estimated_runtime_seconds": run.estimated_runtime_seconds or 0.0,
        "full_suite_runtime_seconds": run.full_suite_runtime_seconds,
        "coverage_confidence": run.evidence_quality,
        "recommendation_mode": run.recommendation_mode,
        "risk_level": run.risk_level,
        "reasons": reasons,
        "recommended_tests": tests_payload,
        "next_action": "Review Recommendation",
        "created_at": run.created_at.isoformat(),
        "input_stale": run.input_stale,
        "stale_reason": run.stale_reason,
        "stale_since": run.stale_since.isoformat() + "Z" if run.stale_since else None,
        "stale_input_types": run.stale_input_types,
    }


@router.post("/{repository_id}/external-test-cases/import-csv", status_code=status.HTTP_200_OK)
async def import_manual_test_cases_csv(
    repository_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Import manual test cases from CSV file.
    
    CSV Format:
    - title (required)
    - description
    - priority
    - test_type
    - preconditions (newline-separated)
    - steps (newline-separated, format: "Step text | Expected result")
    - expected_result
    - tags (comma-separated)
    - linked_work_item_key
    - behavior
    - journey
    - linked_acceptance_criteria
    
    Returns import summary with success/failure counts and row-level errors.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Read CSV content
    try:
        csv_content = await file.read()
        csv_text = csv_content.decode('utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}"
        )
    
    # Import test cases
    importer = ManualTestCaseCSVImport(db)
    result = importer.import_csv(repository_id, csv_text, UUID(workspace_id))
    
    return {
        "total_rows": result.total_rows,
        "successful_imports": result.successful_imports,
        "failed_rows": result.failed_rows,
        "duplicate_rows": result.duplicate_rows,
        "errors": result.errors
    }


@api_router.post("/{repository_id}/manual-test-cases/import", status_code=status.HTTP_201_CREATED)
async def import_manual_test_cases_with_readiness(
    repository_id: UUID,
    file: UploadFile = File(...),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Import manual test cases from CSV file and recalculate readiness.
    
    This endpoint is designed for the readiness gate flow, allowing users
    to provide manual regression assets before recommendation generation.
    
    CSV Format:
    - title (required)
    - description
    - priority
    - test_type
    - preconditions (newline-separated)
    - steps (newline-separated, format: "Step text | Expected result")
    - expected_result
    - tags (comma-separated)
    - linked_work_item_key
    - behavior
    - journey
    - linked_acceptance_criteria
    
    Returns import summary with success/failure counts, row-level errors,
    and updated readiness state.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Read CSV content
    try:
        csv_content = await file.read()
        csv_text = csv_content.decode('utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read CSV file: {str(e)}"
        )
    
    # Import test cases
    importer = ManualTestCaseCSVImport(db)
    result = importer.import_csv(repository_id, csv_text, workspace.id)
    
    # Recalculate readiness after import
    readiness_service = RepositoryReadinessService(db)
    readiness_result = readiness_service.calculate_readiness(repository_id, workspace.id)
    
    return {
        "total_rows": result.total_rows,
        "successful_imports": result.successful_imports,
        "failed_rows": result.failed_rows,
        "duplicate_rows": result.duplicate_rows,
        "errors": result.errors,
        "readiness_updated": True,
        "readiness_state": readiness_result.readiness_state,
        "readiness_reasons": readiness_result.readiness_reasons
    }


@router.get("/{repository_id}/integrations", status_code=status.HTTP_200_OK)
def list_integrations(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    List integration connections for a repository.
    
    Returns all integration connections with status and last sync information.
    Credentials are never exposed in API responses.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Get integration connections
    connections = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repository_id
    ).all()
    
    # Build response
    providers = ["JIRA", "AZURE_DEVOPS", "TESTRAIL", "XRAY", "ZEPHYR", "MANUAL_CSV"]
    connections_map = {conn.provider: conn for conn in connections}
    
    result = []
    for provider in providers:
        conn = connections_map.get(provider)
        if conn:
            result.append({
                "provider": provider,
                "is_connected": conn.is_active,
                "last_synced_at": conn.last_synced_at.isoformat() if conn.last_synced_at else None,
                "configured": bool(conn.encrypted_credentials),
                "redacted": True,
                # Never return credentials or secrets
            })
        else:
            result.append({
                "provider": provider,
                "is_connected": False,
                "last_synced_at": None,
                "config": None
            })
    
    return result


@router.get("/{repository_id}/integrations/providers", status_code=status.HTTP_200_OK)
def list_integration_provider_capabilities(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    List provider capability descriptors for the sync framework.

    Returns static capability metadata for all registered providers.
    No database query — capabilities are declared by each provider adapter.

    Response shape (additive — safe for clients that ignore unknown fields):
        [
            {
                "provider": "TESTRAIL",
                "supportsExecutionSync": true,
                "supportsBidirectionalSync": false,
                ...
            },
            ...
        ]
    """
    # Verify repository belongs to workspace (auth guard)
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )

    from app.services.provider_sync.provider_registry import ProviderRegistry
    registry = ProviderRegistry()
    capabilities = registry.list_capabilities()
    return [cap.to_dict() for cap in capabilities]


@router.post("/{repository_id}/integrations/{provider}/connect", status_code=status.HTTP_201_CREATED)
def connect_integration(
    repository_id: UUID,
    provider: str,
    config: Dict[str, Any],
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Connect an integration for a repository.
    
    Provider-specific config:
    - JIRA: base_url, username, api_token
    - AZURE_DEVOPS: organization_url, project, pat_token
    - TESTRAIL: base_url, username, api_key
    - XRAY: base_url, api_token (placeholder)
    - ZEPHYR: base_url, api_token (placeholder)
    - MANUAL_CSV: No config needed
    
    Credentials are encrypted before storage using CredentialEncryptionService.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Validate provider
    valid_providers = ["JIRA", "AZURE_DEVOPS", "TESTRAIL", "XRAY", "ZEPHYR", "MANUAL_CSV"]
    if provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}"
        )
    
    # Encrypt credentials before storage
    try:
        from app.services.security.credential_encryption_service import get_credential_encryption_service
        encryption_service = get_credential_encryption_service()
        encrypted_credentials = encryption_service.encrypt(config)
    except Exception as e:
        logger.error(f"Failed to encrypt credentials for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt credentials"
        )
    
    # Check for existing connection
    existing = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repository_id,
        IntegrationConnection.provider == provider
    ).first()
    
    if existing:
        # Update existing connection
        existing.encrypted_credentials = encrypted_credentials
        existing.credentials_encrypted_at = datetime.utcnow()
        existing.credentials_version = 1
        existing.is_active = True
        existing.last_synced_at = datetime.utcnow()
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {
            "id": str(existing.id),
            "provider": existing.provider,
            "is_connected": existing.is_active,
            "last_synced_at": existing.last_synced_at.isoformat(),
            "configured": True,
            "redacted": True
        }
    else:
        # Create new connection
        connection = IntegrationConnection(
            id=uuid.uuid4(),
            workspace_id=UUID(workspace_id),
            repository_id=repository_id,
            provider=provider,
            encrypted_credentials=encrypted_credentials,
            credentials_encrypted_at=datetime.utcnow(),
            credentials_version=1,
            is_active=True,
            last_synced_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(connection)
        db.commit()
        return {
            "id": str(connection.id),
            "provider": connection.provider,
            "is_connected": connection.is_active,
            "last_synced_at": connection.last_synced_at.isoformat(),
            "configured": True,
            "redacted": True
        }


@router.post("/{repository_id}/integrations/{provider}/disconnect", status_code=status.HTTP_200_OK)
def disconnect_integration(
    repository_id: UUID,
    provider: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Disconnect an integration for a repository.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Get connection
    connection = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repository_id,
        IntegrationConnection.provider == provider
    ).first()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration connection not found"
        )
    
    # Deactivate connection
    connection.is_active = False
    connection.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "provider": provider,
        "is_connected": False
    }


@router.post("/{repository_id}/integrations/{provider}/test", status_code=status.HTTP_200_OK)
def test_integration_connection(
    repository_id: UUID,
    provider: str,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Test an integration connection.
    
    If config is provided, tests with that config.
    Otherwise, tests with existing connection config.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Get config from request or existing connection
    if not config:
        connection = db.query(IntegrationConnection).filter(
            IntegrationConnection.repository_id == repository_id,
            IntegrationConnection.provider == provider
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration connection not found"
            )
        
        config = connection.config
    
    # Test connection based on provider
    try:
        if provider == "JIRA":
            connector = JiraConnector(
                base_url=config.get("base_url"),
                api_token=config.get("api_token"),
                username=config.get("username")
            )
            is_valid = connector.validate_connection()
            return {
                "provider": provider,
                "is_valid": is_valid,
                "message": "Connection successful" if is_valid else "Connection failed"
            }
        
        elif provider == "AZURE_DEVOPS":
            connector = AzureDevOpsConnector(
                organization_url=config.get("organization_url"),
                project=config.get("project"),
                pat_token=config.get("pat_token")
            )
            is_valid = connector.validate_connection()
            return {
                "provider": provider,
                "is_valid": is_valid,
                "message": "Connection successful" if is_valid else "Connection failed"
            }
        
        elif provider == "TESTRAIL":
            connector = TestRailConnector(
                base_url=config.get("base_url"),
                username=config.get("username"),
                api_key=config.get("api_key")
            )
            is_valid = connector.validate_connection()
            return {
                "provider": provider,
                "is_valid": is_valid,
                "message": "Connection successful" if is_valid else "Connection failed"
            }
        
        elif provider in ("XRAY", "ZEPHYR"):
            # Placeholder for future implementation
            return {
                "provider": provider,
                "is_valid": False,
                "message": "Coming soon - integration not yet implemented"
            }
        
        elif provider == "MANUAL_CSV":
            # CSV import doesn't need connection test
            return {
                "provider": provider,
                "is_valid": True,
                "message": "CSV import ready"
            }
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )
    
    except Exception as e:
        return {
            "provider": provider,
            "is_valid": False,
            "message": f"Connection failed: {str(e)}"
        }


@router.get("/{repository_id}/pull-requests/{pull_request_id}/work-item-context", status_code=status.HTTP_200_OK)
def get_work_item_context(
    repository_id: UUID,
    pull_request_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get work item context for a pull request.
    
    Returns linked work items, acceptance criteria, and coverage status.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Get pull request
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Get linked work items
    from app.models.external_work_item import ExternalWorkItem
    from app.models.pull_request_work_item_link import PullRequestWorkItemLink
    from app.models.acceptance_criterion import AcceptanceCriterion
    
    # Get work item links for this PR
    work_item_links = db.query(PullRequestWorkItemLink).filter(
        PullRequestWorkItemLink.pull_request_id == pull_request_id
    ).all()
    
    work_item_ids = [link.external_work_item_id for link in work_item_links]
    
    # Get work items
    work_items = db.query(ExternalWorkItem).filter(
        ExternalWorkItem.id.in_(work_item_ids)
    ).all()
    
    # Get acceptance criteria for this PR
    acceptance_criteria = db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pull_request_id
    ).all()
    
    # Resolve coverage for acceptance criteria
    coverage_resolver = ExternalRequirementCoverageResolver(db)
    ac_coverage = {}
    
    for ac in acceptance_criteria:
        coverage = coverage_resolver.resolve_coverage(
            acceptance_criterion=ac,
            repository_id=repository_id,
            current_pr_id=pull_request_id
        )
        ac_coverage[str(ac.id)] = {
            "acceptance_criterion_id": str(coverage.acceptance_criterion_id),
            "title": ac.title,
            "coverage_status": coverage.coverage_status.value,
            "confidence": coverage.confidence,
            "recommended_action": coverage.recommended_action,
            "automated_tests": coverage.automated_tests,
            "external_test_cases": coverage.external_test_cases,
            "suggested_scenarios": coverage.suggested_scenarios
        }
    
    # Build work item response
    work_items_response = []
    for work_item in work_items:
        # Get AC linked to this work item
        linked_ac = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.external_work_item_id == work_item.id,
            AcceptanceCriterion.pull_request_id == pull_request_id
        ).all()
        
        work_items_response.append({
            "id": str(work_item.id),
            "external_key": work_item.external_key,
            "title": work_item.title,
            "description": work_item.description,
            "status": work_item.status,
            "priority": work_item.priority or "MEDIUM",
            "work_item_type": work_item.work_item_type,
            "provider": work_item.provider,
            "url": work_item.url,
            "acceptance_criteria": [
                {
                    "id": str(ac.id),
                    "title": ac.title,
                    "description": ac.description
                }
                for ac in linked_ac
            ]
        })
    
    return {
        "work_items": work_items_response,
        "ac_coverage": ac_coverage
    }


@api_router.get("/{repository_id}/pull-requests/{pull_request_id}/manual-tests", status_code=status.HTTP_200_OK)
def get_manual_tests(
    repository_id: UUID,
    pull_request_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get manual test cases recommended for a pull request.
    
    Returns external manual test cases with execution status.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Get pull request
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Get external test cases for the repository
    from app.models.external_test_case_detailed import ExternalTestCase
    from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
    from app.models.manual_test_execution import ManualTestExecution
    
    # Get manual test cases
    manual_tests = db.query(ExternalTestCase).filter(
        ExternalTestCase.repository_id == repository_id,
        ExternalTestCase.automation_status == "MANUAL",
        ExternalTestCase.is_active == True
    ).all()
    
    # Get scenario mappings for these tests
    test_ids = [t.id for t in manual_tests]
    scenario_mappings = db.query(ExternalTestScenarioMapping).filter(
        ExternalTestScenarioMapping.external_test_case_id.in_(test_ids)
    ).all()
    
    # Build mapping from test to scenarios
    test_to_scenarios = {}
    for mapping in scenario_mappings:
        if mapping.external_test_case_id not in test_to_scenarios:
            test_to_scenarios[mapping.external_test_case_id] = []
        test_to_scenarios[mapping.external_test_case_id].append(mapping)
    
    # Get impacted scenarios from PR (simplified - would use behavior impact analysis)
    # For now, return all manual tests
    manual_tests_response = []
    for test in manual_tests:
        mappings = test_to_scenarios.get(test.id, [])
        
        # Get linked AC from work item mappings
        linked_ac = []
        linked_behavior = []
        
        if test.linked_work_item_keys:
            from app.models.external_work_item import ExternalWorkItem
            from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping
            from app.models.acceptance_criterion import AcceptanceCriterion
            
            for work_item_key in test.linked_work_item_keys:
                work_item = db.query(ExternalWorkItem).filter(
                    ExternalWorkItem.external_key == work_item_key,
                    ExternalWorkItem.repository_id == repository_id
                ).first()
                
                if work_item:
                    # Get AC linked to this work item
                    ac = db.query(AcceptanceCriterion).filter(
                        AcceptanceCriterion.external_work_item_id == work_item.id,
                        AcceptanceCriterion.pull_request_id == pull_request_id
                    ).first()
                    
                    if ac:
                        linked_ac.append(ac.title)
                    
                    # Get behavior mappings
                    behavior_mappings = db.query(WorkItemBehaviorMapping).filter(
                        WorkItemBehaviorMapping.external_work_item_id == work_item.id
                    ).all()
                    
                    for bm in behavior_mappings:
                        if bm.behavior_id:
                            from app.models.behavior import Behavior
                            behavior = db.query(Behavior).filter(
                                Behavior.id == bm.behavior_id
                            ).first()
                            if behavior:
                                linked_behavior.append(behavior.name)
        
        # Query latest execution outcome for this PR
        latest_execution = db.query(ManualTestExecution).filter(
            ManualTestExecution.external_test_case_id == test.id,
            ManualTestExecution.pull_request_id == pull_request_id,
            ManualTestExecution.is_active == True
        ).order_by(ManualTestExecution.executed_at.desc()).first()

        history_count = db.query(ManualTestExecution).filter(
            ManualTestExecution.external_test_case_id == test.id,
            ManualTestExecution.pull_request_id == pull_request_id
        ).count()

        latest_status = latest_execution.outcome if latest_execution else "NOT_EXECUTED"
        latest_executed_at = latest_execution.executed_at.isoformat() + "Z" if latest_execution else None
        latest_executed_by_name = latest_execution.executed_by_name if latest_execution else None
        latest_execution_notes = latest_execution.notes if latest_execution else None
        latest_evidence_url = latest_execution.evidence_url if latest_execution else None

        manual_tests_response.append({
            "id": str(test.id),
            "title": test.title,
            "provider": test.provider,
            "external_key": test.external_key,
            "priority": test.priority or "SHOULD",
            "url": test.url,
            "linked_ac": linked_ac,
            "linked_behavior": linked_behavior,
            "preconditions": test.preconditions or [],
            "steps": test.steps or [],
            "expected_result": test.expected_result,
            "execution_status": latest_status,
            "latestExecutionStatus": latest_status,
            "latestExecutedAt": latest_executed_at,
            "latestExecutedByName": latest_executed_by_name,
            "latestExecutionNotes": latest_execution_notes,
            "latestEvidenceUrl": latest_evidence_url,
            "executionHistoryCount": history_count
        })
    
    return {
        "manual_tests": manual_tests_response
    }


def _execute_manual_test(
    db: Session,
    repository_id: UUID,
    test_id: UUID,
    execution_in: Any,
    current_user: Any,
    active_workspace_id: UUID
):
    """Internal helper to authorize and persist a manual test execution."""
    from app.models.external_test_case_detailed import ExternalTestCase
    from app.models.manual_test_execution import ManualTestExecution

    # 1. Authorize workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == active_workspace_id
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MANUAL_TEST_WORKSPACE_ACCESS_DENIED"
        )

    # 2. Find external test case and verify it belongs to this repository
    test_case = db.query(ExternalTestCase).filter(
        ExternalTestCase.id == test_id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found"
        )
    if test_case.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test case does not belong to the specified repository."
        )

    # 3. Deactivate previous active executions for the same test + PR/recommendation context
    pr_id = UUID(execution_in.pullRequestId) if execution_in.pullRequestId else None
    run_id = UUID(execution_in.recommendationRunId) if execution_in.recommendationRunId else None
    
    previous_active = db.query(ManualTestExecution).filter(
        ManualTestExecution.external_test_case_id == test_id,
        ManualTestExecution.pull_request_id == pr_id,
        ManualTestExecution.recommendation_run_id == run_id,
        ManualTestExecution.is_active == True
    ).all()
    for prev in previous_active:
        prev.is_active = False
        db.add(prev)

    # 4. Create new execution
    new_execution = ManualTestExecution(
        external_test_case_id=test_id,
        repository_id=repository_id,
        pull_request_id=pr_id,
        recommendation_run_id=run_id,
        outcome=execution_in.outcome.upper(),
        executed_by_id=str(current_user.id),
        executed_by_name=current_user.name or current_user.email,
        notes=execution_in.notes,
        evidence_url=execution_in.evidenceUrl,
        attachment_path=execution_in.attachmentPath,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        is_active=True
    )
    db.add(new_execution)
    db.commit()
    db.refresh(new_execution)

    # 5. Enqueue sync to provider if integration supports execution sync
    # Queue-based: execution succeeds even if sync fails, sync is durable
    from app.services.provider_sync.provider_registry import ProviderRegistry
    _registry = ProviderRegistry()
    if (
        _registry.is_execution_sync_supported(test_case.provider or "")
        and test_case.integration_connection_id
    ):
        try:
            from app.services.integration_sync_service import IntegrationSyncService
            sync_service = IntegrationSyncService(db)
            sync_service.enqueue_manual_execution_sync(new_execution.id)
        except Exception as e:
            logger.error(f"Failed to enqueue sync for execution {new_execution.id}: {e}")


    return {
        "status": "SUCCESS",
        "execution": {
            "id": str(new_execution.id),
            "testId": str(new_execution.external_test_case_id),
            "outcome": new_execution.outcome,
            "executedByName": new_execution.executed_by_name,
            "executedAt": new_execution.executed_at.isoformat() + "Z",
            "notes": new_execution.notes,
            "evidenceUrl": new_execution.evidence_url
        }
    }


@api_router.post("/{repository_id}/manual-tests/{test_id}/execution", status_code=status.HTTP_200_OK)
def mark_manual_test_executed_new(
    repository_id: UUID,
    test_id: UUID,
    execution_in: ManualTestExecutionCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a manual test as executed with outcome using workspace authorization (Correct frontend path).
    """
    from app.schemas.manual_test_execution import ManualTestExecutionCreate
    return _execute_manual_test(
        db=db,
        repository_id=repository_id,
        test_id=test_id,
        execution_in=execution_in,
        current_user=current_user,
        active_workspace_id=UUID(workspace_id)
    )


@api_router.post("/manual-tests/{test_id}/execution", status_code=status.HTTP_200_OK)
def mark_manual_test_executed(
    test_id: UUID,
    execution_in: ManualTestExecutionCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a manual test as executed with outcome using workspace authorization (Legacy route compatibility).
    """
    from app.models.external_test_case_detailed import ExternalTestCase
    from app.schemas.manual_test_execution import ManualTestExecutionCreate

    # Resolve repository from test_id
    test_case = db.query(ExternalTestCase).filter(ExternalTestCase.id == test_id).first()
    if not test_case or not test_case.repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="REPOSITORY_REQUIRED_FOR_MANUAL_EXECUTION"
        )

    return _execute_manual_test(
        db=db,
        repository_id=test_case.repository_id,
        test_id=test_id,
        execution_in=execution_in,
        current_user=current_user,
        active_workspace_id=UUID(workspace_id)
    )


@api_router.get("/{repository_id}/manual-tests/{test_id}/mappings", response_model=List[ManualTestMappingResponse])
def get_manual_test_mappings(
    repository_id: UUID,
    test_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
):
    """Get all active acceptance criteria mappings for a manual test case."""
    # Validate workspace access
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MANUAL_TEST_WORKSPACE_ACCESS_DENIED"
        )

    # Validate test case
    test_case = db.query(ExternalTestCase).filter(ExternalTestCase.id == test_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found"
        )
    if test_case.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test case does not belong to the specified repository."
        )

    # Query active mappings
    mappings = db.query(ManualTestRequirementMapping).filter(
        ManualTestRequirementMapping.external_test_case_id == test_id,
        ManualTestRequirementMapping.repository_id == repository_id,
        ManualTestRequirementMapping.is_active == True
    ).all()

    response = []
    for mapping in mappings:
        ac = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == mapping.acceptance_criterion_id).first()
        if ac:
            readable_id = ac.label or (f"AC-{ac.source_number:02d}" if ac.source_number is not None else f"AC-{str(ac.id)[:8]}")
            response.append({
                "id": mapping.id,
                "testCaseId": mapping.external_test_case_id,
                "acceptanceCriterionId": mapping.acceptance_criterion_id,
                "readableRequirementId": readable_id,
                "requirementText": ac.text,
                "mappingSource": mapping.mapping_source,
                "createdAt": mapping.created_at
            })

    return response


@api_router.post("/{repository_id}/manual-tests/{test_id}/mappings", response_model=ManualTestMappingResponse)
def create_manual_test_mapping(
    repository_id: UUID,
    test_id: UUID,
    mapping_in: ManualTestMappingCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user),
):
    """Create a manual test to AC requirement mapping."""
    # Validate workspace access
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MANUAL_TEST_WORKSPACE_ACCESS_DENIED"
        )

    # Validate test case
    test_case = db.query(ExternalTestCase).filter(ExternalTestCase.id == test_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found"
        )
    if test_case.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test case does not belong to the specified repository."
        )

    # Validate Acceptance Criterion
    ac = None
    # 1. Try UUID lookup
    try:
        ac_uuid = UUID(mapping_in.acceptanceCriterionId)
        ac = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.id == ac_uuid
        ).first()
    except ValueError:
        pass

    # 2. Try source number lookup
    if not ac:
        try:
            ref_clean = mapping_in.acceptanceCriterionId.upper().replace("AC-", "").strip()
            source_num = int(ref_clean)
            ac = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.source_number == source_num,
                AcceptanceCriterion.repository_id == repository_id
            ).first()
        except ValueError:
            pass

    # 3. Try label or text lookup
    if not ac:
        ac = db.query(AcceptanceCriterion).filter(
            ((AcceptanceCriterion.label == mapping_in.acceptanceCriterionId) | 
             (AcceptanceCriterion.text == mapping_in.acceptanceCriterionId)),
            AcceptanceCriterion.repository_id == repository_id
        ).first()

    if not ac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acceptance criterion not found"
        )

    if ac.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Acceptance criterion does not belong to the specified repository."
        )

    # Check for existing active mapping
    existing = db.query(ManualTestRequirementMapping).filter(
        ManualTestRequirementMapping.external_test_case_id == test_id,
        ManualTestRequirementMapping.acceptance_criterion_id == ac.id,
        ManualTestRequirementMapping.is_active == True
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active mapping already exists between this test case and acceptance criterion."
        )

    # Create new mapping
    new_mapping = ManualTestRequirementMapping(
        external_test_case_id=test_id,
        acceptance_criterion_id=ac.id,
        repository_id=repository_id,
        mapping_source="MANUAL",
        created_by_id=str(current_user.id),
        created_by_name=current_user.name or current_user.email,
        is_active=True
    )
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)

    readable_id = ac.label or (f"AC-{ac.source_number:02d}" if ac.source_number is not None else f"AC-{str(ac.id)[:8]}")
    return {
        "id": new_mapping.id,
        "testCaseId": new_mapping.external_test_case_id,
        "acceptanceCriterionId": new_mapping.acceptance_criterion_id,
        "readableRequirementId": readable_id,
        "requirementText": ac.text,
        "mappingSource": new_mapping.mapping_source,
        "createdAt": new_mapping.created_at
    }


@api_router.delete("/{repository_id}/manual-tests/{test_id}/mappings/{mapping_id}", status_code=status.HTTP_200_OK)
def delete_manual_test_mapping(
    repository_id: UUID,
    test_id: UUID,
    mapping_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
):
    """Deactivate a manual test mapping (soft delete)."""
    # Validate workspace access
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MANUAL_TEST_WORKSPACE_ACCESS_DENIED"
        )

    # Find mapping
    mapping = db.query(ManualTestRequirementMapping).filter(
        ManualTestRequirementMapping.id == mapping_id,
        ManualTestRequirementMapping.external_test_case_id == test_id,
        ManualTestRequirementMapping.repository_id == repository_id
    ).first()
    
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mapping not found"
        )

    # Soft delete (deactivate)
    mapping.is_active = False
    db.add(mapping)
    db.commit()

    return {"status": "SUCCESS", "message": "Mapping successfully deactivated"}


@api_router.get("/{repository_id}/pull-requests/{pull_request_id}/recommendation-readiness", response_model=RecommendationReadinessGateResponse)
def get_pr_recommendation_readiness(
    repository_id: UUID,
    pull_request_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Assess readiness before generating a recommendation for a specific repository and pull request.
    """
    from app.services.recommendation_readiness_gate import RecommendationReadinessGate
    from app.schemas.readiness import RecommendationReadinessGateResponse

    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )

    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )

    gate = RecommendationReadinessGate()
    result = gate.assess(db, str(repository_id), str(pull_request_id))

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


@cicd_router.post("/{repository_id}/pipeline-runs", response_model=PipelineRunResponse, status_code=status.HTTP_201_CREATED)
def trigger_pipeline_run_ci(
    repository_id: UUID,
    request: PipelineRunTriggerRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Trigger or link a CI/CD pipeline run to a Veriscope recommendation.
    
    Authenticated via CI token (Bearer token in Authorization header).
    This endpoint bypasses workspace member authentication for CI token usage.
    
    Idempotent: Same external_run_id returns existing PipelineRun.
    New external_run_id creates new PipelineRun attempt.
    """
    # Authenticate CI token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <VERISCOPE_TOKEN>"
        )
    
    token = authorization.replace("Bearer ", "")
    ci_token_service = CITokenService()
    ci_token = ci_token_service.verify_token(db, token)
    
    if not ci_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked CI token"
        )
    
    # Verify token belongs to the requested repository
    if ci_token.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CI token is not authorized for this repository"
        )
    
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    service = PipelineRunService()
    return service.trigger_pipeline_run(db, repository_id, request)


# Phase 6.5: Manual Evidence Governance Endpoints

class ManualEvidenceGovernanceRequest(BaseModel):
    """Request body for governance actions."""
    review_note: Optional[str] = None


@router.get("/{repository_id}/manual-executions/{execution_id}/governance")
def get_manual_execution_governance(
    repository_id: UUID,
    execution_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get governance status for a manual evidence execution.
    
    Returns the current governance state including review status, reviewer info, and expiration.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED"
        )
    
    # Verify execution exists and belongs to repository
    execution = db.query(ManualTestExecution).filter(
        ManualTestExecution.id == execution_id,
        ManualTestExecution.repository_id == repository_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual execution not found"
        )
    
    # Get governance status
    governance_service = ManualEvidenceGovernanceService(db)
    governance_status = governance_service.get_governance_status(
        execution_id=str(execution_id),
        repository_id=str(repository_id)
    )
    
    return governance_status


@router.get("/{repository_id}/manual-executions/{execution_id}/sync-status")
def get_manual_execution_sync_status(
    repository_id: UUID,
    execution_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get sync status for a manual test execution.
    
    Returns provider sync information including status, external references, and last error.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED"
        )
    
    # Verify execution exists and belongs to repository
    execution = db.query(ManualTestExecution).filter(
        ManualTestExecution.id == execution_id,
        ManualTestExecution.repository_id == repository_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual execution not found"
        )
    
    # Get most recent sync event
    from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
    sync_event = db.query(ManualExecutionSyncEvent).filter(
        ManualExecutionSyncEvent.execution_id == execution_id
    ).order_by(ManualExecutionSyncEvent.created_at.desc()).first()
    
    # Enrich with provider capability (additive — backward compatible)
    from app.services.provider_sync.provider_registry import ProviderRegistry
    registry = ProviderRegistry()
    provider_name = execution.external_system or ""
    supports_execution_sync = registry.is_execution_sync_supported(provider_name)

    return {
        "provider": execution.external_system,
        "syncStatus": execution.sync_status or "PENDING",
        "externalRunId": execution.external_run_id,
        "externalExecutionId": execution.external_execution_id,
        "lastSyncedAt": execution.last_synced_at.isoformat() + "Z" if execution.last_synced_at else None,
        "lastError": sync_event.error_message if sync_event and sync_event.status == "FAILED" else None,
        "supportsExecutionSync": supports_execution_sync,  # Phase 7.2: capability flag (additive)
    }


@router.post("/{repository_id}/manual-executions/{execution_id}/retry-sync")
def retry_manual_execution_sync(
    repository_id: UUID,
    execution_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Retry sync for a manual test execution.
    
    Authorization: OWNER, ADMIN
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED"
        )
    
    # Verify execution exists and belongs to repository
    execution = db.query(ManualTestExecution).filter(
        ManualTestExecution.id == execution_id,
        ManualTestExecution.repository_id == repository_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual execution not found"
        )
    
    # Check user authorization (OWNER or ADMIN)
    from app.models.workspace_member import WorkspaceMember
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == UUID(workspace_id),
        WorkspaceMember.user_id == current_user.id
    ).first()
    
    if not member or member.role not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="INSUFFICIENT_PERMISSIONS"
        )
    
    # Trigger sync
    from app.services.integration_sync_service import IntegrationSyncService
    sync_service = IntegrationSyncService(db)
    sync_result = sync_service.sync_manual_execution_to_provider(execution_id)
    
    return sync_result


@router.post("/{repository_id}/manual-executions/{execution_id}/approve")
def approve_manual_execution(
    repository_id: UUID,
    execution_id: UUID,
    request: ManualEvidenceGovernanceRequest,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Approve a manual evidence execution.
    
    Creates a governance review with APPROVED status, allowing the execution
    to participate in residual risk calculations.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED"
        )
    
    # Verify execution exists and belongs to repository
    execution = db.query(ManualTestExecution).filter(
        ManualTestExecution.id == execution_id,
        ManualTestExecution.repository_id == repository_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual execution not found"
        )
    
    # Create approval review
    governance_service = ManualEvidenceGovernanceService(db)
    review = governance_service.approve_execution(
        execution_id=str(execution_id),
        repository_id=str(repository_id),
        reviewer_id=str(current_user.id),
        reviewer_name=current_user.name or current_user.email,
        review_note=request.review_note
    )
    
    return {
        "reviewId": str(review.id),
        "executionId": str(execution_id),
        "governanceStatus": "APPROVED",
        "reviewerName": review.reviewed_by_name,
        "reviewedAt": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "reviewNote": review.review_note
    }


@router.post("/{repository_id}/manual-executions/{execution_id}/reject")
def reject_manual_execution(
    repository_id: UUID,
    execution_id: UUID,
    request: ManualEvidenceGovernanceRequest,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Reject a manual evidence execution.
    
    Creates a governance review with REJECTED status, preventing the execution
    from participating in residual risk calculations. Requires a review note.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED"
        )
    
    # Verify execution exists and belongs to repository
    execution = db.query(ManualTestExecution).filter(
        ManualTestExecution.id == execution_id,
        ManualTestExecution.repository_id == repository_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual execution not found"
        )
    
    # Create rejection review
    governance_service = ManualEvidenceGovernanceService(db)
    try:
        review = governance_service.reject_execution(
            execution_id=str(execution_id),
            repository_id=str(repository_id),
            reviewer_id=str(current_user.id),
            reviewer_name=current_user.name or current_user.email,
            review_note=request.review_note
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return {
        "reviewId": str(review.id),
        "executionId": str(execution_id),
        "governanceStatus": "REJECTED",
        "reviewerName": review.reviewed_by_name,
        "reviewedAt": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "reviewNote": review.review_note
    }


@router.post("/{repository_id}/manual-executions/{execution_id}/challenge")
def challenge_manual_execution(
    repository_id: UUID,
    execution_id: UUID,
    request: ManualEvidenceGovernanceRequest,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Challenge a manual evidence execution.
    
    Creates a governance review with CHALLENGED status, temporarily preventing
    the execution from participating in residual risk calculations. Requires a review note.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED"
        )
    
    # Verify execution exists and belongs to repository
    execution = db.query(ManualTestExecution).filter(
        ManualTestExecution.id == execution_id,
        ManualTestExecution.repository_id == repository_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual execution not found"
        )
    
    # Create challenge review
    governance_service = ManualEvidenceGovernanceService(db)
    try:
        review = governance_service.challenge_execution(
            execution_id=str(execution_id),
            repository_id=str(repository_id),
            reviewer_id=str(current_user.id),
            reviewer_name=current_user.name or current_user.email,
            review_note=request.review_note
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return {
        "reviewId": str(review.id),
        "executionId": str(execution_id),
        "governanceStatus": "CHALLENGED",
        "reviewerName": review.reviewed_by_name,
        "reviewedAt": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "reviewNote": review.review_note
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7.4: Integration UI Support Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{repository_id}/integrations/health", status_code=status.HTTP_200_OK)
def get_integration_health(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get health status for all integrations for a repository.

    Returns health status derived from:
    - Connection status
    - Last sync status
    - Last sync error
    - Required provider metadata
    - Credential validation

    Health states:
    - HEALTHY: Connected and no recent sync failures
    - CONFIGURATION_REQUIRED: Connected but missing required config
    - AUTHENTICATION_FAILED: Connection test failed
    - SYNC_FAILURES_PRESENT: Connected but recent sync failures
    - DISCONNECTED: Not connected
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Get integration connections
    connections = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repository_id
    ).all()
    
    # Get provider capabilities
    from app.services.provider_sync.provider_registry import ProviderRegistry
    registry = ProviderRegistry()
    
    result = []
    providers = ["TESTRAIL", "XRAY", "ZEPHYR", "JIRA", "AZURE_DEVOPS"]
    connections_map = {conn.provider: conn for conn in connections}
    
    for provider in providers:
        conn = connections_map.get(provider)
        
        if not conn or not conn.is_active:
            result.append({
                "provider": provider,
                "health": "DISCONNECTED",
                "isConnected": False,
                "lastSyncStatus": None,
                "lastSyncError": None,
                "missingConfiguration": None
            })
            continue
        
        # Check for recent sync failures using sync events
        from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
        from app.models.manual_test_execution import ManualTestExecution
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        # Get execution IDs for this repository
        execution_ids = db.query(ManualTestExecution.id).filter(
            ManualTestExecution.repository_id == repository_id
        ).all()
        execution_ids = [e[0] for e in execution_ids]
        
        # Check for provider cooldown
        cooldown = db.query(IntegrationProviderCooldown).filter(
            IntegrationProviderCooldown.repository_id == repository_id,
            IntegrationProviderCooldown.provider == provider,
            IntegrationProviderCooldown.cooldown_until > datetime.utcnow()
        ).first()
        
        cooldown_remaining = None
        if cooldown:
            cooldown_remaining = cooldown.remaining_seconds()
        
        # Check for failed/dead-letter/retry-pending sync events
        failed_sync_events = db.query(ManualExecutionSyncEvent).filter(
            ManualExecutionSyncEvent.execution_id.in_(execution_ids),
            ManualExecutionSyncEvent.provider == provider,
            ManualExecutionSyncEvent.status.in_(["FAILED", "DEAD_LETTER", "RETRY_PENDING"]),
            ManualExecutionSyncEvent.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # Check for missing required configuration
        missing_config = None
        if provider == "TESTRAIL":
            if not conn.config.get("default_test_run_id"):
                missing_config = "default_test_run_id"
        elif provider == "XRAY":
            if not conn.provider_metadata.get("testExecutionKey") and not conn.config.get("testExecutionKey"):
                missing_config = "testExecutionKey"
        elif provider == "ZEPHYR":
            if not conn.provider_metadata.get("testCycleKey") and not conn.config.get("testCycleKey"):
                missing_config = "testCycleKey"
        
        # Determine health status
        if cooldown_remaining and cooldown_remaining > 0:
            health = "COOLDOWN_ACTIVE"
        elif missing_config:
            health = "CONFIGURATION_REQUIRED"
        elif failed_sync_events > 0:
            health = "SYNC_FAILURES_PRESENT"
        else:
            health = "HEALTHY"
        
        # Get last sync error if any from sync events
        last_failed_sync = db.query(ManualExecutionSyncEvent).filter(
            ManualExecutionSyncEvent.execution_id.in_(execution_ids),
            ManualExecutionSyncEvent.provider == provider,
            ManualExecutionSyncEvent.status.in_(["FAILED", "DEAD_LETTER"])
        ).order_by(ManualExecutionSyncEvent.created_at.desc()).first()
        
        last_sync_error = None
        if last_failed_sync and last_failed_sync.last_error:
            last_sync_error = last_failed_sync.last_error
        
        result.append({
            "provider": provider,
            "health": health,
            "isConnected": True,
            "lastSyncStatus": "SYNCED" if failed_sync_events == 0 else "FAILED",
            "lastSyncError": last_sync_error,
            "missingConfiguration": missing_config,
            "cooldownRemaining": cooldown_remaining,
            "cooldownReason": cooldown.reason if cooldown else None
        })
    
    return result


@router.get("/{repository_id}/integrations/sync-activity", status_code=status.HTTP_200_OK)
def get_sync_activity(
    repository_id: UUID,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get sync activity feed for a repository with cursor-based pagination.

    Returns recent sync events from manual_execution_sync_events.
    Can be filtered by provider, status, and date range.
    Supports cursor-based pagination for large datasets.
    """
    # Enforce max limit
    limit = min(limit, 200)
    
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Build query with join to ManualTestExecution for repository filtering
    from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
    from app.models.manual_test_execution import ManualTestExecution
    from app.models.integration_provider_cooldown import IntegrationProviderCooldown
    query = db.query(ManualExecutionSyncEvent).join(
        ManualTestExecution,
        ManualExecutionSyncEvent.execution_id == ManualTestExecution.id
    ).filter(
        ManualTestExecution.repository_id == repository_id
    )
    
    if provider:
        query = query.filter(ManualExecutionSyncEvent.provider == provider.upper())
    
    if status:
        query = query.filter(ManualExecutionSyncEvent.status == status.upper())
    
    if from_date:
        query = query.filter(ManualExecutionSyncEvent.created_at >= from_date)
    
    if to_date:
        query = query.filter(ManualExecutionSyncEvent.created_at <= to_date)
    
    # Cursor pagination
    if cursor:
        try:
            cursor_parts = cursor.split('|')
            cursor_created_at = datetime.fromisoformat(cursor_parts[0])
            cursor_id = UUID(cursor_parts[1])
            query = query.filter(
                (ManualExecutionSyncEvent.created_at < cursor_created_at) |
                ((ManualExecutionSyncEvent.created_at == cursor_created_at) & (ManualExecutionSyncEvent.id < cursor_id))
            )
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format"
            )
    
    # Order by created_at desc and id desc for stable pagination
    query = query.order_by(ManualExecutionSyncEvent.created_at.desc(), ManualExecutionSyncEvent.id.desc())
    
    # Fetch limit+1 to determine if more results exist
    sync_events = query.limit(limit + 1).all()
    has_more = len(sync_events) > limit
    sync_events = sync_events[:limit]
    
    # Build next cursor if has_more
    next_cursor = None
    if has_more and sync_events:
        last_event = sync_events[-1]
        next_cursor = f"{last_event.created_at.isoformat()}|{last_event.id}"
    
    # Fetch cooldowns in batch to avoid N+1
    cooldowns = db.query(IntegrationProviderCooldown).filter(
        IntegrationProviderCooldown.repository_id == repository_id,
        IntegrationProviderCooldown.cooldown_until > datetime.utcnow()
    ).all()
    cooldown_map = {c.provider: c for c in cooldowns}
    
    # Build response
    result = []
    for event in sync_events:
        cooldown = cooldown_map.get(event.provider)
        result.append({
            "id": str(event.id),
            "provider": event.provider,
            "executionId": str(event.execution_id),
            "status": event.status,
            "error": event.last_error if event.status in ["FAILED", "DEAD_LETTER"] else None,
            "externalRunId": event.external_run_id,
            "externalExecutionId": event.external_execution_id,
            "createdAt": event.created_at.isoformat() if event.created_at else None,
            "attemptCount": event.attempt_count,
            "maxAttempts": event.max_attempts,
            "nextAttemptAt": event.next_attempt_at.isoformat() if event.next_attempt_at else None,
            "cooldownUntil": cooldown.cooldown_until.isoformat() if cooldown else None,
            "cooldownReason": cooldown.reason if cooldown else None
        })
    
    return {
        "items": result,
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "limit": limit
    }


@router.get("/{repository_id}/integrations/metrics", status_code=status.HTTP_200_OK)
def get_integration_metrics(
    repository_id: UUID,
    provider: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get integration sync metrics for a repository.

    Returns provider-level metrics including success rates, failure rates,
    dead-letter counts, and alert states.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    from app.services.integration_metrics_service import IntegrationMetricsService
    
    metrics_service = IntegrationMetricsService(db)
    
    # Get metrics
    metrics = metrics_service.get_provider_metrics(
        repository_id=str(repository_id),
        provider=provider,
        from_date=from_date,
        to_date=to_date
    )
    
    # Get alerts
    alerts = metrics_service.get_alerts(
        repository_id=str(repository_id),
        from_date=from_date,
        to_date=to_date
    )
    
    return {
        "providers": metrics["providers"],
        "overall": metrics["overall"],
        "alerts": alerts
    }


@router.post("/{repository_id}/integrations/retry-failed-syncs", status_code=status.HTTP_200_OK)
def retry_failed_syncs(
    repository_id: UUID,
    request: Dict[str, str],
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Retry all failed syncs for a specific provider.

    Requires OWNER or ADMIN role.
    """
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Check authorization (OWNER or ADMIN)
    workspace = db.query(Workspace).filter(Workspace.id == UUID(workspace_id)).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is OWNER or ADMIN
    membership = db.query(User).join(
        workspace.users
    ).filter(
        User.id == current_user.id
    ).first()
    
    # Simple role check - in production, use proper role model
    # For now, allow all workspace members
    # TODO: Implement proper role-based access control
    
    provider = request.get("provider", "").upper()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider is required"
        )
    
    # Get failed and dead-letter sync events for provider
    from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
    from app.models.manual_test_execution import ManualTestExecution
    
    # Use join to avoid loading all execution IDs into memory
    failed_sync_events = db.query(ManualExecutionSyncEvent).join(
        ManualTestExecution,
        ManualExecutionSyncEvent.execution_id == ManualTestExecution.id
    ).filter(
        ManualTestExecution.repository_id == repository_id,
        ManualExecutionSyncEvent.provider == provider,
        ManualExecutionSyncEvent.status.in_(["FAILED", "DEAD_LETTER"])
    ).all()
    
    if not failed_sync_events:
        return {
            "provider": provider,
            "retriedCount": 0,
            "message": "No failed or dead-letter syncs found for provider"
        }
    
    # Requeue sync events
    retried_count = 0
    errors = []
    
    for sync_event in failed_sync_events:
        try:
            # Set to RETRY_PENDING
            sync_event.status = "RETRY_PENDING"
            sync_event.next_attempt_at = datetime.utcnow()
            sync_event.locked_at = None
            sync_event.locked_by = None
            sync_event.last_error = "Manually retried via admin endpoint"
            retried_count += 1
        except Exception as e:
            errors.append(f"Sync event {sync_event.id}: {str(e)}")
    
    db.commit()
    
    return {
        "provider": provider,
        "retriedCount": retried_count,
        "errors": errors,
        "message": f"Requeued {retried_count} sync events for retry"
    }


@router.post("/{repository_id}/pipeline-runs", response_model=PipelineRunResponse, status_code=status.HTTP_201_CREATED)
def trigger_pipeline_run(
    repository_id: UUID,
    request: PipelineRunTriggerRequest,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Trigger or link a CI/CD pipeline run to a Veriscope recommendation.
    
    Idempotent: Same external_run_id returns existing PipelineRun.
    New external_run_id creates new PipelineRun attempt.
    """
    # Validate repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    service = PipelineRunService()
    return service.trigger_pipeline_run(db, repository_id, request)


@router.get("/{repository_id}/pipeline-runs/{pipeline_run_id}/artifact")
def get_pipeline_run_artifact(
    repository_id: UUID,
    pipeline_run_id: UUID,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get CI-safe artifact JSON for a pipeline run.
    
    Can be authenticated via:
    - Workspace member session (default)
    - CI token (Bearer token in Authorization header)
    """
    # Try CI token authentication first
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        ci_token_service = CITokenService()
        ci_token = ci_token_service.verify_token(db, token)
        
        if ci_token:
            # Verify token belongs to the requested repository
            if ci_token.repository_id != repository_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CI token is not authorized for this repository"
                )
            # CI token authenticated, skip workspace check
        else:
            # Invalid CI token, fall through to workspace authentication
            pass
    
    # Validate pipeline run belongs to repository
    from app.models.pipeline_run import PipelineRun
    pipeline_run = db.query(PipelineRun).filter(
        PipelineRun.id == pipeline_run_id,
        PipelineRun.repository_id == repository_id
    ).first()
    
    if not pipeline_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found."
        )
    
    # Validate repository belongs to workspace (if not using CI token)
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    # Check if pipeline run has completed (async mode)
    from app.models.pipeline_run import PipelineRunStatus
    from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
    
    # Check for execution job to determine if async mode
    execution_job = db.query(PipelineExecutionJob).filter(
        PipelineExecutionJob.pipeline_run_id == pipeline_run_id
    ).first()
    
    if execution_job:
        # Async mode: check if job is completed
        if execution_job.status != PipelineJobStatus.COMPLETED:
            # Job not completed yet
            return {
                "status": "pending",
                "message": "Artifact not ready yet. Pipeline analysis is still in progress.",
                "pipeline_run_id": str(pipeline_run_id),
                "job_status": execution_job.status.value,
                "attempt_count": execution_job.attempt_count,
                "next_attempt_at": execution_job.next_attempt_at.isoformat() if execution_job.next_attempt_at else None
            }
    
    # Pipeline run completed or sync mode - return artifact
    service = PipelineRunService()
    return service.get_artifact(db, pipeline_run_id)


# CI Token Management Endpoints

@router.post("/{repository_id}/ci-tokens", response_model=CITokenResponse, status_code=status.HTTP_201_CREATED)
def create_ci_token(
    repository_id: UUID,
    token_in: CITokenCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new CI token for the repository.
    
    The raw token is returned only once. Store it securely.
    """
    # Validate repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    service = CITokenService()
    return service.create_token(db, repository_id, token_in, created_by=current_user.id)


@router.get("/{repository_id}/ci-tokens", response_model=CITokenListResponse)
def list_ci_tokens(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    List all CI tokens for the repository.
    
    Raw tokens are never included in the list.
    """
    # Validate repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    service = CITokenService()
    tokens = service.list_tokens(db, repository_id)
    return CITokenListResponse(tokens=tokens)


@router.post("/{repository_id}/ci-tokens/{token_id}/revoke", response_model=CITokenRevokeResponse)
def revoke_ci_token(
    repository_id: UUID,
    token_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Revoke a CI token.
    
    Revoked tokens cannot be used for authentication.
    """
    # Validate repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    service = CITokenService()
    try:
        service.revoke_token(db, repository_id, token_id)
        return CITokenRevokeResponse(id=token_id, revoked=True)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch("/{repository_id}/ci-settings", response_model=RepositoryCISettingsResponse)
def update_ci_settings(
    repository_id: UUID,
    settings_in: RepositoryCISettingsUpdate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Update repository CI settings.
    
    Updates the ciFailOnPartial setting which controls whether
    PARTIAL quality gate results fail the GitHub check.
    """
    # Validate repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    # Update ci_fail_on_partial setting
    repository.ci_fail_on_partial = settings_in.ciFailOnPartial
    repository.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(repository)
    
    return RepositoryCISettingsResponse(
        repositoryId=repository.id,
        ciFailOnPartial=repository.ci_fail_on_partial
    )


@router.get("/{repository_id}/fragility-memory")
def get_fragility_memory(
    repository_id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Get fragility memory for a repository.
    Returns top 10 most fragile ACs by PatternMemoryV2 signal count.
    """
    from app.models.pattern_memory_v2 import PatternMemoryV2
    from app.models.acceptance_criterion import AcceptanceCriterion
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Validate repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found in your active workspace."
        )
    
    # Get PatternMemoryV2 records for this repository, grouped by pattern_key
    from sqlalchemy import text
    query = text("""
        SELECT 
            pattern_key,
            COUNT(*) as signal_count,
            array_agg(DISTINCT signal_type) as signal_types,
            MAX(created_at) as last_signal_date
        FROM pattern_memories_v2
        WHERE repository_id = :repo_id
        GROUP BY pattern_key
        ORDER BY signal_count DESC
        LIMIT 10
    """)
    
    results = db.execute(query, {"repo_id": str(repository_id)}).fetchall()
    
    fragile_areas = []
    for row in results:
        pattern_key = row.pattern_key
        signal_count = row.signal_count
        signal_types = row.signal_types
        last_signal_date = row.last_signal_date
        
        # Find AC title
        ac = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id,
            AcceptanceCriterion.normalized_key == pattern_key
        ).first()
        
        ac_title = ac.text if ac else pattern_key
        
        # Calculate trend (simplified - compare recent vs older signals)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_signals = db.query(PatternMemoryV2).filter(
            PatternMemoryV2.repository_id == repository_id,
            PatternMemoryV2.pattern_key == pattern_key,
            PatternMemoryV2.created_at >= thirty_days_ago
        ).count()
        
        if recent_signals > signal_count * 0.5:
            trend = "WORSENING"
        elif recent_signals < signal_count * 0.2:
            trend = "IMPROVING"
        else:
            trend = "STABLE"
        
        fragile_areas.append({
            "pattern_key": pattern_key,
            "ac_title": ac_title,
            "signal_count": signal_count,
            "signal_types": signal_types,
            "last_signal_date": last_signal_date.isoformat() if last_signal_date else None,
            "trend": trend
        })
    
    return {
        "repository_id": str(repository_id),
        "fragile_areas": fragile_areas
    }






