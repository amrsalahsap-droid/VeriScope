import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Header, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from collections import defaultdict

from app.db.session import get_db
from app.config import settings
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.test_result import TestCase
from app.models.observability import IngestionJob
from app.models.repository import Repository
from app.schemas.debugging import CoverageDebugResponse
from app.services.coverage_ingestion import CoverageIngestionService, CoverageIngestionError
from app.services.repository_readiness import RepositoryReadinessService
from app.constants.evidence import EvidenceSource

router = APIRouter(prefix="/api/coverage", tags=["Coverage"])
internal_router = APIRouter(prefix="/internal/coverage", tags=["Diagnostics"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_coverage_report(
    file: UploadFile = File(...),
    repository_id: uuid.UUID = Form(...),
    commit_sha: str = Form(...),
    pull_request_id: Optional[uuid.UUID] = Form(None),
    x_correlation_id: Optional[str] = Header(None),
    evidence_source: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Accepts multipart LCOV coverage report uploads.
    Enforces strict upload size bounds and performs direct & heuristic test mapping.
    Recalculates repository readiness after successful ingestion.
    """
    # 1. Pre-reading size check if size is populated in UploadFile
    max_bytes = settings.MAX_LCOV_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": f"Payload too large: Coverage LCOV report size exceeding limit of {settings.MAX_LCOV_SIZE_MB} MB."
            }
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read coverage upload stream: {str(e)}"
        )

    try:
        report = CoverageIngestionService.ingest_coverage(
            db=db,
            repository_id=repository_id,
            commit_sha=commit_sha,
            payload_bytes=file_bytes,
            file_name=file.filename or "coverage.info",
            pull_request_id=pull_request_id,
            correlation_id=x_correlation_id,
            evidence_source=evidence_source or EvidenceSource.MANUAL_UPLOAD.value,
            branch=branch
        )
        db.commit() # Commit transaction on success
    except CoverageIngestionError as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing coverage report: {str(e)}"
        )

    # Recalculate repository readiness after successful coverage ingestion
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if repo:
        readiness_service = RepositoryReadinessService(db)
        readiness_result = readiness_service.calculate_readiness(repository_id, repo.workspace_id)
        
        # Add coverage confidence warning if confidence is LOW
        readiness_reasons = list(readiness_result.readiness_reasons)
        if report.confidence_score == "LOW" and readiness_result.readiness_state == "READY":
            readiness_reasons.append("Coverage mapping confidence is LOW; recommendations may be less precise.")
        
        repository_readiness = {
            "readiness_state": readiness_result.readiness_state,
            "readiness_reasons": readiness_reasons,
            "next_action": readiness_result.next_action
        }
    else:
        repository_readiness = None

    return {
        "coverage_report_id": str(report.id),
        "overall_coverage_pct": report.overall_coverage_pct,
        "total_lines": report.total_lines,
        "covered_lines_count": report.covered_lines_count,
        "uncovered_lines_count": report.uncovered_lines_count,
        "confidence_score": report.confidence_score,
        "confidence_logic": report.confidence_logic,
        "correlation_id": report.correlation_id,
        "created_at": report.created_at.isoformat(),
        "repository_readiness": repository_readiness
    }


@internal_router.get("/{repo_id}/debug", response_model=CoverageDebugResponse)
def get_coverage_diagnostics(
    repo_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Forensic debug endpoint returning structured coverage audit payloads.
    """
    # Query latest report for the repository
    report = (
        db.query(CoverageReport)
        .filter(CoverageReport.repository_id == repo_id)
        .order_by(CoverageReport.created_at.desc())
        .first()
    )

    # Query IngestionJobs
    jobs = db.query(IngestionJob).filter(
        IngestionJob.repository_id == repo_id,
        IngestionJob.job_type == "coverage_ingestion"
    ).order_by(IngestionJob.started_at.desc()).all()
    
    jobs_list = [
        {
            "job_id": str(job.id),
            "status": job.status,
            "error_message": job.error_message,
            "retry_count": job.retry_count,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        }
        for job in jobs
    ]

    if not report:
        return CoverageDebugResponse(
            raw_inputs={
                "repository_id": str(repo_id),
                "latest_report": None
            },
            derived_relationships={
                "mapped_files": [],
                "unmapped_files": [],
                "test_mappings": []
            },
            fallback_heuristics_used=[],
            warnings=["No coverage reports have been ingested for this repository yet"],
            confidence_issues=["NO_COVERAGE_REPORT"],
            telemetry={
                "correlation_id": None,
                "ingestion_jobs": jobs_list
            }
        )

    # 1. Raw Inputs
    filename = "coverage.info"
    if report.raw_artifact:
        filename = report.raw_artifact.artifact_metadata.get("filename", report.raw_artifact.storage_path)

    raw_inputs = {
        "coverage_report_id": str(report.id),
        "commit_sha": report.commit_sha,
        "overall_coverage_pct": report.overall_coverage_pct,
        "total_lines": report.total_lines,
        "covered_lines_count": report.covered_lines_count,
        "uncovered_lines_count": report.uncovered_lines_count,
        "file_hash": report.file_hash,
        "file_name": filename
    }

    # Fetch mapping details
    mapped_files = sorted(list({link.file_path for link in report.test_links}))
    unmapped_files = sorted([fe.file_path for fe in report.file_entries if fe.file_path not in mapped_files])

    # 2. Derived Relationships
    derived_relationships = {
        "mapped_files": mapped_files,
        "unmapped_files": unmapped_files,
        "test_mappings": [
            {
                "file_path": link.file_path,
                "test_case_id": str(link.test_case_id),
                "mapping_type": link.mapping_type,
                "confidence_score": link.confidence_score
            }
            for link in report.test_links
        ]
    }

    # 3. Fallback Heuristics Used
    fallback_heuristics_used = sorted(list({
        link.mapping_type 
        for link in report.test_links 
        if link.mapping_type in ("HEURISTIC_NAMING", "HEURISTIC_PATH")
    }))

    # 4. Warnings
    warnings = []
    if len(unmapped_files) > 0:
        warnings.append(f"unmapped_files_count:{len(unmapped_files)}")
    if report.overall_coverage_pct < 0.20:
        warnings.append("Low overall coverage pct (under 20%)")

    # 5. Confidence Issues
    confidence_issues = [
        f"confidence_score:{report.confidence_score}",
        f"confidence_logic:{report.confidence_logic}"
    ]
    if report.confidence_score == "LOW":
        confidence_issues.append("Low coverage mapping confidence")

    # 6. Telemetry
    telemetry = {
        "correlation_id": report.correlation_id,
        "created_at": report.created_at.isoformat(),
        "ingestion_jobs": jobs_list
    }

    return CoverageDebugResponse(
        raw_inputs=raw_inputs,
        derived_relationships=derived_relationships,
        fallback_heuristics_used=fallback_heuristics_used,
        warnings=warnings,
        confidence_issues=confidence_issues,
        telemetry=telemetry
    )
