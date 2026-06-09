from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.behavior import Behavior
from app.services.journey_risk import JourneyRisk


class JourneyRiskEngine:
    """Engine to assign business risk to journeys based on behaviors."""
    
    # Risk level hierarchy (higher is more severe)
    RISK_HIERARCHY = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }
    
    # Journey-specific risk factors
    JOURNEY_RISK_FACTORS = {
        "Authentication": [
            "User access control",
            "Security vulnerabilities",
            "Session management",
            "Authentication bypass",
        ],
        "Registration": [
            "User onboarding",
            "Account creation",
            "Email verification",
            "Spam prevention",
        ],
        "Billing": [
            "Revenue generation",
            "Payment processing",
            "Financial data",
            "Compliance requirements",
        ],
        "Subscription Lifecycle": [
            "Recurring revenue",
            "Subscription management",
            "Billing cycles",
            "Customer retention",
        ],
        "Notifications": [
            "User communication",
            "System reliability",
            "Message delivery",
            "User engagement",
        ],
        "Administration": [
            "System management",
            "Access control",
            "Data integrity",
            "Operational continuity",
        ],
        "Reporting": [
            "Business intelligence",
            "Data accuracy",
            "Performance metrics",
            "Decision support",
        ],
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the journey risk engine with optional database session."""
        self.db = db
    
    def calculate_journey_risk(
        self,
        journey: Journey,
        behaviors: List[Behavior],
    ) -> JourneyRisk:
        """Calculate risk for a journey based on its behaviors."""
        if not behaviors:
            # No behaviors = unknown risk
            return JourneyRisk(
                journey_id=str(journey.id),
                risk_level="MEDIUM",
                risk_reason="No behaviors found to assess risk",
                affected_users="Unknown",
                confidence="LOW",
                contributing_behaviors=[],
                risk_factors=["Insufficient data"],
            )
        
        # Calculate risk from behaviors
        risk_level, risk_factors = self._calculate_risk_from_behaviors(behaviors)
        
        # Generate explainable reason
        risk_reason = self._generate_risk_reason(journey.name, risk_level, behaviors, risk_factors)
        
        # Estimate affected users
        affected_users = self._estimate_affected_users(journey.name, behaviors)
        
        # Determine confidence
        confidence = self._determine_confidence(behaviors)
        
        # Get contributing behaviors
        contributing_behaviors = [b.name for b in behaviors if b.risk_level in ["HIGH", "CRITICAL"]]
        
        return JourneyRisk(
            journey_id=str(journey.id),
            risk_level=risk_level,
            risk_reason=risk_reason,
            affected_users=affected_users,
            confidence=confidence,
            contributing_behaviors=contributing_behaviors,
            risk_factors=risk_factors,
        )
    
    def _calculate_risk_from_behaviors(
        self,
        behaviors: List[Behavior],
    ) -> tuple[str, List[str]]:
        """Calculate risk level and factors from behaviors."""
        if not behaviors:
            return "MEDIUM", ["No behaviors"]
        
        # Count behaviors by risk level
        risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for behavior in behaviors:
            risk_counts[behavior.risk_level] += 1
        
        # Determine overall risk level
        if risk_counts["CRITICAL"] > 0:
            return "CRITICAL", self._get_risk_factors(behaviors, "CRITICAL")
        elif risk_counts["HIGH"] >= 2:
            return "CRITICAL", self._get_risk_factors(behaviors, "HIGH")
        elif risk_counts["HIGH"] >= 1:
            return "HIGH", self._get_risk_factors(behaviors, "HIGH")
        elif risk_counts["MEDIUM"] >= 3:
            return "HIGH", self._get_risk_factors(behaviors, "MEDIUM")
        elif risk_counts["MEDIUM"] >= 1:
            return "MEDIUM", self._get_risk_factors(behaviors, "MEDIUM")
        else:
            return "LOW", self._get_risk_factors(behaviors, "LOW")
    
    def _get_risk_factors(
        self,
        behaviors: List[Behavior],
        min_risk_level: str,
    ) -> List[str]:
        """Get risk factors from behaviors at or above minimum risk level."""
        factors = []
        min_severity = self.RISK_HIERARCHY.get(min_risk_level, 0)
        
        for behavior in behaviors:
            severity = self.RISK_HIERARCHY.get(behavior.risk_level, 0)
            if severity >= min_severity:
                if behavior.risk_reason:
                    factors.append(behavior.risk_reason)
                else:
                    factors.append(f"{behavior.name} has {behavior.risk_level} risk")
        
        return factors
    
    def _generate_risk_reason(
        self,
        journey_name: str,
        risk_level: str,
        behaviors: List[Behavior],
        risk_factors: List[str],
    ) -> str:
        """Generate explainable reason for risk assignment."""
        # Get journey-specific factors
        journey_factors = self.JOURNEY_RISK_FACTORS.get(journey_name, [])
        
        # Count high-risk behaviors
        high_risk_count = sum(1 for b in behaviors if b.risk_level in ["HIGH", "CRITICAL"])
        
        if risk_level == "CRITICAL":
            if high_risk_count > 0:
                return f"Journey contains {high_risk_count} CRITICAL/HIGH risk behaviors: {', '.join([b.name for b in behaviors if b.risk_level in ['HIGH', 'CRITICAL']][:3])}. Failure could impact core business operations."
            else:
                return f"Journey involves critical business functions: {', '.join(journey_factors[:2])}. High impact on business continuity."
        elif risk_level == "HIGH":
            if high_risk_count > 0:
                return f"Journey contains {high_risk_count} HIGH risk behaviors. Could significantly impact user experience and business operations."
            else:
                return f"Journey involves important business functions: {', '.join(journey_factors[:2])}. Moderate to high impact on operations."
        elif risk_level == "MEDIUM":
            return f"Journey contains behaviors with moderate risk. Could impact user experience but has limited business impact."
        else:
            return f"Journey contains low-risk behaviors. Minimal impact on business operations."
    
    def _estimate_affected_users(
        self,
        journey_name: str,
        behaviors: List[Behavior],
    ) -> str:
        """Estimate affected users based on journey type."""
        # Journey-specific user impact
        user_impact = {
            "Authentication": "All users requiring system access",
            "Registration": "New users and potential customers",
            "Billing": "Paying customers and revenue operations",
            "Subscription Lifecycle": "Active subscribers and revenue streams",
            "Notifications": "All users requiring system communications",
            "Administration": "System administrators and operations team",
            "Reporting": "Business stakeholders and decision makers",
        }
        
        return user_impact.get(journey_name, "System users")
    
    def _determine_confidence(
        self,
        behaviors: List[Behavior],
    ) -> str:
        """Determine confidence in risk assessment."""
        if not behaviors:
            return "LOW"
        
        # Check behavior confidence levels
        high_conf_count = sum(1 for b in behaviors if b.confidence == "HIGH")
        total_count = len(behaviors)
        
        if high_conf_count / total_count >= 0.7:
            return "HIGH"
        elif high_conf_count / total_count >= 0.4:
            return "MODERATE"
        else:
            return "LOW"
    
    def batch_calculate_risks(
        self,
        journeys: List[Journey],
        behaviors_map: dict[str, List[Behavior]],
    ) -> List[JourneyRisk]:
        """Calculate risks for multiple journeys."""
        risks = []
        
        for journey in journeys:
            behaviors = behaviors_map.get(str(journey.id), [])
            risk = self.calculate_journey_risk(journey, behaviors)
            risks.append(risk)
        
        return risks
    
    def get_risk_summary(self, risks: List[JourneyRisk]) -> dict:
        """Get summary of journey risks."""
        if not risks:
            return {
                "total_journeys": 0,
                "by_risk_level": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                "by_confidence": {"HIGH": 0, "MODERATE": 0, "LOW": 0},
            }
        
        by_risk_level = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_confidence = {"HIGH": 0, "MODERATE": 0, "LOW": 0}
        
        for risk in risks:
            by_risk_level[risk.risk_level] += 1
            by_confidence[risk.confidence] += 1
        
        return {
            "total_journeys": len(risks),
            "by_risk_level": by_risk_level,
            "by_confidence": by_confidence,
        }
