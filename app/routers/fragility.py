import uuid
import logging
import threading
from uuid import UUID
from typing import List, Set, Optional
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.schemas.fragility import (
    FragilityPatternListItem,
    EvidenceLinkDetail,
    FragilityPatternDetailResponse,
    FragilityRecalculateRequest,
)
from app.dependencies.auth import require_workspace_member, get_current_workspace
from app.models.user import Workspace

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/fragility", 
    tags=["Fragility"],
    dependencies=[Depends(require_workspace_member())]
)
internal_router = APIRouter(prefix="/internal/fragility", tags=["Fragility Internal"])

# Deduplication store
_recalculating_lock = threading.Lock()
_recalculating_repos: Set[UUID] = set()


@router.get("/{repository_id}", response_model=List[FragilityPatternListItem])
def get_active_patterns(repository_id: UUID, db: Session = Depends(get_db)):
    """Retrieve all active fragility patterns for a given repository."""
    # Verify repository exists
    from app.models.repository import Repository
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repository_id} not found."
        )

    patterns = db.query(FragilityPattern).filter(
        FragilityPattern.repository_id == repository_id,
        FragilityPattern.status == "ACTIVE"
    ).all()

    return [
        FragilityPatternListItem(
            pattern_id=p.id,
            pattern_type=p.pattern_type,
            normalized_pattern_key=p.normalized_pattern_key,
            title=p.title,
            explanation=p.explanation,
            risk_level=p.risk_level,
            evidence_count=p.evidence_count,
            incident_count=p.incident_count,
            last_seen_at=p.last_seen_at
        )
        for p in patterns
    ]


@router.get("/{repository_id}/{pattern_id}", response_model=FragilityPatternDetailResponse)
def get_pattern_detail(
    repository_id: UUID,
    pattern_id: UUID,
    db: Session = Depends(get_db)
):
    """Retrieve full pattern details, including evidence links, failures, incidents, and recommendations."""
    # Verify repository exists
    from app.models.repository import Repository
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repository_id} not found."
        )

    pattern = db.query(FragilityPattern).filter(
        FragilityPattern.id == pattern_id,
        FragilityPattern.repository_id == repository_id
    ).first()

    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fragility pattern with ID {pattern_id} not found for this repository."
        )

    # Resolve evidence links
    evidence_links = db.query(FragilityEvidenceLink).filter(
        FragilityEvidenceLink.fragility_pattern_id == pattern.id
    ).all()

    # Extract linked subcategories
    linked_failures = []
    linked_incidents = []
    linked_recommendations = []

    for link in evidence_links:
        if link.evidence_type == "TEST_FAILURE" or link.source_test_run_id:
            linked_failures.append({
                "source_test_run_id": str(link.source_test_run_id) if link.source_test_run_id else None,
                "source_test_result_id": str(link.source_test_result_id) if link.source_test_result_id else None,
                "evidence_summary": link.evidence_summary
            })
        if link.evidence_type == "INCIDENT" or link.source_incident_id:
            linked_incidents.append({
                "source_incident_id": link.source_incident_id,
                "evidence_summary": link.evidence_summary
            })
        if link.source_recommendation_run_id:
            linked_recommendations.append({
                "source_recommendation_run_id": str(link.source_recommendation_run_id),
                "evidence_summary": link.evidence_summary
            })

    return FragilityPatternDetailResponse(
        id=pattern.id,
        repository_id=pattern.repository_id,
        pattern_type=pattern.pattern_type,
        normalized_pattern_key=pattern.normalized_pattern_key,
        title=pattern.title,
        explanation=pattern.explanation,
        fragility_score=pattern.fragility_score,
        risk_level=pattern.risk_level,
        status=pattern.status,
        confidence_level=pattern.confidence_level,
        pattern_hash=pattern.pattern_hash,
        score_components=pattern.score_components or {},
        replayable_evidence_snapshot=pattern.replayable_evidence_snapshot or {},
        invalidated_reason=pattern.invalidated_reason,
        invalidated_at=pattern.invalidated_at,
        invalidated_by=pattern.invalidated_by,
        fragility_generation_version=pattern.fragility_generation_version,
        scoring_formula_version=pattern.scoring_formula_version,
        evidence_count=pattern.evidence_count,
        incident_count=pattern.incident_count,
        related_failure_count=pattern.related_failure_count,
        context=pattern.context or {},
        first_seen_at=pattern.first_seen_at,
        last_seen_at=pattern.last_seen_at,
        created_at=pattern.created_at,
        updated_at=pattern.updated_at,
        
        evidence_links=[
            EvidenceLinkDetail(
                id=link.id,
                evidence_type=link.evidence_type,
                evidence_summary=link.evidence_summary,
                source_test_run_id=link.source_test_run_id,
                source_test_result_id=link.source_test_result_id,
                source_incident_id=link.source_incident_id,
                source_recommendation_run_id=link.source_recommendation_run_id,
                source_pull_request_id=link.source_pull_request_id,
                created_at=link.created_at
            )
            for link in evidence_links
        ],
        linked_failures=linked_failures,
        linked_incidents=linked_incidents,
        linked_recommendations=linked_recommendations
    )


