from typing import Optional, List
from uuid import UUID
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies.auth import get_current_workspace, require_workspace_member
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.journey_behavior import JourneyBehavior
from app.services.intelligence_dashboard import IntelligenceDashboardService
from app.services.github_app import GitHubAppService
from app.services.behavior_discovery_refresh_pipeline import BehaviorDiscoveryRefreshPipeline
from app.services.journey_discovery_engine import JourneyDiscoveryEngine
from app.services.repository_readiness import RepositoryReadinessService
from app.services.recommendation_readiness_service import RecommendationReadinessService

logger = logging.getLogger("veriscope.intelligence_refresh")

router = APIRouter(
    prefix="/api/intelligence",
    tags=["Intelligence Dashboard"],
    dependencies=[Depends(require_workspace_member())],
)


@router.get("/dashboard")
def get_intelligence_dashboard(
    repository_id: Optional[UUID] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """
    Aggregate and return the Intelligence Dashboard data for the current workspace.

    Optionally filter to a single repository via `repository_id`.
    Returns HTTP 403 if `repository_id` does not belong to the authenticated workspace.
    Returns HTTP 200 with empty/zero values when no runs exist in the lookback window.
    """
    service = IntelligenceDashboardService(db)
    return service.aggregate_dashboard(
        workspace_id=workspace.id,
        repository_id=repository_id,
    )


# APIRouter for /intelligence without /api prefix
intelligence_refresh_router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence Refresh"],
    dependencies=[Depends(require_workspace_member())]
)

class RefreshRequest(BaseModel):
    include_architecture: bool = True
    include_behaviors: bool = True
    include_journeys: bool = True

