from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import math

from app.db.session import get_db
from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey import Journey
from app.models.repository import Repository
from app.schemas.behavior import (
    BehaviorSchema,
    BehaviorDetailSchema,
    BehaviorRiskSchema,
    BehaviorEvidenceSchema,
    BehaviorScenarioSchema,
    JourneySchema,
    JourneyDetailSchema,
    PaginatedResponse,
)
from app.schemas.behavior_diagnostics import BehaviorDiagnosticsResponse
from app.services.behavior_diagnostics_service import BehaviorDiagnosticsService

router = APIRouter()


@router.get("/repositories/{repository_id}/behaviors", response_model=PaginatedResponse)
def get_behaviors(
    repository_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    journey_id: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all behaviors for a repository with pagination and filtering."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Build query
    query = db.query(Behavior).filter(
        Behavior.repository_id == repository_id,
        Behavior.is_deleted == False,
    )
    
    # Apply filters
    if journey_id:
        query = query.filter(Behavior.journey_id == journey_id)
    if risk_level:
        query = query.filter(Behavior.risk_level == risk_level)
    if status:
        query = query.filter(Behavior.status == status)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    behaviors = query.order_by(Behavior.created_at.desc()).offset(offset).limit(page_size).all()
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    return PaginatedResponse(
        items=[BehaviorSchema.model_validate(b) for b in behaviors],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/repositories/{repository_id}/behaviors/{behavior_id}", response_model=BehaviorDetailSchema)
def get_behavior(
    repository_id: str,
    behavior_id: str,
    db: Session = Depends(get_db),
):
    """Get a single behavior with full details including evidences and scenarios."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get behavior
    behavior = db.query(Behavior).filter(
        Behavior.id == behavior_id,
        Behavior.repository_id == repository_id,
        Behavior.is_deleted == False,
    ).first()
    
    if not behavior:
        raise HTTPException(status_code=404, detail="Behavior not found")
    
    # Get journey if exists
    journey_data = None
    if behavior.journey_id:
        journey = db.query(Journey).filter(Journey.id == behavior.journey_id).first()
        if journey:
            journey_data = {
                "id": str(journey.id),
                "name": journey.name,
                "slug": journey.slug,
            }
    
    # Get evidences
    evidences = db.query(BehaviorEvidence).filter(
        BehaviorEvidence.behavior_id == behavior_id,
    ).all()
    
    # Get scenarios
    scenarios = db.query(BehaviorScenario).filter(
        BehaviorScenario.behavior_id == behavior_id,
    ).all()
    
    # Build risk schema
    risk = BehaviorRiskSchema(
        risk_level=behavior.risk_level,
        risk_reason=behavior.risk_reason,
        risk_evidence=behavior.risk_evidence,
    )
    
    # Build response
    behavior_dict = BehaviorSchema.model_validate(behavior).model_dump()
    behavior_dict["journey"] = journey_data
    behavior_dict["risk"] = risk
    behavior_dict["evidences"] = [BehaviorEvidenceSchema.model_validate(e) for e in evidences]
    behavior_dict["scenarios"] = [BehaviorScenarioSchema.model_validate(s) for s in scenarios]
    
    return BehaviorDetailSchema(**behavior_dict)


@router.get("/repositories/{repository_id}/journeys", response_model=PaginatedResponse)
def get_journeys(
    repository_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    risk_level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all journeys for a repository with pagination and filtering."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Build query
    query = db.query(Journey).filter(Journey.repository_id == repository_id)
    
    # Apply filters
    if risk_level:
        query = query.filter(Journey.risk_level == risk_level)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    journeys = query.order_by(Journey.created_at.desc()).offset(offset).limit(page_size).all()
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    return PaginatedResponse(
        items=[JourneySchema.model_validate(j) for j in journeys],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/repositories/{repository_id}/journeys/{journey_id}", response_model=JourneyDetailSchema)
def get_journey(
    repository_id: str,
    journey_id: str,
    db: Session = Depends(get_db),
):
    """Get a single journey with its behaviors."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get journey
    journey = db.query(Journey).filter(
        Journey.id == journey_id,
        Journey.repository_id == repository_id,
    ).first()
    
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    
    # Get behaviors for this journey
    behaviors = db.query(Behavior).filter(
        Behavior.journey_id == journey_id,
        Behavior.is_deleted == False,
    ).all()
    
    # Build response
    journey_dict = JourneySchema.model_validate(journey).model_dump()
    journey_dict["behaviors"] = [BehaviorSchema.model_validate(b) for b in behaviors]
    
    return JourneyDetailSchema(**journey_dict)


@router.get("/repositories/{repository_id}/behaviors/diagnostics", response_model=BehaviorDiagnosticsResponse)
def get_behavior_diagnostics(
    repository_id: str,
    db: Session = Depends(get_db),
):
    """Get behavior discovery diagnostics for a repository."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get diagnostics
    diagnostics_service = BehaviorDiagnosticsService(db)
    diagnostics = diagnostics_service.get_diagnostics(repository_id)
    
    return diagnostics


@router.get("/repositories/{repository_id}/journeys/health")
def get_journey_health(
    repository_id: str,
    db: Session = Depends(get_db),
):
    """Get journey health summary for a repository."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get all journeys for the repository
    journeys = db.query(Journey).filter(
        Journey.repository_id == repository_id,
        Journey.is_deleted == False,
    ).all()
    
    # Build journey health data
    journey_health_list = []
    for journey in journeys:
        # Get behaviors for this journey
        behaviors = db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.journey_id == journey.id,
            Behavior.is_deleted == False,
        ).all()
        
        # Calculate coverage score (simplified - in production use actual coverage data)
        coverage_score = 65.0  # Placeholder - would come from coverage analyzer
        
        # Determine testing health based on coverage
        if coverage_score >= 80:
            testing_health = "HEALTHY"
        elif coverage_score >= 50:
            testing_health = "WARNING"
        else:
            testing_health = "CRITICAL"
        
        journey_health_list.append({
            "id": str(journey.id),
            "name": journey.name,
            "slug": journey.slug,
            "risk_level": journey.risk_level,
            "coverage_score": coverage_score,
            "behavior_count": len(behaviors),
            "testing_health": testing_health,
            "status": journey.status,
            "description": journey.description or "",
            "business_value": journey.business_value or "",
        })
    
    return {
        "journeys": journey_health_list,
        "total_journeys": len(journey_health_list),
    }


@router.get("/repositories/{repository_id}/journeys/{journey_id}/details")
def get_journey_details(
    repository_id: str,
    journey_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information for a specific journey."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get journey
    journey = db.query(Journey).filter(
        Journey.id == journey_id,
        Journey.repository_id == repository_id,
        Journey.is_deleted == False,
    ).first()
    
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    
    # Get behaviors for this journey
    behaviors = db.query(Behavior).filter(
        Behavior.repository_id == repository_id,
        Behavior.journey_id == journey.id,
        Behavior.is_deleted == False,
    ).all()
    
    # Get scenarios for behaviors
    behavior_ids = [b.id for b in behaviors]
    scenarios = db.query(BehaviorScenario).filter(
        BehaviorScenario.behavior_id.in_(behavior_ids),
    ).all()
    
    # Build behavior list with coverage
    behavior_list = []
    for behavior in behaviors:
        behavior_list.append({
            "name": behavior.name,
            "risk_level": behavior.risk_level,
            "coverage": 75.0,  # Placeholder - would come from coverage analyzer
        })
    
    # Build coverage breakdown
    covered = [b.name for b in behaviors if b.risk_level in ["LOW", "MEDIUM"]]
    partially_covered = [b.name for b in behaviors if b.risk_level == "HIGH"]
    uncovered = [b.name for b in behaviors if b.risk_level == "CRITICAL"]
    
    # Build risks
    risks = []
    for behavior in behaviors:
        if behavior.risk_level in ["HIGH", "CRITICAL"]:
            risks.append(f"{behavior.name} has {behavior.risk_level} risk")
    
    return {
        "behaviors": behavior_list,
        "coverage": {
            "covered": covered,
            "partially_covered": partially_covered,
            "uncovered": uncovered,
        },
        "scenarios": len(scenarios),
        "risks": risks,
    }

