"""
Regression Suite API Router

API endpoints for managing regression suites and scope items.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.regression_suite import (
    RegressionSuite, RegressionScopeItem, ScopeOverride,
    SuiteStatus, ScopeTier, ScopePriority, OverrideType, ExecutionStatus
)
from app.models.recommendation import RecommendationRun, SuggestedTestScenario
from app.models.test_result import TestCase
from app.models.external_test_case_detailed import ExternalTestCase
from app.services.regression_suite_builder import RegressionSuiteBuilder

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/recommendations/{recommendation_run_id}/regression-suite")
def create_regression_suite_from_recommendation(
    recommendation_run_id: uuid.UUID,
    created_by: Optional[str] = Query(None),
    force_new: bool = Query(False),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a regression suite from a recommendation run.
    
    Args:
        recommendation_run_id: UUID of the recommendation run
        created_by: Optional user who created the suite
        force_new: If True, create a new suite even if one exists
        db: Database session
        
    Returns:
        Created regression suite details
    """
    try:
        suite_summary = RegressionSuiteBuilder.create_from_recommendation_run(
            db=db,
            recommendation_run_id=recommendation_run_id,
            created_by=created_by,
            force_new=force_new
        )
        
        return suite_summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating regression suite: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create regression suite: {str(e)}")


