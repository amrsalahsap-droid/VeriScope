"""Recommendation Readiness API Endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.db.session import get_db
from app.models.user import Workspace, User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.services.input_readiness_v2_service import InputReadinessV2Service
from app.schemas.readiness import (
    ReadinessAssessmentResponse,
    ReadinessAssessmentCreate,
    ReadinessSummaryResponse
)
from app.schemas.input_readiness_v2 import InputReadinessV2Response
from app.dependencies.auth import get_current_workspace, get_current_user

router = APIRouter(prefix="/readiness", tags=["readiness"])
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

async def optional_workspace(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Workspace]:
    """Optional workspace authentication for development."""
    if not credentials:
        return None
    try:
        from app.dependencies.auth import get_current_workspace
        return await get_current_workspace(credentials, db)
    except:
        return None

async def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Optional user authentication for development."""
    if not credentials:
        return None
    try:
        from app.dependencies.auth import get_current_user
        return await get_current_user(credentials, db)
    except:
        return None

@router.post("/assess", response_model=ReadinessAssessmentResponse, status_code=status.HTTP_201_CREATED)
def assess_readiness(
    assessment_request: ReadinessAssessmentCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Assess repository/PR readiness for recommendation generation.
    
    This endpoint evaluates the available signals and determines whether
    a useful recommendation can be generated.
    """
    # Verify repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == assessment_request.repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Verify pull request exists and belongs to repository if provided
    if assessment_request.pull_request_id:
        pull_request = db.query(PullRequest).filter(
            PullRequest.id == assessment_request.pull_request_id,
            PullRequest.repository_id == assessment_request.repository_id
        ).first()
        
        if not pull_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pull request not found"
            )
    
    # Perform readiness assessment
    service = RecommendationReadinessService(db)
    assessment = service.assess_readiness(
        repository_id=assessment_request.repository_id,
        pull_request_id=assessment_request.pull_request_id
    )
    
    return assessment

@router.get("/repositories/{repository_id}", response_model=ReadinessSummaryResponse)
def get_repository_readiness(
    repository_id: str,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get current readiness status for a repository."""
    # Verify repository belongs to workspace if workspace is provided
    if workspace:
        repository = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    else:
        # Development mode: allow without workspace
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    
    # Always create a fresh assessment to reflect latest state
    # This ensures readiness updates immediately after input changes
    service = RecommendationReadinessService(db)
    latest_assessment = service.assess_readiness(repository_id=repository_id)

    logger.info(f"Repository readiness assessment: repo_id={repository_id}, pr_id={latest_assessment.pull_request_id}, available_signals={latest_assessment.available_signals}, missing_signals={latest_assessment.missing_signals}")

    return ReadinessSummaryResponse(
        repository_id=str(latest_assessment.repository_id),
        pull_request_id=str(latest_assessment.pull_request_id) if latest_assessment.pull_request_id else None,
        readiness_level=latest_assessment.readiness_level,
        expected_confidence=latest_assessment.expected_confidence,
        readiness_score=latest_assessment.readiness_score,
        can_generate=latest_assessment.can_generate,
        can_generate_reason=latest_assessment.can_generate_reason,
        signal_count=len(latest_assessment.available_signals),
        total_signals=15,  # Total number of possible signals
        intelligence_completeness_score=latest_assessment.intelligence_completeness_score,
        release_confidence_ceiling=latest_assessment.release_confidence_ceiling,
        available_inputs=latest_assessment.available_inputs,
        missing_inputs=latest_assessment.missing_inputs,
        recommended_inputs=latest_assessment.recommended_inputs,
        blocking_inputs=latest_assessment.blocking_inputs,
        next_best_actions=latest_assessment.next_best_actions,
        primary_message=latest_assessment.primary_message,
        secondary_message=latest_assessment.secondary_message,
        confidence_reason=latest_assessment.confidence_reason,
        confidence_ceiling=latest_assessment.confidence_ceiling,
        confidence_blockers=latest_assessment.confidence_blockers,
        confidence_limiters=latest_assessment.confidence_limiters,
        pr_package=None,
        recommendation_audit=None
    )

@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}", response_model=ReadinessSummaryResponse)
def get_pull_request_readiness(
    repository_id: str,
    pull_request_id: str,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get current readiness status for a specific pull request."""
    # Verify repository belongs to workspace if workspace is provided
    if workspace:
        repository = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    else:
        # Development mode: allow without workspace
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    
    # Verify pull request exists and belongs to repository
    pull_request = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not pull_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Always create a fresh assessment to reflect latest state
    # This ensures readiness updates immediately after input changes
    service = RecommendationReadinessService(db)
    latest_assessment = service.assess_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )

    logger.info(f"PR readiness assessment: repo_id={repository_id}, pr_id={pull_request_id}, available_signals={latest_assessment.available_signals}, missing_signals={latest_assessment.missing_signals}")

    # Compute pr_package details
    from app.models.pull_request import PullRequestChangedFile, PullRequestSnapshot
    from app.models.recommendation import RecommendationRun

    pr_package_status = "READY"
    pr_package_blockers = []
    pr_package_warnings = []

    # Fetch changed files database rows to be accurate
    changed_files_db = db.query(PullRequestChangedFile).filter(
        PullRequestChangedFile.pull_request_id == pull_request.id
    ).order_by(PullRequestChangedFile.file_path.asc()).all()

    changed_files_count = pull_request.changed_files_count if pull_request.changed_files_count is not None else len(changed_files_db)

    if not pull_request.head_commit_sha:
        pr_package_status = "BLOCKED"
        pr_package_blockers.append("HEAD_SHA_MISSING")
    elif changed_files_count <= 0:
        pr_package_status = "BLOCKED"
        pr_package_blockers.append("CHANGED_FILES_MISSING")
    else:
        # Check for invalid file paths (e.g. empty or whitespace)
        invalid_paths = [f.file_path for f in changed_files_db if not f.file_path or f.file_path.strip() == ""]
        if invalid_paths:
            pr_package_status = "BLOCKED"
            pr_package_blockers.append("CHANGED_FILE_PATH_INVALID")
        else:
            pr_package_status = "READY"

    # Check for truncation warnings
    if pull_request.evidence_truncated:
        pr_package_warnings.append("LARGE_DIFF_TRUNCATED")

    # Check for patch missing warnings
    missing_patch = [f.file_path for f in changed_files_db if not f.patch_summary]
    if missing_patch:
        pr_package_warnings.append("PATCH_MISSING")

    changed_files_list = [
        {
            "file_path": cf.file_path,
            "status": cf.status,
            "additions": cf.additions,
            "deletions": cf.deletions,
            "patch_summary": cf.patch_summary
        }
        for cf in changed_files_db
    ]

    pr_package_obj = {
        "status": pr_package_status,
        "head_commit_sha": pull_request.head_commit_sha,
        "changed_files_count": changed_files_count,
        "changed_files": changed_files_list,
        "blockers": pr_package_blockers,
        "warnings": pr_package_warnings
    }

    # Compute recommendation_audit details
    recommendation_run = (
        db.query(RecommendationRun)
        .filter(RecommendationRun.pull_request_id == pull_request.id)
        .order_by(RecommendationRun.created_at.desc())
        .first()
    )

    audit_status = "UNKNOWN"
    has_snapshot = False
    has_direct_snapshot_json = False
    snapshot_head_sha = None
    is_stale = False
    stale_reason = None
    message = None

    if not recommendation_run:
        audit_status = "NO_RECOMMENDATION_YET"
        message = "No recommendation generated yet for this pull request."
    else:
        # Check for pr_snapshot_id linked to snapshot
        snapshot = None
        if recommendation_run.pr_snapshot_id:
            snapshot = db.query(PullRequestSnapshot).filter(
                PullRequestSnapshot.id == recommendation_run.pr_snapshot_id
            ).first()

        if snapshot:
            has_snapshot = True
            snapshot_head_sha = snapshot.head_commit_sha
            
            if pull_request.head_commit_sha != snapshot.head_commit_sha:
                audit_status = "OUTDATED"
                is_stale = True
                stale_reason = f"PR head commit SHA changed from {snapshot.head_commit_sha} to {pull_request.head_commit_sha}."
                message = f"Generated from {snapshot.head_commit_sha[:7]} (outdated), current PR head is {pull_request.head_commit_sha[:7]}. Regenerate before signoff."
            else:
                audit_status = "AUDITABLE"
                message = "Recommendation has an auditable PR package snapshot."
        
        # Fallback to direct snapshot JSON fields
        elif recommendation_run.head_commit_sha_at_generation and recommendation_run.changed_files_snapshot_json:
            has_direct_snapshot_json = True
            snapshot_head_sha = recommendation_run.head_commit_sha_at_generation
            
            if pull_request.head_commit_sha != recommendation_run.head_commit_sha_at_generation:
                audit_status = "OUTDATED"
                is_stale = True
                stale_reason = f"PR head commit SHA changed from {recommendation_run.head_commit_sha_at_generation} to {pull_request.head_commit_sha}."
                message = f"Generated from {recommendation_run.head_commit_sha_at_generation[:7]} (outdated), current PR head is {pull_request.head_commit_sha[:7]}. Regenerate before signoff."
            else:
                audit_status = "AUDITABLE"
                message = "Recommendation has an auditable PR package snapshot."
        
        else:
            audit_status = "LEGACY_NO_SNAPSHOT"
            message = "Existing recommendation predates PR package snapshot support. Regenerate for auditability."

    recommendation_audit_obj = {
        "status": audit_status,
        "has_snapshot": has_snapshot,
        "has_direct_snapshot_json": has_direct_snapshot_json,
        "snapshot_head_sha": snapshot_head_sha,
        "current_head_sha": pull_request.head_commit_sha,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "message": message
    }

    return ReadinessSummaryResponse(
        repository_id=str(latest_assessment.repository_id),
        pull_request_id=str(latest_assessment.pull_request_id) if latest_assessment.pull_request_id else None,
        readiness_level=latest_assessment.readiness_level,
        expected_confidence=latest_assessment.expected_confidence,
        readiness_score=latest_assessment.readiness_score,
        can_generate=latest_assessment.can_generate,
        can_generate_reason=latest_assessment.can_generate_reason,
        signal_count=len(latest_assessment.available_signals),
        total_signals=15,  # Total number of possible signals
        intelligence_completeness_score=latest_assessment.intelligence_completeness_score,
        release_confidence_ceiling=latest_assessment.release_confidence_ceiling,
        available_inputs=latest_assessment.available_inputs,
        missing_inputs=latest_assessment.missing_inputs,
        recommended_inputs=latest_assessment.recommended_inputs,
        blocking_inputs=latest_assessment.blocking_inputs,
        next_best_actions=latest_assessment.next_best_actions,
        primary_message=latest_assessment.primary_message,
        secondary_message=latest_assessment.secondary_message,
        confidence_reason=latest_assessment.confidence_reason,
        confidence_ceiling=latest_assessment.confidence_ceiling,
        confidence_blockers=latest_assessment.confidence_blockers,
        confidence_limiters=latest_assessment.confidence_limiters,
        pr_package=pr_package_obj,
        recommendation_audit=recommendation_audit_obj
    )

@router.get("/repositories/{repository_id}/assessments", response_model=List[ReadinessAssessmentResponse])
def get_repository_assessments(
    repository_id: str,
    limit: int = 10,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get recent readiness assessments for a repository."""
    # Verify repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Get recent assessments
    from app.models.readiness import RecommendationReadinessAssessment
    
    assessments = db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.repository_id == repository_id
    ).order_by(RecommendationReadinessAssessment.created_at.desc()).limit(limit).all()
    
    service = RecommendationReadinessService(db)
    return [service.populate_assessment_fields(a) for a in assessments]

