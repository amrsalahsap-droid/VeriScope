"""Business Intent Coverage Matrix Generator service.

Generates a matrix showing whether the business intent of the PR is actually validated.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.schemas.business_intent import BusinessIntentCoverageMatrix, BusinessIntentCoverageMatrixRow
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.models.expected_behavior_scenario import ExpectedBehaviorScenario
from app.services.acceptance_criteria_coverage_resolver import AcceptanceCriteriaCoverageResolver


class BusinessIntentCoverageMatrixGenerator:
    """Generates business intent coverage matrix."""
    
    # Status constants
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    MISSING = "MISSING"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    
    # Recommended action constants
    RUN_EXISTING_TEST = "RUN_EXISTING_TEST"
    ADD_AUTOMATED_TEST = "ADD_AUTOMATED_TEST"
    EXECUTE_MANUAL_VALIDATION = "EXECUTE_MANUAL_VALIDATION"
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    CLARIFY_REQUIREMENT = "CLARIFY_REQUIREMENT"
    
    # Confidence impact constants
    NONE = "NONE"
    REDUCED = "REDUCED"
    SIGNIFICANTLY_REDUCED = "SIGNIFICANTLY_REDUCED"
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the generator with optional database session."""
        self.db = db
    
    def generate_matrix(
        self,
        acceptance_criteria: List[AcceptanceCriterion],
        business_intent: Optional[Dict[str, Any]],
        affected_behaviors: List[Behavior],
        affected_journeys: List[Journey],
        business_behavior_mappings: List[BusinessBehaviorMapping],
        expected_scenarios: List[ExpectedBehaviorScenario],
        ac_coverage_report: Optional[Any] = None,
        repository_id: Optional[str] = None
    ) -> BusinessIntentCoverageMatrix:
        """Generate business intent coverage matrix.
        
        Rules:
        - If PR has no business intent/AC, add gap
        - Do not block recommendations, but reduce confidence
        - Matrix must be backend-generated
        """
        rows = []
        
        # Check if PR has business intent or AC
        has_business_intent = len(acceptance_criteria) > 0 or (business_intent and business_intent.get("description"))
        
        if not has_business_intent:
            # Add gap row
            gap_row = BusinessIntentCoverageMatrixRow(
                business_intent_id=None,
                acceptance_criterion_id=None,
                business_intent_text="No business intent or acceptance criteria found",
                affected_behavior_id=None,
                affected_behavior_name=None,
                affected_journey_id=None,
                affected_journey_name=None,
                existing_test_coverage=[],
                suggested_scenario_id=None,
                suggested_scenario_title=None,
                current_pr_execution_status="UNKNOWN",
                status=self.UNKNOWN,
                recommended_action=self.CLARIFY_REQUIREMENT,
                confidence=0.0,
                reason="PR lacks business intent or acceptance criteria"
            )
            rows.append(gap_row)
            
            return BusinessIntentCoverageMatrix(
                rows=rows,
                total_intents=0,
                covered=0,
                partially_covered=0,
                missing=0,
                verified=0,
                unknown=1,
                has_business_intent=False,
                confidence_impact=self.REDUCED,
            )
        
        # Build lookup maps
        behavior_map = {str(b.id): b for b in affected_behaviors}
        journey_map = {str(j.id): j for j in affected_journeys}
        scenario_map = {str(s.id): s for s in expected_scenarios}
        
        # Build AC to mapping
        ac_to_mapping = {}
        for mapping in business_behavior_mappings:
            if mapping.acceptance_criterion_id:
                ac_id = str(mapping.acceptance_criterion_id)
                ac_to_mapping[ac_id] = mapping
        
        # Build AC to coverage status
        ac_to_coverage = {}
        if ac_coverage_report:
            for status in ac_coverage_report.coverage_statuses:
                ac_to_coverage[status.acceptance_criterion_id] = status
        
        # Generate rows for each AC
        for ac in acceptance_criteria:
            ac_id = str(ac.id)
            mapping = ac_to_mapping.get(ac_id)
            coverage_status = ac_to_coverage.get(ac_id)
            
            # Get behavior and journey info
            behavior = None
            journey = None
            if mapping:
                behavior = behavior_map.get(str(mapping.behavior_id))
                if mapping.journey_id:
                    journey = journey_map.get(str(mapping.journey_id))
            
            # Get suggested scenario
            suggested_scenario = None
            if mapping and mapping.is_candidate_missing_scenario == "true":
                # Find expected scenario for this AC
                for scenario in expected_scenarios:
                    if scenario.acceptance_criterion_id == ac.id:
                        suggested_scenario = scenario
                        break
            
            # Determine status and recommended action
            status, recommended_action, confidence, reason = self._determine_status_and_action(
                ac,
                mapping,
                coverage_status,
                suggested_scenario
            )
            
            # Get existing test coverage
            existing_tests = []
            if coverage_status:
                existing_tests = coverage_status.existing_tests
            
            # Get suggested scenario info
            suggested_scenario_id = None
            suggested_scenario_title = None
            if suggested_scenario:
                suggested_scenario_id = str(suggested_scenario.id)
                suggested_scenario_title = suggested_scenario.title
            
            # Get current PR execution status
            current_pr_execution = "NOT_EXECUTED"
            if coverage_status:
                current_pr_execution = coverage_status.current_pr_execution_status
            
            row = BusinessIntentCoverageMatrixRow(
                business_intent_id=None,
                acceptance_criterion_id=ac_id,
                business_intent_text=ac.text,
                affected_behavior_id=str(behavior.id) if behavior else None,
                affected_behavior_name=behavior.name if behavior else None,
                affected_journey_id=str(journey.id) if journey else None,
                affected_journey_name=journey.name if journey else None,
                existing_test_coverage=existing_tests,
                suggested_scenario_id=suggested_scenario_id,
                suggested_scenario_title=suggested_scenario_title,
                current_pr_execution_status=current_pr_execution,
                status=status,
                recommended_action=recommended_action,
                confidence=confidence,
                reason=reason
            )
            
            rows.append(row)
        
        # Calculate statistics
        total = len(rows)
        covered = sum(1 for r in rows if r.status == self.COVERED)
        partially_covered = sum(1 for r in rows if r.status == self.PARTIALLY_COVERED)
        missing = sum(1 for r in rows if r.status == self.MISSING)
        verified = sum(1 for r in rows if r.status == self.VERIFIED)
        unknown = sum(1 for r in rows if r.status == self.UNKNOWN)
        
        # Determine confidence impact
        confidence_impact = self._determine_confidence_impact(
            total, covered, partially_covered, missing, verified
        )
        
        return BusinessIntentCoverageMatrix(
            rows=rows,
            total_intents=total,
            covered=covered,
            partially_covered=partially_covered,
            missing=missing,
            verified=verified,
            unknown=unknown,
            has_business_intent=has_business_intent,
            confidence_impact=confidence_impact,
        )
    
    def _determine_status_and_action(
        self,
        ac: AcceptanceCriterion,
        mapping: Optional[BusinessBehaviorMapping],
        coverage_status: Optional[Any],
        suggested_scenario: Optional[ExpectedBehaviorScenario]
    ) -> tuple:
        """Determine status and recommended action for an AC."""
        
        if not coverage_status:
            # No coverage status - unknown
            return self.UNKNOWN, self.CLARIFY_REQUIREMENT, 0.3, "No coverage information available"
        
        coverage = coverage_status.coverage_status
        
        if coverage == "VERIFIED_ON_CURRENT_PR":
            return self.VERIFIED, self.ALREADY_VERIFIED, 0.95, "Verified on current PR"
        
        if coverage == "COVERED_BY_EXISTING_TEST":
            return self.COVERED, self.RUN_EXISTING_TEST, 0.8, "Covered by existing tests, run on current PR"
        
        if coverage == "PARTIALLY_COVERED":
            if suggested_scenario:
                return self.PARTIALLY_COVERED, self.ADD_AUTOMATED_TEST, 0.6, "Partially covered, add automated test"
            return self.PARTIALLY_COVERED, self.EXECUTE_MANUAL_VALIDATION, 0.5, "Partially covered, manual validation recommended"
        
        if coverage == "MISSING_TEST_COVERAGE":
            if suggested_scenario:
                return self.MISSING, self.ADD_AUTOMATED_TEST, 0.7, "Missing coverage, suggested scenario available"
            return self.MISSING, self.ADD_AUTOMATED_TEST, 0.6, "Missing coverage, add automated test"
        
        if coverage == "MANUAL_VALIDATION_REQUIRED":
            return self.MISSING, self.EXECUTE_MANUAL_VALIDATION, 0.5, "Manual validation required"
        
        return self.UNKNOWN, self.CLARIFY_REQUIREMENT, 0.3, f"Unknown coverage status: {coverage}"
    
    def _determine_confidence_impact(
        self,
        total: int,
        covered: int,
        partially_covered: int,
        missing: int,
        verified: int
    ) -> str:
        """Determine impact on recommendation confidence."""
        
        if total == 0:
            return self.SIGNIFICANTLY_REDUCED
        
        coverage_ratio = (covered + verified) / total if total > 0 else 0
        
        if coverage_ratio >= 0.8:
            return self.NONE
        elif coverage_ratio >= 0.5:
            return self.REDUCED
        else:
            return self.SIGNIFICANTLY_REDUCED