@router.get("/api/regression-suites/{suite_id}")
def get_regression_suite(
    suite_id: uuid.UUID,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get regression suite details.
    
    Args:
        suite_id: UUID of the regression suite
        db: Database session
        
    Returns:
        Regression suite details
    """
    suite = db.query(RegressionSuite).filter(
        RegressionSuite.id == suite_id
    ).first()
    
    if not suite:
        raise HTTPException(status_code=404, detail="Regression suite not found")
    
    return {
        "id": str(suite.id),
        "repository_id": str(suite.repository_id),
        "release_id": str(suite.release_id) if suite.release_id else None,
        "pull_request_id": str(suite.pull_request_id) if suite.pull_request_id else None,
        "recommendation_run_id": str(suite.recommendation_run_id) if suite.recommendation_run_id else None,
        "name": suite.name,
        "description": suite.description,
        "suite_type": suite.suite_type,
        "status": suite.status,
        "confidence_level": suite.confidence_level,
        "scope_score": suite.scope_score,
        "created_by": suite.created_by,
        "created_at": suite.created_at.isoformat() if suite.created_at else None,
        "updated_at": suite.updated_at.isoformat() if suite.updated_at else None,
        "is_active": suite.is_active,
        "scope_items_count": len(suite.scope_items)
    }


@router.get("/api/regression-suites/{suite_id}/scope")
def get_regression_suite_scope(
    suite_id: uuid.UUID,
    tier: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get scope items for a regression suite.
    
    Args:
        suite_id: UUID of the regression suite
        tier: Optional filter by tier
        item_type: Optional filter by item type
        db: Database session
        
    Returns:
        Scope items grouped by tier
    """
    suite = db.query(RegressionSuite).filter(
        RegressionSuite.id == suite_id
    ).first()
    
    if not suite:
        raise HTTPException(status_code=404, detail="Regression suite not found")
    
    query = db.query(RegressionScopeItem).filter(
        RegressionScopeItem.regression_suite_id == suite_id
    )
    
    if tier:
        query = query.filter(RegressionScopeItem.tier == tier)
    
    if item_type:
        query = query.filter(RegressionScopeItem.item_type == item_type)
    
    scope_items = query.all()
    
    # Build response with test details
    items_response = []
    for item in scope_items:
        # Get override history for this item
        overrides = db.query(ScopeOverride).filter(
            ScopeOverride.regression_scope_item_id == item.id
        ).order_by(ScopeOverride.overridden_at.desc()).all()
        
        override_history = []
        for override in overrides:
            override_history.append({
                "id": str(override.id),
                "override_type": override.override_type,
                "original_value": override.original_value,
                "new_value": override.new_value,
                "reason": override.reason,
                "overridden_by": override.overridden_by,
                "overridden_at": override.overridden_at.isoformat() if override.overridden_at else None
            })
        
        item_data = {
            "id": str(item.id),
            "regression_suite_id": str(item.regression_suite_id),
            "item_type": item.item_type,
            "tier": item.tier,
            "priority": item.priority,
            "selection_reason": item.selection_reason,
            "evidence_summary": item.evidence_summary,
            "execution_status": item.execution_status,
            "coverage_status": item.coverage_status,
            "is_excluded": item.is_excluded,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "override_history": override_history,
            "has_overrides": len(override_history) > 0
        }
        
        # Add test details based on type
        if item.test_case_id:
            test_case = db.query(TestCase).filter(TestCase.id == item.test_case_id).first()
            if test_case:
                item_data["test_case"] = {
                    "id": str(test_case.id),
                    "stable_identity": test_case.stable_identity,
                    "test_name": test_case.test_name,
                    "suite_name": test_case.suite_name
                }
        
        if item.external_test_case_id:
            external_test = db.query(ExternalTestCase).filter(
                ExternalTestCase.id == item.external_test_case_id
            ).first()
            if external_test:
                item_data["external_test_case"] = {
                    "id": str(external_test.id),
                    "title": external_test.title,
                    "provider": external_test.provider,
                    "external_key": external_test.external_key
                }
        
        if item.suggested_scenario_id:
            scenario = db.query(SuggestedTestScenario).filter(
                SuggestedTestScenario.id == item.suggested_scenario_id
            ).first()
            if scenario:
                item_data["suggested_scenario"] = {
                    "id": str(scenario.id),
                    "title": scenario.title,
                    "impacted_area": scenario.impacted_area,
                    "testing_type": scenario.testing_type
                }
        
        # Add business context
        if item.behavior_id:
            from app.models.behavior import Behavior
            behavior = db.query(Behavior).filter(Behavior.id == item.behavior_id).first()
            if behavior:
                item_data["behavior"] = {
                    "id": str(behavior.id),
                    "name": behavior.name,
                    "risk_level": behavior.risk_level
                }
        
        if item.journey_id:
            from app.models.journey import Journey
            journey = db.query(Journey).filter(Journey.id == item.journey_id).first()
            if journey:
                item_data["journey"] = {
                    "id": str(journey.id),
                    "name": journey.name,
                    "risk_level": journey.risk_level
                }
        
        items_response.append(item_data)
    
    # Group by tier
    grouped = {
        "MUST_RUN": [],
        "SHOULD_RUN": [],
        "OPTIONAL": [],
        "EXCLUDED": []
    }
    
    for item in items_response:
        if item["is_excluded"]:
            grouped["EXCLUDED"].append(item)
        else:
            tier = item["tier"]
            if tier in grouped:
                grouped[tier].append(item)
    
    return {
        "suite_id": str(suite.id),
        "total_items": len(items_response),
        "grouped_by_tier": grouped,
        "all_items": items_response
    }


@router.patch("/api/regression-suites/{suite_id}/scope/{item_id}")
def update_scope_item(
    suite_id: uuid.UUID,
    item_id: uuid.UUID,
    tier: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    is_excluded: Optional[bool] = Query(None),
    execution_status: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update a scope item (tier, priority, exclusion, execution status).
    
    Args:
        suite_id: UUID of the regression suite
        item_id: UUID of the scope item
        tier: Optional new tier
        priority: Optional new priority
        is_excluded: Optional exclusion flag
        execution_status: Optional execution status
        reason: Required reason for tier or exclusion changes
        db: Database session
        
    Returns:
        Updated scope item
    """
    item = db.query(RegressionScopeItem).filter(
        RegressionScopeItem.id == item_id,
        RegressionScopeItem.regression_suite_id == suite_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Scope item not found")
    
    # Track changes for override
    changes = {}
    override_type = None
    
    if tier is not None and item.tier != tier:
        if not reason:
            raise HTTPException(status_code=400, detail="Reason is required for tier changes")
        changes["tier"] = {"original": item.tier, "new": tier}
        item.tier = tier
        override_type = OverrideType.TIER_CHANGED
    
    if priority is not None and item.priority != priority:
        if not reason:
            raise HTTPException(status_code=400, detail="Reason is required for priority changes")
        changes["priority"] = {"original": item.priority, "new": priority}
        item.priority = priority
        if not override_type:
            override_type = OverrideType.PRIORITY_CHANGED
    
    if is_excluded is not None and item.is_excluded != is_excluded:
        if not reason:
            raise HTTPException(status_code=400, detail="Reason is required for exclusion changes")
        changes["is_excluded"] = {"original": item.is_excluded, "new": is_excluded}
        item.is_excluded = is_excluded
        if not override_type:
            override_type = OverrideType.EXCLUDED if is_excluded else OverrideType.RESTORED
    
    if execution_status is not None and item.execution_status != execution_status:
        changes["execution_status"] = {"original": item.execution_status, "new": execution_status}
        item.execution_status = execution_status
    
    item.updated_at = datetime.utcnow()
    
    # Create override record if there were changes
    if changes and override_type:
        override = ScopeOverride(
            regression_scope_item_id=item.id,
            regression_suite_id=suite_id,
            override_type=override_type,
            original_value=changes,
            new_value={k: v["new"] for k, v in changes.items()},
            reason=reason or "Manual update via API",
            overridden_by="api_user",
            overridden_at=datetime.utcnow()
        )
        db.add(override)
    
    db.commit()
    
    return {
        "id": str(item.id),
        "tier": item.tier,
        "priority": item.priority,
        "is_excluded": item.is_excluded,
        "execution_status": item.execution_status,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None
    }


@router.post("/api/regression-suites/{suite_id}/scope/override")
def create_scope_override(
    suite_id: uuid.UUID,
    scope_item_id: uuid.UUID,
    override_type: str,
    original_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    overridden_by: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create an override record for a scope item.
    
    Args:
        suite_id: UUID of the regression suite
        scope_item_id: UUID of the scope item
        override_type: Type of override
        original_value: Original value before override
        new_value: New value after override
        reason: Reason for override
        overridden_by: User who made the override
        db: Database session
        
    Returns:
        Created override record
    """
    item = db.query(RegressionScopeItem).filter(
        RegressionScopeItem.id == scope_item_id,
        RegressionScopeItem.regression_suite_id == suite_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Scope item not found")
    
    override = ScopeOverride(
        regression_scope_item_id=scope_item_id,
        regression_suite_id=suite_id,
        override_type=override_type,
        original_value=original_value,
        new_value=new_value,
        reason=reason,
        overridden_by=overridden_by or "api_user",
        overridden_at=datetime.utcnow()
    )
    
    db.add(override)
    db.commit()
    
    return {
        "id": str(override.id),
        "regression_scope_item_id": str(override.regression_scope_item_id),
        "regression_suite_id": str(override.regression_suite_id),
        "override_type": override.override_type,
        "original_value": override.original_value,
        "new_value": override.new_value,
        "reason": override.reason,
        "overridden_by": override.overridden_by,
        "overridden_at": override.overridden_at.isoformat() if override.overridden_at else None
    }


@router.get("/api/repositories/{repository_id}/regression-suites")
def list_repository_regression_suites(
    repository_id: uuid.UUID,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List regression suites for a repository.
    
    Args:
        repository_id: UUID of the repository
        status: Optional filter by status
        limit: Maximum number of results
        offset: Offset for pagination
        db: Database session
        
    Returns:
        List of regression suites
    """
    query = db.query(RegressionSuite).filter(
        RegressionSuite.repository_id == repository_id,
        RegressionSuite.is_active == True
    )
    
    if status:
        query = query.filter(RegressionSuite.status == status)
    
    query = query.order_by(RegressionSuite.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    suites = query.all()
    
    return {
        "repository_id": str(repository_id),
        "total": len(suites),
        "suites": [
            {
                "id": str(suite.id),
                "name": suite.name,
                "description": suite.description,
                "suite_type": suite.suite_type,
                "status": suite.status,
                "confidence_level": suite.confidence_level,
                "scope_score": suite.scope_score,
                "created_at": suite.created_at.isoformat() if suite.created_at else None,
                "updated_at": suite.updated_at.isoformat() if suite.updated_at else None,
                "scope_items_count": len(suite.scope_items)
            }
            for suite in suites
        ]
    }


@router.get("/api/releases/{release_id}/regression-suites")
def list_release_regression_suites(
    release_id: uuid.UUID,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List regression suites for a release.
    
    Args:
        release_id: UUID of the release
        status: Optional filter by status
        db: Database session
        
    Returns:
        List of regression suites for the release
    """
    query = db.query(RegressionSuite).filter(
        RegressionSuite.release_id == release_id,
        RegressionSuite.is_active == True
    )
    
    if status:
        query = query.filter(RegressionSuite.status == status)
    
    suites = query.all()
    
    return {
        "release_id": str(release_id),
        "total": len(suites),
        "suites": [
            {
                "id": str(suite.id),
                "name": suite.name,
                "description": suite.description,
                "suite_type": suite.suite_type,
                "status": suite.status,
                "confidence_level": suite.confidence_level,
                "scope_score": suite.scope_score,
                "created_at": suite.created_at.isoformat() if suite.created_at else None,
                "updated_at": suite.updated_at.isoformat() if suite.updated_at else None,
                "scope_items_count": len(suite.scope_items)
            }
            for suite in suites
        ]
    }
