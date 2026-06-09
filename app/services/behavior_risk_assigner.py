from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.behavior import Behavior


@dataclass
class RiskAssignment:
    """Risk assignment with explainable reasoning."""
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    reason: str
    evidence: List[str]


class BehaviorRiskAssigner:
    """Service to assign explainable business risk to behaviors."""
    
    # Risk classification rules with explainable reasons
    RISK_RULES: Dict[str, RiskAssignment] = {
        # CRITICAL - Business-critical security/financial operations
        "Authentication": RiskAssignment(
            risk_level="CRITICAL",
            reason="Authentication is a security-critical operation. Compromise leads to unauthorized access, data breaches, and regulatory violations.",
            evidence=[
                "Handles user credentials and session management",
                "Direct impact on account security",
                "Required for all user operations",
                "High compliance requirements (GDPR, SOC2, etc.)",
            ],
        ),
        "Checkout": RiskAssignment(
            risk_level="CRITICAL",
            reason="Checkout handles payment processing and revenue generation. Failures directly impact business revenue and customer trust.",
            evidence=[
                "Processes financial transactions",
                "Direct revenue impact",
                "Customer trust dependency",
                "Payment gateway integration complexity",
            ],
        ),
        "Administration": RiskAssignment(
            risk_level="CRITICAL",
            reason="Administration controls system-wide settings and permissions. Compromise can lead to complete system takeover.",
            evidence=[
                "Controls system-wide permissions",
                "Access to sensitive configuration",
                "Potential for privilege escalation",
                "Impact on all users and data",
            ],
        ),
        
        # HIGH - Security-sensitive operations with significant business impact
        "Password Reset": RiskAssignment(
            risk_level="HIGH",
            reason="Password reset is a security-sensitive operation that can be exploited for account takeover if not properly implemented.",
            evidence=[
                "Account recovery mechanism",
                "Potential for social engineering attacks",
                "Requires secure token handling",
                "User trust dependency",
            ],
        ),
        "User Registration": RiskAssignment(
            risk_level="HIGH",
            reason="User registration is the entry point for customer acquisition and requires proper validation and security measures.",
            evidence=[
                "Customer acquisition entry point",
                "Data collection compliance requirements",
                "Email verification complexity",
                "Spam/fraud prevention needed",
            ],
        ),
        "Subscription Management": RiskAssignment(
            risk_level="HIGH",
            reason="Subscription management affects recurring revenue and requires accurate billing and proper access control.",
            evidence=[
                "Recurring revenue impact",
                "Billing accuracy requirements",
                "Access control complexity",
                "Customer retention dependency",
            ],
        ),
        "API Integration": RiskAssignment(
            risk_level="HIGH",
            reason="API integrations handle external data exchange and require proper authentication, rate limiting, and error handling.",
            evidence=[
                "External system dependencies",
                "Data exchange security",
                "Rate limiting requirements",
                "Error handling complexity",
            ],
        ),
        
        # MEDIUM - Important features with moderate business impact
        "File Upload": RiskAssignment(
            risk_level="MEDIUM",
            reason="File upload requires security validation and storage management. Issues can lead to security vulnerabilities or resource exhaustion.",
            evidence=[
                "Security validation requirements",
                "Storage management complexity",
                "Potential for malware upload",
                "Resource consumption impact",
            ],
        ),
        "User Management": RiskAssignment(
            risk_level="MEDIUM",
            reason="User management handles profile and settings updates. Issues affect user experience but have limited security impact.",
            evidence=[
                "User experience impact",
                "Data consistency requirements",
                "Profile synchronization complexity",
                "Limited security impact",
            ],
        ),
        
        # LOW - Supporting features with minimal business impact
        "Notifications": RiskAssignment(
            risk_level="LOW",
            reason="Notifications are supporting features for user engagement. Failures have minimal impact on core functionality.",
            evidence=[
                "User engagement enhancement",
                "Non-critical communication",
                "Retry mechanisms available",
                "Minimal business impact",
            ],
        ),
        "Reporting": RiskAssignment(
            risk_level="LOW",
            reason="Reporting provides analytics and insights. Failures affect visibility but not core operations.",
            evidence=[
                "Analytics and insights",
                "Non-operational dependency",
                "Data aggregation complexity",
                "Minimal business impact",
            ],
        ),
        "Search": RiskAssignment(
            risk_level="LOW",
            reason="Search is a convenience feature for content discovery. Failures have minimal impact on core functionality.",
            evidence=[
                "Content discovery enhancement",
                "Non-critical functionality",
                "Alternative navigation available",
                "Minimal business impact",
            ],
        ),
    }
    
    # Default risk assignment for unknown behaviors
    DEFAULT_RISK = RiskAssignment(
        risk_level="MEDIUM",
        reason="Behavior not classified in risk rules. Defaulting to MEDIUM risk as a conservative estimate.",
        evidence=[
            "No specific risk classification available",
            "Conservative default assignment",
            "Requires manual review for accurate classification",
        ],
    )
    
    def __init__(self, db: Session):
        """Initialize the risk assigner with database session."""
        self.db = db
    
    def assign_risk(self, behavior: Behavior) -> Behavior:
        """Assign risk to a single behavior with explainable reasoning."""
        risk_assignment = self._get_risk_assignment(behavior.name)
        
        behavior.risk_level = risk_assignment.risk_level
        behavior.risk_reason = risk_assignment.reason
        behavior.risk_evidence = "\n".join(risk_assignment.evidence)
        
        return behavior
    
    def assign_risk_to_repository(self, repository_id: str) -> List[Behavior]:
        """Assign risk to all behaviors in a repository."""
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
        ).all()
        
        for behavior in behaviors:
            self.assign_risk(behavior)
        
        self.db.commit()
        
        return behaviors
    
    def _get_risk_assignment(self, behavior_name: str) -> RiskAssignment:
        """Get risk assignment for a behavior name."""
        # Check for exact match
        if behavior_name in self.RISK_RULES:
            return self.RISK_RULES[behavior_name]
        
        # Check for partial match (behavior name contains a known keyword)
        for keyword, risk_assignment in self.RISK_RULES.items():
            if keyword.lower() in behavior_name.lower() or behavior_name.lower() in keyword.lower():
                return risk_assignment
        
        # Return default if no match found
        return self.DEFAULT_RISK
    
    def get_risk_summary(self, repository_id: str) -> Dict[str, int]:
        """Get a summary of risk levels for a repository."""
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False,
        ).all()
        
        summary = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
        }
        
        for behavior in behaviors:
            if behavior.risk_level in summary:
                summary[behavior.risk_level] += 1
        
        return summary
    
    def explain_risk(self, behavior: Behavior) -> str:
        """Generate a human-readable explanation of the risk assignment."""
        explanation = f"Behavior: {behavior.name}\n"
        explanation += f"Risk Level: {behavior.risk_level}\n"
        explanation += f"Reason: {behavior.risk_reason}\n"
        explanation += f"Evidence:\n{behavior.risk_evidence}"
        
        return explanation
