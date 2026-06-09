from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.journey import Journey
from app.services.journey_candidate import JourneyCandidate
from app.services.behavior_relationship_engine import BehaviorRelationshipEngine


class JourneyDiscoveryEngine:
    """Engine to automatically infer journeys from behaviors."""
    
    # Known journey patterns (evidence-backed)
    JOURNEY_PATTERNS: Dict[str, List[str]] = {
        "Authentication": ["Login", "Logout", "Password Reset", "Session Validation", "Token Refresh"],
        "Registration": ["Signup", "Email Verification", "Profile Creation", "Welcome Flow"],
        "Billing": ["Subscription", "Invoice", "Payment Retry", "Refund", "Payment Method"],
        "Subscription Lifecycle": ["Subscription Creation", "Subscription Modification", "Subscription Cancellation", "Renewal"],
        "Notifications": ["Email Delivery", "Push Notification", "SMS Notification", "Notification Preferences"],
        "Administration": ["User Management", "Role Management", "Permission Management", "Audit Logging"],
        "Reporting": ["Analytics Dashboard", "Report Generation", "Data Export", "Custom Reports"],
    }
    
    # Behavior to journey mapping (inverse of patterns)
    BEHAVIOR_TO_JOURNEY: Dict[str, str] = {}
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the journey discovery engine with optional database session."""
        self.db = db
        self._build_behavior_to_journey_mapping()
    
    def _build_behavior_to_journey_mapping(self) -> None:
        """Build inverse mapping from behaviors to journeys."""
        for journey_name, behaviors in self.JOURNEY_PATTERNS.items():
            for behavior in behaviors:
                self.BEHAVIOR_TO_JOURNEY[behavior] = journey_name
    
    def discover_journeys(
        self,
        behaviors: List[Behavior],
        repository_id: str,
    ) -> List[JourneyCandidate]:
        """Discover journey candidates from behaviors."""
        candidates = []
        
        # Group behaviors by inferred journey
        journey_groups = self._group_behaviors_by_journey(behaviors)
        
        # Create candidates for each journey group
        for journey_name, journey_behaviors in journey_groups.items():
            if len(journey_behaviors) < 2:
                # Require at least 2 behaviors to form a journey
                continue
            
            candidate = self._create_journey_candidate(
                journey_name,
                journey_behaviors,
                repository_id,
            )
            candidates.append(candidate)
        
        return candidates
    
    def _group_behaviors_by_journey(
        self,
        behaviors: List[Behavior],
    ) -> Dict[str, List[Behavior]]:
        """Group behaviors by their inferred journey."""
        groups: Dict[str, List[Behavior]] = {}
        
        for behavior in behaviors:
            # Infer journey from behavior name
            journey_name = self._infer_journey_from_behavior(behavior.name)
            
            if journey_name:
                if journey_name not in groups:
                    groups[journey_name] = []
                groups[journey_name].append(behavior)
        
        return groups
    
    def _infer_journey_from_behavior(self, behavior_name: str) -> Optional[str]:
        """Infer journey name from behavior name using patterns."""
        # Direct lookup
        if behavior_name in self.BEHAVIOR_TO_JOURNEY:
            return self.BEHAVIOR_TO_JOURNEY[behavior_name]
        
        # Fuzzy matching based on keywords
        behavior_lower = behavior_name.lower()
        
        for journey_name, journey_behaviors in self.JOURNEY_PATTERNS.items():
            for journey_behavior in journey_behaviors:
                if journey_behavior.lower() in behavior_lower or behavior_lower in journey_behavior.lower():
                    return journey_name
        
        # Keyword-based inference
        if any(keyword in behavior_lower for keyword in ["login", "logout", "auth", "session", "token"]):
            return "Authentication"
        if any(keyword in behavior_lower for keyword in ["signup", "register", "onboard", "verification"]):
            return "Registration"
        if any(keyword in behavior_lower for keyword in ["subscription", "billing", "invoice", "payment", "refund"]):
            return "Billing"
        if any(keyword in behavior_lower for keyword in ["notification", "email", "push", "sms"]):
            return "Notifications"
        if any(keyword in behavior_lower for keyword in ["admin", "role", "permission", "audit"]):
            return "Administration"
        if any(keyword in behavior_lower for keyword in ["report", "analytics", "dashboard", "export"]):
            return "Reporting"
        
        return None
    
    def _create_journey_candidate(
        self,
        journey_name: str,
        behaviors: List[Behavior],
        repository_id: str,
    ) -> JourneyCandidate:
        """Create a journey candidate from grouped behaviors."""
        behavior_names = [b.name for b in behaviors]
        
        # Calculate confidence
        confidence, score = self._calculate_journey_confidence(behaviors, journey_name)
        
        # Generate evidence
        evidence = self._generate_journey_evidence(behaviors, journey_name)
        
        # Determine risk level
        risk_level = self._determine_journey_risk(behaviors)
        
        # Generate description
        description = self._generate_journey_description(journey_name, behavior_names)
        
        # Generate business value
        business_value = self._generate_business_value(journey_name)
        
        return JourneyCandidate(
            name=journey_name,
            confidence=confidence,
            behaviors=behavior_names,
            evidence=evidence,
            source_confidence_score=score,
            description=description,
            business_value=business_value,
            risk_level=risk_level,
        )
    
    def _calculate_journey_confidence(
        self,
        behaviors: List[Behavior],
        journey_name: str,
    ) -> tuple[str, float]:
        """Calculate confidence score for a journey candidate."""
        if not behaviors:
            return "LOW", 0.0
        
        # Base score from behavior count
        behavior_count = len(behaviors)
        base_score = min(behavior_count * 20, 100)  # Max 100 points
        
        # Boost for high-confidence behaviors
        high_conf_count = sum(1 for b in behaviors if b.confidence == "HIGH")
        confidence_boost = (high_conf_count / behavior_count) * 20
        
        # Boost for pattern match
        pattern_match = journey_name in self.JOURNEY_PATTERNS
        pattern_boost = 20 if pattern_match else 0
        
        # Calculate total score
        total_score = base_score + confidence_boost + pattern_boost
        total_score = min(total_score, 100)
        
        # Determine confidence level
        if total_score >= 70:
            return "HIGH", total_score
        elif total_score >= 40:
            return "MODERATE", total_score
        else:
            return "LOW", total_score
    
    def _generate_journey_evidence(
        self,
        behaviors: List[Behavior],
        journey_name: str,
    ) -> List[str]:
        """Generate evidence for a journey candidate."""
        evidence = []
        
        # Evidence from behavior count
        evidence.append(f"Journey contains {len(behaviors)} related behaviors")
        
        # Evidence from behavior names
        behavior_names = [b.name for b in behaviors]
        evidence.append(f"Behaviors: {', '.join(behavior_names[:3])}{'...' if len(behavior_names) > 3 else ''}")
        
        # Evidence from pattern match
        if journey_name in self.JOURNEY_PATTERNS:
            evidence.append(f"Matches known journey pattern: {journey_name}")
        
        # Evidence from behavior confidence
        high_conf_count = sum(1 for b in behaviors if b.confidence == "HIGH")
        if high_conf_count > 0:
            evidence.append(f"{high_conf_count} behaviors have HIGH confidence")
        
        # Evidence from discovery sources
        discovery_sources = set(b.discovery_source for b in behaviors)
        if len(discovery_sources) > 1:
            evidence.append(f"Behaviors discovered from {len(discovery_sources)} different sources")
        
        return evidence
    
    def _determine_journey_risk(self, behaviors: List[Behavior]) -> str:
        """Determine risk level for a journey based on its behaviors."""
        if not behaviors:
            return "MEDIUM"
        
        # Check for critical behaviors
        critical_count = sum(1 for b in behaviors if b.risk_level == "CRITICAL")
        high_count = sum(1 for b in behaviors if b.risk_level == "HIGH")
        
        if critical_count > 0:
            return "CRITICAL"
        elif high_count >= 2:
            return "HIGH"
        elif high_count >= 1:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_journey_description(self, journey_name: str, behavior_names: List[str]) -> str:
        """Generate a description for the journey."""
        descriptions = {
            "Authentication": "User authentication and authorization workflow",
            "Registration": "New user registration and onboarding process",
            "Billing": "Payment processing and financial management",
            "Subscription Lifecycle": "Subscription creation, modification, and cancellation",
            "Notifications": "Email and push notification delivery system",
            "Administration": "System administration and management",
            "Reporting": "Analytics and reporting capabilities",
        }
        
        return descriptions.get(journey_name, f"Business workflow for {journey_name}")
    
    def _generate_business_value(self, journey_name: str) -> str:
        """Generate business value description for the journey."""
        business_values = {
            "Authentication": "Critical for user access and security",
            "Registration": "Essential for user acquisition",
            "Billing": "Critical for revenue generation",
            "Subscription Lifecycle": "Critical for recurring revenue",
            "Notifications": "Important for user engagement",
            "Administration": "Important for operations",
            "Reporting": "Important for business insights",
        }
        
        return business_values.get(journey_name, "Supports business operations")
    
    def get_discovery_stats(self, candidates: List[JourneyCandidate]) -> Dict[str, Any]:
        """Get statistics about journey discovery."""
        if not candidates:
            return {
                "total_candidates": 0,
                "total_behaviors": 0,
                "average_score": 0.0,
                "by_confidence": {"HIGH": 0, "MODERATE": 0, "LOW": 0},
                "by_risk": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            }
        
        total_candidates = len(candidates)
        total_behaviors = sum(c.get_behavior_count() for c in candidates)
        average_score = sum(c.source_confidence_score for c in candidates) / total_candidates
        
        by_confidence = {"HIGH": 0, "MODERATE": 0, "LOW": 0}
        by_risk = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        for candidate in candidates:
            by_confidence[candidate.confidence] += 1
            if candidate.risk_level:
                by_risk[candidate.risk_level] += 1
        
        return {
            "total_candidates": total_candidates,
            "total_behaviors": total_behaviors,
            "average_score": average_score,
            "by_confidence": by_confidence,
            "by_risk": by_risk,
        }
