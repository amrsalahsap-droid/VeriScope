"""Source Normalization Service for parsing raw AC text into structured segments."""
import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid

from app.models.source_segment import SourceSegment, SegmentDisposition


class SourceNormalizationService:
    """Normalizes raw source text into structured segments with dispositions."""
    
    # Section header patterns (must be at start of line)
    SECTION_PATTERNS = {
        "acceptance_criteria": [
            r"^acceptance\s*criteria\s*[:\n]?",
            r"^ac\s*[:\n]?",
            r"^requirements\s*[:\n]?",
            r"^criteria\s*[:\n]?",
        ],
        "security_notes": [
            r"^security\s*notes?\s*[:\n]?",
            r"^security\s*considerations?\s*[:\n]?",
        ],
        "test_data": [
            r"^test\s*data\s*[:\n]?",
            r"^examples?\s*[:\n]?",
            r"^suggested\s*valid\s*test\s*data\s*[:\n]?",
            r"^suggested\s*invalid\s*test\s*data\s*[:\n]?",
        ],
    }
    
    # List item patterns
    LIST_ITEM_PATTERNS = [
        r"^\s*(\d+)\.\s+(.+)",  # Numbered list: 1. item
        r"^\s*[-*]\s+(.+)",  # Bullet list: - item or * item
        r"^\s*o\s+(.+)",  # Circle list: o item
    ]
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service with optional database session."""
        self.db = db
    
    def normalize_source_text(
        self,
        raw_text: str,
        repository_id: str,
        pull_request_id: str,
        raw_artifact_id: str = None
    ) -> Tuple[List[SourceSegment], List[Dict[str, Any]]]:
        """Parse raw source text into structured segments.
        
        Returns:
            Tuple of (segments, diagnostics)
        """
        segments = []
        diagnostics = []
        
        if not raw_text or not raw_text.strip():
            diagnostics.append("Empty source text")
            return segments, diagnostics
        
        lines = raw_text.split("\n")
        current_section = "UNKNOWN"
        section_index = 0
        line_number = 0
        
        for line in lines:
            line_number += 1
            stripped = line.strip()
            
            # Check for section headers
            section_changed = False
            for section_name, patterns in self.SECTION_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        current_section = section_name.upper()
                        section_index = 0
                        section_changed = True
                        diagnostics.append(f"Found section: {current_section}")
                        break
                if section_changed:
                    break
            
            if section_changed:
                continue
            
            # Skip empty lines
            if not stripped:
                continue
            
            # Try to match list item patterns
            matched = False
            source_number = None
            
            for pattern in self.LIST_ITEM_PATTERNS:
                match = re.match(pattern, stripped, re.IGNORECASE)
                if match:
                    # Extract source number if present
                    if pattern.startswith(r"^\s*(\d+)"):
                        source_number = int(match.group(1))
                        text_content = match.group(2)
                    else:
                        text_content = match.group(1)
                    
                    # Determine disposition
                    disposition = self._determine_disposition(text_content, current_section)
                    
                    # Create segment
                    segment = SourceSegment(
                        id=uuid.uuid4(),
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        raw_artifact_id=raw_artifact_id,
                        source_section=current_section,
                        source_index=section_index,
                        source_number=source_number,
                        raw_text=text_content,
                        normalized_text=text_content.strip(),
                        disposition=disposition,
                        source_hash=hashlib.md5(text_content.encode()).hexdigest(),
                        line_number=line_number
                    )
                    
                    segments.append(segment)
                    section_index += 1
                    matched = True
                    break
            
            if not matched:
                # Non-list content - could be heading or fragment
                if self._is_heading(stripped):
                    segment = SourceSegment(
                        id=uuid.uuid4(),
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        raw_artifact_id=raw_artifact_id,
                        source_section=current_section,
                        source_index=section_index,
                        source_number=None,
                        raw_text=stripped,
                        normalized_text=stripped.strip(),
                        disposition=SegmentDisposition.HEADING,
                        source_hash=hashlib.md5(stripped.encode()).hexdigest(),
                        line_number=line_number
                    )
                    segments.append(segment)
                elif len(stripped) > 5:  # Only store non-trivial fragments
                    segment = SourceSegment(
                        id=uuid.uuid4(),
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        raw_artifact_id=raw_artifact_id,
                        source_section=current_section,
                        source_index=section_index,
                        source_number=None,
                        raw_text=stripped,
                        normalized_text=stripped.strip(),
                        disposition=SegmentDisposition.FRAGMENT,
                        source_hash=hashlib.md5(stripped.encode()).hexdigest(),
                        line_number=line_number
                    )
                    segments.append(segment)
        
        diagnostics.append(f"Parsed {len(segments)} segments from {len(lines)} lines")
        return segments, diagnostics
    
    def _determine_disposition(self, text: str, section: str) -> str:
        """Determine the disposition of a text segment based on content and section."""
        text_lower = text.lower()
        section_upper = section.upper()
        
        # Section-based disposition
        if section_upper == "SECURITY_NOTES":
            return SegmentDisposition.SECURITY_NOTE
        elif section_upper == "TEST_DATA":
            # Check if it's a label or actual data
            if self._is_test_data_label(text_lower):
                return SegmentDisposition.TEST_DATA_LABEL
            else:
                return SegmentDisposition.TEST_DATA
        
        # Content-based disposition for Acceptance Criteria section
        if section_upper == "ACCEPTANCE_CRITERIA":
            # Check for security note patterns
            if self._is_security_note(text_lower):
                return SegmentDisposition.SECURITY_NOTE
            # Check for architecture note patterns
            elif self._is_architecture_note(text_lower):
                return SegmentDisposition.ARCHITECTURE_NOTE
            # Check for implementation note patterns
            elif self._is_implementation_note(text_lower):
                return SegmentDisposition.IMPLEMENTATION_NOTE
            # Default to acceptance criterion
            else:
                return SegmentDisposition.ACCEPTANCE_CRITERION
        
        return SegmentDisposition.UNKNOWN
    
    def _is_heading(self, text: str) -> bool:
        """Check if text is a heading."""
        text_stripped = text.strip()
        return (
            text_stripped.isupper() or
            text_stripped.endswith(':') or
            re.match(r'^#+\s+', text_stripped) or
            re.match(r'^(acceptance criteria|requirements|criteria|test data|examples|notes|security notes)', text_stripped, re.IGNORECASE)
        )
    
    def _is_test_data_label(self, text: str) -> bool:
        """Check if text is a test data label."""
        patterns = [
            r'^suggested valid test data$',
            r'^suggested invalid test data$',
            r'^test data$',
            r'^examples?$',
            r'^sample data$',
            r'^valid inputs?$',
            r'^invalid inputs?$',
        ]
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _is_security_note(self, text: str) -> bool:
        """Check if text is a security note."""
        patterns = [
            r'password policy must be shared or aligned',
            r'backend is source of truth',
            r'frontend ux only provides',
            r'password changes must be atomic',
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _is_architecture_note(self, text: str) -> bool:
        """Check if text is an architecture note."""
        patterns = [
            r'backend.*source of truth',
            r'frontend.*only provides',
            r'ui.*only provides',
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _is_implementation_note(self, text: str) -> bool:
        """Check if text is an implementation note."""
        patterns = [
            r'^implementation',
            r'^technical',
            r'^internal',
        ]
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def persist_segments(self, segments: List[SourceSegment]) -> List[SourceSegment]:
        """Persist segments to database."""
        if not self.db:
            raise ValueError("Database session required for persistence")
        
        persisted = []
        for segment in segments:
            self.db.add(segment)
            persisted.append(segment)
        
        self.db.commit()
        return persisted
    
    def validate_source_integrity(self, segments: List[SourceSegment]) -> List[Dict[str, Any]]:
        """Validate source integrity and return validation diagnostics.
        
        Returns:
            List of validation diagnostics with severity and message
        """
        diagnostics = []
        
        # Check for SOURCE_SECTION_MISMATCH
        for segment in segments:
            if segment.disposition == SegmentDisposition.ACCEPTANCE_CRITERION:
                if segment.source_section and segment.source_section.upper() != "ACCEPTANCE_CRITERIA":
                    diagnostics.append({
                        "severity": "ERROR",
                        "code": "SOURCE_SECTION_MISMATCH",
                        "message": f"AC segment in wrong section: {segment.source_section}",
                        "segment_id": str(segment.id),
                        "source_number": segment.source_number
                    })
        
        # Check for SECURITY_NOTE_HAS_AC_NUMBER
        for segment in segments:
            if segment.disposition == SegmentDisposition.SECURITY_NOTE and segment.source_number is not None:
                diagnostics.append({
                    "severity": "ERROR",
                    "code": "SECURITY_NOTE_HAS_AC_NUMBER",
                    "message": f"Security note has source number: {segment.source_number}",
                    "segment_id": str(segment.id),
                    "source_number": segment.source_number
                })
        
        # Check for SOURCE_AC_NUMBER_GAP
        ac_segments = [s for s in segments if s.disposition == SegmentDisposition.ACCEPTANCE_CRITERION and s.source_number is not None]
        if ac_segments:
            source_numbers = sorted([s.source_number for s in ac_segments])
            expected_numbers = list(range(1, max(source_numbers) + 1))
            missing_numbers = set(expected_numbers) - set(source_numbers)
            if missing_numbers:
                diagnostics.append({
                    "severity": "WARNING",
                    "code": "SOURCE_AC_NUMBER_GAP",
                    "message": f"Missing AC numbers: {sorted(missing_numbers)}",
                    "missing_numbers": sorted(missing_numbers)
                })
        
        return diagnostics
