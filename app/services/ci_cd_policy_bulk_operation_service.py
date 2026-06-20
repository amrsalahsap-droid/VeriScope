"""
CI/CD Policy Bulk Operation Service

Handles bulk operations for CI/CD governance across multiple repositories.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.models.repository import Repository
from app.models.repository_ci_cd_policy import RepositoryCICDPolicy
from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
from app.services.ci_cd_policy_service import CICDPolicyService
from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService
from app.services.governance_notification_service import GovernanceNotificationService
from app.models.ci_cd_policy_exception import CICDPolicyException


class CICDPolicyBulkOperationService:
    """Service for bulk CI/CD policy operations."""
    
    @staticmethod
    def bulk_apply_preset(
        db: Session,
        repository_ids: List[UUID],
        preset_name: str,
        actor_id: UUID,
        workspace_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply a preset to multiple repositories.
        
        Args:
            db: Database session
            repository_ids: List of repository IDs
            preset_name: Preset name to apply
            actor_id: Actor ID
            reason: Optional reason for the operation
        
        Returns:
            Bulk operation result
        """
        operation_id = uuid4()
        preset_service = CICDPolicyPresetService()
        
        results = []
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for repo_id in repository_ids:
            try:
                # Verify repository exists
                repository = db.query(Repository).filter(Repository.id == repo_id).first()
                if not repository:
                    results.append({
                        "repositoryId": str(repo_id),
                        "status": "SKIPPED",
                        "message": "Repository not found"
                    })
                    skipped_count += 1
                    continue
                
                # Apply preset
                policy = preset_service.apply_preset(
                    db=db,
                    repository_id=repo_id,
                    preset_name=preset_name,
                    actor_id=actor_id,
                    reason=reason or f"Bulk apply {preset_name} preset"
                )
                
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "SUCCESS",
                    "message": f"{preset_name} preset applied."
                })
                succeeded_count += 1
                
            except Exception as e:
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "FAILED",
                    "message": str(e)
                })
                failed_count += 1
        
        # Note: Individual repository operations already log audit events via preset_service.apply_preset
        # Log parent bulk operation audit event if workspace_id is provided
        if workspace_id:
            WorkspaceGovernanceAuditService.log_bulk_operation(
                db=db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type="CI_CD_BULK_POLICY_PARTIAL_FAILURE" if failed_count > 0 else "CI_CD_BULK_POLICY_APPLIED",
                operation_id=operation_id,
                requested_count=len(repository_ids),
                succeeded_count=succeeded_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                reason=reason
            )
        
        return {
            "operationId": str(operation_id),
            "operation": "APPLY_PRESET",
            "requestedCount": len(repository_ids),
            "succeededCount": succeeded_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
            "results": results
        }
    
    @staticmethod
    def bulk_restore_org_default(
        db: Session,
        repository_ids: List[UUID],
        actor_id: UUID,
        workspace_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Restore organization default policy for multiple repositories.
        
        Args:
            db: Database session
            repository_ids: List of repository IDs
            actor_id: Actor ID
            reason: Optional reason for the operation
        
        Returns:
            Bulk operation result
        """
        operation_id = uuid4()
        policy_service = CICDPolicyService()
        
        results = []
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for repo_id in repository_ids:
            try:
                # Verify repository exists
                repository = db.query(Repository).filter(Repository.id == repo_id).first()
                if not repository:
                    results.append({
                        "repositoryId": str(repo_id),
                        "status": "SKIPPED",
                        "message": "Repository not found"
                    })
                    skipped_count += 1
                    continue
                
                # Delete repository policy to restore inheritance
                repo_policy = db.query(RepositoryCICDPolicy).filter(
                    RepositoryCICDPolicy.repository_id == repo_id
                ).first()
                
                if repo_policy:
                    db.delete(repo_policy)
                    db.commit()
                
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "SUCCESS",
                    "message": "Restored organization default policy."
                })
                succeeded_count += 1
                
            except Exception as e:
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "FAILED",
                    "message": str(e)
                })
                failed_count += 1
        
        # Note: Individual repository operations already log audit events
        # Log parent bulk operation audit event if workspace_id is provided
        if workspace_id:
            WorkspaceGovernanceAuditService.log_bulk_operation(
                db=db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type="CI_CD_BULK_POLICY_PARTIAL_FAILURE" if failed_count > 0 else "CI_CD_BULK_POLICY_APPLIED",
                operation_id=operation_id,
                requested_count=len(repository_ids),
                succeeded_count=succeeded_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                reason=reason
            )
        
        return {
            "operationId": str(operation_id),
            "operation": "RESTORE_ORG_DEFAULT",
            "requestedCount": len(repository_ids),
            "succeededCount": succeeded_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
            "results": results
        }
    
    @staticmethod
    def bulk_acknowledge_drift(
        db: Session,
        repository_ids: List[UUID],
        actor_id: UUID,
        workspace_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Acknowledge policy drift for multiple repositories.
        
        This creates policy exceptions for the drift fields.
        
        Args:
            db: Database session
            repository_ids: List of repository IDs
            actor_id: Actor ID
            reason: Optional reason for the operation
        
        Returns:
            Bulk operation result
        """
        operation_id = uuid4()
        preset_service = CICDPolicyPresetService()
        
        results = []
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for repo_id in repository_ids:
            try:
                # Verify repository exists
                repository = db.query(Repository).filter(Repository.id == repo_id).first()
                if not repository:
                    results.append({
                        "repositoryId": str(repo_id),
                        "status": "SKIPPED",
                        "message": "Repository not found"
                    })
                    skipped_count += 1
                    continue
                
                # Detect drift
                drift = preset_service.detect_policy_drift(db, repo_id)
                
                if not drift["drift_detected"]:
                    results.append({
                        "repositoryId": str(repo_id),
                        "status": "SKIPPED",
                        "message": "No drift detected"
                    })
                    skipped_count += 1
                    continue
                
                # Create exception for drift fields
                exception = CICDPolicyException(
                    workspace_id=repository.workspace_id if hasattr(repository, 'workspace_id') else None,
                    repository_id=repo_id,
                    requested_by=actor_id,
                    status="APPROVED",
                    reason=reason or "Bulk acknowledge drift",
                    exception_fields=drift["drift_fields"],
                    decision_reason="Auto-approved via bulk acknowledge drift"
                )
                db.add(exception)
                db.commit()
                
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "SUCCESS",
                    "message": f"Drift acknowledged for {len(drift['drift_fields'])} fields."
                })
                succeeded_count += 1
                
            except Exception as e:
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "FAILED",
                    "message": str(e)
                })
                failed_count += 1
        
        # Note: Individual repository operations already log audit events
        # Log parent bulk operation audit event if workspace_id is provided
        if workspace_id:
            WorkspaceGovernanceAuditService.log_bulk_operation(
                db=db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type="CI_CD_BULK_POLICY_PARTIAL_FAILURE" if failed_count > 0 else "CI_CD_BULK_POLICY_APPLIED",
                operation_id=operation_id,
                requested_count=len(repository_ids),
                succeeded_count=succeeded_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                reason=reason
            )
        
        return {
            "operationId": str(operation_id),
            "operation": "ACKNOWLEDGE_DRIFT",
            "requestedCount": len(repository_ids),
            "succeededCount": succeeded_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
            "results": results
        }
    
    @staticmethod
    def bulk_export_policies(
        db: Session,
        repository_ids: List[UUID],
        actor_id: UUID,
        workspace_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Export policies for multiple repositories.
        
        Args:
            db: Database session
            repository_ids: List of repository IDs
            actor_id: Actor ID
        
        Returns:
            Bulk operation result with exported policies
        """
        operation_id = uuid4()
        policy_service = CICDPolicyService()
        
        results = []
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for repo_id in repository_ids:
            try:
                # Verify repository exists
                repository = db.query(Repository).filter(Repository.id == repo_id).first()
                if not repository:
                    results.append({
                        "repositoryId": str(repo_id),
                        "status": "SKIPPED",
                        "message": "Repository not found",
                        "policy": None
                    })
                    skipped_count += 1
                    continue
                
                # Export policy
                export_data = policy_service.export_policy(db, repo_id)
                
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "SUCCESS",
                    "message": "Policy exported.",
                    "policy": export_data
                })
                succeeded_count += 1
                
            except Exception as e:
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "FAILED",
                    "message": str(e),
                    "policy": None
                })
                failed_count += 1
        
        # Note: Individual repository operations already log audit events
        # Log parent bulk operation audit event if workspace_id is provided
        if workspace_id:
            WorkspaceGovernanceAuditService.log_bulk_operation(
                db=db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type="CI_CD_BULK_POLICY_PARTIAL_FAILURE" if failed_count > 0 else "CI_CD_BULK_POLICY_APPLIED",
                operation_id=operation_id,
                requested_count=len(repository_ids),
                succeeded_count=succeeded_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                reason="Bulk export policies"
            )
        
        return {
            "operationId": str(operation_id),
            "operation": "EXPORT_POLICIES",
            "requestedCount": len(repository_ids),
            "succeededCount": succeeded_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
            "results": results
        }
    
    @staticmethod
    def bulk_scan_compliance(
        db: Session,
        repository_ids: List[UUID],
        actor_id: UUID,
        workspace_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Scan compliance for multiple repositories.
        
        Args:
            db: Database session
            repository_ids: List of repository IDs
            actor_id: Actor ID
        
        Returns:
            Bulk operation result with compliance scores
        """
        operation_id = uuid4()
        
        results = []
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for repo_id in repository_ids:
            try:
                # Verify repository exists
                repository = db.query(Repository).filter(Repository.id == repo_id).first()
                if not repository:
                    results.append({
                        "repositoryId": str(repo_id),
                        "status": "SKIPPED",
                        "message": "Repository not found",
                        "compliance": None
                    })
                    skipped_count += 1
                    continue
                
                # Calculate compliance score
                compliance = CICDPolicyBulkOperationService.calculate_repository_compliance(db, repo_id)
                
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "SUCCESS",
                    "message": "Compliance scanned.",
                    "compliance": compliance
                })
                succeeded_count += 1
                
            except Exception as e:
                results.append({
                    "repositoryId": str(repo_id),
                    "status": "FAILED",
                    "message": str(e),
                    "compliance": None
                })
                failed_count += 1
        
        # Note: Individual repository operations already log audit events
        # Log parent bulk operation audit event if workspace_id is provided
        if workspace_id:
            WorkspaceGovernanceAuditService.log_bulk_operation(
                db=db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type="CI_CD_BULK_POLICY_PARTIAL_FAILURE" if failed_count > 0 else "CI_CD_BULK_POLICY_APPLIED",
                operation_id=operation_id,
                requested_count=len(repository_ids),
                succeeded_count=succeeded_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                reason="Bulk scan compliance"
            )
        
        return {
            "operationId": str(operation_id),
            "operation": "SCAN_COMPLIANCE",
            "requestedCount": len(repository_ids),
            "succeededCount": succeeded_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
            "results": results
        }
    
    @staticmethod
    def calculate_repository_compliance(
        db: Session,
        repository_id: UUID,
        workspace_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Calculate compliance score for a single repository.
        
        Args:
            db: Database session
            repository_id: Repository ID
            workspace_id: Optional organization ID for notifications
        
        Returns:
            Compliance score and status
        """
        from app.services.ci_cd_policy_service import CICDPolicyService
        from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
        from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
        
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            return {
                "repository_id": str(repository_id),
                "repository_name": "Unknown",
                "policy_source": "UNKNOWN",
                "current_preset": None,
                "workspace_default_preset": None,
                "drift_detected": False,
                "drift_risk_level": "NONE",
                "branch_protection_ready": False,
                "manual_override_enabled": False,
                "artifact_required": False,
                "pr_comment_required": False,
                "unknown_gate_fails": False,
                "partial_gate_fails": False,
                "compliance_score": 0,
                "compliance_status": "UNSCANNED",
                "recommended_action": "Repository not found"
            }
        
        policy_service = CICDPolicyService()
        preset_service = CICDPolicyPresetService()
        
        # Get effective policy
        effective = policy_service.get_effective_policy(db, repository_id)
        
        # Get drift
        drift = preset_service.detect_policy_drift(db, repository_id)
        
        # Notify about drift if detected and workspace_id is provided
        if drift["drift_detected"] and workspace_id:
            risk_level = drift["risk_level"]
            if risk_level == "CRITICAL":
                mapped_risk = "CRITICAL"
            elif risk_level == "HIGH":
                mapped_risk = "HIGH"
            else:
                mapped_risk = "STANDARD"
            
            GovernanceNotificationService.notify_drift_detected(
                db=db,
                workspace_id=workspace_id,
                repository_id=repository_id,
                risk_level=mapped_risk
            )
        
        # Get repository policy if exists
        repo_policy = db.query(RepositoryCICDPolicy).filter(
            RepositoryCICDPolicy.repository_id == repository_id
        ).first()
        
        # Get workspace default
        org_default = None
        if hasattr(repository, 'workspace_id') and repository.workspace_id:
            org_default = db.query(WorkspaceCICDPolicyDefault).filter(
                WorkspaceCICDPolicyDefault.workspace_id == repository.workspace_id
            ).first()
        
        # Calculate compliance score (start at 100)
        score = 100
        
        # Deduct for drift
        if drift["drift_detected"]:
            if drift["risk_level"] == "HIGH":
                score -= 20
            elif drift["risk_level"] == "MEDIUM":
                score -= 10
            elif drift["risk_level"] == "CRITICAL":
                score -= 30
        
        # Deduct for missing artifact requirement
        if repo_policy and not repo_policy.require_artifact:
            score -= 10
        
        # Deduct for disabled unknown gate failure
        if repo_policy and not repo_policy.fail_on_unknown_gate:
            score -= 10
        
        # Deduct for manual override without reason
        if repo_policy and repo_policy.allow_manual_override and not repo_policy.manual_override_requires_reason:
            score -= 15
        
        # Deduct for missing branch protection readiness (simplified check)
        # In production, this would check actual branch protection readiness
        if not repo_policy or not repo_policy.enabled:
            score -= 20
        
        # Ensure score is between 0 and 100
        score = max(0, min(100, score))
        
        # Determine compliance status
        if score >= 90:
            status = "COMPLIANT"
        elif score >= 70:
            status = "DRIFTED"
        elif score >= 50:
            status = "HIGH_RISK"
        else:
            status = "CRITICAL"
        
        # Determine recommended action
        if status == "CRITICAL":
            recommended_action = "Immediate review required. Apply STRICT or REGULATED preset."
        elif status == "HIGH_RISK":
            recommended_action = "Review drift and consider aligning with organization default."
        elif status == "DRIFTED":
            recommended_action = "Acknowledge drift or restore organization default."
        else:
            recommended_action = "Maintain current policy configuration."
        
        return {
            "repository_id": str(repository_id),
            "repository_name": repository.full_name,
            "policy_source": effective["source"],
            "current_preset": effective["source_preset"],
            "workspace_default_preset": effective["workspace_default_preset"],
            "drift_detected": drift["drift_detected"],
            "drift_risk_level": drift["risk_level"],
            "branch_protection_ready": repo_policy.enabled if repo_policy else False,
            "manual_override_enabled": repo_policy.allow_manual_override if repo_policy else False,
            "artifact_required": repo_policy.require_artifact if repo_policy else False,
            "pr_comment_required": repo_policy.require_pr_comment if repo_policy else False,
            "unknown_gate_fails": repo_policy.fail_on_unknown_gate if repo_policy else False,
            "partial_gate_fails": repo_policy.ci_fail_on_partial if repo_policy else False,
            "compliance_score": score,
            "compliance_status": status,
            "recommended_action": recommended_action
        }
