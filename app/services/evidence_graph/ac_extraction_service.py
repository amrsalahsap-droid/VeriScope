"""AC Extraction Service - Extracts clean, testable acceptance criteria.

This service extracts only real, testable acceptance criteria from text,
excluding fragments, test data, notes, and implementation statements.
"""
import re
import uuid
import textwrap
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.services.regression_evidence_classifier import RequirementNode, ScenarioSignature
from app.services.regression_evidence_classifier import ScenarioSignatureGenerator


class SegmentDisposition(Enum):
    """Disposition for each extracted segment before RequirementNode creation."""
    PARENT_REQUIREMENT = "PARENT_REQUIREMENT"
    CHILD_RULE = "CHILD_RULE"
    TEST_DATA = "TEST_DATA"
    SECURITY_NOTE = "SECURITY_NOTE"
    IMPLEMENTATION_NOTE = "IMPLEMENTATION_NOTE"
    DUPLICATE = "DUPLICATE"
    FRAGMENT_NOISE = "FRAGMENT_NOISE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass
class SegmentAudit:
    """Audit trail for each extracted segment."""
    raw_text: str
    normalized_text: str
    disposition: SegmentDisposition
    parent_candidate_key: Optional[str] = None
    readable_reason: str = ""
    confidence: float = 0.0
    source_section: str = "AC"
    linked_parent_id: Optional[str] = None


class ExtractionCategory(Enum):
    """Categories for extracted text segments (legacy, kept for compatibility)."""
    REAL_REQUIREMENT = "REAL_REQUIREMENT"
    PARENT_REQUIREMENT = "PARENT_REQUIREMENT"
    CHILD_RULE = "CHILD_RULE"
    CHILD_DETAIL = "CHILD_DETAIL"
    TEST_DATA = "TEST_DATA"
    NOTE = "NOTE"
    SECURITY_NOTE = "SECURITY_NOTE"
    HEADING = "HEADING"
    FRAGMENT = "FRAGMENT"
    DUPLICATE = "DUPLICATE"
    IMPLEMENTATION_DETAIL = "IMPLEMENTATION_DETAIL"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass
class ExtractionAudit:
    """Audit trail for AC extraction."""
    raw_segments_count: int = 0
    real_requirements_count: int = 0
    parent_requirements_count: int = 0
    excluded_fragments_count: int = 0
    test_data_count: int = 0
    excluded_test_data_count: int = 0
    note_count: int = 0
    excluded_notes_count: int = 0
    security_note_count: int = 0
    duplicate_count: int = 0
    child_detail_count: int = 0
    child_rules_count: int = 0
    implementation_detail_count: int = 0
    heading_count: int = 0
    out_of_scope_count: int = 0
    extracted_requirement_nodes: List[Dict[str, Any]] = field(default_factory=list)
    excluded_segments: List[Dict[str, Any]] = field(default_factory=list)
    parent_child_merges: List[Dict[str, Any]] = field(default_factory=list)
    segment_audits: List[SegmentAudit] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of AC extraction."""
    requirement_nodes: List[RequirementNode] = field(default_factory=list)
    excluded_fragments: List[Dict[str, Any]] = field(default_factory=list)
    readable_id_counter: int = 0
    audit: ExtractionAudit = field(default_factory=ExtractionAudit)


class ACExtractionService:
    """Service for extracting clean, testable acceptance criteria."""

    # List item patterns
    LIST_ITEM_PATTERNS = [
        r'^\s*[\-\*]\s+(.+)$',
        r'^\s*\d+\.\s+(.+)$',
        r'^\s*[a-zA-Z]\)\s+(.+)$',
        r'^\s*\[\s*[xX\s]\s*\]\s+(.+)$',
    ]

    # Should/Must patterns
    SHOULD_MUST_PATTERNS = [
        r'\b(should|must|shall)\s+.+',
    ]

    # Fragment patterns to exclude
    FRAGMENT_PATTERNS = [
        r'^must be (rejected|shown|accepted|displayed|hidden|validated|verified|checked|ensured|returned|blocked|allowed|prevented|enforced|required|supported|provided|implemented)$',
        r'^should be (rejected|shown|accepted|displayed|hidden|validated|verified|checked|ensured|returned|blocked|allowed|prevented|enforced|required|supported|provided|implemented)$',
        r'^must (not|not be)$',
        r'^should (not|not be)$',
        r'^continue (successfully|with error|with failure)$',
        r'^\s*[\-\*]+\s*$',
        r'^is (mandatory|required|the source of truth)$',
        r'^are (mandatory|required|consistent)$',
    ]

    # Note/comment patterns to exclude
    NOTE_PATTERNS = [
        r'^(note|comment|todo|fixme|hack|example|test data|suggested valid test data|suggested invalid test data)',
        r'^(implementation|technical|internal|backend|frontend)\s+(note|comment|validation)',
        r'\[.*\]$',
        r'^security notes?$',
        r'^backend validation is the source of truth$',
        r'^frontend validation improves ux$',
        r'^ui validation improves ux$',
        r'^\s*[\-\*]\s+backend validation is the source of truth$',
        r'^\s*[\-\*]\s+frontend validation improves ux',
        r'.*\bpassword policy must be shared or aligned\b.*',
        r'.*\bpassword policy should be shared or aligned\b.*',
        r'.*\bbackend is source of truth\b.*',
        r'.*\bfrontend ux only provides\b.*',
        r'.*\bpassword changes must be atomic\b.*',
    ]

    # Test data patterns to exclude
    TEST_DATA_PATTERNS = [
        r'^[a-z]+\d+$',
        r'^[a-zA-Z0-9]{8,}$',
        r'^[\w\-\.]+@[\w\-]+\.[a-z]{2,}$',
        r'^\d{4}-\d{2}-\d{2}$',
        r'^https?://',
        r'^suggested valid test data$',
        r'^suggested invalid test data$',
        r'^test data$',
        r'^examples?$',
        r'^sample data$',
        r'^valid inputs?$',
        r'^invalid inputs?$',
        r'^test cases?$',
    ]

    # Implementation statement patterns to exclude
    IMPLEMENTATION_PATTERNS = [
        r'^backend validation is the source of truth$',
        r'^ui validation is the source of truth$',
        r'^validation is the source of truth$',
        r'^backend validation is mandatory$',
        r'^ui validation is mandatory$',
    ]

    # Heading patterns to exclude
    HEADING_PATTERNS = [
        r'^(acceptance criteria|requirements|criteria|test data|examples|notes|given|when|then|suggested|backend|frontend|implementation|technical|security|security notes)\s*[:\d]*$',
        r'^(test data|notes|examples|sample data|valid inputs|invalid inputs|test cases)$',
    ]

    # Single-word outcome fragments to exclude
    SINGLE_WORD_OUTCOMES = [
        'rejected', 'accepted', 'shown', 'hidden', 'displayed', 'validated', 'verified',
        'returned', 'blocked', 'allowed', 'prevented', 'enforced', 'required', 'supported',
        'provided', 'implemented', 'consistent', 'mandatory'
    ]

    # Subject/flow keywords
    SUBJECT_KEYWORDS = [
        'user', 'system', 'application', 'app', 'api', 'ui', 'interface',
        'password', 'login', 'signup', 'sign-up', 'reset', 'update',
        'form', 'validation', 'endpoint', 'service', 'component',
        'token', 'session', 'authentication', 'authorization',
        'whitespace', 'space', 'leading', 'trailing', 'empty',
        'confirmation', 'mismatch'
    ]

    # Behavior/outcome keywords
    BEHAVIOR_KEYWORDS = [
        'must', 'should', 'shall', 'will', 'can', 'cannot', 'must not', 'should not',
        'reject', 'accept', 'validate', 'verify', 'check', 'ensure', 'confirm',
        'display', 'show', 'hide', 'render', 'return', 'send', 'receive',
        'allow', 'enable', 'disable', 'prevent', 'block', 'permit',
        'enforce', 'require', 'support', 'provide', 'implement',
        'continue', 'fail', 'succeed', 'complete', 'process', 'handle',
        'are', 'is', 'be', 'not', 'consistent', 'broken', 'works', 'still',
        'update', 'reset', 'bypass'
    ]

    # Outcome keywords
    OUTCOME_KEYWORDS = [
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

    def __init__(self):
        self.signature_generator = ScenarioSignatureGenerator()

    def extract_acceptance_criteria(
        self,
        text: str,
        context: Dict[str, Any] = None
    ) -> ExtractionResult:
        """Extract acceptance criteria from text using the 8-step pipeline.

        Args:
            text: Input text to extract from
            context: Optional context for signature generation

        Returns:
            ExtractionResult with requirement nodes and excluded fragments
        """
        # Deduct indentation from triple-quoted multiline strings or indented text blocks
        text = textwrap.dedent(text)

        if context is None:
            context = {}

        result = ExtractionResult()
        
        # Step 1: Segment raw AC text
        lines = text.split('\n')
        raw_candidates = []  # List of Tuple[str, str, int, int] (text, section_type, indentation_level, original_number)
        current_candidate = []
        current_section = "AC"  # Default section
        current_indent = 0
        is_bullet = False
        original_ac_number = 0  # Track original AC number from source

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_candidate:
                    raw_candidates.append((" ".join(current_candidate), current_section, current_indent, original_ac_number))
                    current_candidate = []
                continue

            # Check if this is a heading
            is_heading = False
            if True:
                for pattern in self.HEADING_PATTERNS:
                    if re.match(pattern, stripped, re.IGNORECASE):
                        # Transition section type based on heading content
                        heading_lower = stripped.lower()
                        cat = ExtractionCategory.HEADING.value
                        if any(kw in heading_lower for kw in ['test data', 'examples', 'sample data', 'inputs']):
                            current_section = "TEST_DATA"
                        elif any(kw in heading_lower for kw in ['security notes', 'security']):
                            current_section = "SECURITY_NOTE"
                            cat = ExtractionCategory.SECURITY_NOTE.value
                        elif any(kw in heading_lower for kw in ['notes', 'comments', 'todo']):
                            current_section = "NOTE"
                            cat = ExtractionCategory.NOTE.value
                        elif any(kw in heading_lower for kw in ['acceptance criteria', 'requirements', 'criteria', 'given when then']):
                            current_section = "AC"
                        else:
                            current_section = "OUT_OF_SCOPE"
                        
                        # Store heading as excluded fragment
                        result.excluded_fragments.append({
                            "text": stripped,
                            "reason": "Heading marker",
                            "category": cat,
                            "source": "acceptance_criteria",
                            "confidence": 0.0
                        })
                        is_heading = True
                        if current_candidate:
                            raw_candidates.append((" ".join(current_candidate), current_section, current_indent, original_ac_number))
                            current_candidate = []
                        break

            if is_heading:
                continue

            # Check list item pattern to start a new candidate
            matched = False
            for pattern in self.LIST_ITEM_PATTERNS:
                match = re.match(pattern, stripped, re.IGNORECASE)
                if match:
                    if current_candidate:
                        raw_candidates.append((" ".join(current_candidate), current_section, current_indent, original_ac_number))
                    # Calculate indentation level (number of leading spaces)
                    leading_spaces = len(line) - len(line.lstrip())
                    current_indent = leading_spaces
                    current_candidate = [match.group(1)]
                    is_bullet = True
                    matched = True
                    # Increment original AC number for numbered items
                    if re.match(r'^\s*\d+\.\s+', stripped):
                        original_ac_number += 1
                    break

            if not matched:
                # Try Should/Must patterns
                for pattern in self.SHOULD_MUST_PATTERNS:
                    match = re.search(pattern, stripped, re.IGNORECASE)
                    if match:
                        if current_candidate:
                            raw_candidates.append((" ".join(current_candidate), current_section, current_indent, original_ac_number))
                        current_indent = len(line) - len(line.lstrip())
                        current_candidate = [match.group(0)]
                        is_bullet = False
                        matched = True
                        break

            if not matched:
                if current_candidate and is_bullet:
                    current_candidate.append(stripped)
                else:
                    if current_candidate:
                        raw_candidates.append((" ".join(current_candidate), current_section, current_indent, original_ac_number))
                    current_indent = len(line) - len(line.lstrip())
                    current_candidate = [stripped]
                    is_bullet = False

        if current_candidate:
            raw_candidates.append((" ".join(current_candidate), current_section, current_indent, original_ac_number))

        result.audit.raw_segments_count = len(raw_candidates)

        # Step 2 & 3: Classify each segment with SegmentDisposition before RequirementNode generation
        parent_candidates = []  # List of Tuple[str, float, int] (text, confidence, original_number)
        child_candidates = []
        test_data_candidates = []
        security_notes = []
        implementation_notes = []
        normalized_keys = set()

        for text_val, section_type, indent, original_number in raw_candidates:
            # Classify segment using new disposition logic
            segment_audit = self._classify_segment(text_val, section_type, indent)
            result.audit.segment_audits.append(segment_audit)

            # Map disposition to existing logic for compatibility
            if segment_audit.disposition == SegmentDisposition.PARENT_REQUIREMENT:
                # Duplicate detection
                from app.services.regression_evidence_classifier import RequirementMatcher
                norm_key = RequirementMatcher.normalize_title(text_val)
                if norm_key in normalized_keys:
                    result.excluded_fragments.append({
                        "text": text_val,
                        "reason": "Duplicate requirement",
                        "category": ExtractionCategory.DUPLICATE.value,
                        "source": "acceptance_criteria",
                        "confidence": segment_audit.confidence
                    })
                    result.audit.duplicate_count += 1
                else:
                    normalized_keys.add(norm_key)
                    parent_candidates.append((text_val, segment_audit.confidence, original_number))
            elif segment_audit.disposition == SegmentDisposition.CHILD_RULE:
                child_candidates.append(text_val)
            elif segment_audit.disposition == SegmentDisposition.TEST_DATA:
                test_data_candidates.append(text_val)
                result.excluded_fragments.append({
                    "text": text_val,
                    "reason": segment_audit.readable_reason,
                    "category": ExtractionCategory.TEST_DATA.value,
                    "source": "acceptance_criteria",
                    "confidence": 0.0
                })
            elif segment_audit.disposition == SegmentDisposition.SECURITY_NOTE:
                security_notes.append(text_val)
                result.excluded_fragments.append({
                    "text": text_val,
                    "reason": segment_audit.readable_reason,
                    "category": ExtractionCategory.SECURITY_NOTE.value,
                    "source": "acceptance_criteria",
                    "confidence": 0.0
                })
            elif segment_audit.disposition == SegmentDisposition.IMPLEMENTATION_NOTE:
                implementation_notes.append(text_val)
                result.excluded_fragments.append({
                    "text": text_val,
                    "reason": segment_audit.readable_reason,
                    "category": ExtractionCategory.NOTE.value,
                    "source": "acceptance_criteria",
                    "confidence": 0.0
                })
            else:
                # FRAGMENT_NOISE, DUPLICATE, OUT_OF_SCOPE
                result.excluded_fragments.append({
                    "text": text_val,
                    "reason": segment_audit.readable_reason,
                    "category": segment_audit.disposition.value,
                    "source": "acceptance_criteria",
                    "confidence": segment_audit.confidence
                })

        # Step 3.5: Normalize parent candidates - merge closely related policy fragments
        parent_candidates = self._normalize_parent_candidates(parent_candidates, result)

        # Create RequirementNodes for parent requirements (Step 5: stable ID only for parents)
        for title, confidence, original_number in parent_candidates:
            # Use original source AC number to preserve source fidelity
            # If original_number is 0 (not from numbered source), use counter
            if original_number > 0:
                readable_id = f"AC-{original_number:02d}"
            else:
                result.readable_id_counter += 1
                readable_id = f"AC-{result.readable_id_counter:02d}"

            # Step 6: Generate scenario signature (only for parents and child rules)
            signature = self.signature_generator.generate_signature(
                title,
                context=context
            )

            req_node = RequirementNode(
                requirement_id=str(uuid.uuid4()),
                readable_id=readable_id,
                title=title,
                flow=signature.flow,
                action=signature.action,
                condition=signature.condition,
                expected_outcome=signature.expected_outcome,
                polarity=signature.polarity,
                validation_layer=signature.validation_layer,
                risk_level=self._determine_risk_level(title),
                source="acceptance_criteria",
                is_real_testable_requirement=True,
                scenario_signature=signature,
                node_type="PARENT_REQUIREMENT"
            )
            req_node.match_score = confidence
            result.requirement_nodes.append(req_node)

        # Step 4: Merge child rules, link test data, and attach notes
        self._merge_child_rules(result, child_candidates, context)
        self._link_test_data(result, test_data_candidates)
        self._attach_notes(result, security_notes, implementation_notes)

        # Step 7: Populate extraction audit
        result.audit.real_requirements_count = len(result.requirement_nodes)
        result.audit.parent_requirements_count = len(result.requirement_nodes)
        result.audit.child_rules_count = sum(len(parent.child_rules) for parent in result.requirement_nodes)
        result.audit.child_detail_count = result.audit.child_rules_count
        
        result.audit.test_data_count = sum(1 for f in result.excluded_fragments if f["category"] == "TEST_DATA")
        result.audit.excluded_test_data_count = result.audit.test_data_count
        
        result.audit.note_count = sum(1 for f in result.excluded_fragments if f["category"] in ("NOTE", "SECURITY_NOTE"))
        result.audit.excluded_notes_count = result.audit.note_count
        
        result.audit.excluded_fragments_count = sum(1 for f in result.excluded_fragments if f["category"] in ("FRAGMENT", "FRAGMENT_NOISE"))
        result.audit.heading_count = sum(1 for f in result.excluded_fragments if f["category"] == "HEADING")
        result.audit.out_of_scope_count = sum(1 for f in result.excluded_fragments if f["category"] == "OUT_OF_SCOPE")
        result.audit.implementation_detail_count = sum(1 for f in result.excluded_fragments if f["category"] == "IMPLEMENTATION_DETAIL")

        result.audit.excluded_segments = result.excluded_fragments
        result.audit.extracted_requirement_nodes = [
            {
                "readable_id": node.readable_id,
                "title": node.title,
                "flow": node.flow,
                "action": node.action,
                "expected_outcome": node.expected_outcome,
                "extraction_confidence": node.match_score
            }
            for node in result.requirement_nodes
        ]

        return result

    def _classify_segment(self, text: str, section_type: str, indent: int) -> SegmentAudit:
        """Classify segment using SegmentDisposition before RequirementNode creation.
        
        Returns:
            SegmentAudit with disposition and reasoning
        """
        text_stripped = text.strip()
        text_lower = text_stripped.lower()
        normalized_text = text_stripped
        
        # Check section contexts first
        if section_type == "TEST_DATA":
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.TEST_DATA,
                readable_reason="Test data section content",
                confidence=0.0,
                source_section=section_type
            )
        if section_type in ("NOTE", "SECURITY_NOTE"):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.SECURITY_NOTE if section_type == "SECURITY_NOTE" else SegmentDisposition.IMPLEMENTATION_NOTE,
                readable_reason="Note section content",
                confidence=0.0,
                source_section=section_type
            )
        if section_type == "OUT_OF_SCOPE":
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.OUT_OF_SCOPE,
                readable_reason="Out of scope section content",
                confidence=0.0,
                source_section=section_type
            )

        # Exclude headings
        if (text_stripped.isupper() or
            text_stripped.endswith(':') or
            any(re.match(pattern, text_lower, re.IGNORECASE) for pattern in self.HEADING_PATTERNS)):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Heading or section marker",
                confidence=0.0,
                source_section=section_type
            )

        # Exclude test data labels & values
        for pattern in self.TEST_DATA_PATTERNS:
            if re.match(pattern, text_stripped) or re.match(pattern, text_lower):
                return SegmentAudit(
                    raw_text=text_stripped,
                    normalized_text=normalized_text,
                    disposition=SegmentDisposition.TEST_DATA,
                    readable_reason="Test data value",
                    confidence=0.0,
                    source_section=section_type
                )

        # Exclude notes
        for pattern in self.NOTE_PATTERNS:
            if re.match(pattern, text_lower):
                return SegmentAudit(
                    raw_text=text_stripped,
                    normalized_text=normalized_text,
                    disposition=SegmentDisposition.SECURITY_NOTE if "security" in text_lower else SegmentDisposition.IMPLEMENTATION_NOTE,
                    readable_reason="Note or comment",
                    confidence=0.0,
                    source_section=section_type
                )

        # Exclude empty or very short text
        if len(text_stripped) < 5:
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Too short",
                confidence=0.0,
                source_section=section_type
            )

        word_count = len(text_stripped.split())
        if word_count < 3:
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Too few words",
                confidence=0.0,
                source_section=section_type
            )

        # Exclude fragments
        for pattern in self.FRAGMENT_PATTERNS:
            if re.match(pattern, text_lower):
                return SegmentAudit(
                    raw_text=text_stripped,
                    normalized_text=normalized_text,
                    disposition=SegmentDisposition.FRAGMENT_NOISE,
                    readable_reason="Fragment without context",
                    confidence=0.0,
                    source_section=section_type
                )

        # Exclude numbers only
        if re.match(r'^\d+$', text_stripped):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Just a number",
                confidence=0.0,
                source_section=section_type
            )

        # Exclude special characters only
        if re.match(r'^[^\w\s]+$', text_stripped):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Special characters only",
                confidence=0.0,
                source_section=section_type
            )

        # Exclude single-word outcomes
        if text_lower in self.SINGLE_WORD_OUTCOMES:
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Single-word outcome fragment",
                confidence=0.0,
                source_section=section_type
            )

        # Exclude implementation statements
        for pattern in self.IMPLEMENTATION_PATTERNS:
            if re.match(pattern, text_lower):
                return SegmentAudit(
                    raw_text=text_stripped,
                    normalized_text=normalized_text,
                    disposition=SegmentDisposition.IMPLEMENTATION_NOTE,
                    readable_reason="Implementation statement, not testable requirement",
                    confidence=0.0,
                    source_section=section_type
                )

        # Check for password policy child rules (must include uppercase/lowercase/number/special character)
        if self._is_password_policy_child_rule(text_lower):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.CHILD_RULE,
                readable_reason="Password complexity policy child rule",
                confidence=0.8,
                source_section=section_type
            )

        # Check for child detail/rule patterns or indentation signal
        if self._is_child_detail(text_lower) or indent >= 2:
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.CHILD_RULE,
                readable_reason="Child detail to be merged with parent",
                confidence=0.5,
                source_section=section_type
            )

        # Check for required structure of a PARENT requirement
        has_subject = any(kw in text_lower for kw in self.SUBJECT_KEYWORDS)
        has_behavior = any(kw in text_lower for kw in self.BEHAVIOR_KEYWORDS)
        has_gwt = re.search(r'\b(given|when|then)\b', text_lower, re.IGNORECASE)

        if not (has_subject or has_gwt):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Missing subject/flow",
                confidence=0.0,
                source_section=section_type
            )

        if not (has_behavior or has_gwt):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Missing expected behavior",
                confidence=0.0,
                source_section=section_type
            )

        has_outcome = any(kw in text_lower for kw in self.OUTCOME_KEYWORDS)
        has_complexity_rule = re.search(r'\b(must be at least|must include|must contain|must match)\b', text_lower, re.IGNORECASE)

        if not (has_outcome or has_gwt or has_complexity_rule):
            return SegmentAudit(
                raw_text=text_stripped,
                normalized_text=normalized_text,
                disposition=SegmentDisposition.FRAGMENT_NOISE,
                readable_reason="Missing testable outcome",
                confidence=0.0,
                source_section=section_type
            )

        # If it passed all, it is a valid PARENT_REQUIREMENT
        confidence = self._calculate_confidence(text_lower, has_subject, has_behavior, has_outcome, has_gwt)
        return SegmentAudit(
            raw_text=text_stripped,
            normalized_text=normalized_text,
            disposition=SegmentDisposition.PARENT_REQUIREMENT,
            readable_reason="Valid acceptance criterion",
            confidence=confidence,
            source_section=section_type
        )

    def _is_password_policy_child_rule(self, text: str) -> bool:
        """Check if text is a password policy child rule."""
        child_patterns = [
            r'.*\bmust include\s+(uppercase|lowercase|number|special character)',
            r'.*\bshould include\s+(uppercase|lowercase|number|special character)',
            r'.*\bmust contain\s+(uppercase|lowercase|number|special character)',
            r'.*\bshould contain\s+(uppercase|lowercase|number|special character)',
            r'.*\bmust be at least\s+\d+\s+characters',
            r'.*\bshould be at least\s+\d+\s+characters',
        ]
        for pattern in child_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _normalize_parent_candidates(self, parent_candidates: List[Tuple[str, float, int]], result: ExtractionResult) -> List[Tuple[str, float, int]]:
        """Merge closely related policy fragments into single parent requirements.
        
        This prevents over-splitting of requirements that describe the same policy
        but are expressed as separate numbered items.
        
        NOTE: Disabled for now to preserve all source AC numbers without silent merging.
        Merging should only happen when explicitly required by the user.
        """
        # Return candidates as-is without merging to preserve all source ACs
        return parent_candidates

    def _classify_candidate(self, text: str, section_type: str, indent: int) -> Tuple[ExtractionCategory, float, str]:
        """Classify candidate segment into one of the 9 categories.
        
        Returns:
            Tuple of (category, confidence, exclusion_reason)
        """
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Check section contexts first
        if section_type == "TEST_DATA":
            return ExtractionCategory.TEST_DATA, 0.0, "Test data section content"
        if section_type in ("NOTE", "SECURITY_NOTE"):
            return ExtractionCategory.NOTE, 0.0, "Note section content"
        if section_type == "OUT_OF_SCOPE":
            return ExtractionCategory.OUT_OF_SCOPE, 0.0, "Out of scope section content"

        # Exclude headings
        if (text_stripped.isupper() or
            text_stripped.endswith(':') or
            any(re.match(pattern, text_lower, re.IGNORECASE) for pattern in self.HEADING_PATTERNS)):
            return ExtractionCategory.HEADING, 0.0, "Heading or section marker"

        # Exclude test data labels & values
        for pattern in self.TEST_DATA_PATTERNS:
            if re.match(pattern, text_stripped) or re.match(pattern, text_lower):
                return ExtractionCategory.TEST_DATA, 0.0, "Test data value"

        # Exclude notes (map security notes to NOTE for compatibility with existing tests)
        for pattern in self.NOTE_PATTERNS:
            if re.match(pattern, text_lower):
                return ExtractionCategory.NOTE, 0.0, "Note or comment"

        # Exclude empty or very short text
        if len(text_stripped) < 5:
            return ExtractionCategory.FRAGMENT, 0.0, "Too short"

        word_count = len(text_stripped.split())
        if word_count < 3:
            return ExtractionCategory.FRAGMENT, 0.0, "Too few words"

        # Exclude fragments
        for pattern in self.FRAGMENT_PATTERNS:
            if re.match(pattern, text_lower):
                return ExtractionCategory.FRAGMENT, 0.0, "Fragment without context"

        # Exclude numbers only
        if re.match(r'^\d+$', text_stripped):
            return ExtractionCategory.FRAGMENT, 0.0, "Just a number"

        # Exclude special characters only
        if re.match(r'^[^\w\s]+$', text_stripped):
            return ExtractionCategory.FRAGMENT, 0.0, "Special characters only"

        # Exclude single-word outcomes
        if text_lower in self.SINGLE_WORD_OUTCOMES:
            return ExtractionCategory.FRAGMENT, 0.0, "Single-word outcome fragment"

        # Exclude implementation statements
        for pattern in self.IMPLEMENTATION_PATTERNS:
            if re.match(pattern, text_lower):
                return ExtractionCategory.IMPLEMENTATION_DETAIL, 0.0, "Implementation statement, not testable requirement"

        # Check for child detail/rule patterns or indentation signal
        if self._is_child_detail(text_lower) or indent >= 2:
            return ExtractionCategory.CHILD_DETAIL, 0.5, "Child detail to be merged with parent"

        # Check for required structure of a PARENT requirement
        has_subject = any(kw in text_lower for kw in self.SUBJECT_KEYWORDS)
        has_behavior = any(kw in text_lower for kw in self.BEHAVIOR_KEYWORDS)
        has_gwt = re.search(r'\b(given|when|then)\b', text_lower, re.IGNORECASE)

        if not (has_subject or has_gwt):
            return ExtractionCategory.FRAGMENT, 0.0, "Missing subject/flow"

        if not (has_behavior or has_gwt):
            return ExtractionCategory.FRAGMENT, 0.0, "Missing expected behavior"

        has_outcome = any(kw in text_lower for kw in self.OUTCOME_KEYWORDS)
        has_complexity_rule = re.search(r'\b(must be at least|must include|must contain|must match)\b', text_lower, re.IGNORECASE)

        if not (has_outcome or has_gwt or has_complexity_rule):
            return ExtractionCategory.FRAGMENT, 0.0, "Missing testable outcome"

        # If it passed all, it is a valid PARENT_REQUIREMENT
        confidence = self._calculate_confidence(text_lower, has_subject, has_behavior, has_outcome, has_gwt)
        return ExtractionCategory.PARENT_REQUIREMENT, confidence, "Valid acceptance criterion"

    def _determine_risk_level(self, text: str) -> str:
        """Determine risk level from text."""
        text_lower = text.lower()

        high_risk_keywords = ["security", "auth", "password", "token", "session", "critical", "bypass"]
        if any(kw in text_lower for kw in high_risk_keywords):
            return "HIGH"

        medium_risk_keywords = ["validate", "verify", "check", "ensure", "confirm", "reject", "accept"]
        if any(kw in text_lower for kw in medium_risk_keywords):
            return "MEDIUM"

        return "LOW"

    def _is_child_detail(self, text: str) -> bool:
        """Check if text is a child detail that should be merged with parent."""
        child_patterns = [
            r'.*\bmust include\s+(uppercase|lowercase|number|special character)',
            r'.*\bshould include\s+(uppercase|lowercase|number|special character)',
            r'.*\bmust be at least\s+\d+\s+characters',
            r'.*\bshould be at least\s+\d+\s+characters',
            r'.*\bmust contain\s+(uppercase|lowercase|number|special character)',
            r'.*\bshould contain\s+(uppercase|lowercase|number|special character)',
            # More specific "must match" patterns - only for regex patterns, not confirmation fields
            r'.*\bmust match\s+(the\s+)?pattern\b',
            r'.*\bshould match\s+(the\s+)?pattern\b',
            r'.*\bmust be\s+(greater|less|equal)\s+than',
            r'.*\bshould be\s+(greater|less|equal)\s+than',
        ]

        for pattern in child_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _calculate_confidence(
        self,
        text: str,
        has_subject: bool,
        has_behavior: bool,
        has_outcome: bool,
        has_gwt: bool
    ) -> float:
        """Calculate confidence score for extraction."""
        confidence = 0.0

        if has_gwt:
            confidence += 0.4
        else:
            if has_subject:
                confidence += 0.2
            if has_behavior:
                confidence += 0.2
            if has_outcome:
                confidence += 0.2

        if has_subject and has_behavior and has_outcome:
            confidence += 0.3

        word_count = len(text.split())
        if word_count >= 8:
            confidence += 0.1
        elif word_count >= 5:
            confidence += 0.05

        action_verbs = ['must', 'should', 'shall', 'will', 'reject', 'accept', 'validate', 'verify']
        if any(verb in text for verb in action_verbs):
            confidence += 0.1

        return min(confidence, 1.0)

    def _merge_child_rules(self, result: ExtractionResult, child_texts: List[str], context: Dict[str, Any]):
        """Merge child rules into parent requirements based on similarity and proximity."""
        for text in child_texts:
            best_parent = None
            best_similarity = 0.0

            # Special handling for password complexity child rules
            if self._is_password_policy_child_rule(text.lower()):
                # Find the password complexity policy parent
                for req_node in result.requirement_nodes:
                    if "password complexity policy" in req_node.title.lower():
                        best_parent = req_node
                        best_similarity = 1.0
                        break
            else:
                # Use similarity-based matching for other child rules
                for req_node in result.requirement_nodes:
                    similarity = self._calculate_similarity(text.lower(), req_node.title.lower())
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_parent = req_node

            # Proximity fallback: if no parent matched confidently but parents exist, group under the last parent
            if (not best_parent or best_similarity < 0.3) and result.requirement_nodes:
                best_parent = result.requirement_nodes[-1]
                best_similarity = 0.1

            if best_parent:
                # Generate signature for the child rule
                signature = self.signature_generator.generate_signature(
                    text,
                    context={"flow": best_parent.flow, **context}
                )

                child_node = RequirementNode(
                    requirement_id=str(uuid.uuid4()),
                    readable_id="",  # No readable ID for child rules
                    title=text,
                    flow=signature.flow,
                    action=signature.action,
                    condition=signature.condition,
                    expected_outcome=signature.expected_outcome,
                    polarity=signature.polarity,
                    validation_layer=signature.validation_layer,
                    risk_level=best_parent.risk_level,
                    source="acceptance_criteria",
                    is_real_testable_requirement=True,
                    parent_requirement_id=best_parent.requirement_id,
                    scenario_signature=signature,
                    node_type="CHILD_RULE"
                )
                child_node.match_score = 0.5
                best_parent.child_rules.append(child_node)

                # Record the merge in audit
                result.audit.parent_child_merges.append({
                    "child_text": text,
                    "parent_readable_id": best_parent.readable_id,
                    "parent_title": best_parent.title,
                    "similarity": best_similarity
                })
            else:
                # No parents to merge with - save to excluded fragments
                result.excluded_fragments.append({
                    "text": text,
                    "reason": "Child detail with no parent requirement to merge",
                    "category": ExtractionCategory.CHILD_DETAIL.value,
                    "source": "acceptance_criteria",
                    "confidence": 0.5
                })

    def _link_test_data(self, result: ExtractionResult, test_data_texts: List[str]):
        """Link test data to relevant parent requirements using keyword overlap."""
        for text in test_data_texts:
            best_parent = None
            best_similarity = 0.0

            for req_node in result.requirement_nodes:
                similarity = self._calculate_similarity(text.lower(), req_node.title.lower())
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_parent = req_node

            if not best_parent and result.requirement_nodes:
                best_parent = result.requirement_nodes[-1]  # Proximity fallback

            if best_parent:
                best_parent.linked_test_data.append(text)

    def _attach_notes(self, result: ExtractionResult, security_notes: List[str], implementation_notes: List[str]):
        """Attach security and implementation notes to relevant parent requirements."""
        all_notes = security_notes + implementation_notes
        for text in all_notes:
            best_parent = None
            best_similarity = 0.0

            for req_node in result.requirement_nodes:
                similarity = self._calculate_similarity(text.lower(), req_node.title.lower())
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_parent = req_node

            if not best_parent and result.requirement_nodes:
                best_parent = result.requirement_nodes[-1]  # Proximity fallback

            if best_parent:
                # Add note to parent's diagnostics or a notes field
                if not hasattr(best_parent, 'notes'):
                    best_parent.notes = []
                best_parent.notes.append(text)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using simple word overlap."""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0
