"""
CI/CD Policy Preset Service

Service for managing policy presets, applying presets to repositories,
detecting drift, and recommending presets based on repository risk.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.ci_cd_policy_presets import (
    CICDPolicyPreset,
    get_preset_definition,
    list_presets,
    PRESET_DEFINITIONS
)
from app.models.repository_ci_cd_policy import RepositoryCICDPolicy
from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService


class CICDPolicyPresetService:
    """Service for CI/CD policy preset management."""
    
    def list_presets(self) -> List[Dict[str, Any]]:
        """List all available presets with their definitions."""
        presets = []
        for preset_name in list_presets():
            definition = get_preset_definition(preset_name)
            presets.append({
                "name": preset_name,
                "definition": definition
            })
        return presets
    
    def get_preset(self, preset_name: str) -> Dict[str, Any]:
        """Get a specific preset definition."""
        return get_preset_definition(preset_name)
    
    def apply_preset(
        self,
        db: Session,
        repository_id: UUID,
        preset_name: str,
        actor_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> RepositoryCICDPolicy:
        """
        Apply a preset to a repository policy.
        
        Args:
            db: Database session
            repository_id: Repository ID
            preset_name: Preset name to apply
            actor_id: Actor ID (user who applied the preset)
            reason: Reason for applying the preset
        
        Returns:
            Updated repository policy
        """
        if preset_name == CICDPolicyPreset.CUSTOM.value:
            raise ValueError("Cannot apply CUSTOM preset - it is a detection state, not a configuration")
        
        preset_definition = get_preset_definition(preset_name)
        if not preset_definition:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        # Get or create repository policy
        from app.services.ci_cd_policy_service import CICDPolicyService
        policy_service = CICDPolicyService()
        policy = policy_service.get_policy(db, repository_id)
        
        # Store before state for audit
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
        
        # Apply preset settings
        settings = preset_definition["settings"]
        policy.ci_fail_on_partial = settings["ci_fail_on_partial"]
        policy.fail_on_unknown_gate = settings["fail_on_unknown_gate"]
        policy.fail_on_missing_recommendation = settings["fail_on_missing_recommendation"]
        policy.require_artifact = settings["require_artifact"]
        policy.require_pr_comment = settings["require_pr_comment"]
        policy.allow_manual_override = settings["allow_manual_override"]
        policy.manual_override_requires_reason = settings["manual_override_requires_reason"]
        policy.strict_mode = settings["strict_mode"]
        policy.updated_at = datetime.utcnow()
        policy.updated_by = actor_id
        
        db.commit()
        db.refresh(policy)
        
        # Log audit event
        after_state = settings.copy()
        changed_fields = list(settings.keys())
        
        CICDPolicyAuditService.log_policy_updated(
            db=db,
            repository_id=repository_id,
            before_policy=before_state,
            after_policy=after_state,
            changed_fields=changed_fields,
            actor_id=actor_id,
            actor_type="USER"
        )
        
        return policy
    
    def detect_preset(self, policy: RepositoryCICDPolicy) -> str:
        """
        Detect which preset a repository policy matches.
        
        Returns CUSTOM if policy does not exactly match any preset.
        
        Args:
            policy: Repository policy
        
        Returns:
            Preset name (PERMISSIVE, STANDARD, STRICT, REGULATED, or CUSTOM)
        """
        policy_settings = {
            "ci_fail_on_partial": policy.ci_fail_on_partial,
            "fail_on_unknown_gate": policy.fail_on_unknown_gate,
            "fail_on_missing_recommendation": policy.fail_on_missing_recommendation,
            "require_artifact": policy.require_artifact,
            "require_pr_comment": policy.require_pr_comment,
            "allow_manual_override": policy.allow_manual_override,
            "manual_override_requires_reason": policy.manual_override_requires_reason,
            "strict_mode": policy.strict_mode
        }
        
        for preset_name, preset_definition in PRESET_DEFINITIONS.items():
            if policy_settings == preset_definition["settings"]:
                return preset_name
        
        return CICDPolicyPreset.CUSTOM.value
    
    def compare_with_preset(
        self,
        policy: RepositoryCICDPolicy,
        preset_name: str
    ) -> Dict[str, Any]:
        """
        Compare a repository policy to a preset.
        
        Args:
            policy: Repository policy
            preset_name: Preset name to compare against
        
        Returns:
            Comparison result with differences
        """
        preset_definition = get_preset_definition(preset_name)
        if not preset_definition:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        preset_settings = preset_definition["settings"]
        
        policy_settings = {
            "ci_fail_on_partial": policy.ci_fail_on_partial,
            "fail_on_unknown_gate": policy.fail_on_unknown_gate,
            "fail_on_missing_recommendation": policy.fail_on_missing_recommendation,
            "require_artifact": policy.require_artifact,
            "require_pr_comment": policy.require_pr_comment,
            "allow_manual_override": policy.allow_manual_override,
            "manual_override_requires_reason": policy.manual_override_requires_reason,
            "strict_mode": policy.strict_mode
        }
        
        differences = {}
        for field in preset_settings:
            if policy_settings[field] != preset_settings[field]:
                differences[field] = {
                    "preset_value": preset_settings[field],
                    "policy_value": policy_settings[field]
                }
        
        return {
            "preset_name": preset_name,
            "matches": len(differences) == 0,
            "differences": differences
        }
    
    def recommend_preset(
        self,
        db: Session,
        repository_id: UUID
    ) -> Dict[str, Any]:
        """
        Recommend a preset based on repository metadata and risk.
        
        Args:
            db: Database session
            repository_id: Repository ID
        
        Returns:
            Recommendation with preset, confidence, reasons, and risk signals
        """
        from app.models.repository import Repository
        from app.models.pipeline_run import PipelineRun
        from app.models.ci_cd_policy_audit import CICDPolicyAuditEvent
        
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            return {
                "recommended_preset": CICDPolicyPreset.STANDARD.value,
                "confidence": "LOW",
                "reasons": ["Repository not found"],
                "risk_signals": [],
                "tradeoffs": []
            }
        
        risk_signals = []
        reasons = []
        
        # Check repository visibility
        if repository.visibility == "public":
            risk_signals.append("public_repository")
            reasons.append("Public repository - may benefit from STANDARD or STRICT")
        elif repository.visibility == "private":
            risk_signals.append("private_repository")
        
        # Check for regulated labels/tags (if available)
        # This would require repository metadata fields for tags/labels
        # For now, we'll skip this as it may not be available
        
        # Check recent quality gate history
        recent_runs = db.query(PipelineRun).filter(
            PipelineRun.repository_id == repository_id
        ).order_by(PipelineRun.created_at.desc()).limit(20).all()
        
        if recent_runs:
            unknown_count = sum(1 for run in recent_runs if run.quality_gate == "UNKNOWN")
            if unknown_count > 5:
                risk_signals.append("high_unknown_frequency")
                reasons.append("High frequency of UNKNOWN quality gates - may benefit from STRICT")
        
        # Check manual override history
        override_events = db.query(CICDPolicyAuditEvent).filter(
            CICDPolicyAuditEvent.repository_id == repository_id,
            CICDPolicyAuditEvent.event_type == "MANUAL_OVERRIDE"
        ).count()
        
        if override_events > 3:
            risk_signals.append("high_override_frequency")
            reasons.append("High frequency of manual overrides - may benefit from REGULATED")
        
        # Determine recommendation based on risk signals
        if len(risk_signals) == 0:
            return {
                "recommended_preset": CICDPolicyPreset.STANDARD.value,
                "confidence": "LOW",
                "reasons": ["Insufficient repository risk metadata; STANDARD is safest default."],
                "risk_signals": [],
                "tradeoffs": [
                    "STANDARD provides balanced enforcement for most use cases",
                    "Can be adjusted later based on actual needs"
                ]
            }
        
        if "high_override_frequency" in risk_signals:
            return {
                "recommended_preset": CICDPolicyPreset.REGULATED.value,
                "confidence": "MEDIUM",
                "reasons": reasons,
                "risk_signals": risk_signals,
                "tradeoffs": [
                    "REGULATED provides maximum enforcement with audit trail",
                    "Manual overrides are allowed but require reason and are audited",
                    "Suitable for compliance-required environments"
                ]
            }
        
        if "high_unknown_frequency" in risk_signals or "public_repository" in risk_signals:
            return {
                "recommended_preset": CICDPolicyPreset.STRICT.value,
                "confidence": "MEDIUM",
                "reasons": reasons,
                "risk_signals": risk_signals,
                "tradeoffs": [
                    "STRICT provides high enforcement for critical repositories",
                    "All non-PASSED quality gates will fail the CI check",
                    "Suitable for production and security-sensitive applications"
                ]
            }
        
        # Default to STANDARD
        return {
            "recommended_preset": CICDPolicyPreset.STANDARD.value,
            "confidence": "LOW",
            "reasons": ["Insufficient risk signals; STANDARD is safest default."],
            "risk_signals": risk_signals,
            "tradeoffs": [
                "STANDARD provides balanced enforcement for most use cases",
                "Can be adjusted later based on actual needs"
            ]
        }
    
    def detect_policy_drift(
        self,
        db: Session,
        repository_id: UUID
    ) -> Dict[str, Any]:
        """
        Detect drift from organization default policy.
        
        Args:
            db: Database session
            repository_id: Repository ID
        
        Returns:
            Drift detection result
        """
        from app.services.ci_cd_policy_service import CICDPolicyService
        from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
        
        policy_service = CICDPolicyService()
        repository_policy = policy_service.get_policy(db, repository_id)
        
        # Get repository
        from app.models.repository import Repository
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            return {
                "drift_detected": False,
                "drift_fields": [],
                "default_values": {},
                "repository_values": {},
                "risk_level": "NONE",
                "recommended_action": "None"
            }
        
        # Get workspace default (only if repository has workspace_id)
        workspace_default = None
        if hasattr(repository, 'workspace_id') and repository.workspace_id:
            workspace_default = db.query(WorkspaceCICDPolicyDefault).filter(
                WorkspaceCICDPolicyDefault.workspace_id == repository.workspace_id
            ).first()
        
        if not workspace_default:
            return {
                "drift_detected": False,
                "drift_fields": [],
                "default_values": {},
                "repository_values": {},
                "risk_level": "NONE",
                "recommended_action": "Configure workspace default policy"
            }
        
        # Get default preset settings
        default_preset = workspace_default.preset_name
        if default_preset == CICDPolicyPreset.CUSTOM.value:
            default_settings = workspace_default.default_policy_json or {}
        else:
            preset_definition = get_preset_definition(default_preset)
            default_settings = preset_definition.get("settings", {})
        
        # Compare settings
        repository_settings = {
            "ci_fail_on_partial": repository_policy.ci_fail_on_partial,
            "fail_on_unknown_gate": repository_policy.fail_on_unknown_gate,
            "fail_on_missing_recommendation": repository_policy.fail_on_missing_recommendation,
            "require_artifact": repository_policy.require_artifact,
            "require_pr_comment": repository_policy.require_pr_comment,
            "allow_manual_override": repository_policy.allow_manual_override,
            "manual_override_requires_reason": repository_policy.manual_override_requires_reason,
            "strict_mode": repository_policy.strict_mode
        }
        
        drift_fields = []
        for field in default_settings:
            if repository_settings[field] != default_settings[field]:
                drift_fields.append(field)
        
        # Determine risk level
        risk_level = "NONE"
        if drift_fields:
            # Check for high-risk drifts
            high_risk_fields = ["ci_fail_on_partial", "fail_on_unknown_gate", "require_artifact"]
            if any(field in drift_fields for field in high_risk_fields):
                risk_level = "HIGH"
            else:
                risk_level = "MEDIUM"
        
        recommended_action = "None"
        if risk_level == "HIGH":
            recommended_action = "Review and align with organization default or document justification"
        elif risk_level == "MEDIUM":
            recommended_action = "Consider aligning with organization default"
        
        return {
            "drift_detected": len(drift_fields) > 0,
            "drift_fields": drift_fields,
            "default_values": default_settings,
            "repository_values": repository_settings,
            "risk_level": risk_level,
            "recommended_action": recommended_action
        }
