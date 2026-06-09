"""
ExistingTestToScenarioMapper
============================
Maps existing JUnit tests to scenario intents to understand what scenarios are already covered.
"""

import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum


class ConfidenceLevel(Enum):
    """Confidence levels for test-to-intent mapping."""
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


@dataclass
class ExistingTestScenarioCoverage:
    """Represents coverage of a scenario intent by an existing test."""
    test_identifier: str
    scenario_intent_key: str
    confidence: ConfidenceLevel
    evidence_terms: List[str]
    source: str = "TEST_NAME_MAPPING"


class ExistingTestToScenarioMapper:
    """
    Maps existing JUnit tests to scenario intents using test name analysis.
    
    Uses normalized tokens, domain synonyms, and pattern matching to determine
    which scenario intents are already covered by existing tests.
    """
    
    # Domain vocabulary and synonyms
    DOMAIN_SYNONYMS = {
        "auth": "authentication",
        "login": "authentication",
        "signin": "authentication",
        "signup": "registration",
        "sign-up": "registration",
        "register": "registration",
        "password": "authentication",
        "token": "authentication",
        "session": "authentication",
        "billing": "payment",
        "payment": "payment",
        "checkout": "payment",
        "order": "payment",
        "invoice": "payment",
        "subscription": "payment",
        "profile": "account",
        "account": "account",
        "user": "account",
        "settings": "account",
        "admin": "admin",
        "notification": "notification",
        "alert": "notification",
        "message": "notification",
    }
    
    # Layer detection patterns
    LAYER_PATTERNS = {
        "api": ["api", "endpoint", "controller", "handler", "rest"],
        "ui": ["ui", "page", "screen", "component", "view", "form"],
        "integration": ["integration", "e2e", "end-to-end", "flow", "journey"],
        "unit": ["unit", "service", "logic", "validator", "util"],
    }
    
    # Case type detection patterns
    CASE_TYPE_PATTERNS = {
        "positive": ["should", "can", "allows", "accepts", "valid", "correct", "successful"],
        "negative": ["reject", "refuse", "deny", "invalid", "incorrect", "fail", "error", "unauthorized"],
        "edge": ["edge", "boundary", "limit", "empty", "null", "maximum", "minimum"],
    }
    
    # Behavior extraction patterns
    BEHAVIOR_PATTERNS = {
        "expired": ["expired", "expire", "timeout", "timed out"],
        "valid": ["valid", "correct", "proper", "authorized"],
        "invalid": ["invalid", "incorrect", "wrong", "malformed"],
        "reset": ["reset", "change", "update", "modify"],
        "create": ["create", "add", "new", "insert"],
        "delete": ["delete", "remove", "destroy"],
        "attach": ["attach", "link", "connect", "associate"],
        "detach": ["detach", "unlink", "disconnect", "dissociate"],
    }
    
    @classmethod
    def normalize_test_name(cls, test_name: str) -> str:
        """
        Normalize test name for consistent matching.
        
        - Convert to lowercase
        - Remove underscores and replace with spaces
        - Remove common test prefixes (test_, should_, it_)
        """
        normalized = test_name.lower()
        # Remove common test prefixes
        for prefix in ["test_", "should_", "it_", "when_", "given_"]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        # Replace underscores with spaces
        normalized = normalized.replace("_", " ")
        # Replace hyphens with spaces
        normalized = normalized.replace("-", " ")
        # Remove extra spaces
        normalized = " ".join(normalized.split())
        return normalized
    
    @classmethod
    def extract_domain(cls, test_name: str, suite_name: Optional[str] = None) -> str:
        """
        Extract domain from test name and suite name.
        
        Returns normalized domain name or "general" if not detected.
        """
        normalized = cls.normalize_test_name(test_name)
        if suite_name:
            normalized_suite = cls.normalize_test_name(suite_name)
            normalized = f"{normalized_suite} {normalized}"
        
        tokens = normalized.split()
        
        # Check for domain synonyms
        for token in tokens:
            if token in cls.DOMAIN_SYNONYMS:
                return cls.DOMAIN_SYNONYMS[token]
        
        return "general"
    
    @classmethod
    def extract_feature(cls, test_name: str, suite_name: Optional[str] = None) -> str:
        """
        Extract feature from test name and suite name.
        
        Returns normalized feature name or "general" if not detected.
        """
        normalized = cls.normalize_test_name(test_name)
        if suite_name:
            normalized_suite = cls.normalize_test_name(suite_name)
            normalized = f"{normalized_suite} {normalized}"
        
        tokens = normalized.split()
        
        # Common feature keywords
        feature_keywords = [
            "token", "password", "email", "username", "profile", "settings",
            "order", "cart", "checkout", "payment", "subscription",
            "notification", "message", "alert", "report", "dashboard"
        ]
        
        for token in tokens:
            if token in feature_keywords:
                return token
        
        return "general"
    
    @classmethod
    def extract_behavior(cls, test_name: str) -> str:
        """
        Extract behavior from test name.
        
        Returns normalized behavior string.
        """
        normalized = cls.normalize_test_name(test_name)
        tokens = normalized.split()
        
        # Check for behavior patterns
        for behavior, patterns in cls.BEHAVIOR_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    # Find the full behavior phrase
                    behavior_tokens = []
                    found_pattern = False
                    for token in tokens:
                        if token in patterns:
                            found_pattern = True
                        if found_pattern:
                            behavior_tokens.append(token)
                    if behavior_tokens:
                        return "-".join(behavior_tokens)
        
        # Fallback: use the action verb
        if "should" in tokens:
            idx = tokens.index("should")
            if idx + 1 < len(tokens):
                return tokens[idx + 1]
        
        return "general"
    
    @classmethod
    def extract_layer(cls, test_name: str, suite_name: Optional[str] = None) -> str:
        """
        Extract layer from test name and suite name.
        
        Returns one of: api, ui, integration, unit
        """
        normalized = cls.normalize_test_name(test_name)
        if suite_name:
            normalized_suite = cls.normalize_test_name(suite_name)
            normalized = f"{normalized_suite} {normalized}"
        
        for layer, patterns in cls.LAYER_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    return layer
        
        # Default to unit if no layer detected
        return "unit"
    
    @classmethod
    def extract_case_type(cls, test_name: str) -> str:
        """
        Extract case type from test name.
        
        Returns one of: positive, negative, edge
        """
        normalized = cls.normalize_test_name(test_name)
        
        for case_type, patterns in cls.CASE_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    return case_type
        
        # Default to positive
        return "positive"
    
    @classmethod
    def generate_canonical_key(
        cls,
        domain: str,
        feature: str,
        behavior: str,
        layer: str,
        case_type: str
    ) -> str:
        """
        Generate canonical key for scenario intent.
        
        Format: domain.feature.behavior.layer.case_type
        """
        normalized_parts = [
            domain.lower().strip().replace(" ", "-"),
            feature.lower().strip().replace(" ", "-"),
            behavior.lower().strip().replace(" ", "-"),
            layer.lower().strip(),
            case_type.lower().strip()
        ]
        return ".".join(normalized_parts)
    
    @classmethod
    def calculate_confidence(
        cls,
        test_name: str,
        domain: str,
        feature: str,
        behavior: str,
        evidence_terms: List[str]
    ) -> ConfidenceLevel:
        """
        Calculate confidence level for the mapping.
        
        Rules:
        - HIGH: Strong token matches, specific behavior detected
        - MODERATE: Generic matches, some evidence
        - LOW: Very generic, weak evidence
        """
        normalized = cls.normalize_test_name(test_name)
        tokens = set(normalized.split())
        evidence_set = set(evidence_terms)
        
        # Count how many evidence terms are in the test name
        matched_terms = len(tokens.intersection(evidence_set))
        
        # HIGH confidence: strong specific matches
        if (
            domain != "general" and
            feature != "general" and
            behavior != "general" and
            matched_terms >= 3
        ):
            return ConfidenceLevel.HIGH
        
        # MODERATE confidence: some matches but generic
        if (
            (domain != "general" or feature != "general") and
            matched_terms >= 2
        ):
            return ConfidenceLevel.MODERATE
        
        # LOW confidence: very generic
        return ConfidenceLevel.LOW
    
    @classmethod
    def map_test_to_intent(
        cls,
        test_identifier: str,
        test_name: str,
        suite_name: Optional[str] = None,
        class_name: Optional[str] = None
    ) -> ExistingTestScenarioCoverage:
        """
        Map a single test to a scenario intent.
        
        Args:
            test_identifier: Unique test identifier (stable_identity)
            test_name: The test method name
            suite_name: The test suite name (optional)
            class_name: The test class name (optional)
        
        Returns:
            ExistingTestScenarioCoverage with mapping details
        """
        # Extract components
        domain = cls.extract_domain(test_name, suite_name)
        feature = cls.extract_feature(test_name, suite_name)
        behavior = cls.extract_behavior(test_name)
        layer = cls.extract_layer(test_name, suite_name)
        case_type = cls.extract_case_type(test_name)
        
        # Generate canonical key
        canonical_key = cls.generate_canonical_key(domain, feature, behavior, layer, case_type)
        
        # Collect evidence terms
        evidence_terms = []
        normalized = cls.normalize_test_name(test_name)
        if suite_name:
            normalized_suite = cls.normalize_test_name(suite_name)
            evidence_terms.extend(normalized_suite.split())
        evidence_terms.extend(normalized.split())
        if class_name:
            normalized_class = cls.normalize_test_name(class_name)
            evidence_terms.extend(normalized_class.split())
        
        # Calculate confidence
        confidence = cls.calculate_confidence(test_name, domain, feature, behavior, evidence_terms)
        
        return ExistingTestScenarioCoverage(
            test_identifier=test_identifier,
            scenario_intent_key=canonical_key,
            confidence=confidence,
            evidence_terms=list(set(evidence_terms)),
            source="TEST_NAME_MAPPING"
        )
    
    @classmethod
    def map_tests_to_intents(
        cls,
        test_results: List[Dict[str, Any]],
        project_understanding: Optional[Dict[str, Any]] = None,
        domain_vocab: Optional[Dict[str, Any]] = None
    ) -> List[ExistingTestScenarioCoverage]:
        """
        Map multiple tests to scenario intents.
        
        Args:
            test_results: List of test result dictionaries with keys:
                - test_identifier
                - test_name
                - suite_name (optional)
                - class_name (optional)
            project_understanding: ProjectUnderstandingSnapshot (optional, for future enhancement)
            domain_vocab: DomainVocabulary (optional, for future enhancement)
        
        Returns:
            List of ExistingTestScenarioCoverage objects
        """
        coverages = []
        
        for test in test_results:
            test_identifier = test.get("test_identifier") or test.get("stable_identity")
            test_name = test.get("test_name") or test.get("name")
            suite_name = test.get("suite_name")
            class_name = test.get("class_name")
            
            if not test_identifier or not test_name:
                continue
            
            coverage = cls.map_test_to_intent(
                test_identifier=test_identifier,
                test_name=test_name,
                suite_name=suite_name,
                class_name=class_name
            )
            coverages.append(coverage)
        
        return coverages
    
    @classmethod
    def get_covered_intent_keys(
        cls,
        coverages: List[ExistingTestScenarioCoverage],
        min_confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    ) -> Set[str]:
        """
        Get set of covered intent keys, filtered by minimum confidence.
        
        Args:
            coverages: List of ExistingTestScenarioCoverage objects
            min_confidence: Minimum confidence level to include
        
        Returns:
            Set of canonical keys for covered intents
        """
        confidence_order = {
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.MODERATE: 2,
            ConfidenceLevel.LOW: 1
        }
        
        min_score = confidence_order.get(min_confidence, 2)
        
        covered_keys = set()
        for coverage in coverages:
            if confidence_order.get(coverage.confidence, 0) >= min_score:
                covered_keys.add(coverage.scenario_intent_key)
        
        return covered_keys