@intelligence_refresh_router.post("/repositories/{repository_id}/refresh")
def refresh_repository_intelligence(
    repository_id: UUID,
    payload: RefreshRequest,
    db: Session = Depends(get_db)
):
    # 1. Lookup repository
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error_code": "REPOSITORY_NOT_FOUND",
                "message": "Repository not found.",
                "recoverable": False
            }
        )
    
    if not repo.is_active or not repo.installation_id:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error_code": "REPOSITORY_NOT_CONNECTED",
                "message": "Repository is not connected to GitHub App. Connect repository first.",
                "recoverable": True,
                "next_action": "CONNECT_REPOSITORY"
            }
        )
    
    # 2. Source sync validation
    if not repo.last_synced_at or repo.latest_sync_status == "FAILED":
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error_code": "SOURCE_NOT_SYNCED",
                "message": "Repository source files are not synced yet. Sync repository before running intelligence.",
                "recoverable": True,
                "next_action": "SYNC_REPOSITORY"
            }
        )
    
    partial_failures = []
    architecture_graph_status = "SKIPPED"
    behaviors_discovered = 0
    journeys_discovered = 0
    
    # Step 1: Architecture graph refresh
    if payload.include_architecture:
        try:
            service = GitHubAppService(db)
            service.sync_repository_architecture(repo.id, repo.installation_id)
            architecture_graph_status = "AVAILABLE"
        except Exception as e:
            logger.exception(f"Architecture refresh failed for repository {repository_id}: {e}")
            partial_failures.append("ARCHITECTURE_REFRESH_FAILED")
            architecture_graph_status = "FAILED"
            
    # Step 2: Behavior discovery refresh
    if payload.include_behaviors:
        if "ARCHITECTURE_REFRESH_FAILED" in partial_failures:
            partial_failures.append("BEHAVIOR_DISCOVERY_SKIPPED")
        else:
            try:
                pipeline = BehaviorDiscoveryRefreshPipeline(db)
                result = pipeline.trigger_manual_refresh(repo)
                if not result.success:
                    partial_failures.append("BEHAVIOR_DISCOVERY_FAILED")
                else:
                    behaviors_discovered = result.behaviors_discovered
            except Exception as e:
                logger.exception(f"Behavior discovery failed for repository {repository_id}: {e}")
                partial_failures.append("BEHAVIOR_DISCOVERY_FAILED")
                
    # Step 3: Journey discovery refresh
    if payload.include_journeys:
        if "BEHAVIOR_DISCOVERY_FAILED" in partial_failures or "BEHAVIOR_DISCOVERY_SKIPPED" in partial_failures:
            partial_failures.append("JOURNEY_DISCOVERY_SKIPPED")
        else:
            try:
                # Load behaviors
                behaviors = db.query(Behavior).filter(
                    Behavior.repository_id == repo.id,
                    Behavior.is_deleted == False
                ).all()
                
                if behaviors:
                    journey_engine = JourneyDiscoveryEngine(db)
                    candidates = journey_engine.discover_journeys(behaviors, str(repo.id))
                    
                    # Persist discovered journeys
                    journeys_created = 0
                    for candidate in candidates:
                        existing_journey = db.query(Journey).filter(
                            Journey.repository_id == repo.id,
                            Journey.name == candidate.name,
                            Journey.is_deleted == False
                        ).first()
                        
                        if existing_journey:
                            existing_journey.description = candidate.description
                            existing_journey.risk_level = candidate.risk_level
                            existing_journey.business_value = candidate.business_value
                            existing_journey.updated_at = datetime.utcnow()
                            journey = existing_journey
                        else:
                            import uuid
                            journey = Journey(
                                id=uuid.uuid4(),
                                repository_id=repo.id,
                                name=candidate.name,
                                slug=candidate.name.lower().replace(" ", "-"),
                                description=candidate.description,
                                risk_level=candidate.risk_level,
                                business_value=candidate.business_value,
                                is_deleted=False,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            db.add(journey)
                            journeys_created += 1
                            
                        # Flush to get journey ID if new
                        db.flush()
                        
                        # Create journey-behavior mappings
                        for behavior_name in candidate.behaviors:
                            behavior = db.query(Behavior).filter(
                                Behavior.repository_id == repo.id,
                                Behavior.name == behavior_name,
                                Behavior.is_deleted == False
                            ).first()
                            
                            if not behavior:
                                continue
                            
                            existing_mapping = db.query(JourneyBehavior).filter(
                                JourneyBehavior.journey_id == journey.id,
                                JourneyBehavior.behavior_id == behavior.id
                            ).first()
                            
                            if not existing_mapping:
                                import uuid
                                mapping = JourneyBehavior(
                                    id=uuid.uuid4(),
                                    journey_id=journey.id,
                                    behavior_id=behavior.id,
                                    relationship_type="PART_OF",
                                    confidence="HIGH"
                                )
                                db.add(mapping)
                    db.commit()
                    journeys_discovered = journeys_created
            except Exception as e:
                logger.exception(f"Journey discovery failed for repository {repository_id}: {e}")
                partial_failures.append("JOURNEY_DISCOVERY_FAILED")
                
    # Step 4: Recalculate readiness
    try:
        # Recalculate repository readiness
        repo_readiness_svc = RepositoryReadinessService(db)
        repo_readiness_svc.calculate_readiness(repo.id, repo.workspace_id)
        
        # Recalculate recommendation readiness
        rec_readiness_svc = RecommendationReadinessService(db)
        rec_readiness_svc.assess_readiness(repository_id=repo.id)
    except Exception as e:
        logger.exception(f"Readiness recalculation failed for repository {repository_id}: {e}")
        partial_failures.append("READINESS_RECALCULATION_FAILED")
        
    return {
        "success": len(partial_failures) < 3,
        "architecture_graph_status": architecture_graph_status,
        "behaviors_discovered": behaviors_discovered,
        "journeys_discovered": journeys_discovered,
        "partial_failures": partial_failures,
        "message": "Repository intelligence refreshed successfully." if not partial_failures else "Repository intelligence refreshed with partial errors."
    }
