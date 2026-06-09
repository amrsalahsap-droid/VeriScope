from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.debugging import RecommendationDebugResponse
from app.services.recommendation import RecommendationService
from app.dependencies.auth import get_current_workspace_id

router = APIRouter(prefix="/recommendations", tags=["Diagnostics"])

@router.get("/{id}/debug", response_model=RecommendationDebugResponse)
def get_debug_chain(id: UUID, db: Session = Depends(get_db)):
    """Retrieve detailed explainability data and forensic audit logs for a recommendation."""
    service = RecommendationService(db)
    return service.get_debug_chain(id)


@router.get("/{id}/external-context-debug")
def get_external_context_debug(
    id: UUID,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace_id)
):
    """
    Retrieve external context integration debug information.
    
    Returns linked issue detection, fetched work items, extracted AC,
    external test cases, mapping confidence, sync errors, and requirement coverage decisions.
    
    Internal/dev only, workspace scoped, no secrets.
    """
    from app.models.recommendation import RecommendationRun, RecommendationInputSnapshot
    from app.models.external_work_item import ExternalWorkItem
    from app.models.pull_request_work_item_link import PullRequestWorkItemLink
    from app.models.acceptance_criterion import AcceptanceCriterion
    from app.models.external_test_case_detailed import ExternalTestCase
    from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
    from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping
    from app.models.integration_connection import IntegrationConnection
    
    # Get recommendation run
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == id,
        RecommendationRun.workspace_id == UUID(workspace_id)
    ).first()
    
    if not run:
        raise HTTPException(status_code=404, detail="Recommendation run not found")
    
    # Get input snapshot
    snapshot = db.query(RecommendationInputSnapshot).filter(
        RecommendationInputSnapshot.recommendation_run_id == id
    ).first()
    
    # Linked issue detection
    linked_issue_detection = {
        "detected_keys": [],
        "linked_count": 0,
        "detection_method": "PR_WORK_ITEM_LINKER"
    }
    
    if run.pull_request_id:
        from app.services.pr_work_item_linker import PRWorkItemLinker
        linker = PRWorkItemLinker(db)
        
        pr = db.query(run.pull_request.__class__).filter(
            run.pull_request.__class__.id == run.pull_request_id
        ).first()
        if pr:
            detected_keys = linker.detect_work_item_keys(
                pr_title=pr.title,
                pr_description=getattr(pr, "description", None) or getattr(pr, "body", None) or "",
                branch_name=getattr(pr, "branch_name", None) or getattr(pr, "source_branch", None) or "",
                commit_messages=[]
            )
            linked_issue_detection["detected_keys"] = detected_keys
            
            work_item_links = db.query(PullRequestWorkItemLink).filter(
                PullRequestWorkItemLink.pull_request_id == run.pull_request_id
            ).all()
            linked_issue_detection["linked_count"] = len(work_item_links)
    
    # Fetched work items
    fetched_work_items = []
    if snapshot and snapshot.linked_work_items:
        fetched_work_items = snapshot.linked_work_items
    
    # Extracted AC
    extracted_ac = []
    if snapshot and snapshot.acceptance_criteria:
        extracted_ac = snapshot.acceptance_criteria
    
    # External test cases
    external_test_cases = []
    if snapshot and snapshot.external_test_cases:
        external_test_cases = snapshot.external_test_cases
    
    # Mapping confidence
    mapping_confidence = {
        "work_item_to_behavior_mappings": 0,
        "test_case_to_scenario_mappings": 0,
        "avg_confidence": 0.0
    }
    
    if run.repository_id:
        work_item_mappings = db.query(WorkItemBehaviorMapping).join(
            ExternalWorkItem,
            WorkItemBehaviorMapping.external_work_item_id == ExternalWorkItem.id
        ).filter(
            ExternalWorkItem.repository_id == run.repository_id
        ).count()
        
        test_case_mappings = db.query(ExternalTestScenarioMapping).join(
            ExternalTestCase,
            ExternalTestScenarioMapping.external_test_case_id == ExternalTestCase.id
        ).filter(
            ExternalTestCase.repository_id == run.repository_id
        ).count()
        
        mapping_confidence["work_item_to_behavior_mappings"] = work_item_mappings
        mapping_confidence["test_case_to_scenario_mappings"] = test_case_mappings
        mapping_confidence["avg_confidence"] = 0.7 if (work_item_mappings > 0 or test_case_mappings > 0) else 0.0
    
    # Sync errors
    sync_errors = []
    if snapshot and snapshot.integration_sync_status:
        for status in snapshot.integration_sync_status:
            if status.get("sync_status") in ("FAILURE", "PARTIAL_SUCCESS"):
                sync_errors.append({
                    "provider": status.get("provider"),
                    "sync_status": status.get("sync_status"),
                    "errors": status.get("errors", []),
                    "last_synced_at": status.get("last_synced_at")
                })
    
    # Requirement coverage decisions
    requirement_coverage_decisions = []
    if snapshot and snapshot.external_requirement_coverage:
        requirement_coverage_decisions = snapshot.external_requirement_coverage
    
    # Integration connections
    integration_connections = []
    if run.repository_id:
        connections = db.query(IntegrationConnection).filter(
            IntegrationConnection.repository_id == run.repository_id,
            IntegrationConnection.is_active == True
        ).all()
        
        for conn in connections:
            integration_connections.append({
                "provider": conn.provider,
                "is_active": conn.is_active,
                "last_synced_at": conn.last_synced_at.isoformat() if conn.last_synced_at else None,
                "config_keys": list(conn.config.keys()) if conn.config else []
            })
    
    return {
        "recommendation_run_id": str(id),
        "repository_id": str(run.repository_id),
        "pull_request_id": str(run.pull_request_id) if run.pull_request_id else None,
        "linked_issue_detection": linked_issue_detection,
        "fetched_work_items": fetched_work_items,
        "extracted_ac": extracted_ac,
        "external_test_cases": external_test_cases,
        "mapping_confidence": mapping_confidence,
        "sync_errors": sync_errors,
        "requirement_coverage_decisions": requirement_coverage_decisions,
        "integration_connections": integration_connections,
        "external_context_gaps": snapshot.external_context_gaps if snapshot else []
    }
