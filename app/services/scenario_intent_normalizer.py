"""
ScenarioIntentNormalizer
=========================
Generates deterministic canonical keys for scenario intents to prevent duplicate or conflicting recommendations.

Canonical key format: domain.feature.behavior.layer.case_type
Example: authentication.reset-password.expired-token-rejected.api.negative
"""

import re
from typing import Dict, Any, Optional


class ScenarioIntentNormalizer:
    """Normalizes scenario fields and generates deterministic canonical keys."""

    # Domain normalization mapping
    DOMAIN_NORMALIZATION = {
        "auth": "authentication",
        "login": "authentication",
        "signin": "authentication",
        "session": "authentication",
        "signup": "authentication",
        "sign-up": "authentication",
        "register": "authentication",
        "registration": "authentication",
        "onboarding": "authentication",
        "password": "authentication",
        "reset-password": "authentication",
        "reset_password": "authentication",
        "billing": "billing",
        "payment": "billing",
        "checkout": "billing",
        "subscription": "billing",
        "invoice": "billing",
        "stripe": "billing",
        "notification": "notifications",
        "email": "notifications",
        "mail": "notifications",
        "sms": "notifications",
        "alert": "notifications",
        "profile": "user-profile",
        "account": "user-profile",
        "settings": "admin-settings",
        "admin": "admin-settings",
        "configuration": "admin-settings",
    }

    # Feature normalization mapping
    FEATURE_NORMALIZATION = {
        "reset password": "reset-password",
        "reset-password": "reset-password",
        "reset_password": "reset-password",
        "password reset": "reset-password",
        "forgot password": "reset-password",
        "forgot-password": "reset-password",
        "forgot_password": "reset-password",
        "recovery": "reset-password",
        "sign up": "signup",
        "sign-up": "signup",
        "sign_up": "signup",
        "register": "signup",
        "registration": "signup",
        "login": "login",
        "signin": "login",
        "sign-in": "login",
        "sign_in": "login",
        "auth": "login",
        "authentication": "login",
        "token": "token",
        "jwt": "token",
        "session": "token",
        "checkout": "checkout",
        "payment": "checkout",
        "subscription": "subscription",
        "billing": "subscription",
        "invoice": "subscription",
        "notification": "notification",
        "email": "notification",
        "profile": "profile",
        "account": "profile",
        "settings": "settings",
        "admin": "settings",
    }

    # Behavior normalization mapping
    BEHAVIOR_NORMALIZATION = {
        "expired": "expired-token-rejected",
        "expired token": "expired-token-rejected",
        "expired-token": "expired-token-rejected",
        "invalid": "invalid-token-rejected",
        "invalid token": "invalid-token-rejected",
        "invalid-token": "invalid-token-rejected",
        "malformed": "malformed-token-rejected",
        "malformed token": "malformed-token-rejected",
        "valid": "valid-token-accepted",
        "valid token": "valid-token-accepted",
        "valid-token": "valid-token-accepted",
        "weak": "weak-password-rejected",
        "weak password": "weak-password-rejected",
        "weak-password": "weak-password-rejected",
        "duplicate": "duplicate-email-rejected",
        "duplicate email": "duplicate-email-rejected",
        "duplicate-email": "duplicate-email-rejected",
        "existing": "duplicate-email-rejected",
        "existing email": "duplicate-email-rejected",
        "reused": "reused-token-rejected",
        "reused token": "reused-token-rejected",
        "reused-token": "reused-token-rejected",
        "unregistered": "unregistered-email-handled",
        "unregistered email": "unregistered-email-handled",
        "nonexistent": "unregistered-email-handled",
        "disabled": "submit-disabled",
        "submit disabled": "submit-disabled",
        "loading": "loading-state-shown",
        "loading state": "loading-state-shown",
    }

    # Layer normalization mapping
    LAYER_NORMALIZATION = {
        "api": "api",
        "endpoint": "api",
        "backend": "api",
        "service": "api",
        "ui": "ui",
        "frontend": "ui",
        "client": "ui",
        "interface": "ui",
        "integration": "integration",
        "e2e": "integration",
        "end-to-end": "integration",
    }

    # Case type normalization mapping
    CASE_TYPE_NORMALIZATION = {
        "positive": "positive",
        "happy": "positive",
        "success": "positive",
        "negative": "negative",
        "error": "negative",
        "failure": "negative",
        "edge": "edge",
        "boundary": "edge",
        "corner": "edge",
        "regression": "regression",
    }

    @classmethod
    def normalize_field(cls, value: str, normalization_map: Dict[str, str]) -> str:
        """Normalize a field value using the provided mapping."""
        if not value:
            return "general"
        
        normalized = value.lower().strip()
        
        # Try exact match first
        if normalized in normalization_map:
            return normalization_map[normalized]
        
        # Try partial match (e.g., "password reset" should match "reset-password")
        for key, mapped_value in normalization_map.items():
            if key in normalized or normalized in key:
                return mapped_value
        
        # Fallback: normalize to kebab-case
        normalized = re.sub(r'[^a-z0-9]+', '-', normalized).strip('-')
        return normalized if normalized else "general"

    @classmethod
    def normalize_domain(cls, domain: str) -> str:
        """Normalize domain field."""
        return cls.normalize_field(domain, cls.DOMAIN_NORMALIZATION)

    @classmethod
    def normalize_feature(cls, feature: str) -> str:
        """Normalize feature field."""
        return cls.normalize_field(feature, cls.FEATURE_NORMALIZATION)

    @classmethod
    def normalize_behavior(cls, behavior: str) -> str:
        """Normalize behavior field."""
        return cls.normalize_field(behavior, cls.BEHAVIOR_NORMALIZATION)

    @classmethod
    def normalize_layer(cls, layer: str) -> str:
        """Normalize layer field."""
        return cls.normalize_field(layer, cls.LAYER_NORMALIZATION)

    @classmethod
    def normalize_case_type(cls, case_type: str) -> str:
        """Normalize case_type field."""
        return cls.normalize_field(case_type, cls.CASE_TYPE_NORMALIZATION)

    @classmethod
    def generate_canonical_key(
        cls,
        domain: str,
        feature: str,
        behavior: str,
        layer: str,
        case_type: str
    ) -> str:
        """
        Generate a deterministic canonical key from scenario fields.
        
        Format: domain.feature.behavior.layer.case_type
        Example: authentication.reset-password.expired-token-rejected.api.negative
        
        Args:
            domain: The domain (e.g., "authentication", "billing")
            feature: The feature (e.g., "reset-password", "signup")
            behavior: The behavior (e.g., "expired-token-rejected", "weak-password-rejected")
            layer: The layer (e.g., "api", "ui", "integration")
            case_type: The case type (e.g., "positive", "negative", "edge")
        
        Returns:
            A deterministic canonical key string.
        """
        normalized_domain = cls.normalize_domain(domain)
        normalized_feature = cls.normalize_feature(feature)
        normalized_behavior = cls.normalize_behavior(behavior)
        normalized_layer = cls.normalize_layer(layer)
        normalized_case_type = cls.normalize_case_type(case_type)
        
        canonical_key = f"{normalized_domain}.{normalized_feature}.{normalized_behavior}.{normalized_layer}.{normalized_case_type}"
        return canonical_key

    @classmethod
    def extract_fields_from_title(cls, title: str) -> Dict[str, str]:
        """
        Extract domain, feature, behavior, layer, and case_type from a scenario title.
        
        This is a heuristic extraction that attempts to parse structured titles.
        Fallbacks to "general" for fields that cannot be extracted.
        
        Args:
            title: The scenario title (e.g., "Validate password reset expired token rejection")
        
        Returns:
            A dictionary with extracted fields: domain, feature, behavior, layer, case_type
        """
        title_lower = title.lower()
        
        # Extract domain
        domain = "general"
        for key, mapped_value in cls.DOMAIN_NORMALIZATION.items():
            if key in title_lower:
                domain = mapped_value
                break
        
        # Extract feature
        feature = "general"
        for key, mapped_value in cls.FEATURE_NORMALIZATION.items():
            if key in title_lower:
                feature = mapped_value
                break
        
        # Extract behavior
        behavior = "general"
        for key, mapped_value in cls.BEHAVIOR_NORMALIZATION.items():
            if key in title_lower:
                behavior = mapped_value
                break
        
        # Extract layer
        layer = "api"  # Default to API
        for key, mapped_value in cls.LAYER_NORMALIZATION.items():
            if key in title_lower:
                layer = mapped_value
                break
        
        # Extract case type
        case_type = "positive"  # Default to positive
        for key, mapped_value in cls.CASE_TYPE_NORMALIZATION.items():
            if key in title_lower:
                case_type = mapped_value
                break
        
        # Special case: if title contains "reject", "block", "fail", it's likely negative
        if any(word in title_lower for word in ["reject", "block", "fail", "error", "invalid", "expired", "weak", "duplicate"]):
            case_type = "negative"
        
        return {
            "domain": domain,
            "feature": feature,
            "behavior": behavior,
            "layer": layer,
            "case_type": case_type
        }

    @classmethod
    def create_intent_from_scenario(
        cls,
        title: str,
        priority: str,
        risk_category: str,
        related_changed_files: list,
        recommendation_run_id: str,
        domain: Optional[str] = None,
        feature: Optional[str] = None,
        behavior: Optional[str] = None,
        layer: Optional[str] = None,
        case_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a scenario intent dictionary from scenario data.
        
        Args:
            title: The scenario title
            priority: The scenario priority (MUST, SHOULD, OPTIONAL)
            risk_category: The risk category (Security, Functional, Regression)
            related_changed_files: List of related changed files
            recommendation_run_id: The recommendation run ID
            domain: Optional domain (extracted from title if not provided)
            feature: Optional feature (extracted from title if not provided)
            behavior: Optional behavior (extracted from title if not provided)
            layer: Optional layer (extracted from title if not provided)
            case_type: Optional case_type (extracted from title if not provided)
        
        Returns:
            A dictionary with scenario intent fields including canonical_key
        """
        # Extract fields from title if not provided
        if not domain or not feature or not behavior or not layer or not case_type:
            extracted = cls.extract_fields_from_title(title)
            domain = domain or extracted["domain"]
            feature = feature or extracted["feature"]
            behavior = behavior or extracted["behavior"]
            layer = layer or extracted["layer"]
            case_type = case_type or extracted["case_type"]
        
        # Generate canonical key
        canonical_key = cls.generate_canonical_key(domain, feature, behavior, layer, case_type)
        
        return {
            "domain": domain,
            "feature": feature,
            "behavior": behavior,
            "layer": layer,
            "case_type": case_type,
            "canonical_key": canonical_key,
            "title": title,
            "priority": priority,
            "risk_category": risk_category,
            "related_changed_files": related_changed_files,
            "recommendation_run_id": recommendation_run_id
        }