@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}/assessments", response_model=List[ReadinessAssessmentResponse])
def get_pull_request_assessments(
    repository_id: str,
    pull_request_id: str,
    limit: int = 5,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get recent readiness assessments for a specific pull request."""
    # Verify repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Verify pull request exists and belongs to repository
    pull_request = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not pull_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Get recent assessments for PR
    from app.models.readiness import RecommendationReadinessAssessment
    
    assessments = db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.repository_id == repository_id,
        RecommendationReadinessAssessment.pull_request_id == pull_request_id
    ).order_by(RecommendationReadinessAssessment.created_at.desc()).limit(limit).all()
    
    service = RecommendationReadinessService(db)
    return [service.populate_assessment_fields(a) for a in assessments]

@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}/requirement-package")
def get_requirement_package(
    repository_id: str,
    pull_request_id: str,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get requirement package with full hierarchy for a pull request."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Verify pull request exists
    pull_request = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not pull_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Get requirement package
    from app.models.requirement_package import RequirementPackage
    from app.models.requirement_group import RequirementGroup
    from app.models.acceptance_criterion import AcceptanceCriterion
    from app.models.testable_scenario import TestableScenario
    
    pkg = db.query(RequirementPackage).filter(
        RequirementPackage.repository_id == repository_id,
        RequirementPackage.pull_request_id == pull_request_id
    ).first()
    
    if not pkg:
        return {
            "exists": False,
            "requirement_package": None,
            "requirement_groups": [],
            "total_ac_count": 0,
            "total_scenario_count": 0,
            "hierarchy_status": {
                "requirement_package": "MISSING",
                "requirement_groups": "MISSING",
                "acceptance_criteria": "MISSING",
                "testable_scenarios": "MISSING",
                "parent_child_mapping": "NOT_APPLICABLE",
                "multiple_enhancements_supported": False,
                "multiple_acs_per_enhancement_supported": False,
                "flattening_risk": "HIGH",
                "required_fixes": ["Add requirement package with grouped enhancements"]
            }
        }
    
    # Get requirement groups
    groups = db.query(RequirementGroup).filter(
        RequirementGroup.requirement_package_id == pkg.id
    ).order_by(RequirementGroup.group_number).all()
    
    # Build hierarchy
    groups_data = []
    total_ac_count = 0
    total_scenario_count = 0
    acs_without_stable_key = 0
    groups_without_stable_key = 0
    duplicate_acs_within_group = 0
    
    for group in groups:
        if not group.stable_group_key:
            groups_without_stable_key += 1
        
        # Get acceptance criteria for this group
        acs = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.requirement_group_id == group.id
        ).order_by(AcceptanceCriterion.ac_number).all()
        
        acs_data = []
        ac_keys_in_group = []
        
        for ac in acs:
            if not ac.stable_ac_key:
                acs_without_stable_key += 1
            
            ac_keys_in_group.append(ac.stable_ac_key)
            
            # Get testable scenarios for this AC
            scenarios = db.query(TestableScenario).filter(
                TestableScenario.acceptance_criterion_id == ac.id
            ).all()
            
            scenarios_data = []
            for scenario in scenarios:
                scenarios_data.append({
                    "id": str(scenario.id),
                    "scenario_key": scenario.scenario_key,
                    "title": scenario.title,
                    "preconditions": scenario.preconditions,
                    "steps": scenario.steps,
                    "expected_result": scenario.expected_result,
                    "scenario_type": scenario.scenario_type,
                    "status": scenario.status
                })
                total_scenario_count += 1
            
            acs_data.append({
                "id": str(ac.id),
                "ac_number": ac.ac_number,
                "stable_ac_key": ac.stable_ac_key,
                "title": ac.title,
                "description": ac.description,
                "raw_text": ac.raw_text,
                "normalized_text": ac.normalized_text,
                "source_type": ac.source_type,
                "source_id": ac.source_id,
                "priority": ac.priority,
                "criticality": ac.criticality,
                "status": ac.status,
                "version": ac.version,
                "testable_scenarios": scenarios_data
            })
            total_ac_count += 1
        
        # Check for duplicate AC keys within group
        if len(ac_keys_in_group) != len(set(ac_keys_in_group)):
            duplicate_acs_within_group += len(ac_keys_in_group) - len(set(ac_keys_in_group))
        
        groups_data.append({
            "id": str(group.id),
            "group_number": group.group_number,
            "group_type": group.group_type,
            "stable_group_key": group.stable_group_key,
            "title": group.title,
            "description": group.description,
            "business_flow": group.business_flow,
            "priority": group.priority,
            "risk_level": group.risk_level,
            "source_type": group.source_type,
            "source_id": group.source_id,
            "status": group.status,
            "acceptance_criteria": acs_data,
            "ac_count": len(acs_data)
        })
    
    # Determine hierarchy status
    hierarchy_status = {
        "requirement_package": "EXISTS",
        "requirement_groups": "EXISTS" if groups else "MISSING",
        "acceptance_criteria": "EXISTS" if total_ac_count > 0 else "MISSING",
        "testable_scenarios": "EXISTS" if total_scenario_count > 0 else "MISSING",
        "parent_child_mapping": "PRESERVED" if groups else "NOT_APPLICABLE",
        "multiple_enhancements_supported": len(groups) > 1,
        "multiple_acs_per_enhancement_supported": any(g["ac_count"] > 1 for g in groups_data),
        "flattening_risk": "LOW" if groups else "HIGH",
        "required_fixes": []
    }
    
    if groups_without_stable_key > 0:
        hierarchy_status["required_fixes"].append(f"{groups_without_stable_key} groups missing stable keys")
    
    if acs_without_stable_key > 0:
        hierarchy_status["required_fixes"].append(f"{acs_without_stable_key} ACs missing stable keys")
    
    if duplicate_acs_within_group > 0:
        hierarchy_status["required_fixes"].append(f"{duplicate_acs_within_group} duplicate AC keys within groups")
    
    if not hierarchy_status["required_fixes"]:
        hierarchy_status["required_fixes"].append("None - hierarchy is healthy")
    
    return {
        "exists": True,
        "requirement_package": {
            "id": str(pkg.id),
            "repository_id": str(pkg.repository_id),
            "pull_request_id": str(pkg.pull_request_id),
            "source_type": pkg.source_type,
            "source_id": pkg.source_id,
            "package_version": pkg.package_version,
            "status": pkg.status,
            "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
            "updated_at": pkg.updated_at.isoformat() if pkg.updated_at else None
        },
        "requirement_groups": groups_data,
        "total_ac_count": total_ac_count,
        "total_scenario_count": total_scenario_count,
        "hierarchy_status": hierarchy_status
    }


@router.get(
    "/repositories/{repository_id}/pull-requests/{pull_request_id}/v2",
    response_model=InputReadinessV2Response,
    summary="Get 12-input readiness assessment (V2)",
)
def get_pull_request_readiness_v2(
    repository_id: str,
    pull_request_id: str,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db),
):
    """
    Returns a deterministic 12-input readiness assessment following the new input contract.
    Replaces the old bucket-based scoring model.
    """
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    pull_request = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id,
    ).first()
    if not pull_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull request not found")

    service = InputReadinessV2Service(db)
    result = service.assess(
        repository_id=repository_id,
        pull_request_id=pull_request_id,
    )

    # Guard contract violation
    if result.generation_status == "BLOCKED" and not result.blockers:
        logger.error(
            f"READINESS CONTRACT VIOLATION in V2: repo={repository_id} pr={pull_request_id} — BLOCKED with no blockers"
        )

    return result
