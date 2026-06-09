from typing import List, Optional, Dict, Set, Any
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.behavior import Behavior
from app.models.journey_behavior import JourneyBehavior
from app.services.journey_impact import JourneyImpact
from app.config import settings


class PRJourneyImpactAnalyzer:
    """Analyzer to identify affected journeys for a PR."""
    
    # Impact level hierarchy
    IMPACT_HIERARCHY = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }
    
    # File path to behavior keyword mapping
    FILE_BEHAVIOR_KEYWORDS = {
        "auth": ["Authentication", "Login", "Logout", "Session"],
        "login": ["Authentication", "Login"],
        "logout": ["Authentication", "Logout"],
        "password": ["Authentication", "Password Reset", "Password Recovery"],
        "reset": ["Authentication", "Password Reset", "Password Recovery"],
        "signup": ["Registration", "Signup", "User Registration"],
        "register": ["Registration", "Signup", "User Registration"],
        "subscription": ["Billing", "Subscription", "Subscription Lifecycle"],
        "billing": ["Billing", "Invoice", "Payment"],
        "invoice": ["Billing", "Invoice"],
        "payment": ["Billing", "Payment", "Payment Processing"],
        "notification": ["Notifications", "Email", "Push", "SMS"],
        "email": ["Notifications", "Email"],
        "push": ["Notifications", "Push"],
        "admin": ["Administration", "User Management", "Role Management"],
        "report": ["Reporting", "Analytics", "Dashboard"],
        "analytics": ["Reporting", "Analytics"],
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the PR journey impact analyzer with optional database session."""
        self.db = db
    
    def analyze_pr_impact(
        self,
        changed_files: List[str],
        behaviors: List[Behavior],
        journey_behaviors: List[JourneyBehavior],
        journeys: List[Journey],
        architecture_impact: Optional[Dict[str, Any]] = None,
    ) -> List[JourneyImpact]:
        """Analyze PR impact on journeys."""
        # Enrich changed files with architecture impact if available
        enriched_changed_files = changed_files
        if architecture_impact and settings.USE_ARCHITECTURE_V2:
            enriched_changed_files = architecture_impact.get("impacted_files", changed_files)
        
        # Map files to behaviors
        file_to_behaviors = self._map_files_to_behaviors(enriched_changed_files, behaviors)
        
        # Map behaviors to journeys
        behavior_to_journeys = self._map_behaviors_to_journeys(journey_behaviors, journeys)
        
        # Calculate impact for each journey
        impacts = []
        for journey in journeys:
            impact = self._calculate_journey_impact(
                journey,
                changed_files,
                file_to_behaviors,
                behavior_to_journeys,
                behaviors,
            )
            if impact:
                impacts.append(impact)
        
        return impacts
    
    def _map_files_to_behaviors(
        self,
        changed_files: List[str],
        behaviors: List[Behavior],
    ) -> Dict[str, List[Behavior]]:
        """Map changed files to related behaviors."""
        file_to_behaviors = {}
        
        for file_path in changed_files:
            file_lower = file_path.lower()
            related_behaviors = []
            
            for behavior in behaviors:
                behavior_lower = behavior.name.lower()
                
                # Check if behavior name appears in file path
                if behavior_lower in file_lower or file_lower in behavior_lower:
                    related_behaviors.append(behavior)
                    continue
                
                # Check keyword matching
                for keyword, behavior_keywords in self.FILE_BEHAVIOR_KEYWORDS.items():
                    if keyword in file_lower and any(
                        bk.lower() in behavior_lower for bk in behavior_keywords
                    ):
                        related_behaviors.append(behavior)
                        break
            
            if related_behaviors:
                file_to_behaviors[file_path] = related_behaviors
        
        return file_to_behaviors
    
    def _map_behaviors_to_journeys(
        self,
        journey_behaviors: List[JourneyBehavior],
        journeys: List[Journey],
    ) -> Dict[str, List[Journey]]:
        """Map behaviors to their parent journeys."""
        behavior_to_journeys = {}
        
        for jb in journey_behaviors:
            behavior_id = str(jb.behavior_id)
            if behavior_id not in behavior_to_journeys:
                behavior_to_journeys[behavior_id] = []
            
            # Find the journey
            journey = next((j for j in journeys if str(j.id) == str(jb.journey_id)), None)
            if journey:
                behavior_to_journeys[behavior_id].append(journey)
        
        return behavior_to_journeys
    
    def _calculate_journey_impact(
        self,
        journey: Journey,
        changed_files: List[str],
        file_to_behaviors: Dict[str, List[Behavior]],
        behavior_to_journeys: Dict[str, List[Journey]],
        all_behaviors: List[Behavior],
    ) -> Optional[JourneyImpact]:
        """Calculate impact for a specific journey."""
        # Find affected behaviors for this journey
        affected_behaviors = []
        affected_files = []
        
        for file_path, behaviors in file_to_behaviors.items():
            for behavior in behaviors:
                # Check if this behavior belongs to the journey
                behavior_journeys = behavior_to_journeys.get(str(behavior.id), [])
                if any(str(j.id) == str(journey.id) for j in behavior_journeys):
                    if behavior.name not in affected_behaviors:
                        affected_behaviors.append(behavior.name)
                    if file_path not in affected_files:
                        affected_files.append(file_path)
        
        if not affected_behaviors:
            return None
        
        # Calculate impact level
        impact_level = self._calculate_impact_level(affected_behaviors, all_behaviors, journey)
        
        # Calculate risk changes
        risk_changes = self._calculate_risk_changes(affected_behaviors, all_behaviors)
        
        # Determine confidence
        confidence = self._determine_confidence(affected_files, affected_behaviors)
        
        # Generate impact reason
        impact_reason = self._generate_impact_reason(
            journey.name,
            affected_behaviors,
            affected_files,
            impact_level,
        )
        
        # Build evidence list from matched files and behaviors
        evidence = []
        for file_path in affected_files:
            for behavior in all_behaviors:
                if behavior.name in affected_behaviors:
                    evidence.append({
                        "type": "FILE_BEHAVIOR_MATCH",
                        "file_path": file_path,
                        "behavior_name": behavior.name,
                        "confidence": confidence,
                    })

        # Build impacted behavior details
        impacted_behavior_details = []
        for behavior in all_behaviors:
            if behavior.name in affected_behaviors:
                impacted_behavior_details.append({
                    "behavior_id": str(behavior.id),
                    "behavior_name": behavior.name,
                    "risk_level": behavior.risk_level or "MEDIUM",
                    "confidence": behavior.confidence or "MEDIUM",
                })

        return JourneyImpact(
            journey_id=str(journey.id),
            journey_name=journey.name,
            impact_level=impact_level,
            affected_behaviors=affected_behaviors,
            affected_files=affected_files,
            risk_changes=risk_changes,
            confidence=confidence,
            impact_reason=impact_reason,
            risk=journey.risk_level or "MEDIUM",
            evidence=evidence,
            impacted_behavior_details=impacted_behavior_details,
        )
    
    def _calculate_impact_level(
        self,
        affected_behaviors: List[str],
        all_behaviors: List[Behavior],
        journey: Journey,
    ) -> str:
        """Calculate impact level based on affected behaviors and journey risk."""
        # Get risk levels of affected behaviors
        behavior_risks = []
        for behavior in all_behaviors:
            if behavior.name in affected_behaviors:
                behavior_risks.append(behavior.risk_level)
        
        # Check for CRITICAL behaviors
        if "CRITICAL" in behavior_risks:
            return "CRITICAL"
        
        # Check for HIGH behaviors
        if behavior_risks.count("HIGH") >= 2:
            return "CRITICAL"
        if "HIGH" in behavior_risks:
            return "HIGH"
        
        # Check journey risk level
        if journey.risk_level == "CRITICAL":
            return "HIGH"
        elif journey.risk_level == "HIGH":
            return "MEDIUM"
        
        # Default based on behavior count
        if len(affected_behaviors) >= 3:
            return "MEDIUM"
        elif len(affected_behaviors) >= 1:
            return "LOW"
        
        return "LOW"
    
    def _calculate_risk_changes(
        self,
        affected_behaviors: List[str],
        all_behaviors: List[Behavior],
    ) -> List[str]:
        """Calculate risk changes from affected behaviors."""
        risk_changes = []
        
        for behavior in all_behaviors:
            if behavior.name in affected_behaviors:
                if behavior.risk_level in ["HIGH", "CRITICAL"]:
                    risk_changes.append(f"{behavior.name} has {behavior.risk_level} risk")
                if behavior.risk_reason:
                    risk_changes.append(f"{behavior.name}: {behavior.risk_reason}")
        
        return risk_changes
    
    def _determine_confidence(
        self,
        affected_files: List[str],
        affected_behaviors: List[str],
    ) -> str:
        """Determine confidence in impact assessment."""
        if not affected_files or not affected_behaviors:
            return "LOW"
        
        # More files and behaviors = higher confidence
        if len(affected_files) >= 3 and len(affected_behaviors) >= 2:
            return "HIGH"
        elif len(affected_files) >= 1 and len(affected_behaviors) >= 1:
            return "MODERATE"
        else:
            return "LOW"
    
    def _generate_impact_reason(
        self,
        journey_name: str,
        affected_behaviors: List[str],
        affected_files: List[str],
        impact_level: str,
    ) -> str:
        """Generate explainable reason for impact."""
        # Cite changed files
        file_citation = ", ".join(affected_files[:3])
        if len(affected_files) > 3:
            file_citation += f", and {len(affected_files) - 3} more"
        
        # Cite affected behaviors
        behavior_citation = ", ".join(affected_behaviors[:3])
        if len(affected_behaviors) > 3:
            behavior_citation += f", and {len(affected_behaviors) - 3} more"
        
        if impact_level == "CRITICAL":
            return f"PR modifies {file_citation}, affecting {behavior_citation} in {journey_name} journey. Changes to critical behaviors could severely impact business operations."
        elif impact_level == "HIGH":
            return f"PR modifies {file_citation}, affecting {behavior_citation} in {journey_name} journey. Changes to high-risk behaviors could significantly impact user experience."
        elif impact_level == "MEDIUM":
            return f"PR modifies {file_citation}, affecting {behavior_citation} in {journey_name} journey. Changes may impact user experience with moderate business impact."
        else:
            return f"PR modifies {file_citation}, affecting {behavior_citation} in {journey_name} journey. Changes have minimal impact on business operations."
    
    def get_impact_summary(self, impacts: List[JourneyImpact]) -> dict:
        """Get summary of PR journey impacts."""
        if not impacts:
            return {
                "total_affected_journeys": 0,
                "by_impact_level": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                "total_affected_behaviors": 0,
                "total_affected_files": 0,
            }
        
        by_impact_level = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        total_affected_behaviors = 0
        total_affected_files = 0
        all_affected_files = set()
        
        for impact in impacts:
            by_impact_level[impact.impact_level] += 1
            total_affected_behaviors += len(impact.affected_behaviors)
            all_affected_files.update(impact.affected_files)
        
        total_affected_files = len(all_affected_files)
        
        return {
            "total_affected_journeys": len(impacts),
            "by_impact_level": by_impact_level,
            "total_affected_behaviors": total_affected_behaviors,
            "total_affected_files": total_affected_files,
        }
