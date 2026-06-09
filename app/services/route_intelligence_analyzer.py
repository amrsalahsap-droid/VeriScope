from dataclasses import dataclass
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
import re


@dataclass
class RouteBehaviorEvidence:
    """Evidence of a behavior inferred from a route."""
    behavior: str  # The inferred behavior name
    route: str  # The route path
    confidence: str  # HIGH, MODERATE, LOW
    http_method: Optional[str] = None  # GET, POST, PUT, DELETE, etc.
    route_pattern: Optional[str] = None  # The pattern that matched (e.g., "reset-password")
    matched_alias: Optional[str] = None  # The specific alias that matched


class RouteIntelligenceAnalyzer:
    """Analyzer to infer behaviors from API routes and app routes."""
    
    # Fallback patterns when database is not available
    FALLBACK_PATTERNS: Dict[str, List[str]] = {
        "Password Reset": ["reset-password", "forgot-password", "password-reset", "recovery", "recover-password"],
        "User Registration": ["signup", "sign-up", "register", "registration", "create-account", "join"],
        "Authentication": ["auth", "login", "logout", "token", "session", "jwt", "password", "signin", "log-in"],
        "Billing": ["billing", "subscription", "invoice", "payment", "plan", "pricing", "checkout"],
        "Notifications": ["notification", "email", "sms", "message", "alert", "push"],
    }
    
    # HTTP method confidence modifiers
    METHOD_CONFIDENCE_BOOST: Dict[str, float] = {
        "POST": 0.2,  # POST routes often indicate actions
        "PUT": 0.15,
        "DELETE": 0.15,
        "PATCH": 0.1,
        "GET": 0.0,  # GET routes are often read-only, less indicative of behaviors
    }
    
    # Route path confidence modifiers
    PATH_CONFIDENCE_BOOST: Dict[str, float] = {
        "/api/": 0.1,  # API routes are more structured
        "/v1/": 0.1,
        "/v2/": 0.1,
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the analyzer with optional database session."""
        self.db = db
        self._pattern_library = None
    
    def _get_pattern_library(self):
        """Get or initialize the pattern library."""
        if self._pattern_library is None and self.db:
            from app.services.behavior_pattern_library import BehaviorPatternLibrary
            self._pattern_library = BehaviorPatternLibrary(self.db)
            self._pattern_library.load_patterns()
        return self._pattern_library
    
    def analyze_route(self, route: str, http_method: Optional[str] = None) -> Optional[RouteBehaviorEvidence]:
        """Analyze a single route and infer behavior."""
        # Normalize route
        route_normalized = self._normalize_route(route)
        
        # Try to match against pattern library
        pattern_library = self._get_pattern_library()
        matched_pattern = None
        matched_alias = None
        
        if pattern_library:
            matched_pattern = pattern_library.match_pattern(route_normalized)
            if matched_pattern:
                matched_alias = self._find_matched_alias(route_normalized, matched_pattern.aliases)
        
        # Fall back to hardcoded patterns if no database match
        if not matched_pattern:
            for behavior_name, aliases in self.FALLBACK_PATTERNS.items():
                for alias in aliases:
                    if alias in route_normalized:
                        matched_pattern = type('obj', (object,), {
                            'name': behavior_name,
                            'aliases': aliases,
                        })()
                        matched_alias = alias
                        break
                if matched_pattern:
                    break
        
        if matched_pattern:
            confidence = self._calculate_confidence(route_normalized, http_method, matched_pattern)
            
            return RouteBehaviorEvidence(
                behavior=matched_pattern.name,
                route=route,
                confidence=confidence,
                http_method=http_method,
                route_pattern=route_normalized,
                matched_alias=matched_alias,
            )
        
        return None
    
    def analyze_routes(self, routes: List[str]) -> List[RouteBehaviorEvidence]:
        """Analyze multiple routes and return behavior evidence."""
        evidences = []
        
        for route in routes:
            # Extract HTTP method if present in route string (e.g., "POST /api/login")
            http_method, route_path = self._extract_method_and_path(route)
            
            evidence = self.analyze_route(route_path, http_method)
            if evidence:
                evidences.append(evidence)
        
        return evidences
    
    def _normalize_route(self, route: str) -> str:
        """Normalize a route path for analysis."""
        # Remove leading/trailing slashes
        route = route.strip().strip('/')
        
        # Convert to lowercase
        route = route.lower()
        
        # Remove version prefixes (v1, v2, etc.)
        route = re.sub(r'^v\d+/', '', route)
        
        # Remove common prefixes
        route = re.sub(r'^api/', '', route)
        
        return route
    
    def _extract_method_and_path(self, route: str) -> tuple[Optional[str], str]:
        """Extract HTTP method and path from a route string."""
        # Check if route starts with HTTP method
        method_pattern = r'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(.+)$'
        match = re.match(method_pattern, route, re.IGNORECASE)
        
        if match:
            return match.group(1).upper(), match.group(2)
        
        return None, route
    
    def _calculate_confidence(self, route: str, http_method: Optional[str], pattern) -> str:
        """Calculate confidence score for a route match."""
        base_confidence = 0.5  # Start at 0.5 (MODERATE)
        
        # Boost for HTTP method
        if http_method:
            base_confidence += self.METHOD_CONFIDENCE_BOOST.get(http_method.upper(), 0.0)
        
        # Boost for path structure
        for path_prefix, boost in self.PATH_CONFIDENCE_BOOST.items():
            if path_prefix in route.lower():
                base_confidence += boost
                break
        
        # Boost for direct alias match (not partial)
        if any(alias == route for alias in pattern.aliases):
            base_confidence += 0.2
        
        # Boost for multi-segment routes (more specific)
        segments = route.split('/')
        if len(segments) >= 2:
            base_confidence += 0.1
        
        # Cap at 1.0
        base_confidence = min(base_confidence, 1.0)
        
        # Convert to confidence level
        if base_confidence >= 0.8:
            return "HIGH"
        elif base_confidence >= 0.5:
            return "MODERATE"
        else:
            return "LOW"
    
    def _find_matched_alias(self, route: str, aliases: List[str]) -> Optional[str]:
        """Find the specific alias that matched the route."""
        route_lower = route.lower()
        
        for alias in aliases:
            if alias.lower() in route_lower:
                return alias
        
        return None
    
    def get_behavior_counts(self, evidences: List[RouteBehaviorEvidence]) -> Dict[str, int]:
        """Get count of evidences by behavior."""
        counts = {}
        
        for evidence in evidences:
            if evidence.behavior not in counts:
                counts[evidence.behavior] = 0
            counts[evidence.behavior] += 1
        
        return counts
    
    def get_high_confidence_evidences(self, evidences: List[RouteBehaviorEvidence]) -> List[RouteBehaviorEvidence]:
        """Filter evidences to only high confidence ones."""
        return [e for e in evidences if e.confidence == "HIGH"]