@internal_router.post("/recalculate", status_code=status.HTTP_200_OK)
def recalculate_fragility(
    req: FragilityRecalculateRequest,
    db: Session = Depends(get_db)
):
    """Deterministically scan and mine fragility patterns, persisting a new immutably preserved snapshot."""
    repository_id = req.repository_id
    history_window_days = req.history_window_days or 90

    # Verify repository exists
    from app.models.repository import Repository
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repository_id} not found."
        )

    # Deduplicate active recalculations
    with _recalculating_lock:
        if repository_id in _recalculating_repos:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Recalculation already in progress for repository {repository_id}."
            )
        _recalculating_repos.add(repository_id)

    try:
        # Mine patterns (recalculate)
        from app.services.fragility_memory_service import FragilityMemoryService
        from app.services.fragility_snapshot_service import FragilitySnapshotService
        
        fragility_service = FragilityMemoryService(db)
        res_mine = fragility_service.mine_fragility_patterns(
            repository_id=repository_id,
            history_window_days=history_window_days
        )
        
        # Preserve historical snapshots: generate a new snapshot
        snapshot_service = FragilitySnapshotService(db)
        snapshot = snapshot_service.generate_fragility_snapshot(
            repository_id=repository_id,
            trigger="MANUAL_RECALCULATION"
        )
        
        return {
            "status": "success",
            "repository_id": str(repository_id),
            "history_window_days": history_window_days,
            "patterns_mined": res_mine.get("patterns_mined", 0),
            "snapshot_id": str(snapshot.id),
            "snapshot_hash": snapshot.snapshot_hash
        }
    except Exception as e:
        logger.error(f"Error during fragility recalculation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recalculation failed: {str(e)}"
        )
    finally:
        with _recalculating_lock:
            _recalculating_repos.discard(repository_id)


@router.get("/{repository_id}/dashboard")
def get_fragility_dashboard(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by status: ACTIVE, STALE"),
    behavior_id: Optional[UUID] = Query(None, description="Filter by behavior ID"),
    journey_id: Optional[UUID] = Query(None, description="Filter by journey ID"),
    timeframe_days: Optional[int] = Query(None, description="Filter by timeframe in days"),
):
    """Get fragility dashboard data for a repository. Workspace-scoped."""
    from app.models.repository import Repository
    from app.services.fragility_dashboard_service import FragilityDashboardService
    
    # Verify repository exists and belongs to workspace
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repository_id} not found."
        )
    
    if repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied."
        )
    
    # Get dashboard data
    dashboard_service = FragilityDashboardService(db)
    dashboard_data = dashboard_service.get_dashboard_data(
        repository_id=repository_id,
        status_filter=status_filter,
        behavior_id=behavior_id,
        journey_id=journey_id,
        timeframe_days=timeframe_days,
    )
    
    return dashboard_data


