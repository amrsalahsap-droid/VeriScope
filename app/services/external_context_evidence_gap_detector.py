"""
External Context Evidence Gap Detector Service

Detects evidence gaps in external business/test context.
Provides recommendations for improving future recommendation accuracy.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.models.external_work_item import ExternalWorkItem
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.pull_request_work_item_link import PullRequestWorkItemLink
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.integration_connection import IntegrationConnection
from app.models.pull_request import PullRequest


logger = logging.getLogger("veriscope.external_context_evidence_gap_detector")


class GapSeverity(str, Enum):
    """Severity level for evidence gaps."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class EvidenceGap:
    """Evidence gap in external context."""
    severity: GapSeverity
    message: str
    impact: str
    recommended_action: str
    gap_type: str  # WORK_ITEM, ACCEPTANCE_CRITERIA, TEST_CASE, INTEGRATION, SYNC, MAPPING


class ExternalContextEvidenceGapDetector:
    """
    Detects evidence gaps in external business/test context.
    
    Rules:
    - Integration gaps lower confidence but do not block recommendations
    - Explain how user can improve future accuracy
    """
    
    def __init__(self, db: Session):
        """Initialize the detector with database session."""
        self.db = db
    
    def detect_evidence_gaps(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID
    ) -> List[EvidenceGap]:
        """
        Detect evidence gaps for a pull request.
        
        Args:
            repository_id: Repository ID
            pull_request_id: Pull request ID
            
        Returns:
            List of EvidenceGap objects
        """
        gaps = []
        
        # Get pull request
        pr = self.db.query(PullRequest).filter(
            PullRequest.id == pull_request_id
        ).first()
        
        if not pr:
            return gaps
        
        # Detect work item gaps
        gaps.extend(self._detect_work_item_gaps(repository_id, pull_request_id, pr))
        
        # Detect acceptance criteria gaps
        gaps.extend(self._detect_acceptance_criteria_gaps(repository_id, pull_request_id))
        
        # Detect test case gaps
        gaps.extend(self._detect_test_case_gaps(repository_id, pull_request_id))
        
        # Detect integration gaps
        gaps.extend(self._detect_integration_gaps(repository_id))
        
        # Detect mapping gaps
        gaps.extend(self._detect_mapping_gaps(repository_id))
        
        # Sort by severity
        severity_order = {
            GapSeverity.CRITICAL: 0,
            GapSeverity.HIGH: 1,
            GapSeverity.MEDIUM: 2,
            GapSeverity.LOW: 3
        }
        
        gaps.sort(key=lambda g: severity_order[g.severity])
        
        return gaps
    
    def _detect_work_item_gaps(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID,
        pr: PullRequest
    ) -> List[EvidenceGap]:
        """Detect work item-related evidence gaps."""
        gaps = []
        
        # Check for linked work items
        work_item_links = self.db.query(PullRequestWorkItemLink).filter(
            PullRequestWorkItemLink.pull_request_id == pull_request_id
        ).all()
        
        if not work_item_links:
            # Try to detect work item keys from PR metadata
            from app.services.pr_work_item_linker import PRWorkItemLinker
            linker = PRWorkItemLinker(self.db)
            
            detected = linker._detect_all_keys(
                pull_request=pr,
                commits=[]
            )
            detected_keys = list(detected.keys())
            
            if detected_keys:
                gaps.append(EvidenceGap(
                    severity=GapSeverity.MEDIUM,
                    message="Work item keys detected in PR but not linked",
                    impact="Business context may be incomplete",
                    recommended_action="Run integration sync to link detected work items",
                    gap_type="WORK_ITEM"
                ))
            else:
                gaps.append(EvidenceGap(
                    severity=GapSeverity.LOW,
                    message="No linked work items detected",
                    impact="Business context may be limited",
                    recommended_action="Include work item keys (e.g., PROJ-123) in PR title or description",
                    gap_type="WORK_ITEM"
                ))
        else:
            # Check if linked work items are available
            work_item_ids = [link.external_work_item_id for link in work_item_links]
            work_items = self.db.query(ExternalWorkItem).filter(
                ExternalWorkItem.id.in_(work_item_ids)
            ).all()
            
            if len(work_items) < len(work_item_ids):
                gaps.append(EvidenceGap(
                    severity=GapSeverity.HIGH,
                    message="Some linked work items are unavailable",
                    impact="Business context incomplete",
                    recommended_action="Sync integration to fetch missing work items",
                    gap_type="WORK_ITEM"
                ))
        
        return gaps
    
    def _detect_acceptance_criteria_gaps(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID
    ) -> List[EvidenceGap]:
        """Detect acceptance criteria-related evidence gaps."""
        gaps = []
        
        # Check for acceptance criteria
        acceptance_criteria = self.db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pull_request_id
        ).all()
        
        if not acceptance_criteria:
            gaps.append(EvidenceGap(
                severity=GapSeverity.MEDIUM,
                message="No acceptance criteria found",
                impact="Cannot validate business requirements",
                recommended_action="Add acceptance criteria to PR description or link work items with AC",
                gap_type="ACCEPTANCE_CRITERIA"
            ))
        else:
            # Check if AC have external work item links
            ac_with_work_items = sum(1 for ac in acceptance_criteria if getattr(ac, 'external_work_item_id', None))
            
            if ac_with_work_items == 0:
                gaps.append(EvidenceGap(
                    severity=GapSeverity.LOW,
                    message="Acceptance criteria not linked to work items",
                    impact="Limited traceability to business requirements",
                    recommended_action="Link acceptance criteria to external work items for better traceability",
                    gap_type="ACCEPTANCE_CRITERIA"
                ))
        
        return gaps
    
    def _detect_test_case_gaps(
        self,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID
    ) -> List[EvidenceGap]:
        """Detect test case-related evidence gaps."""
        gaps = []
        
        # Check for external test cases
        external_test_cases = self.db.query(ExternalTestCase).filter(
            ExternalTestCase.repository_id == repository_id,
            ExternalTestCase.is_active == True
        ).all()
        
        if not external_test_cases:
            gaps.append(EvidenceGap(
                severity=GapSeverity.LOW,
                message="No external test cases found",
                impact="Manual test coverage not available",
                recommended_action="Connect TestRail or import CSV to add manual test cases",
                gap_type="TEST_CASE"
            ))
        else:
            # Check if test cases are mapped to scenarios
            from app.models.external_test_scenario_mapping import ExternalTestScenarioMapping
            test_ids = [t.id for t in external_test_cases]
            scenario_mappings = self.db.query(ExternalTestScenarioMapping).filter(
                ExternalTestScenarioMapping.external_test_case_id.in_(test_ids)
            ).all()
            
            mapped_test_ids = set(mapping.external_test_case_id for mapping in scenario_mappings)
            unmapped_count = len(test_ids) - len(mapped_test_ids)
            
            if unmapped_count > 0:
                gaps.append(EvidenceGap(
                    severity=GapSeverity.LOW,
                    message=f"{unmapped_count} external test cases not mapped to scenarios",
                    impact="Manual test coverage not linked to behavior catalog",
                    recommended_action="Run scenario mapping to link test cases to behaviors",
                    gap_type="MAPPING"
                ))
        
        return gaps
    
    def _detect_integration_gaps(
        self,
        repository_id: uuid.UUID
    ) -> List[EvidenceGap]:
        """Detect integration-related evidence gaps."""
        gaps = []
        
        # Check for active integrations
        integrations = self.db.query(IntegrationConnection).filter(
            IntegrationConnection.repository_id == repository_id,
            IntegrationConnection.is_active == True
        ).all()
        
        if not integrations:
            gaps.append(EvidenceGap(
                severity=GapSeverity.LOW,
                message="No active integrations configured",
                impact="External business/test context unavailable",
                recommended_action="Connect Jira, Azure DevOps, or TestRail in repository settings",
                gap_type="INTEGRATION"
            ))
        else:
            # Check integration sync status
            providers = [conn.provider for conn in integrations]
            
            if "JIRA" not in providers and "AZURE_DEVOPS" not in providers:
                gaps.append(EvidenceGap(
                    severity=GapSeverity.LOW,
                    message="No work item integration configured",
                    impact="Business context from work items unavailable",
                    recommended_action="Connect Jira or Azure DevOps to import work items",
                    gap_type="INTEGRATION"
                ))
            
            if "TESTRAIL" not in providers:
                gaps.append(EvidenceGap(
                    severity=GapSeverity.LOW,
                    message="No test management integration configured",
                    impact="Manual test cases from TMS unavailable",
                    recommended_action="Connect TestRail to import managed test cases",
                    gap_type="INTEGRATION"
                ))
        
        return gaps
    
    def _detect_mapping_gaps(
        self,
        repository_id: uuid.UUID
    ) -> List[EvidenceGap]:
        """Detect mapping-related evidence gaps."""
        gaps = []
        
        # Check for work item behavior mappings (join through ExternalWorkItem)
        from app.models.work_item_behavior_mapping import WorkItemBehaviorMapping
        from app.models.external_work_item import ExternalWorkItem
        work_item_mappings = self.db.query(WorkItemBehaviorMapping).join(
            ExternalWorkItem, WorkItemBehaviorMapping.external_work_item_id == ExternalWorkItem.id
        ).filter(
            ExternalWorkItem.repository_id == repository_id
        ).all()
        
        # Get external work items
        external_work_items = self.db.query(ExternalWorkItem).filter(
            ExternalWorkItem.repository_id == repository_id
        ).all()
        
        if external_work_items and not work_item_mappings:
            gaps.append(EvidenceGap(
                severity=GapSeverity.LOW,
                message="External work items not mapped to behaviors",
                impact="Work items not linked to behavior catalog",
                recommended_action="Run work item behavior mapping to link work items to behaviors",
                gap_type="MAPPING"
            ))
        
        return gaps
