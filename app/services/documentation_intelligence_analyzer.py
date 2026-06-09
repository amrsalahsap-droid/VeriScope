from dataclasses import dataclass
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
import re

from app.services.tokenizer import Tokenizer


@dataclass
class DocumentationBehaviorEvidence:
    """Evidence of a behavior inferred from documentation."""
    behavior: str  # The inferred behavior name
    source_document: str  # The document path or identifier
    excerpt: str  # The relevant excerpt from the document
    confidence: str  # HIGH, MODERATE, LOW
    document_type: Optional[str] = None  # README, ADR, ARCHITECTURE, DOC
    matched_alias: Optional[str] = None  # The specific alias that matched
    line_number: Optional[int] = None  # Line number where evidence was found


class DocumentationIntelligenceAnalyzer:
    """Analyzer to extract behavior evidence from documentation."""
    
    # Document type indicators
    DOCUMENT_TYPE_PATTERNS: Dict[str, str] = {
        r"readme": "README",
        r"adr": "ADR",
        r"architecture": "ARCHITECTURE",
        r"docs/": "DOC",
        r"\.md": "DOC",
        r"\.rst": "DOC",
        r"\.txt": "DOC",
    }
    
    # High confidence documentation patterns (explicit feature descriptions)
    HIGH_CONFIDENCE_PATTERNS: List[str] = [
        r"features:",
        r"capabilities:",
        r"functionality:",
        r"supports",
        r"allows users to",
        r"enables",
        r"provides",
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
    
    def analyze_document(
        self,
        document_path: str,
        content: str,
        document_type: Optional[str] = None
    ) -> List[DocumentationBehaviorEvidence]:
        """Analyze a document and extract behavior evidence."""
        # Infer document type if not provided
        if not document_type:
            document_type = self._infer_document_type(document_path)
        
        # Split content into lines
        lines = content.split('\n')
        
        evidences = []
        
        for line_num, line in enumerate(lines, start=1):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Analyze line for behavior evidence
            evidence = self._analyze_line(line, document_path, document_type, line_num)
            if evidence:
                evidences.append(evidence)
        
        return evidences
    
    def analyze_line(
        self,
        line: str,
        document_path: str,
        document_type: Optional[str] = None,
        line_number: Optional[int] = None
    ) -> Optional[DocumentationBehaviorEvidence]:
        """Analyze a single line of documentation."""
        # Infer document type if not provided
        if not document_type:
            document_type = self._infer_document_type(document_path)
        
        return self._analyze_line(line, document_path, document_type, line_number)
    
    def _analyze_line(
        self,
        line: str,
        document_path: str,
        document_type: str,
        line_number: Optional[int]
    ) -> Optional[DocumentationBehaviorEvidence]:
        """Internal method to analyze a line."""
        # Normalize line
        line_normalized = self._normalize_text(line)
        
        # Tokenize line
        tokens = Tokenizer.tokenize(line_normalized)
        
        # Try to match against pattern library
        pattern_library = self._get_pattern_library()
        matched_pattern = None
        matched_alias = None
        
        if pattern_library:
            matched_pattern = pattern_library.match_pattern(line_normalized)
            if matched_pattern:
                matched_alias = self._find_matched_alias(line_normalized, matched_pattern.aliases)
        
        # Fall back to hardcoded patterns if no database match
        if not matched_pattern:
            for behavior_name, aliases in self.FALLBACK_PATTERNS.items():
                for alias in aliases:
                    if alias in line_normalized:
                        matched_pattern = type('obj', (object,), {
                            'name': behavior_name,
                            'aliases': aliases,
                        })()
                        matched_alias = alias
                        break
                if matched_pattern:
                    break
        
        if matched_pattern:
            confidence = self._calculate_confidence(line, document_type, tokens, matched_pattern)
            
            return DocumentationBehaviorEvidence(
                behavior=matched_pattern.name,
                source_document=document_path,
                excerpt=line.strip(),
                confidence=confidence,
                document_type=document_type,
                matched_alias=matched_alias,
                line_number=line_number,
            )
        
        return None
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for analysis."""
        # Convert to lowercase
        text = text.lower()
        
        # Remove markdown formatting
        text = re.sub(r'[*_`#]+', '', text)
        
        # Remove special characters but keep spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        
        # Strip extra spaces
        text = ' '.join(text.split())
        
        return text
    
    def _infer_document_type(self, document_path: str) -> str:
        """Infer document type from path."""
        document_path_lower = document_path.lower()
        
        for pattern, doc_type in self.DOCUMENT_TYPE_PATTERNS.items():
            if pattern in document_path_lower:
                return doc_type
        
        return "DOC"
    
    def _calculate_confidence(self, line: str, document_type: str, tokens: List[str], pattern) -> str:
        """Calculate confidence score for a documentation match."""
        base_confidence = 0.5  # Start at 0.5 (MODERATE)
        
        # Get aliases from pattern (handle both database model and fallback object)
        aliases = getattr(pattern, 'aliases', [])
        
        # Boost for high confidence patterns (explicit feature descriptions)
        for pattern_str in self.HIGH_CONFIDENCE_PATTERNS:
            if re.search(pattern_str, line.lower()):
                base_confidence += 0.2
                break
        
        # Boost for README files (primary documentation)
        if document_type == "README":
            base_confidence += 0.15
        elif document_type == "ARCHITECTURE":
            base_confidence += 0.1
        
        # Boost for direct alias match (not partial)
        if any(alias in line.lower() for alias in aliases):
            base_confidence += 0.15
        
        # Boost for multiple matching tokens
        matching_tokens = sum(1 for token in tokens if any(alias in token for alias in aliases))
        if matching_tokens >= 2:
            base_confidence += 0.1
        
        # Boost for longer, more descriptive lines
        if len(line) > 50:
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
    
    def _find_matched_alias(self, text: str, aliases: List[str]) -> Optional[str]:
        """Find the specific alias that matched the text."""
        text_lower = text.lower()
        
        for alias in aliases:
            if alias.lower() in text_lower:
                return alias
        
        return None
    
    def get_behavior_counts(self, evidences: List[DocumentationBehaviorEvidence]) -> Dict[str, int]:
        """Get count of evidences by behavior."""
        counts = {}
        
        for evidence in evidences:
            if evidence.behavior not in counts:
                counts[evidence.behavior] = 0
            counts[evidence.behavior] += 1
        
        return counts
    
    def get_high_confidence_evidences(self, evidences: List[DocumentationBehaviorEvidence]) -> List[DocumentationBehaviorEvidence]:
        """Filter evidences to only high confidence ones."""
        return [e for e in evidences if e.confidence == "HIGH"]
    
    def get_evidences_by_document_type(self, evidences: List[DocumentationBehaviorEvidence]) -> Dict[str, List[DocumentationBehaviorEvidence]]:
        """Group evidences by document type."""
        grouped = {}
        
        for evidence in evidences:
            doc_type = evidence.document_type or "unknown"
            if doc_type not in grouped:
                grouped[doc_type] = []
            grouped[doc_type].append(evidence)
        
        return grouped
