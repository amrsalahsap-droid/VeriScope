from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session


@dataclass
class BehaviorRelationship:
    """Relationship between two behaviors."""
    parent_behavior: str  # The behavior that is depended on or extended
    child_behavior: str  # The behavior that depends on or extends
    relationship_type: str  # DEPENDS_ON, PART_OF, EXTENDS
    confidence: str  # HIGH, MODERATE, LOW
    evidence: List[str]  # List of evidence strings supporting the relationship
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary for serialization."""
        return {
            "parent_behavior": self.parent_behavior,
            "child_behavior": self.child_behavior,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


class BehaviorRelationshipEngine:
    """Engine to discover and validate behavior relationships."""
    
    # Known dependency mappings (evidence-backed)
    DEPENDENCY_MAPPINGS: Dict[str, List[str]] = {
        "Password Reset": ["Authentication"],
        "User Registration": ["User Management", "Authentication"],
        "Subscription Renewal": ["Billing"],
        "Subscription Management": ["Billing"],
        "Password Change": ["Authentication"],
        "Email Verification": ["User Registration", "Notifications"],
        "Profile Update": ["User Management", "Authentication"],
        "Account Deletion": ["User Management", "Authentication"],
    }
    
    # Known part-of mappings (evidence-backed)
    PART_OF_MAPPINGS: Dict[str, List[str]] = {
        "Password Reset": ["Authentication"],
        "Password Change": ["Authentication"],
        "Email Verification": ["User Registration"],
        "Login": ["Authentication"],
        "Logout": ["Authentication"],
        "Token Refresh": ["Authentication"],
    }
    
    # Known extends mappings (evidence-backed)
    EXTENDS_MAPPINGS: Dict[str, List[str]] = {
        "Social Login": ["Authentication"],
        "Multi-factor Authentication": ["Authentication"],
        "OAuth Integration": ["Authentication"],
        "Enterprise Billing": ["Billing"],
        "Recurring Billing": ["Billing"],
    }
    
    # Journey-based relationships (behaviors in same journey are related)
    JOURNEY_RELATIONSHIPS: Dict[str, str] = {
        "Authentication": "Authentication",
        "Password Reset": "Authentication",
        "User Registration": "Authentication",
        "Billing": "Billing",
        "Subscription Management": "Billing",
        "User Management": "User Management",
        "Notifications": "Notifications",
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the relationship engine with optional database session."""
        self.db = db
        self._pattern_library = None
    
    def _get_pattern_library(self):
        """Get or initialize the pattern library."""
        if self._pattern_library is None and self.db:
            from app.services.behavior_pattern_library import BehaviorPatternLibrary
            self._pattern_library = BehaviorPatternLibrary(self.db)
            self._pattern_library.load_patterns()
        return self._pattern_library
    
    def discover_relationships(
        self,
        behavior_names: List[str],
        evidences: Optional[Dict[str, List[Any]]] = None,
    ) -> List[BehaviorRelationship]:
        """Discover relationships between behaviors based on evidence."""
        relationships = []
        
        # Get journey information if available
        pattern_library = self._get_pattern_library()
        behavior_journeys = {}
        if pattern_library:
            for behavior_name in behavior_names:
                pattern = pattern_library.get_pattern(behavior_name)
                if pattern:
                    behavior_journeys[behavior_name] = pattern.journey
        
        # Discover DEPENDS_ON relationships
        depends_on_rels = self._discover_depends_on(behavior_names, evidences, behavior_journeys)
        relationships.extend(depends_on_rels)
        
        # Discover PART_OF relationships
        part_of_rels = self._discover_part_of(behavior_names, evidences, behavior_journeys)
        relationships.extend(part_of_rels)
        
        # Discover EXTENDS relationships
        extends_rels = self._discover_extends(behavior_names, evidences, behavior_journeys)
        relationships.extend(extends_rels)
        
        return relationships
    
    def _discover_depends_on(
        self,
        behavior_names: List[str],
        evidences: Optional[Dict[str, List[Any]]],
        behavior_journeys: Dict[str, str],
    ) -> List[BehaviorRelationship]:
        """Discover DEPENDS_ON relationships."""
        relationships = []
        
        for child_behavior in behavior_names:
            # Check known dependency mappings
            if child_behavior in self.DEPENDENCY_MAPPINGS:
                for parent_behavior in self.DEPENDENCY_MAPPINGS[child_behavior]:
                    if parent_behavior in behavior_names:
                        # Validate with evidence
                        evidence_list = self._validate_dependency_evidence(
                            child_behavior,
                            parent_behavior,
                            evidences,
                        )
                        if evidence_list:
                            relationships.append(BehaviorRelationship(
                                parent_behavior=parent_behavior,
                                child_behavior=child_behavior,
                                relationship_type="DEPENDS_ON",
                                confidence="HIGH",
                                evidence=evidence_list,
                            ))
        
        return relationships
    
    def _discover_part_of(
        self,
        behavior_names: List[str],
        evidences: Optional[Dict[str, List[Any]]],
        behavior_journeys: Dict[str, str],
    ) -> List[BehaviorRelationship]:
        """Discover PART_OF relationships."""
        relationships = []
        
        for child_behavior in behavior_names:
            # Check known part-of mappings
            if child_behavior in self.PART_OF_MAPPINGS:
                for parent_behavior in self.PART_OF_MAPPINGS[child_behavior]:
                    if parent_behavior in behavior_names:
                        # Validate with evidence
                        evidence_list = self._validate_part_of_evidence(
                            child_behavior,
                            parent_behavior,
                            evidences,
                            behavior_journeys,
                        )
                        if evidence_list:
                            relationships.append(BehaviorRelationship(
                                parent_behavior=parent_behavior,
                                child_behavior=child_behavior,
                                relationship_type="PART_OF",
                                confidence="HIGH",
                                evidence=evidence_list,
                            ))
        
        return relationships
    
    def _discover_extends(
        self,
        behavior_names: List[str],
        evidences: Optional[Dict[str, List[Any]]],
        behavior_journeys: Dict[str, str],
    ) -> List[BehaviorRelationship]:
        """Discover EXTENDS relationships."""
        relationships = []
        
        for child_behavior in behavior_names:
            # Check known extends mappings
            if child_behavior in self.EXTENDS_MAPPINGS:
                for parent_behavior in self.EXTENDS_MAPPINGS[child_behavior]:
                    if parent_behavior in behavior_names:
                        # Validate with evidence
                        evidence_list = self._validate_extends_evidence(
                            child_behavior,
                            parent_behavior,
                            evidences,
                        )
                        if evidence_list:
                            relationships.append(BehaviorRelationship(
                                parent_behavior=parent_behavior,
                                child_behavior=child_behavior,
                                relationship_type="EXTENDS",
                                confidence="HIGH",
                                evidence=evidence_list,
                            ))
        
        return relationships
    
    def _validate_dependency_evidence(
        self,
        child_behavior: str,
        parent_behavior: str,
        evidences: Optional[Dict[str, List[Any]]],
    ) -> List[str]:
        """Validate DEPENDS_ON relationship with evidence."""
        evidence_list = []
        
        # Add known mapping as evidence
        evidence_list.append(f"Known dependency: {child_behavior} depends on {parent_behavior}")
        
        # Check if both behaviors have evidence in the same files (strong evidence)
        if evidences:
            child_sources = set()
            parent_sources = set()
            
            if child_behavior in evidences:
                for evidence in evidences[child_behavior]:
                    metadata = getattr(evidence, 'metadata', {})
                    source = metadata.get('source_document') or metadata.get('route') or metadata.get('module') or ''
                    if source:
                        child_sources.add(source)
            
            if parent_behavior in evidences:
                for evidence in evidences[parent_behavior]:
                    metadata = getattr(evidence, 'metadata', {})
                    source = metadata.get('source_document') or metadata.get('route') or metadata.get('module') or ''
                    if source:
                        parent_sources.add(source)
            
            # Check for shared sources
            shared_sources = child_sources & parent_sources
            if shared_sources:
                evidence_list.append(f"Shared source files: {', '.join(list(shared_sources)[:3])}")
        
        return evidence_list
    
    def _validate_part_of_evidence(
        self,
        child_behavior: str,
        parent_behavior: str,
        evidences: Optional[Dict[str, List[Any]]],
        behavior_journeys: Dict[str, str],
    ) -> List[str]:
        """Validate PART_OF relationship with evidence."""
        evidence_list = []
        
        # Add known mapping as evidence
        evidence_list.append(f"Known part-of: {child_behavior} is part of {parent_behavior}")
        
        # Check if behaviors are in the same journey
        child_journey = behavior_journeys.get(child_behavior)
        parent_journey = behavior_journeys.get(parent_behavior)
        
        if child_journey and parent_journey and child_journey == parent_journey:
            evidence_list.append(f"Same journey: Both behaviors are in '{child_journey}' journey")
        
        return evidence_list
    
    def _validate_extends_evidence(
        self,
        child_behavior: str,
        parent_behavior: str,
        evidences: Optional[Dict[str, List[Any]]],
    ) -> List[str]:
        """Validate EXTENDS relationship with evidence."""
        evidence_list = []
        
        # Add known mapping as evidence
        evidence_list.append(f"Known extends: {child_behavior} extends {parent_behavior}")
        
        # Check naming similarity (child contains parent name)
        if parent_behavior.lower() in child_behavior.lower():
            evidence_list.append(f"Naming similarity: '{child_behavior}' contains '{parent_behavior}'")
        
        return evidence_list
    
    def build_behavior_graph(
        self,
        relationships: List[BehaviorRelationship],
    ) -> Dict[str, Dict[str, List[str]]]:
        """Build a behavior graph from relationships."""
        graph = {
            "depends_on": {},
            "part_of": {},
            "extends": {},
        }
        
        for rel in relationships:
            if rel.relationship_type == "DEPENDS_ON":
                if rel.child_behavior not in graph["depends_on"]:
                    graph["depends_on"][rel.child_behavior] = []
                graph["depends_on"][rel.child_behavior].append(rel.parent_behavior)
            elif rel.relationship_type == "PART_OF":
                if rel.child_behavior not in graph["part_of"]:
                    graph["part_of"][rel.child_behavior] = []
                graph["part_of"][rel.child_behavior].append(rel.parent_behavior)
            elif rel.relationship_type == "EXTENDS":
                if rel.child_behavior not in graph["extends"]:
                    graph["extends"][rel.child_behavior] = []
                graph["extends"][rel.child_behavior].append(rel.parent_behavior)
        
        return graph
    
    def get_relationships_by_behavior(
        self,
        relationships: List[BehaviorRelationship],
        behavior_name: str,
    ) -> Dict[str, List[BehaviorRelationship]]:
        """Get all relationships for a specific behavior."""
        result = {
            "as_parent": [],
            "as_child": [],
        }
        
        for rel in relationships:
            if rel.parent_behavior == behavior_name:
                result["as_parent"].append(rel)
            if rel.child_behavior == behavior_name:
                result["as_child"].append(rel)
        
        return result
    
    def get_relationships_by_type(
        self,
        relationships: List[BehaviorRelationship],
        relationship_type: str,
    ) -> List[BehaviorRelationship]:
        """Filter relationships by type."""
        return [rel for rel in relationships if rel.relationship_type == relationship_type]
