"""
Pipeline Run Service

Service for creating and managing CI/CD pipeline runs.
"""
import uuid
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus, TriggerSource
from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun
from app.models.release_decision import ReleaseDecision
from app.schemas.pipeline_run import PipelineRunTriggerRequest, PipelineRunResponse, RegressionScopeSummary
from app.services.quality_gate_service import QualityGateService
from app.services.github_check_service import GitHubCheckService
from app.config import settings


class TimeoutError(Exception):
    """Timeout exception for pipeline operations."""
    pass


@contextmanager
def timeout_context(seconds: int):
    """
    Context manager for timeout handling using threading (cross-platform).
    
    NOTE: Due to Python's GIL, threading.Timer cannot reliably interrupt
    the main thread. This context manager provides the timeout mechanism
    structure but does not guarantee actual interruption of long-running
    operations. For production timeout protection, this should be replaced
    with a multiprocessing-based solution or cooperative timeout pattern.
    
    Current behavior: The timer will raise TimeoutError in its thread, but
    this may not interrupt the main thread execution.
    """
    def timeout_handler():
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Create and start timer thread
    timer = threading.Timer(seconds, timeout_handler)
    timer.daemon = True
    timer.start()
    
    try:
        yield
    finally:
        # Cancel timer
        timer.cancel()


