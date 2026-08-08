"""Behavior Taxonomy v2 - Config-driven, generic mapping from changed files to business flows.

This is a generic and extensible classification engine for change impact analysis.
"""

import json
import os
import re
from typing import Dict, List, Set, Optional
from pathlib import Path

# Load config globally on import
CONFIG_FILENAME = "veriscope.config.json"
_loaded_config = {}

def load_repository_config(repo_root: Optional[str] = None) -> dict:
    global _loaded_config
    search_dirs = []
    if repo_root:
        search_dirs.append(Path(repo_root))
    search_dirs.extend([Path.cwd(), Path(__file__).resolve().parent.parent])
    
    for d in search_dirs:
        config_file = d / CONFIG_FILENAME
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    _loaded_config = json.load(f)
                    return _loaded_config
            except Exception:
                pass
    _loaded_config = {}
    return _loaded_config

# Load config initially
load_repository_config()


# Authentication & Password Management Taxonomy (Backward-compatible Overlay)
AUTH_PASSWORD_TAXONOMY = {
    "domain": "authentication",
    "capability": "password_management",
    "keywords": [
        "password", "auth", "login", "signup", "sign-up", "register",
        "reset-password", "update-password", "change password", "forgot password",
        "credential", "session", "token", "sign-in"
    ],
    "flows": {
        "sign-up": ["signup", "sign-up", "register", "create account", "sign up"],
        "update-password": ["update-password", "change password", "password update", "password change"],
        "reset-password": ["reset-password", "forgot password", "password reset"],
        "login": ["login", "sign-in", "authenticate"],
        "login-after-password-update": ["login after password", "login after update", "old password"],
        "account-security": ["account security", "security validation", "password security"],
        "ui-api-consistency": ["ui", "api", "frontend", "backend", "validation consistency", "cross-layer"]
    },
    "risk_defaults": {
        "api validation bypass": "CRITICAL",
        "reset token reuse": "CRITICAL",
        "expired reset token": "CRITICAL",
        "password not updated on failure": "HIGH",
        "login after password update": "HIGH",
        "ui/api consistency": "HIGH",
        "weak password rejection": "HIGH",
        "strong password acceptance": "MEDIUM",
        "password policy enforcement": "HIGH"
    },
    "file_patterns": {
        "sign-up": [
            "signup", "sign-up", "register", "sign_up", "sign_up_form"
        ],
        "update-password": [
            "update-password", "change-password", "password_update", "change_password"
        ],
        "reset-password": [
            "reset-password", "forgot-password", "password_reset", "reset_password"
        ],
        "login": [
            "login", "signin", "auth", "authenticate"
        ],
        "api": [
            "api", "route", "endpoint", "controller"
        ],
        "ui": [
            "component", "form", "ui", "frontend", "page"
        ]
    }
}


# Generic Layer Taxonomy
LAYER_TAXONOMY = {
    "UI": ["components", "pages", "ui", "frontend", "views", "form", "page", "view", "frontend/ui"],
    "API": ["api", "route", "endpoint", "controller", "endpoints", "controllers", "api/route"],
    "Service": ["services", "handlers", "modules", "service", "handler", "modules", "backend/business_logic"],
    "Domain": ["domain", "core"],
    "Data": ["models", "schema", "database", "db", "repository", "model", "schema", "repository", "database/model"],
    "Shared": ["utils", "helpers", "lib", "common", "shared", "utility/helper"],
    "Config": ["config", "settings", "env"],
    "Test": ["test", "spec", "mock", "fixtures"]
}


# Generic Domain Taxonomy
DOMAIN_TAXONOMY = {
    "auth": ["auth", "password", "login", "signup", "credential", "session", "token", "authentication"],
    "billing": ["billing", "invoice", "subscription"],
    "orders": ["order", "cart", "orders"],
    "payments": ["payment", "transaction", "checkout", "payments"],
    "profile": ["profile", "user", "account", "user_management"],
    "admin": ["admin", "dashboard", "portal"]
}


# Generic Flow Dependency Graph
FLOW_DEPENDENCIES = {
    "authentication": {
        "password_management": {
            "sign-up": ["account-security", "ui-api-consistency"],
            "update-password": ["login-after-password-update", "account-security"],
            "reset-password": ["account-security", "login"],
            "login": ["account-security"]
        }
    }
}


def get_taxonomy_for_domain(domain: str) -> Dict:
    """Get taxonomy configuration for a specific domain."""
    if domain in ["authentication", "auth"]:
        return AUTH_PASSWORD_TAXONOMY
    
    # Check loaded config custom domains
    config_taxonomy = _loaded_config.get("domains", {}).get(domain, {})
    if config_taxonomy:
        return config_taxonomy
        
    # Return default generic domain taxonomy fallback
    return {
        "domain": domain,
        "capability": domain,
        "keywords": [domain],
        "flows": {
            f"{domain}-flow": [domain]
        },
        "file_patterns": {
            f"{domain}-flow": [domain]
        }
    }


