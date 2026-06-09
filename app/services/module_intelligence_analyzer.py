from dataclasses import dataclass
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
import re

from app.services.tokenizer import Tokenizer


@dataclass
class ModuleBehaviorEvidence:
    """Evidence of a behavior inferred from a module/folder name."""
    behavior: str  # The inferred behavior name
    module: str  # The module or folder name
    confidence: str  # HIGH, MODERATE, LOW
    module_type: Optional[str] = None  # folder, file, service, etc.
    matched_alias: Optional[str] = None  # The specific alias that matched
    normalized_tokens: Optional[List[str]] = None  # Normalized tokens from module name


class ModuleIntelligenceAnalyzer:
    """Analyzer to infer behaviors from folder names, module names, and service names."""
    
    # Module type indicators
    MODULE_TYPE_PATTERNS: Dict[str, str] = {
        r"service": "service",
        r"controller": "controller",
        r"handler": "handler",
        r"middleware": "middleware",
        r"model": "model",
        r"repository": "repository",
        r"dao": "dao",
    }
    
    # High confidence module patterns (well-structured naming)
    HIGH_CONFIDENCE_PATTERNS: List[str] = [
        r"^services/",
        r"^controllers/",
        r"^handlers/",
        r"^modules/",
        r"^features/",
    ]
    
    # Fallback patterns when database is not available
    FALLBACK_PATTERNS: Dict[str, List[str]] = {
        "Password Reset": ["reset-password", "forgot-password", "password-reset", "recovery", "recover-password"],
        "User Registration": ["signup", "sign-up", "register", "registration", "create-account", "join"],
        "Authentication": ["auth", "login", "logout", "token", "session", "jwt", "password", "signin", "log-in"],
        "Billing": ["billing", "subscription", "invoice", "payment", "plan", "pricing", "checkout"],
        "Notifications": ["notification", "email", "sms", "message", "alert", "push"],
        "User Management": ["user", "profile", "account", "settings"],
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
    
    def analyze_module(self, module_name: str, module_type: Optional[str] = None) -> Optional[ModuleBehaviorEvidence]:
        """Analyze a single module/folder name and infer behavior."""
        # Normalize module name
        module_normalized = self._normalize_module_name(module_name)
        
        # Tokenize module name
        tokens = Tokenizer.tokenize(module_normalized)
        
        # Infer module type if not provided
        if not module_type:
            module_type = self._infer_module_type(module_name)
        
        # Try to match against pattern library
        pattern_library = self._get_pattern_library()
        matched_pattern = None
        matched_alias = None
        
        if pattern_library:
            matched_pattern = pattern_library.match_pattern(module_normalized)
            if matched_pattern:
                matched_alias = self._find_matched_alias(module_normalized, matched_pattern.aliases)
        
        # Fall back to hardcoded patterns if no database match
        if not matched_pattern:
            for behavior_name, aliases in self.FALLBACK_PATTERNS.items():
                for alias in aliases:
                    if alias in module_normalized:
                        matched_pattern = type('obj', (object,), {
                            'name': behavior_name,
                            'aliases': aliases,
                        })()
                        matched_alias = alias
                        break
                if matched_pattern:
                    break
        
        if matched_pattern:
            confidence = self._calculate_confidence(module_name, module_type, tokens, matched_pattern)
            
            return ModuleBehaviorEvidence(
                behavior=matched_pattern.name,
                module=module_name,
                confidence=confidence,
                module_type=module_type,
                matched_alias=matched_alias,
                normalized_tokens=tokens,
            )
        
        return None
    
    def analyze_modules(self, module_names: List[str]) -> List[ModuleBehaviorEvidence]:
        """Analyze multiple module names and return behavior evidence."""
        evidences = []
        
        for module_name in module_names:
            evidence = self.analyze_module(module_name)
            if evidence:
                evidences.append(evidence)
        
        return evidences
    
    def _normalize_module_name(self, module_name: str) -> str:
        """Normalize a module name for analysis."""
        # Convert to lowercase
        module_name = module_name.lower()
        
        # Remove trailing slashes
        module_name = module_name.rstrip('/')
        
        # Replace slashes and hyphens with spaces
        module_name = re.sub(r'[\/\-]', ' ', module_name)
        
        # Remove underscores
        module_name = re.sub(r'_', ' ', module_name)
        
        # Remove special characters
        module_name = re.sub(r'[^a-z0-9\s]', '', module_name)
        
        # Strip extra spaces
        module_name = ' '.join(module_name.split())
        
        return module_name
    
    def _infer_module_type(self, module_name: str) -> Optional[str]:
        """Infer module type from module name or path."""
        module_name_lower = module_name.lower()
        
        for pattern, module_type in self.MODULE_TYPE_PATTERNS.items():
            if pattern in module_name_lower:
                return module_type
        
        # Check if it's a folder (contains slash)
        if '/' in module_name or '\\' in module_name:
            return "folder"
        
        return "file"
    
    def _calculate_confidence(self, module_name: str, module_type: Optional[str], tokens: List[str], pattern) -> str:
        """Calculate confidence score for a module match."""
        base_confidence = 0.5  # Start at 0.5 (MODERATE)
        
        # Get aliases from pattern (handle both database model and fallback object)
        aliases = getattr(pattern, 'aliases', [])
        
        # Boost for well-structured module paths
        for pattern_str in self.HIGH_CONFIDENCE_PATTERNS:
            if re.match(pattern_str, module_name.lower()):
                base_confidence += 0.2
                break
        
        # Boost for specific module types (services, controllers are more indicative)
        if module_type in ["service", "controller", "handler"]:
            base_confidence += 0.15
        elif module_type == "middleware":
            base_confidence += 0.1
        
        # Boost for direct alias match (not partial)
        if any(alias in module_name.lower() for alias in aliases):
            base_confidence += 0.15
        
        # Boost for folder-level matches (more structural)
        if module_type == "folder":
            base_confidence += 0.1
        
        # Boost for multiple matching tokens
        matching_tokens = sum(1 for token in tokens if any(alias in token for alias in aliases))
        if matching_tokens >= 2:
            base_confidence += 0.1
        
        # Boost for short, focused module names (more specific)
        if len(module_name) < 50:
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
    
    def _find_matched_alias(self, module_name: str, aliases: List[str]) -> Optional[str]:
        """Find the specific alias that matched the module name."""
        module_name_lower = module_name.lower()
        
        for alias in aliases:
            if alias.lower() in module_name_lower:
                return alias
        
        return None
    
    def get_behavior_counts(self, evidences: List[ModuleBehaviorEvidence]) -> Dict[str, int]:
        """Get count of evidences by behavior."""
        counts = {}
        
        for evidence in evidences:
            if evidence.behavior not in counts:
                counts[evidence.behavior] = 0
            counts[evidence.behavior] += 1
        
        return counts
    
    def get_high_confidence_evidences(self, evidences: List[ModuleBehaviorEvidence]) -> List[ModuleBehaviorEvidence]:
        """Filter evidences to only high confidence ones."""
        return [e for e in evidences if e.confidence == "HIGH"]
    
    def get_evidences_by_module_type(self, evidences: List[ModuleBehaviorEvidence]) -> Dict[str, List[ModuleBehaviorEvidence]]:
        """Group evidences by module type."""
        grouped = {}
        
        for evidence in evidences:
            module_type = evidence.module_type or "unknown"
            if module_type not in grouped:
                grouped[module_type] = []
            grouped[module_type].append(evidence)
        
        return grouped
