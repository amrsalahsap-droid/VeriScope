from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from datetime import datetime
import re
from pathlib import Path
from sqlalchemy.orm import Session


@dataclass
class BehaviorEvidence:
    """Evidence supporting a discovered behavior candidate."""
    evidence_type: str  # ROUTE, PAGE, MODULE, TEST, PR_TITLE, PR_DESCRIPTION, README, CONFIG, MANUAL
    source_path: Optional[str] = None
    source_name: Optional[str] = None
    excerpt: Optional[str] = None
    confidence: str = "MODERATE"  # HIGH, MODERATE, LOW


@dataclass
class DiscoveredBehaviorCandidate:
    """A candidate behavior discovered from code analysis."""
    name: str
    confidence: str  # HIGH, MODERATE, LOW
    evidences: List[BehaviorEvidence] = field(default_factory=list)
    suggested_slug: Optional[str] = None
    suggested_journey: Optional[str] = None
    suggested_risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    suggested_description: Optional[str] = None
    
    def add_evidence(self, evidence: BehaviorEvidence) -> None:
        """Add evidence to this candidate."""
        self.evidences.append(evidence)
    
    def calculate_aggregate_confidence(self) -> str:
        """Calculate aggregate confidence based on evidence count and individual confidences."""
        if not self.evidences:
            return "LOW"
        
        high_count = sum(1 for e in self.evidences if e.confidence == "HIGH")
        moderate_count = sum(1 for e in self.evidences if e.confidence == "MODERATE")
        
        if high_count >= 2:
            return "HIGH"
        elif high_count >= 1 or moderate_count >= 3:
            return "MODERATE"
        else:
            return "LOW"