class PipelineRunService:
    """Service for pipeline run operations."""
    
    @staticmethod
    def trigger_pipeline_run(
        db: Session,
        repository_id: uuid.UUID,
        request: PipelineRunTriggerRequest
    ) -> PipelineRunResponse:
        """
        Trigger or link a pipeline run.
        
        Idempotency rule:
        - Same external_run_id returns existing PipelineRun
        - New external_run_id creates new PipelineRun attempt
        
        GitHub integration:
        - Creates pending check/status when pipeline starts
        - Updates check/status when analysis completes
        - Posts/updates PR comment with quality gate result
        """
        # Validate repository
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError(f"Repository {repository_id} not found")
        
        # Check for existing pipeline run with same external_run_id
        existing_run = db.query(PipelineRun).filter(
            PipelineRun.repository_id == repository_id,
            PipelineRun.external_run_id == request.external_run_id
        ).first()
        
        if existing_run:
            # Return existing run (idempotent)
            return PipelineRunService._build_response(db, existing_run)
        
        # Resolve PR if provided
        pull_request: Optional[PullRequest] = None
        if request.pull_request_number:
            pull_request = db.query(PullRequest).filter(
                PullRequest.repository_id == repository_id,
                PullRequest.number == request.pull_request_number
            ).first()
        
        # Find or create recommendation run
        recommendation_run: Optional[RecommendationRun] = None
        if pull_request:
            # Look for existing recommendation for this PR
            recommendation_run = db.query(RecommendationRun).filter(
                RecommendationRun.repository_id == repository_id,
                RecommendationRun.pull_request_id == pull_request.id
            ).order_by(RecommendationRun.created_at.desc()).first()
        
        # Create new pipeline run
        pipeline_run = PipelineRun(
            id=uuid.uuid4(),
            repository_id=repository_id,
            recommendation_run_id=recommendation_run.id if recommendation_run else None,
            pull_request_id=pull_request.id if pull_request else None,
            provider=request.provider,
            external_run_id=request.external_run_id,
            commit_sha=request.commit_sha,
            branch=request.branch,
            status=PipelineRunStatus.RUNNING.value,
            quality_gate=QualityGateStatus.UNKNOWN.value,
            trigger_source=TriggerSource(request.trigger_source).value,
            started_at=datetime.utcnow(),
            metadata_json={"pull_request_number": request.pull_request_number} if request.pull_request_number else None
        )
        
        db.add(pipeline_run)
        db.commit()
        db.refresh(pipeline_run)
        
        # Create async execution job
        execution_job = PipelineExecutionJob(
            id=uuid.uuid4(),
            pipeline_run_id=pipeline_run.id,
            repository_id=repository_id,
            pull_request_id=pull_request.id if pull_request else None,
            recommendation_run_id=recommendation_run.id if recommendation_run else None,
            status=PipelineJobStatus.PENDING,
            attempt_count=0,
            max_attempts=5,
            metadata_json={
                "pull_request_number": request.pull_request_number,
                "provider": request.provider,
                "external_run_id": request.external_run_id
            }
        )
        
        db.add(execution_job)
        db.commit()
        db.refresh(execution_job)
        
        # Initialize GitHub check service if we have repository integration
        github_service = None
        if repository.owner and repository.full_name and repository.installation_id:
            try:
                from app.services.github_api_client import GitHubApiClient
                github_client = GitHubApiClient()
                github_token = github_client.get_installation_token(repository.installation_id)
                github_service = GitHubCheckService(
                    github_token=github_token,
                    ci_fail_on_partial=repository.ci_fail_on_partial if hasattr(repository, 'ci_fail_on_partial') else False
                )
            except Exception as e:
                import logging
                logging.getLogger("veriscope.pipeline").error(f"Failed to resolve GitHub installation token: {e}")
        
        # Publish GitHub pending status/check
        if github_service and repository.owner and repository.full_name:
            try:
                owner, repo = repository.full_name.split('/', 1)
                github_service.create_commit_status(
                    owner=owner,
                    repo=repo,
                    commit_sha=request.commit_sha,
                    state="pending",
                    description="Veriscope analysis queued",
                    context="veriscope/quality-gate"
                )
            except Exception as e:
                # Log error but don't fail pipeline trigger
                import logging
                logging.getLogger("veriscope.pipeline").error(f"Failed to publish GitHub pending status: {e}")
        
        # Return immediately without computing final quality gate
        # The background worker will handle processing
        return PipelineRunService._build_response(db, pipeline_run)
    
    @staticmethod
    def _update_quality_gate(
        db: Session,
        pipeline_run: PipelineRun,
        recommendation_run: RecommendationRun
    ) -> None:
        """Update quality gate based on recommendation state."""
        # Get release decision
        release_decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == recommendation_run.id
        ).first()
        
        # Get required before release count from regression scope
        required_count = 0
        if recommendation_run.requirement_evidence_snapshot_json:
            # Parse snapshot to get required items count
            try:
                import json
                snapshot = json.loads(recommendation_run.requirement_evidence_snapshot_json)
                # Extract required count from snapshot structure
                required_count = len(snapshot.get("required_items", []))
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Compute quality gate
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=release_decision,
            recommendation_health=recommendation_run.evidence_health_status,
            required_before_release_count=required_count,
            has_blocking_failed_tests=False,  # TODO: implement from test results
            recommendation_generation_failed=False  # TODO: implement based on recommendation state
        )
        
        pipeline_run.quality_gate = quality_gate
        
        # Update status based on quality gate
        if quality_gate in [QualityGateStatus.PASSED, QualityGateStatus.PARTIAL, QualityGateStatus.FAILED]:
            pipeline_run.status = PipelineRunStatus.COMPLETED.value
            pipeline_run.completed_at = datetime.utcnow()
        elif quality_gate == QualityGateStatus.BLOCKED:
            pipeline_run.status = PipelineRunStatus.FAILED.value
            pipeline_run.completed_at = datetime.utcnow()
    
    @staticmethod
    def _build_response(db: Session, pipeline_run: PipelineRun) -> PipelineRunResponse:
        """Build CI-safe response from pipeline run."""
        # Get recommendation run if linked
        recommendation_run = None
        if pipeline_run.recommendation_run_id:
            recommendation_run = db.query(RecommendationRun).filter(
                RecommendationRun.id == pipeline_run.recommendation_run_id
            ).first()
        
        # Get release decision
        release_decision = None
        if recommendation_run:
            release_decision = db.query(ReleaseDecision).filter(
                ReleaseDecision.recommendation_run_id == recommendation_run.id
            ).first()
        
        # Get regression scope summary
        regression_scope = RegressionScopeSummary()
        required_count = 0
        if recommendation_run and recommendation_run.requirement_evidence_snapshot_json:
            try:
                import json
                snapshot = json.loads(recommendation_run.requirement_evidence_snapshot_json)
                required_count = len(snapshot.get("required_items", []))
                regression_scope.required = required_count
                regression_scope.recommended = len(snapshot.get("recommended_items", []))
                regression_scope.optional = len(snapshot.get("optional_items", []))
                regression_scope.safe_to_skip = len(snapshot.get("safe_to_skip_items", []))
                regression_scope.total_executable = (
                    regression_scope.required + 
                    regression_scope.recommended + 
                    regression_scope.optional
                )
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Get changed files count
        changed_files = 0
        if pipeline_run.pull_request_id:
            pr = db.query(PullRequest).filter(PullRequest.id == pipeline_run.pull_request_id).first()
            if pr:
                changed_files = pr.changed_files_count
        
        # Build summary
        summary = QualityGateService.get_summary_text(
            pipeline_run.quality_gate,
            required_count
        )
        
        return PipelineRunResponse(
            pipeline_run_id=pipeline_run.id,
            recommendation_run_id=pipeline_run.recommendation_run_id,
            quality_gate=pipeline_run.quality_gate,
            release_decision=release_decision.decision_status if release_decision else None,
            recommendation_health=recommendation_run.evidence_health_status if recommendation_run else None,
            required_before_release=required_count,
            regression_scope=regression_scope,
            changed_files=changed_files,
            summary=summary,
            status=pipeline_run.status,
            created_at=pipeline_run.created_at
        )
    
    @staticmethod
    def get_artifact(db: Session, pipeline_run_id: uuid.UUID) -> Dict[str, Any]:
        """Generate CI-safe artifact JSON."""
        pipeline_run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
        if not pipeline_run:
            raise ValueError(f"Pipeline run {pipeline_run_id} not found")
        
        response = PipelineRunService._build_response(db, pipeline_run)
        
        # Get PR number
        pr_number = None
        if pipeline_run.pull_request_id:
            pr = db.query(PullRequest).filter(PullRequest.id == pipeline_run.pull_request_id).first()
            if pr:
                pr_number = pr.number
        
        return {
            "recommendation_run_id": str(response.recommendation_run_id) if response.recommendation_run_id else None,
            "pipeline_run_id": str(response.pipeline_run_id),
            "pull_request_number": pr_number,
            "commit_sha": pipeline_run.commit_sha,
            "changed_files": response.changed_files,
            "recommendation_health": response.recommendation_health,
            "release_decision": response.release_decision,
            "required_before_release": response.required_before_release,
            "regression_scope": response.regression_scope.dict(),
            "quality_gate": response.quality_gate,
            "timestamp": datetime.utcnow().isoformat()
        }
