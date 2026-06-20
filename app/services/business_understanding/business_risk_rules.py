"""
Generic business risk rules for semantic risk assessment.

This module provides deterministic risk scoring based on requirement semantics.
It does not use LLMs and is designed to be a fallback for business context generation.
"""

from typing import List, Tuple, Optional
from enum import Enum


class RiskLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class Priority(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    UNKNOWN = "UNKNOWN"


class BusinessRiskRules:
    """
    Generic semantic risk pattern matching for business context generation.
    
    Uses keyword and pattern matching to assign risk levels and priorities
    based on requirement semantics. This is deterministic and does not use LLMs.
    """
    
    # Critical / P0 patterns - security, access control, data integrity
    CRITICAL_P0_PATTERNS = [
        # Authentication and authorization
        ("authentication", 10),
        ("authorization", 10),
        ("account access", 10),
        ("login", 8),
        ("password", 8),
        ("token", 8),
        ("credential", 8),
        ("session", 7),
        
        # Password-specific critical operations
        ("password update", 10),
        ("password reset", 10),
        ("old password", 10),
        ("new password", 8),
        ("password change", 10),
        
        # Security enforcement
        ("invalid", 7),
        ("reject", 8),
        ("expire", 8),
        ("reuse", 8),
        ("token validity", 10),
        
        # Data integrity and atomicity
        ("atomic", 10),
        ("atomicity", 10),
        ("data loss", 10),
        ("rollback", 8),
        ("transaction", 7),
        
        # Security policy
        ("security policy", 10),
        ("policy bypass", 10),
        ("backend validation", 9),
        ("source of truth", 9),
        
        # Financial and sensitive operations
        ("payment", 10),
        ("transaction", 8),
        ("financial", 10),
        ("privacy", 10),
        ("personal data", 9),
        
        # Permission escalation
        ("permission", 8),
        ("escalation", 10),
        ("privilege", 9),
        
        # Exposure risks
        ("exposure", 9),
        ("leak", 9),
        ("disclosure", 10),
    ]
    
    # High / P1 patterns - important user journeys, validation consistency
    HIGH_P1_PATTERNS = [
        # Validation consistency
        ("validation", 6),
        ("consistency", 7),
        ("api validation", 8),
        ("ui validation", 7),
        
        # Direct API protection
        ("direct api", 8),
        ("bypass", 7),
        ("endpoint", 6),
        
        # Input validation for state integrity
        ("input validation", 7),
        ("invalid state", 8),
        ("state mutation", 8),
        ("failed operation", 7),
        
        # Important user journeys
        ("user journey", 6),
        ("workflow", 6),
        ("completion", 7),
        
        # Password enforcement consistency
        ("weak password", 8),
        ("strong password", 8),
        ("sign-up", 6),
        ("update", 6),
        ("reset", 7),
    ]
    
    # Medium / P2 patterns - UX, messaging, boundary validation
    MEDIUM_P2_PATTERNS = [
        # Validation messaging
        ("message", 5),
        ("error message", 6),
        ("validation message", 6),
        ("clarity", 5),
        
        # UX consistency
        ("ux", 5),
        ("user experience", 5),
        ("consistency", 5),
        
        # Boundary validation
        ("boundary", 5),
        ("limit", 5),
        ("maximum", 5),
        ("minimum", 5),
        
        # Non-security workflow
        ("workflow", 5),
        ("correctness", 6),
        
        # Password UX specifics
        ("whitespace", 5),
        ("confirmation", 5),
        ("mismatch", 5),
        ("safe", 5),
        ("user-friendly", 5),
    ]
    
    # Low / P3 patterns - cosmetic, display, non-blocking
    LOW_P3_PATTERNS = [
        ("cosmetic", 3),
        ("display", 3),
        ("copy", 3),
        ("text", 2),
        ("label", 2),
        ("format", 2),
        ("non-blocking", 2),
    ]
    
    @classmethod
    def assess_risk(cls, requirement_text: str, requirement_title: str = "") -> Tuple[RiskLevel, Priority, List[str]]:
        """
        Assess risk level and priority based on requirement semantics.
        
        Args:
            requirement_text: The full requirement text
            requirement_title: Optional requirement title/readable ID
            
        Returns:
            Tuple of (risk_level, priority, risk_reasons)
        """
        combined_text = f"{requirement_title} {requirement_text}".lower()
        reasons = []
        
        # Check Critical / P0 patterns
        critical_score = 0
        for pattern, weight in cls.CRITICAL_P0_PATTERNS:
            if pattern in combined_text:
                critical_score += weight
                reasons.append(f"Contains '{pattern}' - critical security/access control pattern")
        
        # Check High / P1 patterns
        high_score = 0
        for pattern, weight in cls.HIGH_P1_PATTERNS:
            if pattern in combined_text:
                high_score += weight
                if f"Contains '{pattern}'" not in " ".join(reasons):
                    reasons.append(f"Contains '{pattern}' - important validation/journey pattern")
        
        # Check Medium / P2 patterns
        medium_score = 0
        for pattern, weight in cls.MEDIUM_P2_PATTERNS:
            if pattern in combined_text:
                medium_score += weight
                if f"Contains '{pattern}'" not in " ".join(reasons):
                    reasons.append(f"Contains '{pattern}' - UX/messaging pattern")
        
        # Check Low / P3 patterns
        low_score = 0
        for pattern, weight in cls.LOW_P3_PATTERNS:
            if pattern in combined_text:
                low_score += weight
                if f"Contains '{pattern}'" not in " ".join(reasons):
                    reasons.append(f"Contains '{pattern}' - cosmetic/display pattern")
        
        # Semantic markers for downgrades
        is_ux_or_message = any(p in combined_text for p in ["message", "user-friendly", "clarity", "ux", "user experience", "friendly", "safe", "expose", "internal"])
        is_cosmetic = any(p in combined_text for p in ["cosmetic", "display", "color", "button", "theme", "style", "design system"])

        if is_cosmetic:
            reasons.append("Cosmetic or styling requirement - classified as LOW risk")
            return RiskLevel.LOW, Priority.P3, reasons

        if is_ux_or_message:
            reasons.append("UX or messaging requirement - classified as MEDIUM risk")
            return RiskLevel.MEDIUM, Priority.P2, reasons

        if critical_score >= 8:
            return RiskLevel.CRITICAL, Priority.P0, reasons
        
        if high_score >= 5:
            return RiskLevel.HIGH, Priority.P1, reasons
        
        if medium_score >= 4:
            return RiskLevel.MEDIUM, Priority.P2, reasons
        
        if low_score >= 3:
            return RiskLevel.LOW, Priority.P3, reasons
        
        # Unknown if no patterns matched or insufficient evidence
        if not reasons or (critical_score == 0 and high_score == 0 and medium_score == 0 and low_score == 0):
            reasons = ["Insufficient semantic evidence for deterministic risk classification."]
            return RiskLevel.UNKNOWN, Priority.UNKNOWN, reasons
        
        return RiskLevel.UNKNOWN, Priority.UNKNOWN, reasons
    
    @classmethod
    def infer_capability(cls, requirement_text: str) -> str:
        """Infer business capability from requirement text."""
        text_lower = requirement_text.lower()
        
        if "password" in text_lower:
            return "Account Security"
        elif "authentication" in text_lower or "login" in text_lower:
            return "Authentication"
        elif "authorization" in text_lower or "permission" in text_lower:
            return "Authorization"
        elif "payment" in text_lower or "transaction" in text_lower:
            return "Payment Processing"
        elif "privacy" in text_lower or "personal data" in text_lower:
            return "Data Privacy"
        elif "api" in text_lower:
            return "API Security"
        else:
            return "General"
    
    @classmethod
    def infer_user_journey(cls, requirement_text: str) -> str:
        """Infer user journey from requirement text."""
        text_lower = requirement_text.lower()
        
        if "password" in text_lower and ("update" in text_lower or "change" in text_lower):
            return "Password Update"
        elif "password" in text_lower and ("reset" in text_lower or "recover" in text_lower):
            return "Password Reset"
        elif "login" in text_lower or "sign in" in text_lower:
            return "Login"
        elif "sign up" in text_lower or "register" in text_lower:
            return "Registration"
        elif "payment" in text_lower:
            return "Payment"
        else:
            return "General"
    
    @classmethod
    def infer_actor(cls, requirement_text: str) -> str:
        """Infer affected actor from requirement text."""
        text_lower = requirement_text.lower()
        
        if "admin" in text_lower:
            return "Administrator"
        elif "user" in text_lower:
            return "User"
        elif "customer" in text_lower:
            return "Customer"
        elif "system" in text_lower:
            return "System"
        else:
            return "User"
    
    @classmethod
    def infer_business_action(cls, requirement_text: str) -> str:
        """Infer business action from requirement text."""
        text_lower = requirement_text.lower()
        
        if "password" in text_lower and ("update" in text_lower or "change" in text_lower):
            return "Change password"
        elif "password" in text_lower and "reset" in text_lower:
            return "Reset password"
        elif "login" in text_lower:
            return "Login"
        elif "sign up" in text_lower or "register" in text_lower:
            return "Register"
        elif "validate" in text_lower:
            return "Validate input"
        else:
            return "Perform action"
