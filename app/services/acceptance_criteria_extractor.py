"""Acceptance Criteria Extractor service.

Extracts acceptance criteria from PR descriptions or linked story text,
recognizing various formats and classifying criterion types.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid

from app.models.acceptance_criterion import AcceptanceCriterion


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
        r"acceptance\s*criteria\s*[:\n]",
        r"ac\s*[:\n]",
        r"requirements\s*[:\n]",
        r"criteria\s*[:\n]",
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
    
    def extract_from_pr_description(
        self,
        pr_description: str,
        repository_id: str,
        pull_request_id: str,
        source: str = "PR_DESCRIPTION"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Extract acceptance criteria from a PR description.
        
        Returns:
            Tuple of (criteria_list, evidence_gap)
            - criteria_list: List of extracted criteria dictionaries
            - evidence_gap: Dictionary with evidence gap info if no AC found
        """
        if not pr_description or not pr_description.strip():
            return [], self._create_evidence_gap("Empty PR description")
        
        # Try to find AC section
        ac_section = self._find_ac_section(pr_description)
        
        if not ac_section:
            # Try to extract from entire description if no explicit section
            ac_section = pr_description
        
        # Extract criteria from the section
        criteria = self._extract_criteria_from_text(ac_section, source)
        
        if not criteria:
            return [], self._create_evidence_gap("No acceptance criteria found in PR description")
        
        # Normalize and deduplicate
        criteria = self._normalize_and_deduplicate(criteria)
        
        # Classify criterion types
        for criterion in criteria:
            criterion["criterion_type"] = self._classify_criterion_type(criterion["text"])
        
        return criteria, {}
    
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
        
        criteria = self._extract_criteria_from_text(story_text, source)
        
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
    
    def _extract_criteria_from_text(self, text: str, source: str) -> List[Dict[str, Any]]:
        """Extract individual criteria from text."""
        criteria = []
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
                            criteria.append({
                                "text": criterion_text,
                                "source": source,
                                "confidence": self._calculate_confidence(criterion_text),
                                "evidence_excerpt": line,
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
                                criteria.append({
                                    "text": criterion_text,
                                    "source": source,
                                    "confidence": self._calculate_confidence(criterion_text),
                                    "evidence_excerpt": line,
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
                criteria.append({
                    "text": criterion_text,
                    "source": source,
                    "confidence": self._calculate_confidence(criterion_text),
                    "evidence_excerpt": line,
                })
        
        return criteria
    
    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence score for a criterion (0.0 to 1.0)."""
        text_lower = text.lower()
        
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
        
        # Add normalized key to each criterion
        for key, criterion in normalized.items():
            criterion["normalized_key"] = key
        
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
    ) -> List[AcceptanceCriterion]:
        """Persist extracted criteria to the database."""
        if isinstance(repository_id, str):
            repository_id = uuid.UUID(repository_id)
        if isinstance(pull_request_id, str):
            pull_request_id = uuid.UUID(pull_request_id)

        if not self.db:
            self.db = db
        
        persisted = []
        
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
                db.commit()
                persisted.append(existing)
                continue
            
            # Create new criterion
            criterion = AcceptanceCriterion(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                text=criterion_data["text"],
                normalized_key=criterion_data["normalized_key"],
                criterion_type=criterion_data.get("criterion_type", "UNKNOWN"),
                source=criterion_data["source"],
                confidence=criterion_data["confidence"],
                evidence_excerpt=criterion_data.get("evidence_excerpt"),
            )
            db.add(criterion)
            db.commit()
            persisted.append(criterion)
        
        return persisted
    
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
        criteria = self._extract_criteria_from_text(acceptance_criteria_text, source)
        
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
