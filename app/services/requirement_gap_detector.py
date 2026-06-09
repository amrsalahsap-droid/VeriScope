"""Requirement Gap Detector service.

Identifies missing or unclear business intent in PRs.
"""
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.schemas.requirement_gap import RequirementGap, RequirementGapReport
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.schemas.acceptance_criteria import AcceptanceCriteriaCoverageReport


class RequirementGapDetector:
    """Detects gaps in business intent and requirements."""
    
    # Severity levels
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    
    # Gap types
    MISSING_PR_DESCRIPTION = "MISSING_PR_DESCRIPTION"
    MISSING_ACCEPTANCE_CRITERIA = "MISSING_ACCEPTANCE_CRITERIA"
    VAGUE_REQUIREMENT = "VAGUE_REQUIREMENT"
    UNMAPPED_BUSINESS_BEHAVIOR = "UNMAPPED_BUSINESS_BEHAVIOR"
    UNTESTED_ACCEPTANCE_CRITERION = "UNTESTED_ACCEPTANCE_CRITERION"
    
    # Trust levels
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"
    
    # Vague language indicators
    VAGUE_INDICATORS = [
        "maybe", "might", "could", "possibly", "perhaps",
        "consider", "think about", "look into", "explore",
        "nice to have", "would be good", "should consider",
        "at some point", "in the future", "eventually"
    ]
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the detector with optional database session."""
        self.db = db
    
    def detect_gaps(
        self,
        pr_description: str,
        acceptance_criteria: List[AcceptanceCriterion],
        affected_behaviors: List[Behavior],
        business_behavior_mappings: List[BusinessBehaviorMapping],
        ac_coverage_report: Optional[AcceptanceCriteriaCoverageReport] = None,
        changed_files: Optional[List[str]] = None
    ) -> RequirementGapReport:
        """Detect requirement gaps.
        
        Detects:
        - empty PR description
        - no acceptance criteria
        - vague requirement text
        - changed high-risk behavior with no stated expected behavior
        - AC exists but no related test/scenario
        - behavior impacted but no business intent mapped
        """
        gaps = []
        
        # Check for empty PR description
        if not pr_description or not pr_description.strip():
            gaps.append(RequirementGap(
                severity=self.CRITICAL,
                gap_type=self.MISSING_PR_DESCRIPTION,
                message="PR description is empty or missing",
                impact="Cannot understand business intent, recommendation quality significantly reduced",
                recommended_action="Add a clear PR description explaining the business intent and expected behavior"
            ))
        
        # Check for missing acceptance criteria
        if not acceptance_criteria:
            gaps.append(RequirementGap(
                severity=self.HIGH,
                gap_type=self.MISSING_ACCEPTANCE_CRITERIA,
                message="No acceptance criteria found in PR",
                impact="Cannot validate business intent, recommendation confidence reduced",
                recommended_action="Add acceptance criteria to PR description or link to a story with criteria"
            ))
        else:
            # Check for vague requirements in AC
            for ac in acceptance_criteria:
                if self._is_vague_requirement(ac.text):
                    gaps.append(RequirementGap(
                        severity=self.MEDIUM,
                        gap_type=self.VAGUE_REQUIREMENT,
                        message=f"Vague requirement: '{ac.text[:50]}...'",
                        impact="Unclear business intent may lead to incorrect recommendations",
                        recommended_action="Clarify the requirement with specific expected behavior"
                    ))
        
        # Check for unmapped business behaviors
        affected_behavior_ids = {str(b.id) for b in affected_behaviors}
        mapped_behavior_ids = {str(m.behavior_id) for m in business_behavior_mappings}
        unmapped_behaviors = affected_behavior_ids - mapped_behavior_ids
        
        if unmapped_behaviors:
            for behavior in affected_behaviors:
                if str(behavior.id) in unmapped_behaviors:
                    severity = self.HIGH if behavior.risk_level in ["HIGH", "CRITICAL"] else self.MEDIUM
                    gaps.append(RequirementGap(
                        severity=severity,
                        gap_type=self.UNMAPPED_BUSINESS_BEHAVIOR,
                        message=f"Behavior '{behavior.name}' is impacted but not mapped to business intent",
                        impact=f"Cannot validate behavior coverage for {behavior.name}",
                        recommended_action=f"Add acceptance criteria that covers the '{behavior.name}' behavior"
                    ))
        
        # Check for untested acceptance criteria
        if ac_coverage_report:
            for status in ac_coverage_report.coverage_statuses:
                if status.coverage_status in ["MISSING_TEST_COVERAGE", "MANUAL_VALIDATION_REQUIRED"]:
                    # Find the AC
                    ac = next((a for a in acceptance_criteria if str(a.id) == status.acceptance_criterion_id), None)
                    if ac:
                        severity = self.HIGH if ac.priority == "MUST" else self.MEDIUM
                        gaps.append(RequirementGap(
                            severity=severity,
                            gap_type=self.UNTESTED_ACCEPTANCE_CRITERION,
                            message=f"Acceptance criterion has no test coverage: '{ac.text[:50]}...'",
                            impact="Cannot verify this requirement through automated testing",
                            recommended_action="Add automated test or manual validation for this criterion"
                        ))
        
        # Generate report
        return self._generate_report(gaps)
    
    def _is_vague_requirement(self, text: str) -> bool:
        """Check if requirement text is vague."""
        text_lower = text.lower()
        
        for indicator in self.VAGUE_INDICATORS:
            if indicator in text_lower:
                return True
        
        # Check for very short requirements
        if len(text.split()) < 3:
            return True
        
        return False
    
    def _generate_report(self, gaps: List[RequirementGap]) -> RequirementGapReport:
        """Generate requirement gap report."""
        
        total = len(gaps)
        critical = sum(1 for g in gaps if g.severity == self.CRITICAL)
        high = sum(1 for g in gaps if g.severity == self.HIGH)
        medium = sum(1 for g in gaps if g.severity == self.MEDIUM)
        low = sum(1 for g in gaps if g.severity == self.LOW)
        
        has_critical = critical > 0
        
        # Determine overall trust level
        overall_trust_level = self._determine_trust_level(critical, high, medium, low)
        
        return RequirementGapReport(
            gaps=gaps,
            total_gaps=total,
            critical_gaps=critical,
            high_gaps=high,
            medium_gaps=medium,
            low_gaps=low,
            has_critical_gaps=has_critical,
            overall_trust_level=overall_trust_level
        )
    
    def _determine_trust_level(self, critical: int, high: int, medium: int, low: int) -> str:
        """Determine overall trust level based on gaps."""
        
        if critical > 0:
            return self.VERY_LOW
        
        if high >= 2:
            return self.LOW
        
        if high == 1:
            return self.MEDIUM
        
        if medium >= 3:
            return self.MEDIUM
        
        if medium > 0:
            return self.HIGH
        
        return self.HIGH
