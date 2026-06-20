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
            if in_ac_section and re.match(r"^\s*#{1,3}\s+", stripped):
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
                                })
                            else:
                                excluded_fragments.append({
                                    "text": criterion_text,
                                    "reason": reason,
                                    "source": source
                                })
                        current_criterion = []
                    
                    # Start new criterion
                    current_criterion.append(match.group(1))
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
        if isinstance(repository_id, str):
            repository_id = uuid.UUID(repository_id)
        if isinstance(pull_request_id, str):
            pull_request_id = uuid.UUID(pull_request_id)

        if not self.db:
            self.db = db
        
        persisted = []
        excluded_fragments = []
        
        for criterion_data in criteria:
            # Check if already exists (by repository_id + pull_request_id + normalized key)
            existing = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == repository_id,
                AcceptanceCriterion.pull_request_id == pull_request_id,
                AcceptanceCriterion.normalized_key == criterion_data["normalized_key"]
            ).first()
            
            if existing:
                # Update existing criterion details for this PR
                existing.source = criterion_data["source"]
                existing.confidence = criterion_data["confidence"]
                existing.evidence_excerpt = criterion_data.get("evidence_excerpt")
                existing.text = criterion_data["text"]
                existing.criterion_type = criterion_data.get("criterion_type", "UNKNOWN")
                existing.label = criterion_data.get("label")
                db.commit()
                persisted.append(existing)
                continue
            
            # Create new criterion
            criterion = AcceptanceCriterion(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                source_section=criterion_data.get("source_section", "ACCEPTANCE_CRITERIA"),
                source_number=criterion_data.get("source_number"),
                text=criterion_data["text"],
                normalized_key=criterion_data["normalized_key"],
                label=criterion_data.get("label"),
                criterion_type=criterion_data.get("criterion_type", "UNKNOWN"),
                source=criterion_data["source"],
                confidence=criterion_data["confidence"],
                evidence_excerpt=criterion_data.get("evidence_excerpt"),
            )
            db.add(criterion)
            db.commit()
            persisted.append(criterion)
        
        return persisted, excluded_fragments
    
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
