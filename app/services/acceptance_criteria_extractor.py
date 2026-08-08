"""Acceptance Criteria Extractor service.

Extracts acceptance criteria from PR descriptions or linked story text,
recognizing various formats and classifying criterion types.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid

from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.source_segment import SourceSegment, SegmentDisposition
from app.services.source_normalization_service import SourceNormalizationService


class AcceptanceCriteriaExtractor:
    """Extracts and classifies acceptance criteria from text sources."""
    
    # Criterion type keywords for classification
    TYPE_KEYWORDS = {
        "FUNCTIONAL": [
            "feature", "functionality", "user can", "system should", "user must",
            "allow", "enable", "support", "provide", "implement"
        ],
        "VALIDATION": [
            "validate", "verify", "check", "ensure", "confirm", "assert",
            "must be", "should be", "cannot be", "must not"
        ],
        "SECURITY": [
            "security", "auth", "authentication", "authorization", "permission",
            "access", "token", "password", "encrypt", "secure", "protect"
        ],
        "UI": [
            "ui", "interface", "display", "show", "hide", "render", "view",
            "page", "screen", "button", "form", "input", "modal", "dialog"
        ],
        "API": [
            "api", "endpoint", "request", "response", "json", "http", "rest",
            "graphql", "webhook", "service", "call", "invoke"
        ],
        "INTEGRATION": [
            "integration", "external", "third-party", "service", "provider",
            "connect", "sync", "push", "pull", "webhook", "callback"
        ],
        "PERFORMANCE": [
            "performance", "fast", "slow", "latency", "response time", "load",
            "scale", "throughput", "optimize", "cache", "efficient"
        ],
        "DATABASE": [
            "database", "db", "sql", "query", "table", "record", "store",
            "persist", "save", "delete", "update", "index", "migration"
        ],
    }
    
    # Pattern for recognizing AC sections
    AC_SECTION_PATTERNS = [
        r"acceptance\s*criteria\s*[:\n]?",
        r"ac\s*[:\n]?",
        r"requirements\s*[:\n]?",
        r"criteria\s*[:\n]?",
        r"given.*when.*then",
    ]
    
    # Section header patterns for business requirement parsing.
    # All patterns are anchored (^) and require a colon so they only match
    # dedicated section headers, not content lines.
    SECTION_PATTERNS = {
        "business_change": [
            r"^business change\s*:",
            r"^business summary\s*:",
            r"^change summary\s*:",
        ],
        "affected_journeys": [
            r"^affected journeys\s*:",
            r"^affected users\s*:",
            r"^affected flows\s*:",
        ],
        "acceptance_criteria": [
            r"^acceptance criteria\s*:",
            r"^acceptance criterion\s*:",
        ],
        "invalid_test_data": [
            r"^invalid test data\s*(?:examples?)?\s*:",
            r"^negative test data\s*(?:examples?)?\s*:",
            r"^bad test data\s*(?:examples?)?\s*:",
        ],
        "valid_test_data": [
            r"^valid test data\s*(?:examples?)?\s*:",
            r"^positive test data\s*(?:examples?)?\s*:",
        ],
        "security_notes": [
            r"^security notes?\s*:",
        ],
        "risk_notes": [
            r"^risk notes?\s*:",
        ],
        "integration_notes": [
            r"^integration notes?\s*:",
            r"^api notes?\s*:",
        ],
        "out_of_scope": [
            r"^out of scope\s*:",
            r"^not in scope\s*:",
        ],
        "notes": [
            r"^notes?\s*:",
            r"^assumptions?\s*:",
        ],
    }
    
    # Pattern for recognizing list items
    LIST_ITEM_PATTERNS = [
        r"^\s*[-*]\s+(.+)",  # - item or * item
        r"^\s*\d+\.\s+(.+)",  # 1. item
        r"^\s*\[\s*[x\s]\s*\]\s+(.+)",  # [x] item or [ ] item
        r"^\s*o\s+(.+)",  # o item
    ]
    
    # Pattern for recognizing Should/Must statements
    SHOULD_MUST_PATTERNS = [
        r"(should|must|shall)\s+(.+)",
        r"(user|system|app|application)\s+(should|must|shall)\s+(.+)",
    ]
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the extractor with optional database session."""
        self.db = db
        self.normalization_service = SourceNormalizationService(db) if db else None
    
    def extract_from_pr_description(
        self,
        pr_description: str,
        repository_id: str,
        pull_request_id: str,
        source: str = "PR_DESCRIPTION",
        use_source_normalization: bool = True
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Extract acceptance criteria from a PR description.
        
        Returns:
            Tuple of (criteria_list, evidence_gap)
            - criteria_list: List of extracted criteria dictionaries
            - evidence_gap: Dictionary with evidence gap info if no AC found
        """
        if not pr_description or not pr_description.strip():
            return [], self._create_evidence_gap("Empty PR description")
        
        # Use source normalization if enabled and service is available
        if use_source_normalization and self.normalization_service:
            return self._extract_with_normalization(
                pr_description, repository_id, pull_request_id, source
            )
        
        # Legacy extraction (fallback)
        # Try to find AC section
        ac_section = self._find_ac_section(pr_description)
        
        if not ac_section:
            # Try to extract from entire description if no explicit section
            ac_section = pr_description
        
        # Extract criteria from the section
        criteria, excluded_fragments = self._extract_criteria_from_text(ac_section, source)
        
        if not criteria:
            return [], self._create_evidence_gap("No acceptance criteria found in PR description")
        
        # Normalize and deduplicate
        criteria = self._normalize_and_deduplicate(criteria)
        
        # Classify criterion types
        for criterion in criteria:
            criterion["criterion_type"] = self._classify_criterion_type(criterion["text"])
        
        return criteria, {}
    
    def _extract_with_normalization(
        self,
        raw_text: str,
        repository_id: str,
        pull_request_id: str,
        source: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Extract using source normalization service.
        
        Returns:
            Tuple of (criteria_list, diagnostics)
        """
        # Parse source text into segments
        segments, diagnostics = self.normalization_service.normalize_source_text(
            raw_text, repository_id, pull_request_id
        )
        
        # Validate source integrity
        validation_diagnostics = self.normalization_service.validate_source_integrity(segments)
        diagnostics.extend(validation_diagnostics)
        
        # Persist segments if db is available
        if self.db:
            self.normalization_service.persist_segments(segments)
        
        # Extract only ACCEPTANCE_CRITERION disposition segments
        ac_segments = [s for s in segments if s.disposition == SegmentDisposition.ACCEPTANCE_CRITERION]
        
        if not ac_segments:
            return [], self._create_evidence_gap("No acceptance criteria found after normalization")
        
        # Convert segments to criteria format
        criteria = []
        for segment in ac_segments:
            criteria.append({
                "text": segment.normalized_text,
                "source": source,
                "confidence": 0.8,  # Higher confidence for normalized extraction
                "evidence_excerpt": segment.raw_text,
                "source_section": segment.source_section,
                "source_number": segment.source_number,
                "source_hash": segment.source_hash,
            })
        
        # Classify criterion types
        for criterion in criteria:
            criterion["criterion_type"] = self._classify_criterion_type(criterion["text"])
        
        return criteria, {"diagnostics": diagnostics}
    
    def extract_from_linked_story(
        self,
        story_text: str,
        repository_id: str,
        pull_request_id: str,
        source: str = "LINKED_STORY"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Extract acceptance criteria from a linked story text."""
        if not story_text or not story_text.strip():
            return [], self._create_evidence_gap("Empty story text")
        
        criteria, excluded_fragments = self._extract_criteria_from_text(story_text, source)
        
        if not criteria:
            return [], self._create_evidence_gap("No acceptance criteria found in linked story")
        
        # Normalize and deduplicate
        criteria = self._normalize_and_deduplicate(criteria)
        
        # Classify criterion types
        for criterion in criteria:
            criterion["criterion_type"] = self._classify_criterion_type(criterion["text"])
        
        return criteria, {}
    
    def _find_ac_section(self, text: str) -> Optional[str]:
        """Find the acceptance criteria section in text."""
        text_lower = text.lower()
        
        for pattern in self.AC_SECTION_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if match:
                # Return text from match to end or next major section
                start = match.start()
                # Find next major section (##, ###, etc.)
                end_match = re.search(r"\n\s*#{1,3}\s+", text[start+50:])
                if end_match:
                    end = start + 50 + end_match.start()
                    return text[start:end]
                else:
                    return text[start:]
        
        return None
    
    def _extract_criteria_from_text(self, text: str, source: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract individual criteria from text.
        
        Returns:
            Tuple of (criteria_list, excluded_fragments)
            - criteria_list: List of valid acceptance criteria
            - excluded_fragments: List of excluded text fragments with reasons
        """
        criteria = []
        excluded_fragments = []
        lines = text.split("\n")
        
        # If there are no AC section headers in the text, assume the entire text is the AC section
        has_ac_header = False
        for pattern in self.AC_SECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                has_ac_header = True
                break
        
        in_ac_section = not has_ac_header
        current_criterion = []
        current_source_number = None
        # Compiled inline; also used by resolver via _AC_LABEL_RE
        _AC_PREFIX_RE = re.compile(r'^[Aa][Cc][-\s]?0*(\d+)[:\s]\s*(.+)', re.DOTALL)
        
        for line in lines:
            stripped = line.strip()
            
            # Check if this line starts an AC section
            if not in_ac_section:
                for pattern in self.AC_SECTION_PATTERNS:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        in_ac_section = True
                        break
                if not in_ac_section:
                    continue
            
            # Check if we're leaving the AC section
            # Stop at major headers OR section markers that indicate non-AC content
            if in_ac_section:
                should_break = False
                if re.match(r"^\s*#{1,3}\s+", stripped):
                    should_break = True
                else:
                    # Stop at common section markers that follow AC sections
                    section_end_patterns = [
                        r"invalid test data",
                        r"valid test data",
                        r"test data",
                        r"examples?",
                        r"sample data",
                        r"security notes?",
                        r"out of scope",
                        r"notes?",
                        r"assumptions",
                        r"dependencies"
                    ]
                    for pattern in section_end_patterns:
                        if re.search(pattern, stripped, re.IGNORECASE):
                            should_break = True
                            break
                if should_break:
                    break
            
            # Try to match list item patterns
            matched = False
            for pattern in self.LIST_ITEM_PATTERNS:
                match = re.match(pattern, stripped, re.IGNORECASE)
                if match:
                    # Save previous criterion if exists
                    if current_criterion:
                        criterion_text = " ".join(current_criterion).strip()
                        if criterion_text:
                            # Validate the criterion
                            is_valid, reason = self._is_valid_acceptance_criterion(criterion_text)
                            if is_valid:
                                criteria.append({
                                    "text": criterion_text,
                                    "source": source,
                                    "confidence": self._calculate_confidence(criterion_text),
                                    "evidence_excerpt": line,
                                    "source_number": current_source_number,
                                })
                            else:
                                excluded_fragments.append({
                                    "text": criterion_text,
                                    "reason": reason,
                                    "source": source
                                })
                        current_criterion = []
                        current_source_number = None
                    
                    # Start new criterion — detect AC-NN: prefix and strip it
                    raw_item = match.group(1)
                    ac_prefix_match = _AC_PREFIX_RE.match(raw_item)
                    if ac_prefix_match:
                        current_source_number = int(ac_prefix_match.group(1))
                        raw_item = ac_prefix_match.group(2).strip()
                    else:
                        current_source_number = None
                    current_criterion.append(raw_item)
                    matched = True
                    break
            
            if not matched:
                # Try Should/Must patterns
                for pattern in self.SHOULD_MUST_PATTERNS:
                    match = re.search(pattern, stripped, re.IGNORECASE)
                    if match:
                        # Save previous criterion if exists
                        if current_criterion:
                            criterion_text = " ".join(current_criterion).strip()
                            if criterion_text:
                                # Validate the criterion
                                is_valid, reason = self._is_valid_acceptance_criterion(criterion_text)
                                if is_valid:
                                    criteria.append({
                                        "text": criterion_text,
                                        "source": source,
                                        "confidence": self._calculate_confidence(criterion_text),
                                        "evidence_excerpt": line,
                                    })
                                else:
                                    excluded_fragments.append({
                                        "text": criterion_text,
                                        "reason": reason,
                                        "source": source
                                    })
                            current_criterion = []
                        
                        # Start new criterion
                        current_criterion.append(match.group(0))
                        matched = True
                        break
            
            if not matched and current_criterion:
                # Continuation of current criterion
                current_criterion.append(stripped)
        
        # Save last criterion
        if current_criterion:
            criterion_text = " ".join(current_criterion).strip()
            if criterion_text:
                # Validate the criterion
                is_valid, reason = self._is_valid_acceptance_criterion(criterion_text)
                if is_valid:
                    criteria.append({
                        "text": criterion_text,
                        "source": source,
                        "confidence": self._calculate_confidence(criterion_text),
                        "evidence_excerpt": line,
                        "source_number": current_source_number,
                    })
                else:
                    excluded_fragments.append({
                        "text": criterion_text,
                        "reason": reason,
                        "source": source
                    })
        
        return criteria, excluded_fragments
    
    def _is_valid_acceptance_criterion(self, text: str) -> Tuple[bool, str]:
        """Validate if text is a real, testable acceptance criterion.
        
        Returns:
            Tuple of (is_valid, reason)
        
        A valid AC must have:
        - subject/flow (what is being tested)
        - expected behavior (what should happen)
        - testable outcome (verifiable result)
        
        Excludes:
        - examples only
        - test data values
        - notes
        - headings
        - fragments
        - repeated clauses
        - incomplete phrases
        - implementation comments
        """
        text_lower = text.strip().lower()
        text_stripped = text.strip()
        
        # Exclude empty or very short text
        if len(text_stripped) < 5:
            return False, "Too short"
        
        word_count = len(text_stripped.split())
        if word_count < 3:
            return False, "Too few words"
        
        # Exclude headings (all caps, ends with colon, or typical heading patterns)
        if (text_stripped.isupper() or 
            text_stripped.endswith(':') or 
            re.match(r'^(acceptance criteria|requirements|criteria|test data|examples|notes|given|when|then|suggested|backend|frontend|implementation|technical)\s*[:\d]*$', text_lower, re.IGNORECASE)):
            return False, "Heading or section marker"
        
        # Exclude test data patterns (values like "Password123", "short1", etc.)
        test_data_patterns = [
            r'^[a-z]+\d+$',  # short1, test2, etc.
            r'^[a-zA-Z0-9]{8,}$',  # Password-like strings
            r'^[\w\-\.]+@[\w\-]+\.[a-z]{2,}$',  # Email addresses
            r'^\d{4}-\d{2}-\d{2}$',  # Dates
            r'^https?://',  # URLs
        ]
        for pattern in test_data_patterns:
            if re.match(pattern, text_stripped):
                return False, "Test data value"
        
        # Exclude fragments that are just clauses without context
        fragment_patterns = [
            r'^must be (rejected|shown|accepted|displayed|hidden|validated|verified|checked|ensured|returned|blocked|allowed|prevented|enforced|required|supported|provided|implemented)$',
            r'^should be (rejected|shown|accepted|displayed|hidden|validated|verified|checked|ensured|returned|blocked|allowed|prevented|enforced|required|supported|provided|implemented)$',
            r'^must (not|not be)$',
            r'^should (not|not be)$',
            r'^continue (successfully|with error|with failure)$',
            r'^\s*[\-\*]+\s*$',  # Empty list markers
            r'^is (mandatory|required|the source of truth)$',
            r'^are (mandatory|required|consistent)$',
        ]
        for pattern in fragment_patterns:
            if re.match(pattern, text_lower):
                return False, "Fragment without context"
        
        # Exclude notes and meta-comments
        note_patterns = [
            r'^(note|comment|todo|fixme|hack|example|test data|suggested valid test data|suggested invalid test data)',
            r'^(implementation|technical|internal|backend|frontend)\s+(note|comment|validation)',
            r'^\[.*\]$',  # Bracketed notes like [TODO], [NOTE]
            r'^security notes?$',
            r'^backend validation is the source of truth$',
        ]
        for pattern in note_patterns:
            if re.match(pattern, text_lower):
                return False, "Note or comment"
        
        # Exclude lines that are just numbers or identifiers
        if re.match(r'^\d+$', text_stripped):
            return False, "Just a number"
        
        # Exclude lines that are just special characters
        if re.match(r'^[^\w\s]+$', text_stripped):
            return False, "Special characters only"
        
        # Exclude single-word fragments that are just outcomes
        single_word_outcomes = ['rejected', 'accepted', 'shown', 'hidden', 'displayed', 'validated', 'verified', 'returned', 'blocked', 'allowed', 'prevented', 'enforced', 'required', 'supported', 'provided', 'implemented', 'consistent', 'mandatory']
        if text_lower in single_word_outcomes:
            return False, "Single-word outcome fragment"
        
        # Exclude test data labels
        test_data_labels = [
            r'^suggested valid test data$',
            r'^suggested invalid test data$',
            r'^test data$',
            r'^examples?$',
            r'^sample data$',
            r'^valid inputs?$',
            r'^invalid inputs?$',
            r'^test cases?$',
        ]
        for pattern in test_data_labels:
            if re.match(pattern, text_lower):
                return False, "Test data label"
        
        # Exclude generic implementation statements
        implementation_patterns = [
            r'^backend validation is the source of truth$',
            r'^ui validation is the source of truth$',
            r'^validation is the source of truth$',
            r'^backend validation is mandatory$',
            r'^ui validation is mandatory$',
        ]
        for pattern in implementation_patterns:
            if re.match(pattern, text_lower):
                return False, "Implementation statement, not testable requirement"
        
        # Check for required AC structure: must have subject/flow AND behavior
        # Subject/flow indicators
        subject_keywords = [
            'user', 'system', 'application', 'app', 'api', 'ui', 'interface',
            'password', 'login', 'signup', 'sign-up', 'reset', 'update',
            'form', 'validation', 'endpoint', 'service', 'component',
            'token', 'session', 'authentication', 'authorization',
            'whitespace', 'space', 'leading', 'trailing', 'empty',
            'confirmation', 'mismatch'
        ]
        
        # Behavior/outcome indicators
        behavior_keywords = [
            'must', 'should', 'shall', 'will', 'can', 'cannot', 'must not', 'should not',
            'reject', 'accept', 'validate', 'verify', 'check', 'ensure', 'confirm',
            'display', 'show', 'hide', 'render', 'return', 'send', 'receive',
            'allow', 'enable', 'disable', 'prevent', 'block', 'permit',
            'enforce', 'require', 'support', 'provide', 'implement',
            'continue', 'fail', 'succeed', 'complete', 'process', 'handle',
            'are', 'is', 'be', 'not', 'consistent', 'broken', 'works', 'still',
            'update', 'reset', 'bypass'
        ]
        
        has_subject = any(keyword in text_lower for keyword in subject_keywords)
        has_behavior = any(keyword in text_lower for keyword in behavior_keywords)
        
        # Also check for Given-When-Then pattern which is always valid
        has_gwt = re.search(r'\b(given|when|then)\b', text_lower, re.IGNORECASE)
        
        if not (has_subject or has_gwt):
            return False, "Missing subject/flow"
        
        if not (has_behavior or has_gwt):
            return False, "Missing expected behavior"
        
        # Check for testable outcome (result-oriented words)
        outcome_keywords = [
            'reject', 'accept', 'valid', 'invalid', 'success', 'failure', 'error',
            'display', 'show', 'hide', 'return', 'send', 'receive', 'store',
            'enforce', 'require', 'allow', 'prevent', 'block', 'permit',
            'verified', 'validated', 'checked', 'ensured', 'confirmed',
            'consistent', 'match', 'works', 'handled', 'occur', 'update',
            'broken', 'still', 'continue', 'complete', 'process',
            'reset', 'bypass', 'mismatch', 'confirmation',
            'view', 'download', 'access', 'history', 'details', 'method',
            'billing', 'payment', 'invoice'
        ]
        
        has_outcome = any(keyword in text_lower for keyword in outcome_keywords)
        
        # GWT patterns inherently have outcomes
        if not (has_outcome or has_gwt):
            return False, "Missing testable outcome"
        
        return True, "Valid acceptance criterion"
    
    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence score for a criterion (0.0 to 1.0)."""
        text_lower = text.lower()
        
        # First check if it's a valid AC at all
        is_valid, reason = self._is_valid_acceptance_criterion(text)
        if not is_valid:
            return 0.0  # Invalid ACs get zero confidence
        
        # High confidence indicators
        high_confidence_indicators = [
            "must", "shall", "required", "mandatory",
            "given", "when", "then",
            "verify", "validate", "ensure",
        ]
        
        # Low confidence indicators (vague prose)
        low_confidence_indicators = [
            "maybe", "might", "could", "possibly",
            "consider", "think about", "look into",
            "nice to have", "would be good",
        ]
        
        confidence = 0.5  # Base confidence
        
        for indicator in high_confidence_indicators:
            if indicator in text_lower:
                confidence += 0.15
        
        for indicator in low_confidence_indicators:
            if indicator in text_lower:
                confidence -= 0.2
        
        # Length check (too short or too long reduces confidence)
        word_count = len(text.split())
        if word_count < 3:
            confidence -= 0.3
        elif word_count > 50:
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _generate_ac_label(self, index: int, text: str) -> str:
        """Generate a human-readable AC label.
        
        Args:
            index: Sequential index (1-based)
            text: The criterion text
            
        Returns:
            Label like "AC-01 Weak passwords are rejected during sign-up"
        """
        # Truncate text to fit within reasonable length (max ~80 chars for label)
        max_text_length = 60
        truncated_text = text[:max_text_length].strip()
        if len(text) > max_text_length:
            truncated_text = truncated_text.rsplit(' ', 1)[0] + '...'
        
        # Format: AC-NN Text
        return f"AC-{index:02d} {truncated_text}"
    
    def _normalize_and_deduplicate(self, criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize criteria text and remove duplicates."""
        normalized = {}
        
        for criterion in criteria:
            # Normalize text for key
            normalized_text = self._normalize_text(criterion["text"])
            normalized_key = self._generate_normalized_key(normalized_text)
            
            # Keep the one with higher confidence if duplicate
            if normalized_key in normalized:
                if criterion["confidence"] > normalized[normalized_key]["confidence"]:
                    normalized[normalized_key] = criterion
            else:
                normalized[normalized_key] = criterion
        
        # Add normalized key and label to each criterion
        index = 1
        for key, criterion in normalized.items():
            criterion["normalized_key"] = key
            criterion["label"] = self._generate_ac_label(index, criterion["text"])
            index += 1
        
        return list(normalized.values())
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing punctuation
        text = text.strip(".,!?;:")
        return text
    
    def _generate_normalized_key(self, normalized_text: str) -> str:
        """Generate a normalized key for deduplication."""
        # Remove common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        words = [w for w in normalized_text.split() if w not in stop_words]
        return " ".join(words)
    
    def _classify_criterion_type(self, text: str) -> str:
        """Classify the type of acceptance criterion."""
        text_lower = text.lower()
        
        scores = {criterion_type: 0 for criterion_type in self.TYPE_KEYWORDS}
        
        for criterion_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[criterion_type] += 1
        
        # Return type with highest score, or UNKNOWN if no match
        max_score = max(scores.values())
        if max_score == 0:
            return "UNKNOWN"
        
        return max(scores, key=scores.get)
    
    def _create_evidence_gap(self, reason: str) -> Dict[str, Any]:
        """Create an evidence gap dictionary."""
        return {
            "type": "ACCEPTANCE_CRITERIA_MISSING",
            "reason": reason,
            "suggested_action": "Add acceptance criteria to PR description or link to a story with criteria",
        }
    
    def persist_criteria(
        self,
        criteria: List[Dict[str, Any]],
        repository_id: Any,
        pull_request_id: Any,
        db: Session
    ) -> Tuple[List[AcceptanceCriterion], List[Dict[str, Any]]]:
        """Persist extracted criteria to the database.
        
        Returns:
            Tuple of (persisted_criteria, excluded_fragments)
        """
        import re
        import uuid
        from datetime import datetime
        from app.models.requirement_package import RequirementPackage
        from app.models.requirement_group import RequirementGroup
        from app.models.acceptance_criterion import AcceptanceCriterion

        if isinstance(repository_id, str):
            repository_id = uuid.UUID(repository_id)
        if isinstance(pull_request_id, str):
            pull_request_id = uuid.UUID(pull_request_id)

        if not self.db:
            self.db = db
        
        # 1. Retrieve or create RequirementPackage
        pkg = db.query(RequirementPackage).filter(
            RequirementPackage.repository_id == repository_id,
            RequirementPackage.pull_request_id == pull_request_id
        ).first()
        if pkg:
            # Delete existing requirement groups (Acceptance criteria will have FK set to NULL first)
            db.query(RequirementGroup).filter(RequirementGroup.requirement_package_id == pkg.id).delete()
            db.commit()
        else:
            pkg = RequirementPackage(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                source_type="MANUAL_USER_INPUT",
                package_version="1.0.0",
                status="NEEDS_REVIEW",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(pkg)
            db.commit()

        # Helper function to parse hierarchical text
        def parse_hierarchical_text(text: str):
            lines = text.split("\n")
            groups = []
            current_group = {
                "group_title": "General Requirements",
                "group_type": "ENHANCEMENT",
                "ac_lines": []
            }
            
            group_pattern = re.compile(r"^(?:Enhancement|Feature|Bug\s*Fix|Tech\s*Debt|Non-Functional|Security|Group)\s*\d*\s*[:\-]\s*(.*)$", re.IGNORECASE)
            header_pattern = re.compile(r"^#+\s*(.*)$")
            
            for line in lines:
                line_strip = line.strip()
                if not line_strip:
                    continue
                
                g_match = group_pattern.match(line_strip)
                h_match = header_pattern.match(line_strip)
                
                if g_match or h_match:
                    title = g_match.group(1).strip() if g_match else h_match.group(1).strip()
                    g_type = "ENHANCEMENT"
                    lower_line = line_strip.lower()
                    if "bug" in lower_line:
                        g_type = "BUG_FIX"
                    elif "tech" in lower_line or "debt" in lower_line:
                        g_type = "TECH_DEBT"
                    elif "security" in lower_line:
                        g_type = "SECURITY"
                    elif "non-functional" in lower_line or "nfr" in lower_line:
                        g_type = "NON_FUNCTIONAL"
                        
                    if current_group["ac_lines"]:
                        groups.append(current_group)
                    
                    current_group = {
                        "group_title": title or line_strip,
                        "group_type": g_type,
                        "ac_lines": []
                    }
                else:
                    clean_line = re.sub(r"^[\-\*\+]\s*(?:AC\-\d+\s*)?", "", line_strip)
                    clean_line = re.sub(r"^\d+[\.\)]\s*", "", clean_line)
                    clean_line = re.sub(r"^\[[\s[xX]?\]\s*", "", clean_line)
                    clean_line = clean_line.strip()
                    if clean_line and len(clean_line) > 5:
                        current_group["ac_lines"].append(clean_line)
                        
            if current_group["ac_lines"] or not groups:
                groups.append(current_group)
            return groups

        # Helper to make stable slug keys
        def make_slug(val):
            val_clean = re.sub(r"[^a-zA-Z0-9\s\-]", "", val).strip().lower()
            return re.sub(r"[\s\-]+", "-", val_clean)

        # Helper to generate stable group key with full context
        def generate_stable_group_key(repository_id, pull_request_id, group_slug, source_type):
            """Generate stable group key considering repository, PR, and source."""
            return f"repo:{repository_id}:pr:{pull_request_id}:group:{group_slug}:source:{source_type}"

        # Helper to generate stable AC key with full context
        def generate_stable_ac_key(repository_id, pull_request_id, group_slug, ac_slug, source_type):
            """Generate stable AC key considering repository, PR, group, and source."""
            return f"repo:{repository_id}:pr:{pull_request_id}:group:{group_slug}:ac:{ac_slug}:source:{source_type}"

        # Get text source to parse groups
        text_to_parse = ""
        from app.models.business_intent import BusinessIntentOverride
        bio = db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.pull_request_id == pull_request_id,
            BusinessIntentOverride.is_active == True
        ).first()
        if bio and bio.acceptance_criteria:
            text_to_parse = bio.acceptance_criteria
            
        if not text_to_parse:
            from app.models.pull_request import PullRequest
            pr = db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
            if pr and pr.description:
                text_to_parse = pr.description
                
        if not text_to_parse:
            text_to_parse = "\n".join([c.get("evidence_excerpt") or c["text"] for c in criteria])

        parsed_groups = parse_hierarchical_text(text_to_parse)

        # Determine source type for stable keys
        source_type = "MANUAL_USER_INPUT"
        if bio:
            source_type = "BUSINESS_INTENT_OVERRIDE"
        elif criteria and criteria[0].get("source"):
            source_type = criteria[0].get("source")

        # Persist groups and build group dictionary mapping titles to group records
        group_records = {}
        for index, pg in enumerate(parsed_groups, start=1):
            group_slug = make_slug(pg["group_title"])
            stable_group_key = generate_stable_group_key(
                str(repository_id), 
                str(pull_request_id), 
                group_slug, 
                source_type
            )
            
            group_rec = RequirementGroup(
                id=uuid.uuid4(),
                requirement_package_id=pkg.id,
                pull_request_id=pull_request_id,
                group_number=index,
                group_type=pg["group_type"],
                stable_group_key=stable_group_key,
                title=pg["group_title"],
                status="NEEDS_REVIEW"
            )
            db.add(group_rec)
            db.commit()
            group_records[pg["group_title"]] = group_rec

        # Map each criterion to group
        def get_group_for_ac_text(ac_text):
            norm_ac = ac_text.lower().strip()
            for pg in parsed_groups:
                for line in pg["ac_lines"]:
                    if norm_ac in line.lower() or line.lower() in norm_ac:
                        return group_records[pg["group_title"]]
            # Fallback
            if parsed_groups:
                return group_records[parsed_groups[0]["group_title"]]
            return None

        persisted = []
        excluded_fragments = []
        ac_number = 1
        
        for criterion_data in criteria:
            group_rec = get_group_for_ac_text(criterion_data["text"])
            group_id = group_rec.id if group_rec else None
            group_slug = make_slug(group_rec.title) if group_rec else "general"
            # Use normalized text for AC slug to ensure uniqueness within group
            ac_slug = make_slug(criterion_data.get("normalized_text") or criterion_data["text"])
            stable_ac_key = generate_stable_ac_key(
                str(repository_id),
                str(pull_request_id),
                group_slug,
                ac_slug,
                source_type
            )

            existing = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == repository_id,
                AcceptanceCriterion.pull_request_id == pull_request_id,
                AcceptanceCriterion.normalized_key == criterion_data["normalized_key"]
            ).first()
            
            if existing:
                # Update existing criterion details for this PR
                existing.requirement_group_id = group_id
                existing.ac_number = ac_number
                existing.stable_ac_key = stable_ac_key
                existing.source = criterion_data["source"]
                existing.confidence = criterion_data["confidence"]
                existing.evidence_excerpt = criterion_data.get("evidence_excerpt")
                existing.text = criterion_data["text"]
                existing.criterion_type = criterion_data.get("criterion_type", "UNKNOWN")
                existing.label = criterion_data.get("label")
                # Propagate source_number when available (e.g. after AC-NN: prefix detection)
                if criterion_data.get("source_number") is not None:
                    existing.source_number = criterion_data["source_number"]
                existing.status = "NEEDS_REVIEW"
                existing.version = existing.version + 1 if existing.version else 2
                db.commit()
                persisted.append(existing)
            else:
                # Create new criterion
                criterion = AcceptanceCriterion(
                    id=uuid.uuid4(),
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    requirement_group_id=group_id,
                    ac_number=ac_number,
                    stable_ac_key=stable_ac_key,
                    source_section=criterion_data.get("source_section", "ACCEPTANCE_CRITERIA"),
                    source_number=criterion_data.get("source_number"),
                    text=criterion_data["text"],
                    normalized_key=criterion_data["normalized_key"],
                    label=criterion_data.get("label"),
                    criterion_type=criterion_data.get("criterion_type", "UNKNOWN"),
                    source=criterion_data["source"],
                    confidence=criterion_data["confidence"],
                    evidence_excerpt=criterion_data.get("evidence_excerpt"),
                    status="NEEDS_REVIEW",
                    version=1
                )
                db.add(criterion)
                db.commit()
                persisted.append(criterion)
            ac_number += 1
        
        return persisted, excluded_fragments
    
    # Sections that terminate AC collection when encountered
    AC_STOP_SECTIONS = {
        "invalid_test_data", "valid_test_data", "security_notes",
        "risk_notes", "integration_notes", "out_of_scope", "notes",
    }

    # Maps SECTION_PATTERNS key → output dict key
    SECTION_KEY_MAP = {
        "business_change":    "business_change_summary",
        "affected_journeys":  "affected_journeys",
        "acceptance_criteria":"acceptance_criteria",
        "invalid_test_data":  "invalid_test_data_examples",
        "valid_test_data":    "valid_test_data_examples",
        "security_notes":     "security_notes",
        "risk_notes":         "risk_notes",
        "integration_notes":  "integration_notes",
        "out_of_scope":       "out_of_scope_notes",
        "notes":              "out_of_scope_notes",
    }

    # Strict AC line: must begin with a number or AC-id prefix
    AC_LINE_RE = re.compile(r"^\d+[\.\)]\s+|^AC[-\s]?\d+\s*[-:]?\s*", re.IGNORECASE)

    def parse_business_requirements_sections(
        self,
        text: str
    ) -> Dict[str, Any]:
        """Parse business requirements text into strictly separated sections.

        Only lines inside the 'Acceptance Criteria:' section that match the
        AC_LINE_RE pattern (e.g. '1. …', '2) …', 'AC-01 …') become acceptance
        criteria.  Everything else is stored in its own bucket and is NEVER
        counted as an AC.

        Returns dict with keys:
            business_change_summary, affected_journeys, acceptance_criteria,
            invalid_test_data_examples, valid_test_data_examples,
            security_notes, risk_notes, integration_notes, out_of_scope_notes,
            rejected_lines
        """
        import logging
        logger = logging.getLogger(__name__)

        # List-bucket keys
        LIST_BUCKETS = {
            "affected_journeys", "acceptance_criteria",
            "invalid_test_data_examples", "valid_test_data_examples",
            "security_notes", "risk_notes", "integration_notes",
        }

        sections: Dict[str, Any] = {
            "business_change_summary": None,
            "affected_journeys": [],
            "acceptance_criteria": [],
            "invalid_test_data_examples": [],
            "valid_test_data_examples": [],
            "security_notes": [],
            "risk_notes": [],
            "integration_notes": [],
            "out_of_scope_notes": None,
            "rejected_lines": [],
        }

        current_section: str | None = None   # SECTION_PATTERNS key
        in_ac_section: bool = False
        current_list_content: list[str] = []

        def _flush(section_key: str | None, content: list[str]) -> None:
            """Flush accumulated list content into the right bucket."""
            if not section_key or not content:
                return
            dest = self.SECTION_KEY_MAP.get(section_key)
            if dest is None:
                return
            if dest in LIST_BUCKETS:
                existing = sections.get(dest)
                if isinstance(existing, list):
                    existing.extend(content)
            elif dest == "out_of_scope_notes":
                sections["out_of_scope_notes"] = "\n".join(content)
            # business_change_summary is handled inline (after colon)

        for raw in text.split("\n"):
            stripped = raw.strip()
            if not stripped:
                continue

            # ── Detect section header ─────────────────────────────────────────
            new_section: str | None = None
            for sec_name, patterns in self.SECTION_PATTERNS.items():
                for pat in patterns:
                    if re.search(pat, stripped, re.IGNORECASE):
                        new_section = sec_name
                        break
                if new_section:
                    break

            if new_section is not None:
                # Flush previous section's accumulated list content
                _flush(current_section, current_list_content)
                current_list_content = []

                # Transition state
                current_section = new_section
                in_ac_section = (new_section == "acceptance_criteria")
                if new_section in self.AC_STOP_SECTIONS:
                    in_ac_section = False

                # Capture inline value after the colon on the header line
                colon_idx = stripped.find(":")
                if colon_idx != -1:
                    inline = stripped[colon_idx + 1:].strip()
                    if inline:
                        dest = self.SECTION_KEY_MAP.get(new_section)
                        if dest == "business_change_summary":
                            sections["business_change_summary"] = inline
                        elif dest in LIST_BUCKETS:
                            # Inline list item on same line as header (rare)
                            sections[dest].append(inline)  # type: ignore[union-attr]
                continue

            # ── Accumulate content under current section ──────────────────────
            if current_section is None:
                sections["rejected_lines"].append(stripped)
                continue

            dest = self.SECTION_KEY_MAP.get(current_section)

            if dest == "acceptance_criteria":
                if not in_ac_section:
                    sections["rejected_lines"].append(stripped)
                    continue
                # Strict: only numbered / AC-id lines
                if self.AC_LINE_RE.match(stripped):
                    ac_text = self.AC_LINE_RE.sub("", stripped).strip()
                    if len(ac_text) > 3:
                        current_list_content.append(ac_text)
                    else:
                        sections["rejected_lines"].append(stripped)
                else:
                    sections["rejected_lines"].append(stripped)

            elif dest in LIST_BUCKETS:
                clean = re.sub(r"^[\-\*\+]\s+", "", stripped)
                clean = re.sub(r"^\d+[\.\)]\s+", "", clean).strip()
                if clean:
                    current_list_content.append(clean)

            elif dest == "out_of_scope_notes":
                current_list_content.append(stripped)

            else:
                sections["rejected_lines"].append(stripped)

        # Flush final section
        _flush(current_section, current_list_content)

        logger.info(
            "[INPUT_2_SECTION_PARSE] business_change=%s journeys=%d acs=%d "
            "invalid_td=%d valid_td=%d security=%d rejected=%d",
            bool(sections["business_change_summary"]),
            len(sections["affected_journeys"]),
            len(sections["acceptance_criteria"]),
            len(sections["invalid_test_data_examples"]),
            len(sections["valid_test_data_examples"]),
            len(sections["security_notes"]),
            len(sections["rejected_lines"]),
        )

        return sections

    def extract_from_business_intent_override(
        self,
        acceptance_criteria_text: str,
        business_intent_override_id: str,
        repository_id: str,
        source: str = "BUSINESS_INTENT_OVERRIDE"
    ) -> List[Dict[str, Any]]:
        """Extract structured acceptance criteria from business intent override text.
        
        Args:
            acceptance_criteria_text: Raw acceptance criteria text from user input
            business_intent_override_id: ID of the business intent override
            repository_id: Repository ID
            source: Source identifier
            
        Returns:
            List of extracted scenario dictionaries with structured data
        """
        if not acceptance_criteria_text or not acceptance_criteria_text.strip():
            return []
        
        # Extract criteria from the text
        criteria, excluded_fragments = self._extract_criteria_from_text(acceptance_criteria_text, source)
        
        if not criteria:
            return []
        
        # Normalize and deduplicate
        criteria = self._normalize_and_deduplicate(criteria)
        
        # Classify criterion types
        for criterion in criteria:
            criterion["criterion_type"] = self._classify_criterion_type(criterion["text"])
        
        # Convert to structured scenarios
        scenarios = []
        for i, criterion in enumerate(criteria):
            scenario = {
                "scenario_title": f"Scenario {i + 1}",
                "scenario_description": criterion["text"],
                "preconditions": self._extract_preconditions(criterion["text"]),
                "steps": self._extract_steps(criterion["text"]),
                "expected_results": self._extract_expected_results(criterion["text"]),
                "test_data": self._extract_test_data(criterion["text"]),
                "testing_type": self._determine_testing_type(criterion["text"], criterion["criterion_type"]),
                "priority": self._determine_priority(criterion["text"]),
                "automation_candidate": self._is_automation_candidate(criterion["text"]),
                "extraction_confidence": criterion["confidence"],
                "completeness_score": self._assess_completeness(criterion["text"]),
                "source_text": criterion["text"],
                "criterion_type": criterion["criterion_type"]
            }
            scenarios.append(scenario)
        
        return scenarios
    
    def _extract_preconditions(self, text: str) -> List[str]:
        """Extract preconditions from criterion text."""
        preconditions = []
        
        # Look for precondition patterns
        patterns = [
            r"(?:given|when|as a|as an)\s+(.+?)(?:\s+when|\s+then|\s+and|$)",
            r"(?:precondition|前提|前提条件)[:]\s*(.+?)(?:\n|$)",
            r"(?:setup|prepare|before)[:]\s*(.+?)(?:\n|$)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            preconditions.extend([match.strip() for match in matches if match.strip()])
        
        return preconditions[:3]  # Limit to top 3
    
    def _extract_steps(self, text: str) -> List[str]:
        """Extract steps from criterion text."""
        steps = []
        
        # Look for step patterns
        patterns = [
            r"(?:when|then|and)\s+(.+?)(?:\s+when|\s+then|\s+and|$)",
            r"(?:step\s*\d*[:]\s*)(.+?)(?:\n|$)",
            r"(?:\d+\.\s*)(.+?)(?:\n|$)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            steps.extend([match.strip() for match in matches if match.strip()])
        
        return steps[:5]  # Limit to top 5
    
    def _extract_expected_results(self, text: str) -> List[str]:
        """Extract expected results from criterion text."""
        results = []
        
        # Look for result patterns
        patterns = [
            r"(?:then|so that|such that)\s+(.+?)(?:\s+when|\s+then|\s+and|$)",
            r"(?:expect|verify|check|ensure|result)[:]\s*(.+?)(?:\n|$)",
            r"(?:should|must|shall)\s+(.+?)(?:\n|$)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend([match.strip() for match in matches if match.strip()])
        
        return results[:3]  # Limit to top 3
    
    def _extract_test_data(self, text: str) -> Dict[str, Any]:
        """Extract test data from criterion text."""
        test_data = {}
        
        # Look for data patterns
        patterns = [
            r"(?:with|using)\s+(.+?)(?:\s+when|\s+then|\s+and|$)",
            r"(?:data[:]\s*)(.+?)(?:\n|$)",
            r"(?:input[:]\s*)(.+?)(?:\n|$)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if "=" in match:
                    key, value = match.split("=", 1)
                    test_data[key.strip()] = value.strip()
                else:
                    test_data[f"data_{len(test_data) + 1}"] = match.strip()
        
        return test_data
    
    def _determine_testing_type(self, text: str, criterion_type: str) -> str:
        """Determine testing type from text and criterion type."""
        type_mapping = {
            "FUNCTIONAL": "functional",
            "SECURITY": "security",
            "UI": "ui",
            "API": "api",
            "INTEGRATION": "integration",
            "PERFORMANCE": "performance",
            "DATABASE": "database"
        }
        
        return type_mapping.get(criterion_type, "functional")
    
    def _determine_priority(self, text: str) -> str:
        """Determine priority from text."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["must", "critical", "required", "essential"]):
            return "must_run"
        elif any(word in text_lower for word in ["should", "important", "recommended"]):
            return "should_run"
        else:
            return "could_run"
    
    def _is_automation_candidate(self, text: str) -> bool:
        """Determine if criterion is suitable for automation."""
        text_lower = text.lower()
        
        # Non-automatable patterns
        non_automatable = [
            "manual", "visual", "usability", "accessibility", "exploratory",
            "look and feel", "user experience", "manual testing"
        ]
        
        return not any(word in text_lower for word in non_automatable)
    
    def _assess_completeness(self, text: str) -> str:
        """Assess completeness of criterion description."""
        text_lower = text.lower()
        
        # Check for completeness indicators
        has_given = any(word in text_lower for word in ["given", "as a", "as an"])
        has_when = any(word in text_lower for word in ["when", "and"])
        has_then = any(word in text_lower for word in ["then", "so that", "such that"])
        
        if has_given and has_when and has_then:
            return "COMPLETE"
        elif has_when and has_then:
            return "PARTIAL"
        else:
            return "MINIMAL"
