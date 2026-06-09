from typing import List, Optional, Dict, Set
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.behavior import Behavior
from app.models.journey_relationship import JourneyRelationship
from app.models.journey_behavior import JourneyBehavior
from app.models.journey_step import JourneyStep


class JourneyRelationshipEngine:
    """Engine to discover and analyze cross-journey dependencies."""
    
    # Relationship types
    RELATIONSHIP_TYPES = {
        "DEPENDS_ON": "Source journey requires target journey to complete",
        "TRIGGERS": "Source journey initiates target journey",
        "EXTENDS": "Source journey extends functionality of target journey",
    }
    
    # Evidence types
    EVIDENCE_TYPES = {
        "CODE_REFERENCE": "Code references between journey files",
        "BEHAVIOR_LINK": "Shared behaviors between journeys",
        "FLOW_TRANSITION": "Explicit flow transitions in journey steps",
        "USER_FLOW": "User flow documentation or evidence",
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the journey relationship engine with optional database session."""
        self.db = db
    
    def discover_relationships(
        self,
        journeys: List[Journey],
        behaviors: List[Behavior],
        journey_behaviors: List[JourneyBehavior],
        journey_steps: Optional[List[JourneyStep]] = None,
    ) -> List[JourneyRelationship]:
        """Discover cross-journey relationships based on evidence."""
        relationships = []
        
        # Build journey to behaviors map
        journey_behavior_map = self._build_journey_behavior_map(journey_behaviors)
        
        # Discover relationships through shared behaviors
        behavior_relationships = self._discover_behavior_relationships(
            journeys,
            behaviors,
            journey_behavior_map,
        )
        relationships.extend(behavior_relationships)
        
        # Discover relationships through journey steps
        if journey_steps:
            step_relationships = self._discover_step_relationships(
                journeys,
                journey_steps,
                journey_behavior_map,
            )
            relationships.extend(step_relationships)
        
        return relationships
    
    def _build_journey_behavior_map(
        self,
        journey_behaviors: List[JourneyBehavior],
    ) -> Dict[str, Set[str]]:
        """Build map of journey_id to behavior_ids."""
        journey_behavior_map = {}
        for jb in journey_behaviors:
            journey_id = str(jb.journey_id)
            behavior_id = str(jb.behavior_id)
            if journey_id not in journey_behavior_map:
                journey_behavior_map[journey_id] = set()
            journey_behavior_map[journey_id].add(behavior_id)
        return journey_behavior_map
    
    def _discover_behavior_relationships(
        self,
        journeys: List[Journey],
        behaviors: List[Behavior],
        journey_behavior_map: Dict[str, Set[str]],
    ) -> List[JourneyRelationship]:
        """Discover relationships through shared behaviors."""
        relationships = []
        
        # Build behavior to journeys map
        behavior_journey_map = {}
        for journey_id, behavior_ids in journey_behavior_map.items():
            for behavior_id in behavior_ids:
                if behavior_id not in behavior_journey_map:
                    behavior_journey_map[behavior_id] = set()
                behavior_journey_map[behavior_id].add(journey_id)
        
        # Find shared behaviors between journeys
        for behavior_id, journey_ids in behavior_journey_map.items():
            if len(journey_ids) > 1:
                # Multiple journeys share this behavior
                journey_ids_list = list(journey_ids)
                for i in range(len(journey_ids_list)):
                    for j in range(i + 1, len(journey_ids_list)):
                        source_id = journey_ids_list[i]
                        target_id = journey_ids_list[j]
                        
                        # Find the behavior
                        behavior = next((b for b in behaviors if str(b.id) == behavior_id), None)
                        if not behavior:
                            continue
                        
                        # Determine relationship type based on behavior context
                        relationship_type = self._determine_relationship_type(behavior.name)
                        
                        # Create relationship
                        relationship = JourneyRelationship(
                            id=None,  # Will be set on persist
                            source_journey_id=source_id,
                            target_journey_id=target_id,
                            relationship_type=relationship_type,
                            evidence_type="BEHAVIOR_LINK",
                            evidence_source=behavior.name,
                            evidence_excerpt=f"Shared behavior: {behavior.name}",
                            confidence="HIGH",
                            relationship_description=f"Journeys share behavior: {behavior.name}",
                        )
                        relationships.append(relationship)
        
        return relationships
    
    def _discover_step_relationships(
        self,
        journeys: List[Journey],
        journey_steps: List[JourneyStep],
        journey_behavior_map: Dict[str, Set[str]],
    ) -> List[JourneyRelationship]:
        """Discover relationships through journey step transitions."""
        relationships = []
        
        # Build journey steps map
        journey_steps_map = {}
        for step in journey_steps:
            journey_id = str(step.journey_id)
            if journey_id not in journey_steps_map:
                journey_steps_map[journey_id] = []
            journey_steps_map[journey_id].append(step)
        
        # Analyze step transitions for flow relationships
        for journey_id, steps in journey_steps_map.items():
            sorted_steps = sorted(steps, key=lambda s: s.step_order)
            
            for i in range(len(sorted_steps) - 1):
                current_step = sorted_steps[i]
                next_step = sorted_steps[i + 1]
                
                # Check if step references another journey
                if current_step.behavior_id and next_step.behavior_id:
                    # This is a simplified check - in production, analyze behavior context
                    # to determine if it references another journey
                    pass
        
        return relationships
    
    def _determine_relationship_type(self, behavior_name: str) -> str:
        """Determine relationship type based on behavior name."""
        behavior_lower = behavior_name.lower()
        
        # Dependency indicators
        if any(kw in behavior_lower for kw in ["login", "auth", "session", "token"]):
            return "DEPENDS_ON"
        
        # Trigger indicators
        if any(kw in behavior_lower for kw in ["signup", "register", "create", "start"]):
            return "TRIGGERS"
        
        # Extension indicators
        if any(kw in behavior_lower for kw in ["upgrade", "extend", "enhance", "add"]):
            return "EXTENDS"
        
        # Default to DEPENDS_ON
        return "DEPENDS_ON"
    
    def analyze_cross_journey_impact(
        self,
        affected_journey_ids: List[str],
        relationships: List[JourneyRelationship],
    ) -> Dict[str, List[str]]:
        """Analyze cross-journey impact from affected journeys."""
        impact_map = {}
        
        # Build relationship graph
        for rel in relationships:
            source_id = str(rel.source_journey_id)
            target_id = str(rel.target_journey_id)
            
            # If source is affected, target is impacted
            if source_id in affected_journey_ids:
                if target_id not in impact_map:
                    impact_map[target_id] = []
                impact_map[target_id].append(f"Affected by {rel.relationship_type} relationship from source journey")
            
            # If target is affected, source is impacted (for DEPENDS_ON)
            if target_id in affected_journey_ids and rel.relationship_type == "DEPENDS_ON":
                if source_id not in impact_map:
                    impact_map[source_id] = []
                impact_map[source_id].append(f"Depends on affected target journey")
        
        return impact_map
    
    def get_journey_dependencies(
        self,
        journey_id: str,
        relationships: List[JourneyRelationship],
    ) -> Dict[str, List[Dict]]:
        """Get all dependencies for a journey."""
        dependencies = {
            "outgoing": [],  # This journey depends on others
            "incoming": [],  # Other journeys depend on this
        }
        
        for rel in relationships:
            source_id = str(rel.source_journey_id)
            target_id = str(rel.target_journey_id)
            
            if source_id == journey_id:
                dependencies["outgoing"].append({
                    "target_journey_id": target_id,
                    "relationship_type": rel.relationship_type,
                    "evidence_type": rel.evidence_type,
                    "confidence": rel.confidence,
                })
            
            if target_id == journey_id:
                dependencies["incoming"].append({
                    "source_journey_id": source_id,
                    "relationship_type": rel.relationship_type,
                    "evidence_type": rel.evidence_type,
                    "confidence": rel.confidence,
                })
        
        return dependencies
    
    def persist_relationships(
        self,
        relationships: List[JourneyRelationship],
    ) -> List[JourneyRelationship]:
        """Persist discovered relationships to database."""
        if not self.db:
            return relationships
        
        persisted = []
        for rel in relationships:
            # Check if relationship already exists
            existing = self.db.query(JourneyRelationship).filter(
                JourneyRelationship.source_journey_id == rel.source_journey_id,
                JourneyRelationship.target_journey_id == rel.target_journey_id,
                JourneyRelationship.relationship_type == rel.relationship_type,
            ).first()
            
            if not existing:
                self.db.add(rel)
                self.db.commit()
                self.db.refresh(rel)
                persisted.append(rel)
            else:
                persisted.append(existing)
        
        return persisted
