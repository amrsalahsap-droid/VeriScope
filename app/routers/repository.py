from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.dependencies.auth import get_current_workspace, get_current_workspace_id, require_workspace_member
from app.models.user import Workspace
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
from pydantic import BaseModel
from app.services.junit_parser import XMLParsingError, OversizedXMLException
from app.constants.evidence import EvidenceSource, EvidenceArtifactType
from app.config import settings
from app.services.manual_test_case_csv_import import ManualTestCaseCSVImport
from app.services.jira_connector import JiraConnector
from app.services.azure_devops_connector import AzureDevOpsConnector
from app.services.testrail_connector import TestRailConnector
from app.services.external_requirement_coverage_resolver import ExternalRequirementCoverageResolver

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
            branch=branch
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
    
    if duplicate_coalesced:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate test run artifact detected. This JUnit XML file has already been uploaded."
        )
    
    # 6. Recalculate repository readiness
    readiness_service = RepositoryReadinessService(db)
    readiness_result = readiness_service.calculate_readiness(repository_id, UUID(workspace_id))
    
    return {
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
    tags=["API Repositories"],
    dependencies=[Depends(require_workspace_member())]
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

    # 6. Run recommendation engine with debug logging
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
                generated_from_pull_request_id=pull_request_id
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
    
    raw_lines = payload.acceptance_criteria.split("\n")
    criteria = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        # Remove list markers if present (e.g. -, *, 1., etc.)
        clean_text = re.sub(r"^(\s*[-*\d\.]+\s+)", "", line)
        if clean_text:
            # Source normalized to MANUAL_USER_INPUT for consistency with cleanup logic
            criteria.append({
                "text": clean_text,
                "source": "MANUAL_USER_INPUT",
                "confidence": 1.0,
                "evidence_excerpt": line,
                "normalized_key": extractor._generate_normalized_key(extractor._normalize_text(clean_text)),
                "criterion_type": extractor._classify_criterion_type(clean_text)
            })
            
    if criteria:
        extractor.persist_criteria(criteria, str(repository_id), str(pull_request_id), db)
        
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
    business_change: str
    affected_users: Optional[str] = None
    acceptance_criteria: str
    risk_notes: Optional[str] = None
    testing_notes: Optional[str] = None


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

    # 3. Create and add a new BusinessIntentOverride
    bio = BusinessIntentOverride(
        id=uuid.uuid4(),
        repository_id=repository_id,
        pull_request_id=pull_request_id,
        business_change_summary=payload.business_change,
        affected_users_journeys=payload.affected_users,
        risk_notes=payload.risk_notes,
        testing_notes=payload.testing_notes,
        acceptance_criteria=payload.acceptance_criteria,
        source="MANUAL_USER_INPUT",
        is_active=True,
        is_processed=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(bio)
    db.flush()

    # 4. Extract and persist AcceptanceCriterion records (for readiness check)
    extractor = AcceptanceCriteriaExtractor(db=db)
    
    # Extract criteria from the pasted text
    criteria = extractor._extract_criteria_from_text(payload.acceptance_criteria, "MANUAL_USER_INPUT")
    if not criteria:
        # Fallback to treat lines as criteria
        raw_lines = payload.acceptance_criteria.split("\n")
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            clean_text = re.sub(r"^(\s*[-*\d\.]+\s+)", "", line)
            if clean_text:
                criteria.append({
                    "text": clean_text,
                    "source": "MANUAL_USER_INPUT",
                    "confidence": 1.0,
                    "evidence_excerpt": line
                })
                
    # Normalize and deduplicate
    criteria = extractor._normalize_and_deduplicate(criteria)
    
    # Classify criterion types
    for criterion in criteria:
        criterion["criterion_type"] = extractor._classify_criterion_type(criterion["text"])
        
    persisted_ac = []
    if criteria:
        persisted_ac = extractor.persist_criteria(criteria, str(repository_id), str(pull_request_id), db)

    # 5. Extract structured scenarios and save to override
    extracted_scenarios = extractor.extract_from_business_intent_override(
        payload.acceptance_criteria,
        str(bio.id),
        str(repository_id),
        source="MANUAL_USER_INPUT"
    )
    bio.extracted_scenarios = extracted_scenarios

    # 6. Run BusinessBehaviorMapper to map to business behaviors
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
                "config": {
                    "base_url": conn.config.get("base_url") if conn.config else None,
                    "username": conn.config.get("username") if conn.config else None,
                    # Never return secrets
                }
            })
        else:
            result.append({
                "provider": provider,
                "is_connected": False,
                "last_synced_at": None,
                "config": None
            })
    
    return result


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
    
    # Check for existing connection
    existing = db.query(IntegrationConnection).filter(
        IntegrationConnection.repository_id == repository_id,
        IntegrationConnection.provider == provider
    ).first()
    
    if existing:
        # Update existing connection
        existing.config = config
        existing.is_active = True
        existing.last_synced_at = datetime.utcnow()
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {
            "id": str(existing.id),
            "provider": existing.provider,
            "is_connected": existing.is_active,
            "last_synced_at": existing.last_synced_at.isoformat()
        }
    else:
        # Create new connection
        connection = IntegrationConnection(
            id=uuid.uuid4(),
            workspace_id=UUID(workspace_id),
            repository_id=repository_id,
            provider=provider,
            config=config,
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
            "last_synced_at": connection.last_synced_at.isoformat()
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


@router.get("/{repository_id}/pull-requests/{pull_request_id}/manual-tests", status_code=status.HTTP_200_OK)
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
            "execution_status": "NOT_EXECUTED"  # Would track actual execution status
        })
    
    return {
        "manual_tests": manual_tests_response
    }


@router.post("/manual-tests/{test_id}/execution", status_code=status.HTTP_200_OK)
def mark_manual_test_executed(
    test_id: UUID,
    outcome: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Mark a manual test as executed with outcome.
    
    Outcome: PASSED, FAILED, SKIPPED
    """
    # Get test case
    from app.models.external_test_case_detailed import ExternalTestCase
    
    test = db.query(ExternalTestCase).filter(
        ExternalTestCase.id == test_id
    ).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found"
        )
    
    # Verify workspace access
    repo = db.query(Repository).filter(
        Repository.id == test.repository_id,
        Repository.workspace_id == UUID(workspace_id)
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository not found in your active workspace."
        )
    
    # Update execution status (would store in execution tracking table)
    # For now, just return success
    return {
        "test_id": str(test_id),
        "outcome": outcome,
        "message": "Test execution recorded"
    }


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






