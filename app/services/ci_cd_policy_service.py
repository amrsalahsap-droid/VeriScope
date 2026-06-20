"""
CI/CD Policy Service

Manages repository-level CI/CD quality gate policies for controlling
how Veriscope maps release decisions into CI results, GitHub statuses/checks,
PR comments, and branch protection behavior.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.repository_ci_cd_policy import RepositoryCICDPolicy
from app.models.repository import Repository
from app.models.pipeline_run import QualityGateStatus
from app.models.release_decision import ReleaseDecision
from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
from app.services.ci_cd_policy_presets import CICDPolicyPreset, get_preset_definition


class CICDPolicyService:
    """Service for managing CI/CD policies."""
    
    def get_policy(self, db: Session, repository_id: UUID) -> RepositoryCICDPolicy:
        """
        Get repository CI/CD policy.
        
        If no policy exists, create a default policy with safe defaults.
        """
        policy = db.query(RepositoryCICDPolicy).filter(
            RepositoryCICDPolicy.repository_id == repository_id
        ).first()
        
        if not policy:
            # Create default policy with safe defaults
            policy = RepositoryCICDPolicy(
                repository_id=repository_id,
                enabled=True,
                required_check_name="Veriscope Quality Gate",
                ci_fail_on_partial=False,
                fail_on_unknown_gate=True,
                fail_on_missing_recommendation=True,
                require_artifact=True,
                require_pr_comment=True,
                allow_manual_override=False,
                manual_override_requires_reason=True,
                strict_mode=False
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
        
        return policy
    
    def get_effective_policy(
        self,
        db: Session,
        repository_id: UUID
    ) -> Dict[str, Any]:
        """
        Get effective policy with inheritance information.
        
        Priority:
        1. Repository explicit policy (if exists)
        2. Workspace default policy (if exists and repository has workspace_id)
        3. System default (STANDARD preset)
        
        Returns:
            Dict with effective policy and source information
        """
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            # Fallback to system default
            preset_definition = get_preset_definition(CICDPolicyPreset.STANDARD.value)
            return {
                "effective_policy": preset_definition["settings"],
                "source": "SYSTEM_DEFAULT",
                "source_preset": CICDPolicyPreset.STANDARD.value,
                "workspace_default_preset": None,
                "repository_override_exists": False,
                "drift_from_default": False,
                "drift_fields": []
            }
        
        # Check for repository explicit policy
        repository_policy = db.query(RepositoryCICDPolicy).filter(
            RepositoryCICDPolicy.repository_id == repository_id
        ).first()
        
        if repository_policy:
            # Repository has explicit policy
            from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
            preset_service = CICDPolicyPresetService()
            detected_preset = preset_service.detect_preset(repository_policy)
            
            # Check for drift from workspace default (only if repository has workspace_id)
            drift_from_default = False
            drift_fields = []
            workspace_default_preset = None
            
            if hasattr(repository, 'workspace_id') and repository.workspace_id:
                workspace_default = db.query(WorkspaceCICDPolicyDefault).filter(
                    WorkspaceCICDPolicyDefault.workspace_id == repository.workspace_id
                ).first()
                
                if workspace_default:
                    workspace_default_preset = workspace_default.preset_name
                    if detected_preset != CICDPolicyPreset.CUSTOM.value and detected_preset != workspace_default_preset:
                        drift_from_default = True
                        drift_fields = ["preset_mismatch"]
            
            return {
                "effective_policy": {
                    "enabled": repository_policy.enabled,
                    "required_check_name": repository_policy.required_check_name,
                    "ci_fail_on_partial": repository_policy.ci_fail_on_partial,
                    "fail_on_unknown_gate": repository_policy.fail_on_unknown_gate,
                    "fail_on_missing_recommendation": repository_policy.fail_on_missing_recommendation,
                    "require_artifact": repository_policy.require_artifact,
                    "require_pr_comment": repository_policy.require_pr_comment,
                    "allow_manual_override": repository_policy.allow_manual_override,
                    "manual_override_requires_reason": repository_policy.manual_override_requires_reason,
                    "strict_mode": repository_policy.strict_mode
                },
                "source": "REPOSITORY_OVERRIDE",
                "source_preset": detected_preset,
                "workspace_default_preset": workspace_default_preset,
                "repository_override_exists": True,
                "drift_from_default": drift_from_default,
                "drift_fields": drift_fields
            }
        
        # No repository policy, check workspace default (only if repository has workspace_id)
        if hasattr(repository, 'workspace_id') and repository.workspace_id:
            workspace_default = db.query(WorkspaceCICDPolicyDefault).filter(
                WorkspaceCICDPolicyDefault.workspace_id == repository.workspace_id
            ).first()
            
            if workspace_default:
                # Use workspace default
                default_preset = workspace_default.preset_name
                if default_preset == CICDPolicyPreset.CUSTOM.value:
                    effective_settings = workspace_default.default_policy_json or {}
                else:
                    preset_definition = get_preset_definition(default_preset)
                    effective_settings = preset_definition.get("settings", {})
                
                return {
                    "effective_policy": effective_settings,
                    "source": "WORKSPACE_DEFAULT",
                    "source_preset": default_preset,
                    "workspace_default_preset": default_preset,
                    "repository_override_exists": False,
                    "drift_from_default": False,
                    "drift_fields": []
                }
        
        # No organization default or repository doesn't have organization_id, use system default
        preset_definition = get_preset_definition(CICDPolicyPreset.STANDARD.value)
        return {
            "effective_policy": preset_definition["settings"],
            "source": "SYSTEM_DEFAULT",
            "source_preset": CICDPolicyPreset.STANDARD.value,
            "workspace_default_preset": None,
            "repository_override_exists": False,
            "drift_from_default": False,
            "drift_fields": []
        }
    
    def update_policy(
        self,
        db: Session,
        repository_id: UUID,
        payload: Dict[str, Any],
        actor_id: Optional[UUID] = None
    ) -> RepositoryCICDPolicy:
        """
        Update repository CI/CD policy.
        
        Args:
            db: Database session
            repository_id: Repository ID
            payload: Policy update payload
            actor_id: User ID making the change (for audit)
        
        Returns:
            Updated policy
        """
        policy = self.get_policy(db, repository_id)
        
        # Track changes for audit
        before = {
            "enabled": policy.enabled,
            "required_check_name": policy.required_check_name,
            "ci_fail_on_partial": policy.ci_fail_on_partial,
            "fail_on_unknown_gate": policy.fail_on_unknown_gate,
            "fail_on_missing_recommendation": policy.fail_on_missing_recommendation,
            "require_artifact": policy.require_artifact,
            "require_pr_comment": policy.require_pr_comment,
            "allow_manual_override": policy.allow_manual_override,
            "manual_override_requires_reason": policy.manual_override_requires_reason,
            "strict_mode": policy.strict_mode
        }
        
        # Update fields from payload
        if "enabled" in payload:
            policy.enabled = payload["enabled"]
        if "required_check_name" in payload:
            policy.required_check_name = payload["required_check_name"]
        if "ci_fail_on_partial" in payload:
            policy.ci_fail_on_partial = payload["ci_fail_on_partial"]
        if "fail_on_unknown_gate" in payload:
            policy.fail_on_unknown_gate = payload["fail_on_unknown_gate"]
        if "fail_on_missing_recommendation" in payload:
            policy.fail_on_missing_recommendation = payload["fail_on_missing_recommendation"]
        if "require_artifact" in payload:
            policy.require_artifact = payload["require_artifact"]
        if "require_pr_comment" in payload:
            policy.require_pr_comment = payload["require_pr_comment"]
        if "allow_manual_override" in payload:
            policy.allow_manual_override = payload["allow_manual_override"]
        if "manual_override_requires_reason" in payload:
            policy.manual_override_requires_reason = payload["manual_override_requires_reason"]
        if "strict_mode" in payload:
            policy.strict_mode = payload["strict_mode"]
        
        policy.updated_at = datetime.utcnow()
        policy.updated_by = actor_id
        
        db.commit()
        db.refresh(policy)
        
        # TODO: Log audit event for policy update
        
        return policy
    
    def resolve_quality_gate_outcome(
        self,
        db: Session,
        repository_id: UUID,
        release_decision: Optional[str],
        recommendation_health: Optional[str],
        quality_gate: Optional[str],
        has_recommendation_run: bool = True
    ) -> Dict[str, Any]:
        """
        Resolve quality gate outcome based on policy.
        
        Args:
            db: Database session
            repository_id: Repository ID
            release_decision: Release decision value
            recommendation_health: Recommendation health status
            quality_gate: Current quality gate
            has_recommendation_run: Whether a recommendation run exists
        
        Returns:
            Dict with github_conclusion, would_block_pr, quality_gate, reason, rules_applied
        """
        policy = self.get_policy(db, repository_id)
        
        # If policy is disabled, return neutral
        if not policy.enabled:
            return {
                "github_conclusion": "neutral",
                "would_block_pr": False,
                "quality_gate": quality_gate or "UNKNOWN",
                "reason": "CI/CD policy is disabled for this repository.",
                "rules_applied": ["POLICY_DISABLED"]
            }
        
        # Handle missing recommendation run
        if not has_recommendation_run:
            if policy.fail_on_missing_recommendation:
                return {
                    "github_conclusion": "failure",
                    "would_block_pr": True,
                    "quality_gate": "UNKNOWN",
                    "reason": "No recommendation run exists and fail_on_missing_recommendation is enabled.",
                    "rules_applied": ["MISSING_RECOMMENDATION", "FAIL_ON_MISSING_RECOMMENDATION_TRUE"]
                }
            else:
                return {
                    "github_conclusion": "neutral",
                    "would_block_pr": False,
                    "quality_gate": "UNKNOWN",
                    "reason": "No recommendation run exists but fail_on_missing_recommendation is disabled.",
                    "rules_applied": ["MISSING_RECOMMENDATION", "FAIL_ON_MISSING_RECOMMENDATION_FALSE"]
                }
        
        # Map release decision to quality gate
        if quality_gate is None:
            # Compute quality gate from release decision
            if release_decision == "Fully Verified":
                quality_gate = QualityGateStatus.PASSED.value
            elif release_decision == "Partially Verified":
                quality_gate = QualityGateStatus.PARTIAL.value
            elif release_decision == "Not Verified":
                quality_gate = QualityGateStatus.FAILED.value
            elif release_decision == "Blocked":
                quality_gate = QualityGateStatus.BLOCKED.value
            else:
                quality_gate = QualityGateStatus.UNKNOWN.value
        
        # Apply quality gate rules
        rules_applied = []
        
        if quality_gate == QualityGateStatus.PASSED.value:
            # PASSED always maps to success
            github_conclusion = "success"
            would_block_pr = False
            reason = "Release decision is Fully Verified."
            rules_applied.append("QUALITY_GATE_PASSED")
        
        elif quality_gate == QualityGateStatus.FAILED.value:
            github_conclusion = "failure"
            would_block_pr = True
            reason = "Release decision is Not Verified."
            rules_applied.append("QUALITY_GATE_FAILED")
        
        elif quality_gate == QualityGateStatus.BLOCKED.value:
            github_conclusion = "failure"
            would_block_pr = True
            reason = "Release decision is Blocked."
            rules_applied.append("QUALITY_GATE_BLOCKED")
        
        elif quality_gate == QualityGateStatus.PARTIAL.value:
            if policy.ci_fail_on_partial or policy.strict_mode:
                github_conclusion = "failure"
                would_block_pr = True
                reason = "Release decision is Partially Verified and ciFailOnPartial is enabled (or strict mode)."
                rules_applied.extend(["QUALITY_GATE_PARTIAL", "CI_FAIL_ON_PARTIAL_TRUE"])
            else:
                github_conclusion = "neutral"
                would_block_pr = False
                reason = "Release decision is Partially Verified and ciFailOnPartial is disabled."
                rules_applied.extend(["QUALITY_GATE_PARTIAL", "CI_FAIL_ON_PARTIAL_FALSE"])
        
        elif quality_gate == QualityGateStatus.UNKNOWN.value:
            if policy.fail_on_unknown_gate or policy.strict_mode:
                github_conclusion = "failure"
                would_block_pr = True
                reason = "Quality gate is UNKNOWN and fail_on_unknown_gate is enabled (or strict mode)."
                rules_applied.extend(["QUALITY_GATE_UNKNOWN", "FAIL_ON_UNKNOWN_GATE_TRUE"])
            else:
                github_conclusion = "neutral"
                would_block_pr = False
                reason = "Quality gate is UNKNOWN but fail_on_unknown_gate is disabled."
                rules_applied.extend(["QUALITY_GATE_UNKNOWN", "FAIL_ON_UNKNOWN_GATE_FALSE"])
        
        else:
            # Default to neutral for unknown quality gates
            github_conclusion = "neutral"
            would_block_pr = False
            reason = "Unknown quality gate state."
            rules_applied.append("UNKNOWN_QUALITY_GATE")
        
        # Hard rule: Recommendation Health Ready must never publish success unless Release Decision is Fully Verified
        # This guard only prevents invalid success, does not override valid neutral/failure policy behavior
        if github_conclusion == "success" and recommendation_health == "Ready" and release_decision != "Fully Verified":
            github_conclusion = "failure"
            would_block_pr = True
            reason = "Recommendation Health is Ready but Release Decision is not Fully Verified. Hard rule violation."
            rules_applied.append("HARD_RULE_READY_REQUIRES_FULLY_VERIFIED")
        
        return {
            "github_conclusion": github_conclusion,
            "would_block_pr": would_block_pr,
            "quality_gate": quality_gate,
            "reason": reason,
            "rules_applied": rules_applied
        }
    
    def export_policy(
        self,
        db: Session,
        repository_id: UUID
    ) -> Dict[str, Any]:
        """
        Export repository policy as JSON.
        
        Args:
            db: Database session
            repository_id: Repository ID
        
        Returns:
            Export JSON with version, type, preset, and policy settings
        """
        policy = self.get_policy(db, repository_id)
        
        from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
        preset_service = CICDPolicyPresetService()
        detected_preset = preset_service.detect_preset(policy)
        
        return {
            "version": "1.0",
            "type": "veriscope.cicd.policy",
            "preset": detected_preset,
            "policy": {
                "enabled": policy.enabled,
                "required_check_name": policy.required_check_name,
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
    
    def import_policy(
        self,
        db: Session,
        repository_id: UUID,
        import_data: Dict[str, Any],
        actor_id: Optional[UUID] = None
    ) -> RepositoryCICDPolicy:
        """
        Import policy from JSON.
        
        Args:
            db: Database session
            repository_id: Repository ID
            import_data: Import JSON data
            actor_id: Actor ID (user who imported the policy)
        
        Returns:
            Updated repository policy
        """
        # Validate schema
        if import_data.get("type") != "veriscope.cicd.policy":
            raise ValueError("Invalid import type: must be veriscope.cicd.policy")
        
        if "policy" not in import_data:
            raise ValueError("Missing policy field in import data")
        
        policy_data = import_data["policy"]
        
        # Validate allowed fields
        allowed_fields = {
            "enabled", "required_check_name", "ci_fail_on_partial",
            "fail_on_unknown_gate", "fail_on_missing_recommendation",
            "require_artifact", "require_pr_comment", "allow_manual_override",
            "manual_override_requires_reason", "strict_mode"
        }
        
        for field in policy_data:
            if field not in allowed_fields:
                raise ValueError(f"Unknown field in import data: {field}")
        
        # Import policy
        policy = self.update_policy(db, repository_id, policy_data, actor_id)
        
        # Log audit event
        from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService
        CICDPolicyAuditService.log_policy_updated(
            db=db,
            repository_id=repository_id,
            before_policy={},
            after_policy=policy_data,
            changed_fields=list(policy_data.keys()),
            actor_id=actor_id,
            actor_type="USER"
        )
        
        return policy
    
    def clone_policy(
        self,
        db: Session,
        source_repository_id: UUID,
        target_repository_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> RepositoryCICDPolicy:
        """
        Clone policy from one repository to another.
        
        Args:
            db: Database session
            source_repository_id: Source repository ID
            target_repository_id: Target repository ID
            actor_id: Actor ID (user who cloned the policy)
        
        Returns:
            Updated target repository policy
        """
        # Get source policy
        source_policy = self.get_policy(db, source_repository_id)
        
        # Prepare clone data
        clone_data = {
            "enabled": source_policy.enabled,
            "required_check_name": source_policy.required_check_name,
            "ci_fail_on_partial": source_policy.ci_fail_on_partial,
            "fail_on_unknown_gate": source_policy.fail_on_unknown_gate,
            "fail_on_missing_recommendation": source_policy.fail_on_missing_recommendation,
            "require_artifact": source_policy.require_artifact,
            "require_pr_comment": source_policy.require_pr_comment,
            "allow_manual_override": source_policy.allow_manual_override,
            "manual_override_requires_reason": source_policy.manual_override_requires_reason,
            "strict_mode": source_policy.strict_mode
        }
        
        # Apply to target
        target_policy = self.update_policy(db, target_repository_id, clone_data, actor_id)
        
        # Log audit event
        from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService
        CICDPolicyAuditService.log_policy_updated(
            db=db,
            repository_id=target_repository_id,
            before_policy={},
            after_policy=clone_data,
            changed_fields=list(clone_data.keys()),
            actor_id=actor_id,
            actor_type="USER"
        )
        
        return target_policy
    
    def apply_manual_override(
        self,
        db: Session,
        repository_id: UUID,
        original_quality_gate: str,
        override_decision: str,
        reason: str,
        actor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Apply manual override to quality gate decision.
        
        Args:
            db: Database session
            repository_id: Repository ID
            original_quality_gate: Original quality gate value
            override_decision: Override decision (success, failure, neutral)
            reason: Reason for the override
            actor_id: User ID applying the override
        
        Returns:
            Dict with override details
        
        Raises:
            ValueError: If manual override is not allowed or reason is required but not provided
        """
        policy = self.get_policy(db, repository_id)
        
        # Check if manual override is allowed
        if not policy.allow_manual_override:
            raise ValueError("Manual override is not allowed for this repository")
        
        # Check if reason is required
        if policy.manual_override_requires_reason and not reason:
            raise ValueError("Reason is required for manual override")
        
        # Log the override event
        from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService
        CICDPolicyAuditService.log_manual_override(
            db=db,
            repository_id=repository_id,
            original_quality_gate=original_quality_gate,
            override_decision=override_decision,
            reason=reason,
            actor_id=actor_id,
            actor_type="USER"
        )
        
        return {
            "original_quality_gate": original_quality_gate,
            "override_decision": override_decision,
            "reason": reason,
            "actor_id": str(actor_id) if actor_id else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def preview_policy(
        self,
        db: Session,
        repository_id: UUID,
        scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preview policy outcome for a given scenario.
        
        Args:
            db: Database session
            repository_id: Repository ID
            scenario: Scenario with release_decision, recommendation_health, quality_gate, etc.
        
        Returns:
            Preview result with github_conclusion, would_block_pr, reason, rules_applied
        """
        release_decision = scenario.get("releaseDecision")
        recommendation_health = scenario.get("recommendationHealth")
        quality_gate = scenario.get("qualityGate")
        has_recommendation_run = scenario.get("hasRecommendationRun", True)
        
        return self.resolve_quality_gate_outcome(
            db=db,
            repository_id=repository_id,
            release_decision=release_decision,
            recommendation_health=recommendation_health,
            quality_gate=quality_gate,
            has_recommendation_run=has_recommendation_run
        )
