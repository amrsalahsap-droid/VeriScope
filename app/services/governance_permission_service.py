"""
Governance Permission Service

Handles role-based access control for governance operations.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.models.governance_role_assignment import GovernanceRoleAssignment, GovernanceRole, ScopeType
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.user import User
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService


# Role to permission mapping
ROLE_PERMISSIONS = {
    GovernanceRole.GOVERNANCE_OWNER: [
        "governance.policy.view",
        "governance.policy.update",
        "governance.policy.apply_preset",
        "governance.policy.import",
        "governance.policy.export",
        "governance.policy.clone",
        "governance.policy.bulk_preview",
        "governance.policy.bulk_apply",
        "governance.org_default.view",
        "governance.org_default.update",
        "governance.drift.view",
        "governance.drift.acknowledge",
        "governance.exception.request",
        "governance.exception.approve",
        "governance.exception.reject",
        "governance.exception.revoke",
        "governance.analytics.view",
        "governance.executive_report.view",
        "governance.executive_report.export",
        "governance.audit.view",
        "governance.roles.view",
        "governance.roles.assign",
        "governance.access_review.create",
        "governance.access_review.decide",
        "governance.access_review.complete",
        "governance.evidence_pack.export",
        "governance.security_signals.view",
    ],
    GovernanceRole.POLICY_ADMIN: [
        "governance.policy.view",
        "governance.policy.update",
        "governance.policy.apply_preset",
        "governance.policy.import",
        "governance.policy.export",
        "governance.policy.clone",
        "governance.policy.bulk_preview",
        "governance.policy.bulk_apply",
        "governance.org_default.view",
        "governance.org_default.update",
        "governance.drift.view",
        "governance.drift.acknowledge",
        "governance.exception.request",
        "governance.analytics.view",
        "governance.audit.view",
        "governance.roles.view",
        "governance.access_review.create",
        "governance.access_review.decide",
        "governance.access_review.complete",
        "governance.evidence_pack.export",
        "governance.security_signals.view",
    ],
    GovernanceRole.EXCEPTION_APPROVER: [
        "governance.policy.view",
        "governance.exception.approve",
        "governance.exception.reject",
        "governance.exception.revoke",
        "governance.analytics.view",
        "governance.audit.view",
        "governance.roles.view",
        "governance.access_review.decide",
    ],
    GovernanceRole.REPOSITORY_POLICY_MANAGER: [
        "governance.policy.view",
        "governance.policy.update",
        "governance.exception.request",
        "governance.drift.view",
        "governance.analytics.view",
        "governance.roles.view",
        "governance.access_review.decide",
        "governance.security_signals.view",
    ],
    GovernanceRole.GOVERNANCE_VIEWER: [
        "governance.policy.view",
        "governance.analytics.view",
        "governance.audit.view",
        "governance.roles.view",
        "governance.security_signals.view",
    ],
    GovernanceRole.EXECUTIVE_VIEWER: [
        "governance.policy.view",
        "governance.analytics.view",
        "governance.executive_report.view",
        "governance.executive_report.export",
        "governance.audit.view",
        "governance.roles.view",
        "governance.evidence_pack.export",
        "governance.security_signals.view",
    ],
    GovernanceRole.AUDITOR: [
        "governance.policy.view",
        "governance.analytics.view",
        "governance.audit.view",
        "governance.roles.view",
        "governance.evidence_pack.export",
        "governance.security_signals.view",
    ],
}


class GovernancePermissionService:
    """Service for checking and managing governance permissions."""
    
    @staticmethod
    def get_user_roles(
        db: Session,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active, non-expired role assignments for a user.
        
        Returns both workspace-scoped and repository-scoped roles.
        """
        now = datetime.utcnow()
        
        # Query active, non-expired role assignments
        query = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.user_id == user_id,
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.is_active == True,
            (GovernanceRoleAssignment.expires_at.is_(None)) | 
            (GovernanceRoleAssignment.expires_at > now)
        )
        
        # If repository_id is specified, include repository-scoped roles
        if repository_id:
            # Verify the repository belongs to this workspace
            repo_exists = db.query(Repository).filter(
                Repository.id == repository_id,
                Repository.workspace_id == workspace_id
            ).first() is not None
            
            if repo_exists:
                query = query.filter(
                    (GovernanceRoleAssignment.scope_type == ScopeType.WORKSPACE) |
                    (
                        (GovernanceRoleAssignment.scope_type == ScopeType.REPOSITORY) &
                        (GovernanceRoleAssignment.repository_id == repository_id)
                    )
                )
            else:
                # If repository does not belong to the workspace, ignore repository-scoped role assignments
                query = query.filter(GovernanceRoleAssignment.scope_type == ScopeType.WORKSPACE)
        else:
            # Only workspace-scoped roles when no repository specified
            query = query.filter(GovernanceRoleAssignment.scope_type == ScopeType.WORKSPACE)
        
        assignments = query.all()
        
        return [
            {
                "id": str(assignment.id),
                "role": assignment.role.value,
                "scope_type": assignment.scope_type.value,
                "repository_id": str(assignment.repository_id) if assignment.repository_id else None,
                "assigned_by": str(assignment.assigned_by) if assignment.assigned_by else None,
                "created_at": assignment.created_at.isoformat(),
                "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
            }
            for assignment in assignments
        ]
    
    @staticmethod
    def has_permission(
        db: Session,
        user_id: uuid.UUID,
        permission: str,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Check if a user has a specific permission.
        
        Returns True if the user has any role that grants the permission.
        """
        roles = GovernancePermissionService.get_user_roles(db, user_id, workspace_id, repository_id)
        
        for role_data in roles:
            role = GovernanceRole(role_data["role"])
            if permission in ROLE_PERMISSIONS.get(role, []):
                return True
        
        return False
    
    @staticmethod
    def require_permission(
        db: Session,
        user_id: uuid.UUID,
        permission: str,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Require a permission. Returns access decision with diagnostics.
        
        If permission is granted, returns {"allowed": true}.
        If permission is denied, returns {"allowed": false, ...diagnostics}.
        Logs permission check as audit event.
        """
        allowed = GovernancePermissionService.has_permission(
            db, user_id, permission, workspace_id, repository_id
        )
        
        # Log permission check
        if actor_id:
            WorkspaceGovernanceAuditService.log_permission_check(
                db=db,
                workspace_id=workspace_id,
                repository_id=repository_id,
                actor_id=actor_id,
                target_user_id=user_id,
                permission=permission,
                decision="ALLOWED" if allowed else "DENIED",
                reason="Permission check" if allowed else "Insufficient permissions"
            )
        
        if allowed:
            return {"allowed": True}
        
        # Provide access denied diagnostics
        explanation = GovernancePermissionService.explain_access_decision(
            db, user_id, permission, workspace_id, repository_id
        )
        
        return {"allowed": False, **explanation}
    
    @staticmethod
    def list_effective_permissions(
        db: Session,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        List all effective permissions for a user based on their roles.
        
        Returns the union of all permissions from their active roles.
        """
        roles = GovernancePermissionService.get_user_roles(db, user_id, workspace_id, repository_id)
        
        # Collect all permissions from all roles
        permissions = set()
        role_details = []
        
        for role_data in roles:
            role = GovernanceRole(role_data["role"])
            role_perms = ROLE_PERMISSIONS.get(role, [])
            permissions.update(role_perms)
            
            role_details.append({
                "role": role.value,
                "scope_type": role_data["scope_type"],
                "repository_id": role_data["repository_id"],
                "permissions": role_perms,
            })
        
        return {
            "user_id": str(user_id),
            "workspace_id": str(workspace_id),
            "repository_id": str(repository_id) if repository_id else None,
            "roles": role_details,
            "effective_permissions": sorted(list(permissions)),
        }
    
    @staticmethod
    def explain_access_decision(
        db: Session,
        user_id: uuid.UUID,
        permission: str,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Explain an access decision with safe diagnostics.
        
        Returns:
        - permission_required: The permission being checked
        - scope_checked: The scope (workspace or repository)
        - reason: Why access was denied
        - how_to_request_access: How the user can request access
        - matched_roles: Roles that were checked (if any)
        """
        roles = GovernancePermissionService.get_user_roles(db, user_id, workspace_id, repository_id)
        
        if not roles:
            return {
                "permission_required": permission,
                "scope_checked": f"Workspace {workspace_id}" + (f", Repository {repository_id}" if repository_id else ""),
                "reason": "No active governance role assignments found for this user in the specified scope.",
                "how_to_request_access": "Contact your governance owner or policy admin to request a governance role assignment.",
                "matched_roles": [],
            }
        
        # Check if any role has the permission
        matched_roles = []
        for role_data in roles:
            role = GovernanceRole(role_data["role"])
            if permission in ROLE_PERMISSIONS.get(role, []):
                matched_roles.append(role_data)
        
        if matched_roles:
            # This shouldn't happen if has_permission returned False, but handle it
            return {
                "permission_required": permission,
                "scope_checked": f"Workspace {workspace_id}" + (f", Repository {repository_id}" if repository_id else ""),
                "reason": "Access should be granted based on role assignments.",
                "how_to_request_access": "No action needed.",
                "matched_roles": matched_roles,
            }
        
        # User has roles but none grant the permission
        role_names = [r["role"] for r in roles]
        return {
            "permission_required": permission,
            "scope_checked": f"Workspace {workspace_id}" + (f", Repository {repository_id}" if repository_id else ""),
            "reason": f"User has governance roles ({', '.join(role_names)}) but none grant the required permission '{permission}'.",
            "how_to_request_access": "Contact your governance owner or policy admin to request a role with this permission.",
            "matched_roles": roles,
        }
    
    @staticmethod
    def can_approve_own_exception(
        db: Session,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID
    ) -> bool:
        """
        Check if a user can approve their own exception requests.
        
        By default, this is false. Only GOVERNANCE_OWNER with explicit
        self_approval_allowed setting can approve their own exceptions.
        
        For now, this always returns False (no self-approval allowed).
        """
        # Future: Check workspace setting for self_approval_allowed
        # For now, block all self-approvals
        return False
    
    @staticmethod
    def is_repository_policy_manager(
        db: Session,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        repository_id: uuid.UUID
    ) -> bool:
        """
        Check if a user is a REPOSITORY_POLICY_MANAGER for a specific repository.
        """
        roles = GovernancePermissionService.get_user_roles(db, user_id, workspace_id, repository_id)
        
        for role_data in roles:
            if role_data["role"] == GovernanceRole.REPOSITORY_POLICY_MANAGER.value:
                if role_data["scope_type"] == ScopeType.REPOSITORY.value:
                    if role_data["repository_id"] == str(repository_id):
                        return True
                elif role_data["scope_type"] == ScopeType.WORKSPACE.value:
                    # Workspace-scoped role applies to all repositories
                    return True
        
        return False
