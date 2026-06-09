from typing import List, Dict, Set
from dataclasses import dataclass
import re
from app.services.behavior_discovery_engine import DiscoveredBehaviorCandidate, BehaviorEvidence


class BehaviorMergeService:
    """Service to merge duplicate behavior candidates into canonical behaviors."""
    
    # Synonym mapping: variations -> canonical name
    SYNONYM_MAPPING: Dict[str, str] = {
        # Password Reset variations
        "reset-password": "Password Reset",
        "password-reset": "Password Reset",
        "forgot-password": "Password Reset",
        "recover-password": "Password Reset",
        "password-recovery": "Password Reset",
        "reset-password": "Password Reset",
        
        # User Registration variations
        "signup": "User Registration",
        "sign-up": "User Registration",
        "register": "User Registration",
        "registration": "User Registration",
        "create-account": "User Registration",
        "user-registration": "User Registration",
        
        # Authentication variations
        "login": "Authentication",
        "log-in": "Authentication",
        "signin": "Authentication",
        "sign-in": "Authentication",
        "auth": "Authentication",
        "authentication": "Authentication",
        
        # Subscription Management variations
        "billing": "Subscription Management",
        "subscription": "Subscription Management",
        "subscription-management": "Subscription Management",
        "plan": "Subscription Management",
        "pricing": "Subscription Management",
        
        # Checkout variations
        "checkout": "Checkout",
        "check-out": "Checkout",
        "cart": "Checkout",
        "payment": "Checkout",
        "purchase": "Checkout",
        
        # User Management variations
        "profile": "User Management",
        "settings": "User Management",
        "account": "User Management",
        "user": "User Management",
        "user-management": "User Management",
        
        # Notifications variations
        "notification": "Notifications",
        "notifications": "Notifications",
        "alert": "Notifications",
        "alerts": "Notifications",
        "message": "Notifications",
        "email": "Notifications",
        
        # Reporting variations
        "report": "Reporting",
        "reporting": "Reporting",
        "analytics": "Reporting",
        "dashboard": "Reporting",
        "statistics": "Reporting",
        
        # Administration variations
        "admin": "Administration",
        "administration": "Administration",
        "manage": "Administration",
        "management": "Administration",
        "control": "Administration",
        
        # File Upload variations
        "upload": "File Upload",
        "file-upload": "File Upload",
        "file": "File Upload",
        "attachment": "File Upload",
        
        # Search variations
        "search": "Search",
        "query": "Search",
        "find": "Search",
        
        # API Integration variations
        "api": "API Integration",
        "api-integration": "API Integration",
        "webhook": "API Integration",
        "webhooks": "API Integration",
        "integration": "API Integration",
    }
    
    def __init__(self):
        """Initialize the merge service."""
        self.canonical_behaviors: Dict[str, DiscoveredBehaviorCandidate] = {}
    
    def merge_candidates(self, candidates: List[DiscoveredBehaviorCandidate]) -> List[DiscoveredBehaviorCandidate]:
        """Merge duplicate behavior candidates into canonical behaviors."""
        # Group candidates by canonical key
        groups = self._group_candidates(candidates)
        
        # Merge each group into a single canonical candidate
        for canonical_key, group_candidates in groups.items():
            merged = self._merge_group(canonical_key, group_candidates)
            self.canonical_behaviors[canonical_key] = merged
        
        return list(self.canonical_behaviors.values())
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a behavior name for comparison."""
        # Convert to lowercase
        normalized = name.lower()
        # Remove special characters (keep hyphens and underscores)
        normalized = re.sub(r'[^a-z0-9\-_]', '', normalized)
        # Replace underscores with hyphens
        normalized = normalized.replace('_', '-')
        # Remove multiple consecutive hyphens
        normalized = re.sub(r'-+', '-', normalized)
        # Strip leading/trailing hyphens
        normalized = normalized.strip('-')
        return normalized
    
    def _generate_canonical_key(self, candidate: DiscoveredBehaviorCandidate) -> str:
        """Generate a canonical key for a candidate."""
        # First check if the name is already in synonym mapping
        normalized = self._normalize_name(candidate.name)
        
        if normalized in self.SYNONYM_MAPPING:
            return self.SYNONYM_MAPPING[normalized]
        
        # If not in mapping, use the candidate's suggested slug or normalized name
        if candidate.suggested_slug:
            return candidate.suggested_slug
        
        return normalized
    
    def _group_candidates(self, candidates: List[DiscoveredBehaviorCandidate]) -> Dict[str, List[DiscoveredBehaviorCandidate]]:
        """Group candidates by their canonical key."""
        groups: Dict[str, List[DiscoveredBehaviorCandidate]] = {}
        
        for candidate in candidates:
            canonical_key = self._generate_canonical_key(candidate)
            
            if canonical_key not in groups:
                groups[canonical_key] = []
            
            groups[canonical_key].append(candidate)
        
        return groups
    
    def _merge_group(self, canonical_key: str, candidates: List[DiscoveredBehaviorCandidate]) -> DiscoveredBehaviorCandidate:
        """Merge a group of candidates into a single canonical candidate."""
        if not candidates:
            raise ValueError("Cannot merge empty candidate group")
        
        # Use the first candidate as base, but prefer candidates with higher confidence
        base_candidate = max(candidates, key=lambda c: self._confidence_score(c.confidence))
        
        # Merge all evidences
        merged_evidences: List[BehaviorEvidence] = []
        seen_evidence_keys: Set[str] = set()
        
        for candidate in candidates:
            for evidence in candidate.evidences:
                # Create a unique key for evidence to avoid duplicates
                evidence_key = self._generate_evidence_key(evidence)
                
                if evidence_key not in seen_evidence_keys:
                    merged_evidences.append(evidence)
                    seen_evidence_keys.add(evidence_key)
        
        # Calculate aggregate confidence
        aggregate_confidence = self._calculate_aggregate_confidence(merged_evidences)
        
        # Determine canonical name (use synonym mapping if available)
        canonical_name = self._get_canonical_name(canonical_key)
        
        # Create merged candidate
        merged = DiscoveredBehaviorCandidate(
            name=canonical_name,
            confidence=aggregate_confidence,
            evidences=merged_evidences,
            suggested_slug=self._normalize_name(canonical_name),
            suggested_journey=base_candidate.suggested_journey,
            suggested_risk_level=base_candidate.suggested_risk_level,
            suggested_description=f"Merged from {len(candidates)} candidate(s): {', '.join(c.name for c in candidates)}",
        )
        
        return merged
    
    def _generate_evidence_key(self, evidence: BehaviorEvidence) -> str:
        """Generate a unique key for evidence to detect duplicates."""
        parts = [
            evidence.evidence_type,
            evidence.source_path or "",
            evidence.source_name or "",
        ]
        return "|".join(parts)
    
    def _confidence_score(self, confidence: str) -> int:
        """Convert confidence string to numeric score."""
        scores = {
            "HIGH": 3,
            "MODERATE": 2,
            "LOW": 1,
        }
        return scores.get(confidence, 0)
    
    def _calculate_aggregate_confidence(self, evidences: List[BehaviorEvidence]) -> str:
        """Calculate aggregate confidence from merged evidences."""
        if not evidences:
            return "LOW"
        
        high_count = sum(1 for e in evidences if e.confidence == "HIGH")
        moderate_count = sum(1 for e in evidences if e.confidence == "MODERATE")
        
        if high_count >= 2:
            return "HIGH"
        elif high_count >= 1 or moderate_count >= 3:
            return "MODERATE"
        else:
            return "LOW"
    
    def _get_canonical_name(self, canonical_key: str) -> str:
        """Get the canonical name from a canonical key."""
        # Check if the key is already a canonical name
        if canonical_key in self.SYNONYM_MAPPING.values():
            return canonical_key
        
        # Check if the key maps to a canonical name
        if canonical_key in self.SYNONYM_MAPPING:
            return self.SYNONYM_MAPPING[canonical_key]
        
        # If not found, convert slug to title case
        return canonical_key.replace('-', ' ').title()
    
    def cluster_evidences_by_type(self, candidate: DiscoveredBehaviorCandidate) -> Dict[str, List[BehaviorEvidence]]:
        """Cluster evidences by type for analysis."""
        clusters: Dict[str, List[BehaviorEvidence]] = {}
        
        for evidence in candidate.evidences:
            if evidence.evidence_type not in clusters:
                clusters[evidence.evidence_type] = []
            clusters[evidence.evidence_type].append(evidence)
        
        return clusters
