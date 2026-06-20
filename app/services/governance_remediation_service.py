"""
Governance Remediation Service

Implements controlled manual remediation workflows for role assignments,
repository policies, exceptions, and access reviews.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.models.governance_remediation_action import GovernanceRemediationAction
from app.models.governance_role_assignment import GovernanceRoleAssignment, GovernanceRole, ScopeType
from app.models.governance_access_review_item import GovernanceAccessReviewItem
from app.models.ci_cd_policy_exception import CICDPolicyException
from app.models.repository_ci_cd_policy import RepositoryCICDPolicy
from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent
from app.models.user import User, Workspace
from app.models.repository import Repository
from app.services.governance_permission_service import GovernancePermissionService
from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService


class GovernanceRemediationService:
    """Service managing governance remediation actions."""

    @staticmethod
    def verify_actor_permissions(
        db: Session,
        actor_id: uuid.UUID,
        workspace_id: uuid.UUID,
        action_type: str,
        repository_id: Optional[uuid.UUID] = None
    ) -> bool:
        """Verify actor has permission for a specific action type at the boundary."""
        roles = GovernancePermissionService.get_user_roles(db, actor_id, workspace_id, repository_id)
        if not roles:
            return False

        role_names = {r["role"] for r in roles}

        # GOVERNANCE_OWNER always has permission
        if GovernanceRole.GOVERNANCE_OWNER.value in role_names:
            return True

        role_actions = {"REVOKE_ROLE", "CHANGE_ROLE_SCOPE", "EXTEND_ROLE_EXPIRY", "REACTIVATE_ROLE", "DEACTIVATE_ROLE"}
        policy_actions = {"REMOVE_REPOSITORY_POLICY_OVERRIDE", "APPLY_WORKSPACE_DEFAULT_POLICY"}
        exception_actions = {"REVOKE_EXCEPTION", "MARK_EXCEPTION_EXPIRED"}
        finding_actions = {"ACKNOWLEDGE_FINDING", "MARK_REMEDIATION_NOT_REQUIRED"}

        if action_type in role_actions:
            return GovernancePermissionService.has_permission(db, actor_id, "governance.roles.assign", workspace_id, repository_id)
        elif action_type in policy_actions:
            if GovernancePermissionService.has_permission(db, actor_id, "governance.policy.update", workspace_id):
                return True
            if repository_id and GovernancePermissionService.is_repository_policy_manager(db, actor_id, workspace_id, repository_id):
                return True
            return False
        elif action_type in exception_actions:
            return GovernancePermissionService.has_permission(db, actor_id, "governance.exception.revoke", workspace_id, repository_id)
        elif action_type in finding_actions:
            if action_type == "MARK_REMEDIATION_NOT_REQUIRED":
                return GovernancePermissionService.has_permission(db, actor_id, "governance.remediation.confirm", workspace_id, repository_id)
            return (
                GovernancePermissionService.has_permission(db, actor_id, "governance.remediation.confirm", workspace_id, repository_id) or
                GovernancePermissionService.has_permission(db, actor_id, "governance.audit.view", workspace_id, repository_id)
            )

        return False

    @staticmethod
    def is_last_active_owner(db: Session, workspace_id: uuid.UUID, assignment_id: uuid.UUID) -> bool:
        """Check if role assignment is the last active GOVERNANCE_OWNER in the workspace."""
        assignment = db.query(GovernanceRoleAssignment).filter(GovernanceRoleAssignment.id == assignment_id).first()
        if not assignment:
            return False

        if assignment.role != GovernanceRole.GOVERNANCE_OWNER or assignment.scope_type != ScopeType.WORKSPACE:
            return False

        now = datetime.utcnow()
        active_owners = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.role == GovernanceRole.GOVERNANCE_OWNER,
            GovernanceRoleAssignment.scope_type == ScopeType.WORKSPACE,
            GovernanceRoleAssignment.is_active == True,
            (GovernanceRoleAssignment.expires_at.is_(None)) | (GovernanceRoleAssignment.expires_at > now)
        ).all()

        is_target_active = assignment.is_active and (assignment.expires_at is None or assignment.expires_at > now)
        if is_target_active and len(active_owners) <= 1:
            # Verify the target is one of the active owners counted
            owner_ids = [o.id for o in active_owners]
            if assignment.id in owner_ids:
                return True

        return False

    @staticmethod
    def log_audit_event(
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        event_type: str,
        action: GovernanceRemediationAction,
        decision: str = "EXECUTED",
        reason: Optional[str] = None
    ) -> None:
        """Create and log a searchable audit event."""
        role_actions = {"REVOKE_ROLE", "CHANGE_ROLE_SCOPE", "EXTEND_ROLE_EXPIRY", "REACTIVATE_ROLE", "DEACTIVATE_ROLE"}
        policy_actions = {"REMOVE_REPOSITORY_POLICY_OVERRIDE", "APPLY_WORKSPACE_DEFAULT_POLICY"}
        exception_actions = {"REVOKE_EXCEPTION", "MARK_EXCEPTION_EXPIRED"}
        finding_actions = {"ACKNOWLEDGE_FINDING", "MARK_REMEDIATION_NOT_REQUIRED"}

        permission_val = None
        if action.action_type in role_actions:
            permission_val = "governance.roles.assign"
        elif action.action_type in policy_actions:
            permission_val = "governance.policy.update"
        elif action.action_type in exception_actions:
            permission_val = "governance.exception.revoke"
        elif action.action_type in finding_actions:
            permission_val = "governance.remediation.confirm"

        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=action.target_user_id,
            repository_id=action.repository_id,
            event_type=event_type,
            permission=permission_val,
            role=action.target_role,
            decision=decision,
            reason=reason or f"Remediation action {action.action_type} executed",
            audit_metadata={
                "action_id": str(action.id),
                "source_type": action.source_type,
                "source_id": str(action.source_id) if action.source_id else None,
                "action_type": action.action_type,
                "target_assignment_id": str(action.target_assignment_id) if action.target_assignment_id else None,
                "target_exception_id": str(action.target_exception_id) if action.target_exception_id else None,
                "target_policy_id": str(action.target_policy_id) if action.target_policy_id else None,
                "impact_preview": action.impact_preview_json,
                "execution_result": action.execution_result_json,
                "failure_reason": action.failure_reason
            }
        )
        db.add(event)
        db.commit()

    @classmethod
    def create_remediation_action(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        requested_by: uuid.UUID,
        source_type: str,
        action_type: str,
        source_id: Optional[uuid.UUID] = None,
        target_user_id: Optional[uuid.UUID] = None,
        target_role: Optional[str] = None,
        target_assignment_id: Optional[uuid.UUID] = None,
        target_exception_id: Optional[uuid.UUID] = None,
        target_policy_id: Optional[uuid.UUID] = None,
        repository_id: Optional[uuid.UUID] = None,
        confirmation_message: Optional[str] = None
    ) -> GovernanceRemediationAction:
        """Create a new manual remediation action in DRAFT state."""
        # Resolve repository_id from assignment or exception if not provided
        resolved_repo_id = repository_id
        if not resolved_repo_id and target_assignment_id:
            assign = db.query(GovernanceRoleAssignment).filter(GovernanceRoleAssignment.id == target_assignment_id).first()
            if assign:
                resolved_repo_id = assign.repository_id
        if not resolved_repo_id and target_exception_id:
            exc = db.query(CICDPolicyException).filter(CICDPolicyException.id == target_exception_id).first()
            if exc:
                resolved_repo_id = exc.repository_id

        # Verification of workspace ownership
        if repository_id:
            repo = db.query(Repository).filter(Repository.id == repository_id, Repository.workspace_id == workspace_id).first()
            if not repo:
                raise ValueError("Repository does not belong to the specified workspace.")

        if target_assignment_id:
            assign = db.query(GovernanceRoleAssignment).filter(
                GovernanceRoleAssignment.id == target_assignment_id,
                GovernanceRoleAssignment.workspace_id == workspace_id
            ).first()
            if not assign:
                raise ValueError("Role assignment does not belong to the specified workspace.")

        if target_exception_id:
            exc = db.query(CICDPolicyException).filter(
                CICDPolicyException.id == target_exception_id,
                CICDPolicyException.workspace_id == workspace_id
            ).first()
            if not exc:
                raise ValueError("Exception does not belong to the specified workspace.")

        if not cls.verify_actor_permissions(db, requested_by, workspace_id, action_type, resolved_repo_id):
            raise PermissionError("Actor does not have permission to create this action.")

        # Default confirmation message
        if not confirmation_message:
            confirmation_message = (
                f"Manual confirmation required for {action_type}. "
                "This action changes governance configuration only after confirmation and does not change evidence, "
                "quality gate, release decision, or GitHub status history."
            )

        action = GovernanceRemediationAction(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            repository_id=repository_id,
            source_type=source_type,
            source_id=source_id,
            action_type=action_type,
            status="DRAFT",
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            target_user_id=target_user_id,
            target_role=target_role,
            target_assignment_id=target_assignment_id,
            target_exception_id=target_exception_id,
            target_policy_id=target_policy_id,
            impact_preview_json={},
            requires_confirmation=True,
            confirmation_message=confirmation_message
        )

        db.add(action)
        db.commit()
        db.refresh(action)

        # Link to access review items if source matches
        if source_type == "ACCESS_REVIEW_ITEM" and source_id:
            item = db.query(GovernanceAccessReviewItem).filter(
                GovernanceAccessReviewItem.id == source_id,
                GovernanceAccessReviewItem.workspace_id == workspace_id
            ).first()
            if item:
                item.remediation_action_id = action.id
                item.remediation_status = "ACTION_CREATED"
                db.commit()

        cls.log_audit_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=requested_by,
            event_type="GOVERNANCE_REMEDIATION_ACTION_CREATED",
            action=action,
            decision="CREATED",
            reason=f"Remediation action {action_type} created in DRAFT"
        )

        return action

    @classmethod
    def preview_remediation_action(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        action_id: uuid.UUID,
        actor_id: uuid.UUID
    ) -> GovernanceRemediationAction:
        """Generate impact preview and update status to PENDING_CONFIRMATION."""
        action = db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.id == action_id,
            GovernanceRemediationAction.workspace_id == workspace_id
        ).first()

        if not action:
            raise ValueError("Remediation action not found.")

        if action.status not in {"DRAFT", "PENDING_CONFIRMATION"}:
            raise ValueError("Can only preview actions in DRAFT or PENDING_CONFIRMATION status.")

        # Re-check permissions
        if not cls.verify_actor_permissions(db, actor_id, workspace_id, action.action_type, action.repository_id):
            raise PermissionError("Actor does not have permission to preview this action.")

        preview = {}

        if action.action_type in {"REVOKE_ROLE", "DEACTIVATE_ROLE", "CHANGE_ROLE_SCOPE", "EXTEND_ROLE_EXPIRY", "REACTIVATE_ROLE"}:
            if not action.target_assignment_id:
                raise ValueError("Target assignment ID is required for role remediations.")
            assignment = db.query(GovernanceRoleAssignment).filter(
                GovernanceRoleAssignment.id == action.target_assignment_id
            ).first()
            if not assignment:
                raise ValueError("Target role assignment not found.")

            user = db.query(User).filter(User.id == assignment.user_id).first()

            preview = {
                "target_user": user.email if user else str(assignment.user_id),
                "current_role": assignment.role.value,
                "current_scope": assignment.scope_type.value,
                "affected_repositories": [str(assignment.repository_id)] if assignment.repository_id else [],
                "current_expiry": assignment.expires_at.isoformat() if assignment.expires_at else None,
                "risk": "HIGH" if assignment.role == GovernanceRole.GOVERNANCE_OWNER else "MEDIUM",
            }

            if action.action_type == "CHANGE_ROLE_SCOPE":
                preview["new_scope"] = "REPOSITORY" if assignment.scope_type == ScopeType.WORKSPACE else "WORKSPACE"
            elif action.action_type == "EXTEND_ROLE_EXPIRY":
                preview["new_expiry"] = (datetime.utcnow().replace(year=datetime.utcnow().year + 1)).isoformat()

        elif action.action_type in {"REMOVE_REPOSITORY_POLICY_OVERRIDE", "APPLY_WORKSPACE_DEFAULT_POLICY"}:
            if not action.repository_id:
                raise ValueError("Repository ID is required for policy remediations.")
            repo = db.query(Repository).filter(Repository.id == action.repository_id).first()
            if not repo:
                raise ValueError("Repository not found.")

            preset_service = CICDPolicyPresetService()
            drift = preset_service.detect_policy_drift(db, action.repository_id)

            preview = {
                "repository": repo.name,
                "current_policy": drift.get("repository_values", {}),
                "workspace_default_policy": drift.get("default_values", {}),
                "diff_summary": drift.get("drift_fields", []),
                "drift_risk_level": drift.get("risk_level", "NONE"),
                "affected_ci_cd_behavior": "Enforces workspace defaults on quality gate verification."
            }

        elif action.action_type in {"REVOKE_EXCEPTION", "MARK_EXCEPTION_EXPIRED"}:
            if not action.target_exception_id:
                raise ValueError("Target exception ID is required for exception remediations.")
            exc = db.query(CICDPolicyException).filter(CICDPolicyException.id == action.target_exception_id).first()
            if not exc:
                raise ValueError("Target exception not found.")

            requester = db.query(User).filter(User.id == exc.requested_by).first()

            preview = {
                "exception_id": str(exc.id),
                "repository_id": str(exc.repository_id),
                "requester": requester.email if requester else str(exc.requested_by),
                "current_status": exc.status,
                "expiry_date": exc.expires_at.isoformat() if exc.expires_at else None,
                "reason": exc.reason,
                "affected_policy": exc.exception_fields
            }

        action.impact_preview_json = preview
        action.status = "PENDING_CONFIRMATION"
        db.commit()
        db.refresh(action)

        # Update access review item status
        if action.source_type == "ACCESS_REVIEW_ITEM" and action.source_id:
            item = db.query(GovernanceAccessReviewItem).filter(GovernanceAccessReviewItem.id == action.source_id).first()
            if item:
                item.remediation_status = "ACTION_CREATED"
                db.commit()

        cls.log_audit_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_REMEDIATION_PREVIEWED",
            action=action,
            decision="PREVIEWED",
            reason=f"Remediation action {action.action_type} preview generated"
        )

        return action

    @classmethod
    def confirm_remediation_action(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        action_id: uuid.UUID,
        confirm_text: str,
        actor_id: uuid.UUID
    ) -> GovernanceRemediationAction:
        """Confirm a remediation action by typing CONFIRM."""
        action = db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.id == action_id,
            GovernanceRemediationAction.workspace_id == workspace_id
        ).first()

        if not action:
            raise ValueError("Remediation action not found.")

        if action.status != "PENDING_CONFIRMATION":
            raise ValueError("Action must be PENDING_CONFIRMATION before confirmation.")

        # Re-check permissions
        if not cls.verify_actor_permissions(db, actor_id, workspace_id, action.action_type, action.repository_id):
            raise PermissionError("Actor does not have permission to confirm this action.")

        if confirm_text != "CONFIRM":
            raise ValueError("Invalid confirmation text. Must type exactly CONFIRM.")

        action.status = "CONFIRMED"
        action.confirmed_by = actor_id
        action.confirmed_at = datetime.utcnow()
        db.commit()
        db.refresh(action)

        # Update access review item status
        if action.source_type == "ACCESS_REVIEW_ITEM" and action.source_id:
            item = db.query(GovernanceAccessReviewItem).filter(GovernanceAccessReviewItem.id == action.source_id).first()
            if item:
                item.remediation_status = "ACTION_CONFIRMED"
                db.commit()

        cls.log_audit_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_REMEDIATION_CONFIRMED",
            action=action,
            decision="CONFIRMED",
            reason=f"Remediation action {action.action_type} confirmed"
        )

        return action

    @classmethod
    def execute_remediation_action(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        action_id: uuid.UUID,
        actor_id: uuid.UUID
    ) -> GovernanceRemediationAction:
        """Execute a confirmed remediation action."""
        action = db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.id == action_id,
            GovernanceRemediationAction.workspace_id == workspace_id
        ).first()

        if not action:
            raise ValueError("Remediation action not found.")

        if action.status != "CONFIRMED":
            raise ValueError("Action must be CONFIRMED before execution.")

        # Re-check permissions again at the boundary
        if not cls.verify_actor_permissions(db, actor_id, workspace_id, action.action_type, action.repository_id):
            action.status = "FAILED"
            action.failure_reason = "Actor does not have execution permissions."
            db.commit()
            cls.log_audit_event(db, workspace_id, actor_id, "GOVERNANCE_REMEDIATION_FAILED", action, "FAILED", action.failure_reason)
            return action

        try:
            # 1. Role Remediation Workflows
            if action.action_type in {"REVOKE_ROLE", "DEACTIVATE_ROLE", "CHANGE_ROLE_SCOPE", "EXTEND_ROLE_EXPIRY", "REACTIVATE_ROLE"}:
                if not action.target_assignment_id:
                    raise ValueError("Target assignment ID is required.")

                # Safety Check: last GOVERNANCE_OWNER check
                if action.action_type in {"REVOKE_ROLE", "DEACTIVATE_ROLE", "CHANGE_ROLE_SCOPE"}:
                    if cls.is_last_active_owner(db, workspace_id, action.target_assignment_id):
                        # Block deactivating or changing scope of the last owner
                        raise ValueError("Cannot mutate the last active GOVERNANCE_OWNER in this workspace.")

                assignment = db.query(GovernanceRoleAssignment).filter(
                    GovernanceRoleAssignment.id == action.target_assignment_id,
                    GovernanceRoleAssignment.workspace_id == workspace_id
                ).first()

                if not assignment:
                    raise ValueError("Role assignment target not found.")

                before_state = {
                    "role": assignment.role.value,
                    "scope_type": assignment.scope_type.value,
                    "repository_id": str(assignment.repository_id) if assignment.repository_id else None,
                    "is_active": assignment.is_active,
                    "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None
                }

                if action.action_type in {"REVOKE_ROLE", "DEACTIVATE_ROLE"}:
                    assignment.is_active = False
                elif action.action_type == "CHANGE_ROLE_SCOPE":
                    # Toggle scope
                    if assignment.scope_type == ScopeType.WORKSPACE:
                        # Cannot change to empty repository scope - need repository_id
                        # If preview specified repository, use it. Otherwise require target repository
                        if not action.repository_id:
                            raise ValueError("Repository ID is required to scope role to repository.")
                        # Verify repository belongs to workspace
                        repo = db.query(Repository).filter(
                            Repository.id == action.repository_id,
                            Repository.workspace_id == workspace_id
                        ).first()
                        if not repo:
                            raise ValueError("Repository does not belong to the specified workspace.")
                        assignment.scope_type = ScopeType.REPOSITORY
                        assignment.repository_id = action.repository_id
                    else:
                        assignment.scope_type = ScopeType.WORKSPACE
                        assignment.repository_id = None
                elif action.action_type == "EXTEND_ROLE_EXPIRY":
                    # Extend by 1 year
                    new_expiry = datetime.utcnow() + timedelta(days=365)
                    if new_expiry <= datetime.utcnow():
                        raise ValueError("Invalid expiry date. Must be in the future.")
                    assignment.expires_at = new_expiry
                elif action.action_type == "REACTIVATE_ROLE":
                    # Reactivate
                    assignment.is_active = True
                    # Expired check
                    if assignment.expires_at and assignment.expires_at < datetime.utcnow():
                        # Set new expiry to 30 days from now if reactivating an expired role
                        assignment.expires_at = datetime.utcnow() + timedelta(days=30)

                db.commit()
                db.refresh(assignment)

                action.execution_result_json = {
                    "before": before_state,
                    "after": {
                        "role": assignment.role.value,
                        "scope_type": assignment.scope_type.value,
                        "repository_id": str(assignment.repository_id) if assignment.repository_id else None,
                        "is_active": assignment.is_active,
                        "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None
                    }
                }

                action.status = "EXECUTED"
                action.completed_at = datetime.utcnow()
                db.commit()

                cls.log_audit_event(
                    db=db,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    event_type="GOVERNANCE_ROLE_REMEDIATION_EXECUTED",
                    action=action,
                    decision="EXECUTED"
                )

            # 2. Policy Remediation Workflows
            elif action.action_type in {"REMOVE_REPOSITORY_POLICY_OVERRIDE", "APPLY_WORKSPACE_DEFAULT_POLICY"}:
                if not action.repository_id:
                    raise ValueError("Repository ID is required.")

                repo = db.query(Repository).filter(
                    Repository.id == action.repository_id,
                    Repository.workspace_id == workspace_id
                ).first()
                if not repo:
                    raise ValueError("Repository does not belong to the specified workspace.")

                policy = db.query(RepositoryCICDPolicy).filter(
                    RepositoryCICDPolicy.repository_id == action.repository_id
                ).first()

                if not policy:
                    raise ValueError("Repository CI/CD policy not found.")

                before_state = {
                    "ci_fail_on_partial": policy.ci_fail_on_partial,
                    "fail_on_unknown_gate": policy.fail_on_unknown_gate,
                    "fail_on_missing_recommendation": policy.fail_on_missing_recommendation,
                    "require_artifact": policy.require_artifact,
                    "require_pr_comment": policy.require_pr_comment,
                    "allow_manual_override": policy.allow_manual_override,
                    "manual_override_requires_reason": policy.manual_override_requires_reason,
                    "strict_mode": policy.strict_mode
                }

                if action.action_type == "REMOVE_REPOSITORY_POLICY_OVERRIDE":
                    # Delete custom repository policy, causing it to fall back to workspace defaults
                    db.delete(policy)
                    db.commit()
                    action.execution_result_json = {
                        "before": before_state,
                        "after": "DELETED (Inheriting Workspace Default)"
                    }
                elif action.action_type == "APPLY_WORKSPACE_DEFAULT_POLICY":
                    # Copy defaults
                    defaults = db.query(WorkspaceCICDPolicyDefault).filter(
                        WorkspaceCICDPolicyDefault.workspace_id == workspace_id
                    ).first()
                    if not defaults:
                        raise ValueError("Workspace default policy not configured.")

                    # Copy defaults to policy
                    if defaults.preset_name == "CUSTOM":
                        settings = defaults.default_policy_json or {}
                    else:
                        from app.services.ci_cd_policy_presets import get_preset_definition
                        preset_def = get_preset_definition(defaults.preset_name)
                        settings = preset_def.get("settings", {})

                    policy.ci_fail_on_partial = settings.get("ci_fail_on_partial", False)
                    policy.fail_on_unknown_gate = settings.get("fail_on_unknown_gate", True)
                    policy.fail_on_missing_recommendation = settings.get("fail_on_missing_recommendation", True)
                    policy.require_artifact = settings.get("require_artifact", True)
                    policy.require_pr_comment = settings.get("require_pr_comment", True)
                    policy.allow_manual_override = settings.get("allow_manual_override", False)
                    policy.manual_override_requires_reason = settings.get("manual_override_requires_reason", True)
                    policy.strict_mode = settings.get("strict_mode", False)
                    policy.updated_at = datetime.utcnow()
                    policy.updated_by = actor_id

                    db.commit()
                    db.refresh(policy)

                    action.execution_result_json = {
                        "before": before_state,
                        "after": {
                            "ci_fail_on_partial": policy.ci_fail_on_partial,
                            "fail_on_unknown_gate": policy.fail_on_unknown_gate,
                            "fail_on_missing_recommendation": policy.fail_on_missing_recommendation,
                            "require_artifact": policy.require_artifact,
                            "require_pr_comment": policy.require_pr_comment,
                            "allow_manual_override": policy.allow_manual_override,
                            "manual_override_requires_reason": policy.manual_override_requires_reason,
                            "strict_mode": policy.strict_mode
                        }
                    }

                action.status = "EXECUTED"
                action.completed_at = datetime.utcnow()
                db.commit()

                cls.log_audit_event(
                    db=db,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    event_type="GOVERNANCE_POLICY_REMEDIATION_EXECUTED",
                    action=action,
                    decision="EXECUTED"
                )

            # 3. Exception Remediation Workflows
            elif action.action_type in {"REVOKE_EXCEPTION", "MARK_EXCEPTION_EXPIRED"}:
                if not action.target_exception_id:
                    raise ValueError("Target exception ID is required.")

                exc = db.query(CICDPolicyException).filter(
                    CICDPolicyException.id == action.target_exception_id,
                    CICDPolicyException.workspace_id == workspace_id
                ).first()

                if not exc:
                    raise ValueError("Exception target not found.")

                if exc.status == "REVOKED" and action.action_type == "REVOKE_EXCEPTION":
                    raise ValueError("Exception is already revoked.")
                if exc.status == "EXPIRED" and action.action_type == "MARK_EXCEPTION_EXPIRED":
                    raise ValueError("Exception is already expired.")

                before_status = exc.status
                exc.status = "REVOKED" if action.action_type == "REVOKE_EXCEPTION" else "EXPIRED"
                exc.updated_at = datetime.utcnow()
                exc.decision_reason = f"Remediated by admin action {action.action_type}"

                db.commit()
                db.refresh(exc)

                action.execution_result_json = {
                    "before_status": before_status,
                    "after_status": exc.status
                }

                action.status = "EXECUTED"
                action.completed_at = datetime.utcnow()
                db.commit()

                cls.log_audit_event(
                    db=db,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    event_type="GOVERNANCE_EXCEPTION_REMEDIATION_EXECUTED",
                    action=action,
                    decision="EXECUTED"
                )

            # 4. Access Review findings tracking
            elif action.action_type in {"ACKNOWLEDGE_FINDING", "MARK_REMEDIATION_NOT_REQUIRED"}:
                action.status = "EXECUTED"
                action.completed_at = datetime.utcnow()
                action.execution_result_json = {"acknowledged": True}
                db.commit()

                cls.log_audit_event(
                    db=db,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    event_type="GOVERNANCE_REMEDIATION_EXECUTED",
                    action=action,
                    decision="EXECUTED"
                )

            else:
                raise NotImplementedError(f"Action type {action.action_type} execution not implemented.")

            # Update linked access review item status
            if action.source_type == "ACCESS_REVIEW_ITEM" and action.source_id:
                item = db.query(GovernanceAccessReviewItem).filter(GovernanceAccessReviewItem.id == action.source_id).first()
                if item:
                    item.remediation_status = "ACTION_EXECUTED"
                    db.commit()

        except Exception as e:
            action.status = "FAILED"
            action.failure_reason = str(e)
            db.commit()

            # Update review item status on failure
            if action.source_type == "ACCESS_REVIEW_ITEM" and action.source_id:
                item = db.query(GovernanceAccessReviewItem).filter(GovernanceAccessReviewItem.id == action.source_id).first()
                if item:
                    item.remediation_status = "ACTION_FAILED"
                    db.commit()

            cls.log_audit_event(
                db=db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                event_type="GOVERNANCE_REMEDIATION_FAILED",
                action=action,
                decision="FAILED",
                reason=action.failure_reason
            )

        return action

    @classmethod
    def cancel_remediation_action(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        action_id: uuid.UUID,
        actor_id: uuid.UUID
    ) -> GovernanceRemediationAction:
        """Cancel a remediation action in DRAFT, PENDING_CONFIRMATION, or CONFIRMED state."""
        action = db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.id == action_id,
            GovernanceRemediationAction.workspace_id == workspace_id
        ).first()

        if not action:
            raise ValueError("Remediation action not found.")

        if action.status not in {"DRAFT", "PENDING_CONFIRMATION", "CONFIRMED"}:
            raise ValueError("Cannot cancel completed, failed, or already cancelled actions.")

        action.status = "CANCELLED"
        action.cancelled_at = datetime.utcnow()
        db.commit()
        db.refresh(action)

        # Update review item status
        if action.source_type == "ACCESS_REVIEW_ITEM" and action.source_id:
            item = db.query(GovernanceAccessReviewItem).filter(GovernanceAccessReviewItem.id == action.source_id).first()
            if item:
                item.remediation_status = "NOT_STARTED"
                db.commit()

        cls.log_audit_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_REMEDIATION_CANCELLED",
            action=action,
            decision="CANCELLED",
            reason="Remediation action cancelled by user"
        )

        return action

    @staticmethod
    def list_remediation_actions(
        db: Session,
        workspace_id: uuid.UUID,
        status: Optional[str] = None,
        action_type: Optional[str] = None,
        source_type: Optional[str] = None
    ) -> List[GovernanceRemediationAction]:
        """List remediation actions in the workspace."""
        query = db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.workspace_id == workspace_id
        )

        if status:
            query = query.filter(GovernanceRemediationAction.status == status)
        if action_type:
            query = query.filter(GovernanceRemediationAction.action_type == action_type)
        if source_type:
            query = query.filter(GovernanceRemediationAction.source_type == source_type)

        return query.order_by(GovernanceRemediationAction.created_at.desc()).all()

    @staticmethod
    def get_remediation_action(
        db: Session,
        workspace_id: uuid.UUID,
        action_id: uuid.UUID
    ) -> Optional[GovernanceRemediationAction]:
        """Get details of a specific remediation action."""
        return db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.id == action_id,
            GovernanceRemediationAction.workspace_id == workspace_id
        ).first()

    @staticmethod
    def get_remediation_summary(db: Session, workspace_id: uuid.UUID) -> Dict[str, Any]:
        """Get summary metrics of remediation actions."""
        actions = db.query(GovernanceRemediationAction).filter(
            GovernanceRemediationAction.workspace_id == workspace_id
        ).all()

        summary = {
            "pending_confirmations": sum(1 for a in actions if a.status == "PENDING_CONFIRMATION"),
            "confirmed_actions": sum(1 for a in actions if a.status == "CONFIRMED"),
            "executed_actions": sum(1 for a in actions if a.status == "EXECUTED"),
            "failed_actions": sum(1 for a in actions if a.status == "FAILED"),
            "cancelled_actions": sum(1 for a in actions if a.status == "CANCELLED"),
            "by_type": {},
            "recent_actions": []
        }

        for action in actions:
            summary["by_type"][action.action_type] = summary["by_type"].get(action.action_type, 0) + 1

        # Sorted by creation
        sorted_actions = sorted(actions, key=lambda x: x.created_at, reverse=True)[:5]
        summary["recent_actions"] = [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
                "completed_at": a.completed_at.isoformat() if a.completed_at else None
            }
            for a in sorted_actions
        ]

        return summary

    @classmethod
    def preview_bulk_remediation(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        bulk_type: str,
        actor_id: uuid.UUID,
        reason: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Identify potential bulk items and generate previews."""
        now = datetime.utcnow()
        previews = []

        if bulk_type == "expired_role_cleanup":
            # Expired role assignments
            expired = db.query(GovernanceRoleAssignment).filter(
                GovernanceRoleAssignment.workspace_id == workspace_id,
                GovernanceRoleAssignment.is_active == True,
                GovernanceRoleAssignment.expires_at < now
            ).all()

            for item in expired:
                previews.append({
                    "item_id": str(item.id),
                    "action_type": "REVOKE_ROLE",
                    "target_id": str(item.id),
                    "target_user_id": str(item.user_id),
                    "details": f"Revoke expired assignment of {item.role.value} for user {item.user_id}."
                })

        elif bulk_type == "expired_exception_cleanup":
            # Expired exceptions
            expired_exc = db.query(CICDPolicyException).filter(
                CICDPolicyException.workspace_id == workspace_id,
                CICDPolicyException.status == "APPROVED",
                CICDPolicyException.expires_at < now
            ).all()

            for item in expired_exc:
                previews.append({
                    "item_id": str(item.id),
                    "action_type": "MARK_EXCEPTION_EXPIRED",
                    "target_id": str(item.id),
                    "details": f"Mark exception on repo {item.repository_id} as expired."
                })

        elif bulk_type == "policy_drift_remediation":
            # Repositories with drift
            repos = db.query(Repository).filter(Repository.workspace_id == workspace_id).all()
            preset_service = CICDPolicyPresetService()
            for repo in repos:
                drift = preset_service.detect_policy_drift(db, repo.id)
                if drift.get("drift_detected"):
                    previews.append({
                        "item_id": str(repo.id),
                        "action_type": "APPLY_WORKSPACE_DEFAULT_POLICY",
                        "target_id": str(repo.id),
                        "details": f"Align repo {repo.name} with workspace default. Drift fields: {', '.join(drift.get('drift_fields', []))}."
                    })

        cls.log_audit_event(
            db=db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_BULK_REMEDIATION_PREVIEWED",
            action=GovernanceRemediationAction(
                workspace_id=workspace_id,
                source_type="MANUAL",
                action_type="ACKNOWLEDGE_FINDING",
                status="DRAFT",
                requested_by=actor_id,
                impact_preview_json={"bulk_type": bulk_type, "count": len(previews)},
                confirmation_message="Bulk preview logs"
            ),
            decision="PREVIEWED"
        )

        return previews

    @classmethod
    def execute_bulk_remediation(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        items: List[Dict[str, Any]],
        actor_id: uuid.UUID,
        reason: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Execute multiple remediation actions with isolated per-item results."""
        results = []

        bulk_event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_BULK_REMEDIATION_EXECUTED",
            permission="governance.remediation.bulk_execute",
            decision="EXECUTED",
            reason=reason or "Bulk remediation execution started",
            requested_count=len(items),
            succeeded_count=0,
            failed_count=0,
            skipped_count=0
        )
        db.add(bulk_event)
        db.commit()

        for item in items:
            item_id = item["item_id"]
            action_type = item["action_type"]
            target_id = item["target_id"]

            try:
                # 1. Create remediation action
                role_actions = {"REVOKE_ROLE", "DEACTIVATE_ROLE", "CHANGE_ROLE_SCOPE", "EXTEND_ROLE_EXPIRY", "REACTIVATE_ROLE"}
                policy_actions = {"REMOVE_REPOSITORY_POLICY_OVERRIDE", "APPLY_WORKSPACE_DEFAULT_POLICY"}
                action = cls.create_remediation_action(
                    db=db,
                    workspace_id=workspace_id,
                    requested_by=actor_id,
                    source_type="MANUAL",
                    action_type=action_type,
                    target_assignment_id=uuid.UUID(target_id) if action_type in role_actions else None,
                    target_exception_id=uuid.UUID(target_id) if action_type in {"REVOKE_EXCEPTION", "MARK_EXCEPTION_EXPIRED"} else None,
                    repository_id=uuid.UUID(target_id) if action_type in policy_actions else None
                )

                # 2. Preview
                cls.preview_remediation_action(db, workspace_id, action.id, actor_id)

                # 3. Confirm
                cls.confirm_remediation_action(db, workspace_id, action.id, "CONFIRM", actor_id)

                # 4. Execute
                executed = cls.execute_remediation_action(db, workspace_id, action.id, actor_id)

                if executed.status == "EXECUTED":
                    results.append({
                        "item_id": item_id,
                        "action_type": action_type,
                        "target_id": target_id,
                        "status": "SUCCESS",
                        "success": True,
                        "failure_reason": None,
                        "execution_result": executed.execution_result_json
                    })
                    bulk_event.succeeded_count += 1
                else:
                    results.append({
                        "item_id": item_id,
                        "action_type": action_type,
                        "target_id": target_id,
                        "status": "FAILED",
                        "success": False,
                        "failure_reason": executed.failure_reason,
                        "execution_result": None
                    })
                    bulk_event.failed_count += 1

            except Exception as e:
                results.append({
                    "item_id": item_id,
                    "action_type": action_type,
                    "target_id": target_id,
                    "status": "FAILED",
                    "success": False,
                    "failure_reason": str(e),
                    "execution_result": None
                })
                bulk_event.failed_count += 1

        db.commit()
        return results
