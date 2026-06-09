import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Header, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.config import settings
from app.models.test_result import TestRun, TestResult
from app.models.artifact import RawArtifact
from app.models.observability import IngestionJob
from app.schemas.debugging import TestRunDebugResponse
from app.services.test_ingestion import TestIngestionService
from app.services.junit_parser import XMLParsingError, OversizedXMLException
from app.constants.evidence import EvidenceSource

router = APIRouter(prefix="/api/test-results", tags=["Test Results"])
internal_router = APIRouter(prefix="/internal/test-runs", tags=["Diagnostics"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_junit_xml(
    file: UploadFile = File(...),
    repository_id: uuid.UUID = Form(...),
    commit_sha: Optional[str] = Form(None),
    pull_request_id: Optional[uuid.UUID] = Form(None),
    parent_test_run_id: Optional[uuid.UUID] = Form(None),
    ingestion_reason: str = Form("ORIGINAL_UPLOAD"),
    x_correlation_id: Optional[str] = Header(None),
    x_source_correlation_id: Optional[str] = Header(None),
    request_origin: Optional[str] = Header(None),
    evidence_source: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Ingests, validates, and stores a JUnit XML test execution report.
    Returns the ingested TestRun metadata or short-circuits if duplicate coalesced.
    """
    # Fast pre-reading size check if size is populated in UploadFile
    max_bytes = settings.MAX_JUNIT_XML_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": f"Payload too large: JUnit XML size exceeding limit of {settings.MAX_JUNIT_XML_SIZE_MB} MB."
            }
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file stream: {str(e)}"
        )

    ingestion_service = TestIngestionService(db)

    try:
        test_run, duplicate_coalesced = ingestion_service.ingest_junit_xml(
            file_bytes=file_bytes,
            filename=file.filename or "unknown_junit.xml",
            repository_id=repository_id,
            commit_sha=commit_sha,
            pull_request_id=pull_request_id,
            parent_test_run_id=parent_test_run_id,
            ingestion_reason=ingestion_reason,
            correlation_id=x_correlation_id,
            source_correlation_id=x_source_correlation_id,
            request_origin=request_origin,
            evidence_source=evidence_source or EvidenceSource.MANUAL_UPLOAD.value
        )
    except OversizedXMLException as e:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": str(e)}
        )
    except XMLParsingError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failure: {str(e)}"
        )

    return {
        "test_run_id": str(test_run.id),
        "status": test_run.status,
        "evidence_health_status": test_run.evidence_health_status,
        "consistency_status": test_run.consistency_status,
        "consistency_severity": test_run.consistency_severity,
        "total_tests": test_run.total_tests,
        "passed_tests": test_run.passed_tests,
        "failed_tests": test_run.failed_tests,
        "skipped_tests": test_run.skipped_tests,
        "duration": test_run.duration,
        "duplicate_coalesced": duplicate_coalesced,
        "correlation_id": test_run.correlation_id
    }


@internal_router.get("/{id}/debug", response_model=TestRunDebugResponse)
def get_test_run_debug(
    id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Forensic debug endpoint with structured audit blocks for a specific TestRun.
    """
    test_run = db.query(TestRun).filter(TestRun.id == id).first()
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TestRun with ID '{id}' was not found."
        )

    # Fetch raw artifact details if associated
    artifact_filename = "unknown_junit.xml"
    artifact_size = 0
    raw_artifact_ref = None
    if test_run.raw_artifact_id:
        raw_artifact = db.query(RawArtifact).filter(RawArtifact.id == test_run.raw_artifact_id).first()
        if raw_artifact:
            artifact_filename = raw_artifact.artifact_metadata.get("filename", raw_artifact.storage_path)
            artifact_size = raw_artifact.artifact_metadata.get("artifact_size_bytes", 0)
            raw_artifact_ref = str(raw_artifact.id)

    # 1. Raw Inputs
    raw_inputs = {
        "junit_xml_filename": artifact_filename,
        "size_bytes": artifact_size,
        "raw_byte_reference": raw_artifact_ref,
        "repository_id": str(test_run.repository_id),
        "commit_sha": test_run.commit_sha,
        "parent_test_run_id": str(test_run.parent_test_run_id) if test_run.parent_test_run_id else None,
        "ingestion_reason": test_run.ingestion_reason
    }

    # Query all results for this test run
    results = db.query(TestResult).filter(TestResult.test_run_id == id).all()

    # 2. Derived Relationships
    derived_relationships = {
        "test_cases": [
            {
                "result_id": str(res.id),
                "test_case_id": str(res.test_case_id),
                "status": res.status,
                "duration": res.duration
            }
            for res in results
        ],
        "metrics": {
            "total_tests": test_run.total_tests,
            "passed_tests": test_run.passed_tests,
            "failed_tests": test_run.failed_tests,
            "skipped_tests": test_run.skipped_tests,
            "duration": test_run.duration
        }
    }

    # 3. Fallback Heuristics Used
    fallback_heuristics_used = []
    # Check if duplicate was coalesced (based on reason or metadata)
    is_coalesced = test_run.ingestion_diagnostics.get("duplicate_coalesced", False) if test_run.ingestion_diagnostics else False
    if is_coalesced:
        fallback_heuristics_used.append("duplicate_coalescing_applied")
    else:
        fallback_heuristics_used.append("duplicate_coalescing_checked")
        
    if test_run.ingestion_reason == "FALLBACK_RUN":
        fallback_heuristics_used.append("execution_fallback_rules")

    # 4. Warnings
    warnings = []
    if test_run.diagnostics_truncated:
        warnings.append("diagnostics_truncated")
    
    # Check stack trace compliance redaction states
    redacted_count = db.query(TestResult).filter(
        TestResult.test_run_id == id,
        TestResult.stack_trace_redaction_status == "REDACTED"
    ).count()
    if redacted_count > 0:
        warnings.append(f"redacted_stack_traces_count:{redacted_count}")

    # 5. Confidence Issues
    confidence_issues = []
    confidence_issues.append(f"evidence_health_status:{test_run.evidence_health_status}")
    confidence_issues.append(f"consistency_status:{test_run.consistency_status}")
    confidence_issues.append(f"consistency_severity:{test_run.consistency_severity}")

    # Query IngestionJob executions
    jobs = db.query(IngestionJob).filter(
        IngestionJob.repository_id == test_run.repository_id,
        IngestionJob.job_type == "junit_parsing"
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

    # 6. Telemetry
    telemetry = {
        "correlation_id": test_run.correlation_id,
        "source_correlation_id": test_run.source_correlation_id,
        "request_origin": test_run.request_origin,
        "created_at": test_run.created_at.isoformat(),
        "ingestion_jobs": jobs_list
    }

    return TestRunDebugResponse(
        raw_inputs=raw_inputs,
        derived_relationships=derived_relationships,
        fallback_heuristics_used=fallback_heuristics_used,
        warnings=warnings,
        confidence_issues=confidence_issues,
        telemetry=telemetry
    )