class BehaviorDiscoveryEngine:
    """Deterministic behavior discovery engine using pattern matching."""
    
    # Pattern mapping: keyword patterns -> normalized behavior name
    BEHAVIOR_PATTERNS: Dict[str, str] = {
        # Password Reset
        r"reset[-_]?password": "Password Reset",
        r"forgot[-_]?password": "Password Reset",
        r"recover[-_]?password": "Password Reset",
        
        # User Registration
        r"sign[-_]?up": "User Registration",
        r"register": "User Registration",
        r"signup": "User Registration",
        r"create[-_]?account": "User Registration",
        
        # Authentication
        r"login": "Authentication",
        r"auth": "Authentication",
        r"signin": "Authentication",
        r"log[-_]?in": "Authentication",
        
        # Subscription Management
        r"billing": "Subscription Management",
        r"subscription": "Subscription Management",
        r"plan": "Subscription Management",
        r"pricing": "Subscription Management",
        
        # Checkout
        r"checkout": "Checkout",
        r"cart": "Checkout",
        r"payment": "Checkout",
        r"purchase": "Checkout",
        
        # User Management
        r"profile": "User Management",
        r"settings": "User Management",
        r"account": "User Management",
        r"user": "User Management",
        
        # Notifications
        r"notification": "Notifications",
        r"alert": "Notifications",
        r"message": "Notifications",
        r"email": "Notifications",
        
        # Reporting
        r"report": "Reporting",
        r"analytics": "Reporting",
        r"dashboard": "Reporting",
        r"statistics": "Reporting",
        
        # Administration
        r"admin": "Administration",
        r"manage": "Administration",
        r"control": "Administration",
        
        # File Upload
        r"upload": "File Upload",
        r"file": "File Upload",
        r"attachment": "File Upload",
        
        # Search
        r"search": "Search",
        r"query": "Search",
        r"find": "Search",
        
        # API Integration
        r"api": "API Integration",
        r"webhook": "API Integration",
        r"integration": "API Integration",
    }
    
    # Journey mapping: behavior -> suggested journey
    JOURNEY_MAPPING: Dict[str, str] = {
        "Password Reset": "Authentication",
        "User Registration": "Authentication",
        "Authentication": "Authentication",
        "Subscription Management": "Billing",
        "Checkout": "Billing",
        "User Management": "User Management",
        "Notifications": "Notifications",
        "Reporting": "Reporting",
        "Administration": "Administration",
        "File Upload": "User Management",
        "Search": "User Management",
        "API Integration": "Integration",
    }
    
    # Risk level mapping based on behavior type
    RISK_MAPPING: Dict[str, str] = {
        "Password Reset": "HIGH",
        "User Registration": "HIGH",
        "Authentication": "CRITICAL",
        "Subscription Management": "HIGH",
        "Checkout": "CRITICAL",
        "User Management": "MEDIUM",
        "Notifications": "LOW",
        "Reporting": "LOW",
        "Administration": "CRITICAL",
        "File Upload": "MEDIUM",
        "Search": "LOW",
        "API Integration": "HIGH",
    }
    
    def __init__(self, repository_path: str, db: Optional[Session] = None):
        """Initialize the discovery engine with a repository path and optional database session."""
        self.repository_path = Path(repository_path)
        self.candidates: Dict[str, DiscoveredBehaviorCandidate] = {}
        self.db = db
        self._pattern_library = None
    
    def _get_pattern_library(self):
        """Get or initialize the pattern library."""
        if self._pattern_library is None and self.db:
            from app.services.behavior_pattern_library import BehaviorPatternLibrary
            self._pattern_library = BehaviorPatternLibrary(self.db)
            self._pattern_library.load_patterns()
        return self._pattern_library
    
    def discover_behaviors(
        self,
        routes: Optional[List[str]] = None,
        pages: Optional[List[str]] = None,
        folders: Optional[List[str]] = None,
        modules: Optional[List[str]] = None,
        test_names: Optional[List[str]] = None,
    ) -> List[DiscoveredBehaviorCandidate]:
        """Discover behavior candidates from various sources."""
        # Scan routes
        if routes:
            self._scan_routes(routes)
        
        # Scan pages
        if pages:
            self._scan_pages(pages)
        
        # Scan folders
        if folders:
            self._scan_folders(folders)
        
        # Scan modules
        if modules:
            self._scan_modules(modules)
        
        # Scan test names
        if test_names:
            self._scan_test_names(test_names)
        
        # Finalize candidates
        self._finalize_candidates()
        
        return list(self.candidates.values())
    
    def _normalize_behavior_name(self, text: str) -> Optional[str]:
        """Normalize text to a behavior name using pattern matching."""
        text_lower = text.lower()
        
        # First try pattern library if available
        pattern_library = self._get_pattern_library()
        if pattern_library:
            matched_pattern = pattern_library.match_pattern(text)
            if matched_pattern:
                return matched_pattern.name
        
        # Fall back to hardcoded patterns
        for pattern, behavior_name in self.BEHAVIOR_PATTERNS.items():
            if re.search(pattern, text_lower):
                return behavior_name
        
        return None
    
    def _get_or_create_candidate(self, behavior_name: str) -> DiscoveredBehaviorCandidate:
        """Get existing candidate or create new one."""
        if behavior_name not in self.candidates:
            slug = self._generate_slug(behavior_name)
            
            # Try to get journey and risk from pattern library
            pattern_library = self._get_pattern_library()
            if pattern_library:
                pattern = pattern_library.get_pattern(behavior_name)
                if pattern:
                    journey = pattern.journey
                    risk = pattern.risk_level
                    description = pattern.description
                else:
                    journey = self.JOURNEY_MAPPING.get(behavior_name, "General")
                    risk = self.RISK_MAPPING.get(behavior_name, "MEDIUM")
                    description = f"Automatically discovered behavior: {behavior_name}"
            else:
                journey = self.JOURNEY_MAPPING.get(behavior_name, "General")
                risk = self.RISK_MAPPING.get(behavior_name, "MEDIUM")
                description = f"Automatically discovered behavior: {behavior_name}"
            
            self.candidates[behavior_name] = DiscoveredBehaviorCandidate(
                name=behavior_name,
                confidence="LOW",
                suggested_slug=slug,
                suggested_journey=journey,
                suggested_risk_level=risk,
                suggested_description=description,
            )
        
        return self.candidates[behavior_name]
    
    def _generate_slug(self, behavior_name: str) -> str:
        """Generate a URL-friendly slug from behavior name."""
        return behavior_name.lower().replace(" ", "-").replace("_", "-")
    
    def _scan_routes(self, routes: List[str]) -> None:
        """Scan route paths for behavior patterns."""
        for route in routes:
            behavior_name = self._normalize_behavior_name(route)
            if behavior_name:
                candidate = self._get_or_create_candidate(behavior_name)
                candidate.add_evidence(BehaviorEvidence(
                    evidence_type="ROUTE",
                    source_path=route,
                    source_name=route,
                    confidence="HIGH",
                ))
    
    def _scan_pages(self, pages: List[str]) -> None:
        """Scan page paths for behavior patterns."""
        for page in pages:
            behavior_name = self._normalize_behavior_name(page)
            if behavior_name:
                candidate = self._get_or_create_candidate(behavior_name)
                candidate.add_evidence(BehaviorEvidence(
                    evidence_type="PAGE",
                    source_path=page,
                    source_name=page,
                    confidence="HIGH",
                ))
    
    def _scan_folders(self, folders: List[str]) -> None:
        """Scan folder names for behavior patterns."""
        for folder in folders:
            behavior_name = self._normalize_behavior_name(folder)
            if behavior_name:
                candidate = self._get_or_create_candidate(behavior_name)
                candidate.add_evidence(BehaviorEvidence(
                    evidence_type="MODULE",
                    source_path=folder,
                    source_name=folder,
                    confidence="MODERATE",
                ))
    
    def _scan_modules(self, modules: List[str]) -> None:
        """Scan module names for behavior patterns."""
        for module in modules:
            behavior_name = self._normalize_behavior_name(module)
            if behavior_name:
                candidate = self._get_or_create_candidate(behavior_name)
                candidate.add_evidence(BehaviorEvidence(
                    evidence_type="MODULE",
                    source_path=module,
                    source_name=module,
                    confidence="MODERATE",
                ))
    
    def _scan_test_names(self, test_names: List[str]) -> None:
        """Scan test names for behavior patterns."""
        for test_name in test_names:
            behavior_name = self._normalize_behavior_name(test_name)
            if behavior_name:
                candidate = self._get_or_create_candidate(behavior_name)
                candidate.add_evidence(BehaviorEvidence(
                    evidence_type="TEST",
                    source_path=None,
                    source_name=test_name,
                    excerpt=test_name,
                    confidence="MODERATE",
                ))
    
    def _finalize_candidates(self) -> None:
        """Finalize all candidates with aggregate confidence."""
        for candidate in self.candidates.values():
            candidate.confidence = candidate.calculate_aggregate_confidence()