@internal_router.get("/repositories/{repository_id}/fragility-debug")
def get_repository_fragility_debug(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get detailed fragility debug information for a repository. Internal/dev only, workspace-scoped."""
    from app.models.repository import Repository
    from app.models.fragility_memory_v2 import FragilityMemoryV2
    from app.models.fragility_evidence_event import FragilityEvidenceEvent
    
    # Verify repository exists and belongs to workspace
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repository_id} not found."
        )
    
    if repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied."
        )
    
    # Get all fragility memories
    memories = db.query(FragilityMemoryV2).filter(
        FragilityMemoryV2.repository_id == repository_id
    ).all()
    
    # Get evidence events for all memories
    memory_ids = [m.id for m in memories]
    evidence_events = []
    if memory_ids:
        evidence_events = db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id.in_(memory_ids)
        ).all()
    
    # Build evidence map
    evidence_map = {}
    for event in evidence_events:
        memory_id_str = str(event.fragility_memory_id)
        if memory_id_str not in evidence_map:
            evidence_map[memory_id_str] = []
        evidence_map[memory_id_str].append({
            "id": str(event.id),
            "evidence_type": event.evidence_type,
            "source_entity_type": event.source_entity_type,
            "source_entity_id": str(event.source_entity_id) if event.source_entity_id else None,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "context_data": event.context_data,
        })
    
    # Build memory debug data
    memories_debug = []
    for memory in memories:
        memory_id_str = str(memory.id)
        memories_debug.append({
            "id": memory_id_str,
            "memory_key": memory.memory_key,
            "memory_type": memory.memory_type,
            "subject_type": memory.subject_type,
            "subject_id": str(memory.subject_id) if memory.subject_id else None,
            "subject_name": memory.subject_name,
            "risk_level": memory.risk_level,
            "fragility_score": memory.fragility_score,
            "confidence": memory.confidence,
            "status": memory.status,
            "score_breakdown": memory.score_breakdown,
            "decay_applied": memory.decay_applied,
            "decay_factor": memory.decay_factor,
            "first_seen_at": memory.first_seen_at.isoformat() if memory.first_seen_at else None,
            "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
            "last_updated_at": memory.last_updated_at.isoformat() if memory.last_updated_at else None,
            "evidence_events": evidence_map.get(memory_id_str, []),
            "evidence_count": len(evidence_map.get(memory_id_str, [])),
        })
    
    return {
        "repository_id": str(repository_id),
        "total_memories": len(memories),
        "memories": memories_debug,
        "total_evidence_events": len(evidence_events),
    }


@internal_router.get("/recommendations/{recommendation_run_id}/fragility-debug")
def get_recommendation_fragility_debug(
    recommendation_run_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get detailed fragility debug information for a recommendation run. Internal/dev only, workspace-scoped."""
    from app.models.recommendation import RecommendationRun
    from app.models.repository import Repository
    from app.models.fragility_pattern import FragilitySnapshot
    
    # Verify recommendation run exists and belongs to workspace
    run = db.query(RecommendationRun).filter(
        RecommendationRun.id == recommendation_run_id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation run with ID {recommendation_run_id} not found."
        )
    
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo or repo.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied."
        )
    
    # Get fragility snapshot for this run
    snapshot = db.query(FragilitySnapshot).filter(
        FragilitySnapshot.repository_id == run.repository_id,
        FragilitySnapshot.recommendation_run_id == recommendation_run_id
    ).first()
    
    if not snapshot:
        # Try to get the latest snapshot for the repository
        snapshot = db.query(FragilitySnapshot).filter(
            FragilitySnapshot.repository_id == run.repository_id
        ).order_by(FragilitySnapshot.generated_at.desc()).first()
    
    if not snapshot:
        return {
            "recommendation_run_id": str(recommendation_run_id),
            "repository_id": str(run.repository_id),
            "snapshot": None,
            "message": "No fragility snapshot found for this recommendation run or repository.",
        }
    
    # Get changed files from the run
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
    
    # Analyze which signals were applied vs skipped
    metadata = snapshot.snapshot_metadata or {}
    v2_metadata = metadata.get("v2", {})
    
    behavior_fragility = v2_metadata.get("behavior_fragility", [])
    journey_fragility = v2_metadata.get("journey_fragility", [])
    scenario_fragility = v2_metadata.get("scenario_fragility", [])
    file_hotspots = v2_metadata.get("file_hotspots", [])
    risky_combinations = v2_metadata.get("risky_combinations", [])
    
    # Determine applied signals (those related to changed files or impact)
    applied_signals = []
    skipped_signals = []
    
    changed_files_set = set(changed_files) if changed_files else set()
    
    # Check file hotspots
    for hotspot in file_hotspots:
        file_path = hotspot.get("subject_name", "")
        if file_path and any(file_path in cf or cf in file_path for cf in changed_files_set):
            applied_signals.append({
                "type": "file_hotspot",
                "subject": file_path,
                "score": hotspot.get("fragility_score"),
                "reason": "File changed matches hotspot",
            })
        else:
            skipped_signals.append({
                "type": "file_hotspot",
                "subject": file_path,
                "score": hotspot.get("fragility_score"),
                "reason": "File not changed in this PR",
            })
    
    # Check risky combinations
    for combo in risky_combinations:
        combo_subject = combo.get("subject_name", "")
        if any(cf in combo_subject for cf in changed_files_set):
            applied_signals.append({
                "type": "risky_combination",
                "subject": combo_subject,
                "score": combo.get("fragility_score"),
                "reason": "Combination involves changed files",
            })
        else:
            skipped_signals.append({
                "type": "risky_combination",
                "subject": combo_subject,
                "score": combo.get("fragility_score"),
                "reason": "Combination does not involve changed files",
            })
    
    # Calculate scoring contribution
    total_applied_score = sum(s.get("score", 0) for s in applied_signals)
    total_skipped_score = sum(s.get("score", 0) for s in skipped_signals)
    
    return {
        "recommendation_run_id": str(recommendation_run_id),
        "repository_id": str(run.repository_id),
        "snapshot": {
            "id": str(snapshot.id),
            "snapshot_hash": snapshot.snapshot_hash,
            "generated_at": snapshot.generated_at.isoformat() if snapshot.generated_at else None,
            "metadata": metadata,
        },
        "changed_files": changed_files,
        "applied_signals": applied_signals,
        "skipped_signals": skipped_signals,
        "scoring_contribution": {
            "total_applied_score": total_applied_score,
            "total_skipped_score": total_skipped_score,
            "applied_count": len(applied_signals),
            "skipped_count": len(skipped_signals),
        },
        "evidence_links": {
            "behavior_fragility_count": len(behavior_fragility),
            "journey_fragility_count": len(journey_fragility),
            "scenario_fragility_count": len(scenario_fragility),
            "file_hotspots_count": len(file_hotspots),
            "risky_combinations_count": len(risky_combinations),
        },
    }