def classify_file_layer(file_path: str, config: Optional[dict] = None) -> str:
    """Classify a file path into a layer category."""
    if not config:
        config = _loaded_config
        
    file_path_lower = file_path.lower().replace("\\", "/")
    
    # 1. Check veriscope.config.json layer rules first
    layer_rules = config.get("layer_path_rules", {})
    for pattern, layer in layer_rules.items():
        if pattern.lower() in file_path_lower:
            return layer
            
    # 2. Fallback to default layer patterns
    for layer_name, patterns in LAYER_TAXONOMY.items():
        for pattern in patterns:
            if pattern in file_path_lower:
                return layer_name
                
    return "Unknown"


def classify_file_domain(file_path: str, config: Optional[dict] = None) -> str:
    """Classify a file path into a domain category."""
    if not config:
        config = _loaded_config
        
    file_path_lower = file_path.lower().replace("\\", "/")
    
    # 1. Check veriscope.config.json domain aliases first
    domain_aliases = config.get("domain_aliases", {})
    for pattern, domain in domain_aliases.items():
        if pattern.lower() in file_path_lower:
            # Map "auth" to "authentication" for backward compatibility
            if domain == "auth":
                return "authentication"
            return domain
            
    # 2. Fallback to default domain taxonomy
    for domain_name, patterns in DOMAIN_TAXONOMY.items():
        for pattern in patterns:
            if pattern in file_path_lower:
                # Map "auth" to "authentication" for backward compatibility
                if domain_name == "auth":
                    return "authentication"
                return domain_name
                
    return "unknown"


def infer_file_capability(file_path: str, domain: str, config: Optional[dict] = None) -> str:
    """Infer capability or flow from the file path/module/config."""
    if not config:
        config = _loaded_config
        
    file_path_clean = file_path.replace("\\", "/")
    parts = file_path_clean.split("/")
    
    if parts:
        filename = parts[-1]
        base_name = filename.split(".")[0]
        if base_name and base_name not in ["index", "main", "app", "route"]:
            return base_name
            
    if len(parts) > 1:
        # Extract parent directory or base filename as capability
        parent_folder = parts[-2]
        if parent_folder not in ["src", "app", "modules", "services", "controllers", "routes", "models"]:
            return parent_folder
            
    return domain


def classify_file_risk_tags(file_path: str, domain: str, layer: str, config: Optional[dict] = None) -> List[str]:
    """Classify risk tags based on file path keywords, domains, layers, and configuration."""
    if not config:
        config = _loaded_config
        
    tags = set()
    file_path_lower = file_path.lower().replace("\\", "/")

    # Check config critical paths / high-risk modules
    critical_paths = config.get("critical_paths", [])
    for cp in critical_paths:
        if cp.lower() in file_path_lower:
            tags.add("security")

    # Layer based risk tags
    if layer == "API":
        tags.add("performance")
    elif layer == "Data":
        tags.add("data_loss")

    # Domain based risk tags
    if domain in ["auth", "authentication"]:
        tags.add("security")
        tags.add("compliance")
    elif domain in ["billing", "payments"]:
        tags.add("financial")
        tags.add("compliance")
    elif domain == "orders":
        tags.add("financial")

    # Keyword mapping
    keywords_mapping = {
        "security": ["password", "token", "auth", "credential", "security", "bypass", "permission", "access", "jwt", "login", "crypt"],
        "data_loss": ["delete", "drop", "purge", "database", "migration", "remove", "truncate"],
        "compliance": ["gdpr", "audit", "privacy", "consent", "policy", "legal", "terms"],
        "financial": ["price", "charge", "invoice", "refund", "amount", "cost", "payment", "card", "billing"],
        "availability": ["health", "ping", "heartbeat", "retry", "circuit", "failover", "timeout"],
        "performance": ["cache", "redis", "optimize", "query", "index", "speed", "slow", "metric"]
    }

    for tag, keywords in keywords_mapping.items():
        for kw in keywords:
            if kw in file_path_lower:
                tags.add(tag)
                break

    if not tags:
        tags.add("unknown")

    return sorted(list(tags))


def extract_flows_from_file(file_path: str, taxonomy: Dict) -> List[str]:
    """Extract flows from a file path using taxonomy patterns."""
    file_path_lower = file_path.lower()
    matched_flows = []
    
    for flow_name, flow_patterns in taxonomy.get("flows", {}).items():
        for pattern in flow_patterns:
            if pattern in file_path_lower:
                matched_flows.append(flow_name)
                break
                
    # If no flows matched, fall back to inferring flow from file name
    if not matched_flows and taxonomy.get("domain") != "authentication":
        inferred = infer_file_capability(file_path, taxonomy.get("domain", "unknown"))
        matched_flows.append(f"{inferred}-flow")
        
    return matched_flows


def get_indirect_flows(flows: List[str], domain: str = "authentication") -> List[str]:
    """Get indirect flows based on flow dependency graph."""
    indirect = set()
    
    for flow in flows:
        if domain in FLOW_DEPENDENCIES:
            for capability, flow_deps in FLOW_DEPENDENCIES[domain].items():
                if flow in flow_deps:
                    indirect.update(flow_deps[flow])
                    
    return list(indirect - set(flows))


def get_security_sensitive_flows(domain: str = "authentication") -> Set[str]:
    """Get flows that are security-sensitive."""
    if domain in ["authentication", "auth"]:
        return {
            "sign-up", "update-password", "reset-password", "login",
            "account-security", "api validation", "token management"
        }
    return set()
