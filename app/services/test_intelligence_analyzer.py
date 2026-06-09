from dataclasses import dataclass
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
import re

from app.services.tokenizer import Tokenizer


@dataclass
class TestBehaviorEvidence:
    """Evidence of a behavior inferred from a test name."""
    behavior: str  # The inferred behavior name
    test_identifier: str  # The test name or identifier
    confidence: str  # HIGH, MODERATE, LOW
    test_type: Optional[str] = None  # unit, integration, e2e, etc.
    matched_alias: Optional[str] = None  # The specific alias that matched
    normalized_tokens: Optional[List[str]] = None  # Normalized tokens from test name


class TestIntelligenceAnalyzer:
    """Analyzer to infer behaviors from test names, suite names, and class names."""
    
    # Test naming patterns that indicate high confidence
    HIGH_CONFIDENCE_PATTERNS: List[str] = [
        r"^test_",
        r"^should_",
        r"^it_",
        r"^spec_",
    ]
    
    # Test type indicators
    TEST_TYPE_PATTERNS: Dict[str, str] = {
        r"e2e": "e2e",
        r"end.to.end": "e2e",
        r"integration": "integration",
        r"unit": "unit",
        r"api": "api",
    }
    
    # Fallback patterns when database is not available
    FALLBACK_PATTERNS: Dict[str, List[str]] = {
        "Password Reset": ["reset-password", "forgot-password", "password-reset", "recovery", "recover-password", "token"],
        "User Registration": ["signup", "sign-up", "register", "registration", "create-account", "join"],
        "Authentication": ["auth", "login", "logout", "token", "session", "jwt", "password", "signin", "log-in"],
        "Billing": ["billing", "subscription", "invoice", "payment", "plan", "pricing", "checkout"],
        "Notifications": ["notification", "email", "sms", "message", "alert", "push"],
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
    
    def analyze_test(self, test_name: str, test_type: Optional[str] = None) -> Optional[TestBehaviorEvidence]:
        """Analyze a single test name and infer behavior."""
        # Normalize test name
        test_normalized = self._normalize_test_name(test_name)
        
        # Tokenize test name
        tokens = Tokenizer.tokenize(test_normalized)
        
        # Infer test type if not provided
        if not test_type:
            test_type = self._infer_test_type(test_name)
        
        # Try to match against pattern library
        pattern_library = self._get_pattern_library()
        matched_pattern = None
        matched_alias = None
        
        if pattern_library:
            matched_pattern = pattern_library.match_pattern(test_normalized)
            if matched_pattern:
                matched_alias = self._find_matched_alias(test_normalized, matched_pattern.aliases)
        
        # Fall back to hardcoded patterns if no database match
        if not matched_pattern:
            for behavior_name, aliases in self.FALLBACK_PATTERNS.items():
                for alias in aliases:
                    if alias in test_normalized:
                        matched_pattern = type('obj', (object,), {
                            'name': behavior_name,
                            'aliases': aliases,
                        })()
                        matched_alias = alias
                        break
                if matched_pattern:
                    break
        
        if matched_pattern:
            confidence = self._calculate_confidence(test_name, test_type, tokens, matched_pattern)
            
            return TestBehaviorEvidence(
                behavior=matched_pattern.name,
                test_identifier=test_name,
                confidence=confidence,
                test_type=test_type,
                matched_alias=matched_alias,
                normalized_tokens=tokens,
            )
        
        return None
    
    def analyze_tests(self, test_names: List[str]) -> List[TestBehaviorEvidence]:
        """Analyze multiple test names and return behavior evidence."""
        evidences = []
        
        for test_name in test_names:
            evidence = self.analyze_test(test_name)
            if evidence:
                evidences.append(evidence)
        
        return evidences
    
    def _normalize_test_name(self, test_name: str) -> str:
        """Normalize a test name for analysis."""
        # Convert to lowercase
        test_name = test_name.lower()
        
        # Remove common test prefixes
        test_name = re.sub(r'^(test_|should_|it_|spec_)', '', test_name)
        
        # Remove underscores and hyphens (replace with spaces for better matching)
        test_name = re.sub(r'[_\-]', ' ', test_name)
        
        # Remove special characters
        test_name = re.sub(r'[^a-z0-9\s]', '', test_name)
        
        # Strip extra spaces
        test_name = ' '.join(test_name.split())
        
        return test_name
    
    def _infer_test_type(self, test_name: str) -> Optional[str]:
        """Infer test type from test name or path."""
        test_name_lower = test_name.lower()
        
        for pattern, test_type in self.TEST_TYPE_PATTERNS.items():
            if pattern in test_name_lower:
                return test_type
        
        return None
    
    def _calculate_confidence(self, test_name: str, test_type: Optional[str], tokens: List[str], pattern) -> str:
        """Calculate confidence score for a test match."""
        base_confidence = 0.5  # Start at 0.5 (MODERATE)
        
        # Get aliases from pattern (handle both database model and fallback object)
        aliases = getattr(pattern, 'aliases', [])
        
        # Boost for well-structured test names
        for pattern_str in self.HIGH_CONFIDENCE_PATTERNS:
            if re.match(pattern_str, test_name.lower()):
                base_confidence += 0.2
                break
        
        # Boost for integration/e2e tests (more business-focused)
        if test_type in ["integration", "e2e"]:
            base_confidence += 0.15
        elif test_type == "api":
            base_confidence += 0.1
        
        # Boost for direct alias match (not partial)
        if any(alias in test_name.lower() for alias in aliases):
            base_confidence += 0.15
        
        # Boost for multiple matching tokens
        matching_tokens = sum(1 for token in tokens if any(alias in token for alias in aliases))
        if matching_tokens >= 2:
            base_confidence += 0.1
        
        # Boost for descriptive test names (longer names are more specific)
        if len(test_name) > 30:
            base_confidence += 0.05
        
        # Cap at 1.0
        base_confidence = min(base_confidence, 1.0)
        
        # Convert to confidence level
        if base_confidence >= 0.8:
            return "HIGH"
        elif base_confidence >= 0.5:
            return "MODERATE"
        else:
            return "LOW"
    
    def _find_matched_alias(self, test_name: str, aliases: List[str]) -> Optional[str]:
        """Find the specific alias that matched the test name."""
        test_name_lower = test_name.lower()
        
        for alias in aliases:
            if alias.lower() in test_name_lower:
                return alias
        
        return None
    
    def get_behavior_counts(self, evidences: List[TestBehaviorEvidence]) -> Dict[str, int]:
        """Get count of evidences by behavior."""
        counts = {}
        
        for evidence in evidences:
            if evidence.behavior not in counts:
                counts[evidence.behavior] = 0
            counts[evidence.behavior] += 1
        
        return counts
    
    def get_high_confidence_evidences(self, evidences: List[TestBehaviorEvidence]) -> List[TestBehaviorEvidence]:
        """Filter evidences to only high confidence ones."""
        return [e for e in evidences if e.confidence == "HIGH"]
    
    def get_evidences_by_test_type(self, evidences: List[TestBehaviorEvidence]) -> Dict[str, List[TestBehaviorEvidence]]:
        """Group evidences by test type."""
        grouped = {}
        
        for evidence in evidences:
            test_type = evidence.test_type or "unknown"
            if test_type not in grouped:
                grouped[test_type] = []
            grouped[test_type].append(evidence)
        
        return grouped
