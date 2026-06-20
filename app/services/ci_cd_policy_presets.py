"""
CI/CD Policy Presets

Predefined policy configurations for enterprise governance.
"""

from enum import Enum
from typing import Dict, Any

class CICDPolicyPreset(str, Enum):
    """Available CI/CD policy presets."""
    PERMISSIVE = "PERMISSIVE"
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    REGULATED = "REGULATED"
    CUSTOM = "CUSTOM"


# Preset definitions
PRESET_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    CICDPolicyPreset.PERMISSIVE.value: {
        "name": "Permissive",
        "description": "Minimal quality gate enforcement. Suitable for experimental or low-risk repositories.",
        "risk_level": "LOW",
        "recommended_use_case": "Experimental repositories, internal tools, non-critical services",
        "settings": {
            "ci_fail_on_partial": False,
            "fail_on_unknown_gate": False,
            "fail_on_missing_recommendation": False,
            "require_artifact": False,
            "require_pr_comment": False,
            "allow_manual_override": True,
            "manual_override_requires_reason": False,
            "strict_mode": False
        },
        "impact": {
            "partial": "neutral (does not block PR)",
            "unknown": "neutral (does not block PR)",
            "missing_recommendation": "neutral (does not block PR)",
            "manual_override": "allowed without reason",
            "artifact_requirement": "not required",
            "pr_comment_requirement": "not required"
        }
    },
    
    CICDPolicyPreset.STANDARD.value: {
        "name": "Standard",
        "description": "Balanced quality gate enforcement. Suitable for most production repositories.",
        "risk_level": "MEDIUM",
        "recommended_use_case": "Production services, customer-facing applications, standard repositories",
        "settings": {
            "ci_fail_on_partial": False,
            "fail_on_unknown_gate": True,
            "fail_on_missing_recommendation": True,
            "require_artifact": True,
            "require_pr_comment": True,
            "allow_manual_override": False,
            "manual_override_requires_reason": False,
            "strict_mode": False
        },
        "impact": {
            "partial": "neutral (does not block PR)",
            "unknown": "failure (blocks PR)",
            "missing_recommendation": "failure (blocks PR)",
            "manual_override": "not allowed",
            "artifact_requirement": "required",
            "pr_comment_requirement": "required"
        }
    },
    
    CICDPolicyPreset.STRICT.value: {
        "name": "Strict",
        "description": "High quality gate enforcement. Suitable for critical production repositories.",
        "risk_level": "HIGH",
        "recommended_use_case": "Critical production services, security-sensitive applications, core infrastructure",
        "settings": {
            "ci_fail_on_partial": True,
            "fail_on_unknown_gate": True,
            "fail_on_missing_recommendation": True,
            "require_artifact": True,
            "require_pr_comment": True,
            "allow_manual_override": False,
            "manual_override_requires_reason": False,
            "strict_mode": True
        },
        "impact": {
            "partial": "failure (blocks PR)",
            "unknown": "failure (blocks PR)",
            "missing_recommendation": "failure (blocks PR)",
            "manual_override": "not allowed",
            "artifact_requirement": "required",
            "pr_comment_requirement": "required"
        }
    },
    
    CICDPolicyPreset.REGULATED.value: {
        "name": "Regulated",
        "description": "Maximum quality gate enforcement with audit trail. Suitable for regulated industries.",
        "risk_level": "CRITICAL",
        "recommended_use_case": "Regulated industries (finance, healthcare), compliance-required applications",
        "settings": {
            "ci_fail_on_partial": True,
            "fail_on_unknown_gate": True,
            "fail_on_missing_recommendation": True,
            "require_artifact": True,
            "require_pr_comment": True,
            "allow_manual_override": True,
            "manual_override_requires_reason": True,
            "strict_mode": True
        },
        "impact": {
            "partial": "failure (blocks PR)",
            "unknown": "failure (blocks PR)",
            "missing_recommendation": "failure (blocks PR)",
            "manual_override": "allowed with reason (audited)",
            "artifact_requirement": "required",
            "pr_comment_requirement": "required"
        }
    }
}


def get_preset_definition(preset_name: str) -> Dict[str, Any]:
    """Get preset definition by name."""
    if preset_name == CICDPolicyPreset.CUSTOM.value:
        return {
            "name": "Custom",
            "description": "Custom policy configuration. Repository policy has been manually modified.",
            "risk_level": "VARIES",
            "recommended_use_case": "Repository-specific requirements",
            "settings": {},
            "impact": {
                "partial": "depends on configuration",
                "unknown": "depends on configuration",
                "missing_recommendation": "depends on configuration",
                "manual_override": "depends on configuration",
                "artifact_requirement": "depends on configuration",
                "pr_comment_requirement": "depends on configuration"
            }
        }
    return PRESET_DEFINITIONS.get(preset_name, {})


def list_presets() -> list:
    """List all available presets."""
    return [
        CICDPolicyPreset.PERMISSIVE.value,
        CICDPolicyPreset.STANDARD.value,
        CICDPolicyPreset.STRICT.value,
        CICDPolicyPreset.REGULATED.value
    ]
