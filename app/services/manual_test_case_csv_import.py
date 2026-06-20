"""
Manual Test Case CSV Import Service

Allows MVP users to import manual test cases without external tool integration.
Parses CSV files and creates ExternalTestCase records with provider MANUAL_CSV.
"""

import csv
import io
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.external_test_case_detailed import ExternalTestCase
from app.models.repository import Repository
from app.models.behavior import Behavior
from app.models.journey import Journey


logger = logging.getLogger("veriscope.manual_csv_import")


@dataclass
class ImportResult:
    """Result of CSV import operation."""
    total_rows: int
    successful_imports: int
    failed_rows: int
    duplicate_rows: int
    errors: List[Dict[str, Any]]


@dataclass
class ParsedTestCase:
    """Parsed test case from CSV row."""
    title: str
    description: Optional[str]
    priority: Optional[str]
    test_type: Optional[str]
    preconditions: List[str]
    steps: List[Dict[str, str]]
    expected_result: Optional[str]
    tags: List[str]
    linked_work_item_key: Optional[str]
    behavior_name: Optional[str]
    journey_name: Optional[str]
    linked_acceptance_criteria: Optional[str]
    row_number: int


class ManualTestCaseCSVImport:
    """
    Service for importing manual test cases from CSV files.
    
    CSV Format:
    - title (required)
    - description
    - priority
    - test_type
    - preconditions (newline-separated)
    - steps (newline-separated, format: "Step text | Expected result")
    - expected_result
    - tags (comma-separated)
    - linked_work_item_key
    - behavior
    - journey
    """
    
    REQUIRED_COLUMNS = ['title']
    OPTIONAL_COLUMNS = [
        'description', 'priority', 'test_type', 'preconditions',
        'steps', 'expected_result', 'tags', 'linked_work_item_key',
        'behavior', 'journey', 'linked_acceptance_criteria'
    ]
    
    def __init__(self, db: Session):
        """Initialize the CSV import service with database session."""
        self.db = db
    
    def import_csv(
        self,
        repository_id: uuid.UUID,
        csv_content: str,
        workspace_id: uuid.UUID
    ) -> ImportResult:
        """
        Import test cases from CSV content.
        
        Args:
            repository_id: Repository to import test cases into
            csv_content: CSV file content as string
            workspace_id: Workspace ID for the repository
            
        Returns:
            ImportResult with summary of import operation
        """
        result = ImportResult(
            total_rows=0,
            successful_imports=0,
            failed_rows=0,
            duplicate_rows=0,
            errors=[]
        )
        
        try:
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Validate columns
            if not csv_reader.fieldnames:
                result.errors.append({
                    "row": 0,
                    "error": "CSV has no columns"
                })
                return result
            
            missing_required = [col for col in self.REQUIRED_COLUMNS if col not in csv_reader.fieldnames]
            if missing_required:
                result.errors.append({
                    "row": 0,
                    "error": f"Missing required columns: {', '.join(missing_required)}"
                })
                return result
            
            # Parse and import each row
            for row_number, row in enumerate(csv_reader, start=1):
                result.total_rows += 1
                
                try:
                    # Parse test case
                    parsed = self._parse_row(row, row_number)
                    
                    # Validate required fields
                    if not parsed.title:
                        result.errors.append({
                            "row": row_number,
                            "error": "Title is required"
                        })
                        result.failed_rows += 1
                        continue
                    
                    # Check for duplicates
                    if self._is_duplicate(repository_id, parsed.title, parsed.linked_work_item_key):
                        result.duplicate_rows += 1
                        result.errors.append({
                            "row": row_number,
                            "error": f"Duplicate test case: title '{parsed.title}' with linked_work_item_key '{parsed.linked_work_item_key}'"
                        })
                        continue
                    
                    # Resolve behavior and journey
                    behavior_id = self._resolve_behavior(repository_id, parsed.behavior_name)
                    journey_id = self._resolve_journey(repository_id, parsed.journey_name)
                    
                    # Create ExternalTestCase
                    test_case = ExternalTestCase(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        repository_id=repository_id,
                        integration_connection_id=None,  # Manual CSV has no integration connection
                        provider="MANUAL_CSV",
                        external_id=str(uuid.uuid4()),  # Generate unique ID for manual import
                        external_key=None,  # Manual CSV has no external key
                        title=parsed.title,
                        description=parsed.description,
                        preconditions=parsed.preconditions,
                        steps=parsed.steps,
                        expected_result=parsed.expected_result,
                        priority=parsed.priority,
                        test_type=parsed.test_type,
                        automation_status="MANUAL",  # Manual CSV imports are always manual
                        tags=parsed.tags,
                        linked_work_item_keys=[parsed.linked_work_item_key] if parsed.linked_work_item_key else [],
                        behavior_id=behavior_id,
                        journey_id=journey_id,
                        scenario_intent_key=None,
                        url=None,
                        raw_payload={"csv_row": row},
                        last_synced_at=datetime.utcnow(),
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    self.db.add(test_case)
                    
                    # Phase 6.1: Import linked AC mapping if matching AC exists
                    if parsed.linked_acceptance_criteria:
                        from app.models.acceptance_criterion import AcceptanceCriterion
                        from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
                        
                        ac_refs = [ref.strip() for ref in parsed.linked_acceptance_criteria.split(',') if ref.strip()]
                        for ac_ref in ac_refs:
                            ac = None
                            try:
                                ac_uuid = uuid.UUID(ac_ref)
                                ac = self.db.query(AcceptanceCriterion).filter(
                                    AcceptanceCriterion.id == ac_uuid,
                                    AcceptanceCriterion.repository_id == repository_id
                                ).first()
                            except ValueError:
                                pass
                            
                            if not ac:
                                try:
                                    ref_clean = ac_ref.upper().replace("AC-", "").strip()
                                    source_num = int(ref_clean)
                                    ac = self.db.query(AcceptanceCriterion).filter(
                                        AcceptanceCriterion.source_number == source_num,
                                        AcceptanceCriterion.repository_id == repository_id
                                    ).first()
                                except ValueError:
                                    pass
                            
                            if not ac:
                                ac = self.db.query(AcceptanceCriterion).filter(
                                    (AcceptanceCriterion.label == ac_ref) | (AcceptanceCriterion.text == ac_ref),
                                    AcceptanceCriterion.repository_id == repository_id
                                ).first()
                                
                            if ac:
                                mapping = ManualTestRequirementMapping(
                                    id=uuid.uuid4(),
                                    external_test_case_id=test_case.id,
                                    acceptance_criterion_id=ac.id,
                                    repository_id=repository_id,
                                    mapping_source="IMPORTED",
                                    is_active=True
                                )
                                self.db.add(mapping)
                    
                    result.successful_imports += 1
                    
                except Exception as e:
                    result.failed_rows += 1
                    result.errors.append({
                        "row": row_number,
                        "error": str(e)
                    })
                    logger.error(f"Error importing CSV row {row_number}: {e}")
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            result.errors.append({
                "row": 0,
                "error": f"CSV parsing error: {str(e)}"
            })
            logger.error(f"CSV import error: {e}")
        
        return result
    
    def _parse_row(self, row: Dict[str, str], row_number: int) -> ParsedTestCase:
        """
        Parse a CSV row into ParsedTestCase.
        
        Args:
            row: CSV row dictionary
            row_number: Row number for error reporting
            
        Returns:
            ParsedTestCase object
        """
        title = row.get('title', '').strip()
        description = row.get('description', '').strip() or None
        priority = row.get('priority', '').strip() or None
        test_type = row.get('test_type', '').strip() or None
        
        # Parse preconditions (newline-separated)
        preconditions_str = row.get('preconditions', '').strip()
        preconditions = [line.strip() for line in preconditions_str.split('\n') if line.strip()] if preconditions_str else []
        
        # Parse steps (newline-separated, format: "Step text | Expected result")
        steps_str = row.get('steps', '').strip()
        steps = self._parse_steps(steps_str) if steps_str else []
        
        expected_result = row.get('expected_result', '').strip() or None
        
        # Parse tags (comma-separated)
        tags_str = row.get('tags', '').strip()
        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
        
        linked_work_item_key = row.get('linked_work_item_key', '').strip() or None
        behavior_name = row.get('behavior', '').strip() or None
        journey_name = row.get('journey', '').strip() or None
        linked_acceptance_criteria = row.get('linked_acceptance_criteria', '').strip() or None
        
        return ParsedTestCase(
            title=title,
            description=description,
            priority=priority,
            test_type=test_type,
            preconditions=preconditions,
            steps=steps,
            expected_result=expected_result,
            tags=tags,
            linked_work_item_key=linked_work_item_key,
            behavior_name=behavior_name,
            journey_name=journey_name,
            linked_acceptance_criteria=linked_acceptance_criteria,
            row_number=row_number
        )
    
    def _parse_steps(self, steps_str: str) -> List[Dict[str, str]]:
        """
        Parse steps string into list of step dictionaries.
        
        Format: "Step text | Expected result" (one per line)
        Fallback: Just step text if no separator found
        
        Args:
            steps_str: Steps string from CSV
            
        Returns:
            List of step dictionaries with 'step' and 'expected' keys
        """
        steps = []
        lines = steps_str.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to split by pipe separator
            if '|' in line:
                parts = line.split('|', 1)
                step_text = parts[0].strip()
                expected = parts[1].strip() if len(parts) > 1 else ''
            else:
                # Fallback: use entire line as step text
                step_text = line
                expected = ''
            
            steps.append({
                'step': step_text,
                'expected': expected
            })
        
        return steps
    
    def _is_duplicate(
        self,
        repository_id: uuid.UUID,
        title: str,
        linked_work_item_key: Optional[str]
    ) -> bool:
        """
        Check if a test case with the same title and linked_work_item_key already exists.
        
        Args:
            repository_id: Repository ID
            title: Test case title
            linked_work_item_key: Linked work item key
            
        Returns:
            True if duplicate exists, False otherwise
        """
        existing = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == repository_id,
            ExternalTestCase.title == title,
            ExternalTestCase.provider == "MANUAL_CSV"
        ).first()
        
        if not existing:
            return False
        
        # If linked_work_item_key is provided, check it matches
        if linked_work_item_key:
            existing_keys = existing.linked_work_item_keys or []
            return linked_work_item_key in existing_keys
        
        # If no linked_work_item_key, consider it a duplicate if existing also has none
        existing_keys = existing.linked_work_item_keys or []
        return len(existing_keys) == 0
    
    def _resolve_behavior(
        self,
        repository_id: uuid.UUID,
        behavior_name: Optional[str]
    ) -> Optional[uuid.UUID]:
        """
        Resolve behavior name to behavior ID.
        
        Args:
            repository_id: Repository ID
            behavior_name: Behavior name
            
        Returns:
            Behavior ID if found, None otherwise
        """
        if not behavior_name:
            return None
        
        behavior = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.name == behavior_name,
            Behavior.is_deleted == False
        ).first()
        
        return behavior.id if behavior else None
    
    def _resolve_journey(
        self,
        repository_id: uuid.UUID,
        journey_name: Optional[str]
    ) -> Optional[uuid.UUID]:
        """
        Resolve journey name to journey ID.
        
        Args:
            repository_id: Repository ID
            journey_name: Journey name
            
        Returns:
            Journey ID if found, None otherwise
        """
        if not journey_name:
            return None
        
        journey = self.db.query(Journey).filter(
            Journey.repository_id == repository_id,
            Journey.name == journey_name,
            Journey.is_deleted == False
        ).first()
        
        return journey.id if journey else None
