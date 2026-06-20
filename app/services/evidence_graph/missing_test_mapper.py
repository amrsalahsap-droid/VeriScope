"""Missing Test Mapper - Generates missing tests only from uncovered requirements.

This service generates missing test cards only from requirements classified
as MISSING_AUTOMATED_COVERAGE, not from fragments or already verified scenarios.
"""
from typing import List, Dict, Any
from dataclasses import dataclass, field

from app.services.regression_evidence_classifier import (
    RequirementNode,
    EvidenceClassification,
)


class MissingTestGenerationError(Exception):
    """Raised when hard fail gates are violated during missing test generation."""
    pass


@dataclass
class MissingTestCard:
    """Card representing a missing test."""
    requirement_id: str
    readable_id: str
    requirement_title: str
    flow: str
    suggested_test_objective: str
    suggested_layer: str
    risk_if_skipped: str
    why_missing: str
    why_existing_tests_dont_cover: str
    why_current_pr_execution_did_not_cover_it: str = ""
    best_rejected_candidate: str = ""
    best_rejected_candidate_score: float = 0.0
    best_rejected_candidate_rejection_reason: str = ""


class MissingTestMapper:
    """Service for mapping missing tests from uncovered requirements."""

    def __init__(self):
        self.missing_tests: List[MissingTestCard] = []

    def generate_missing_tests(
        self,
        requirements: List[RequirementNode],
        match_table: List[Any] = None
    ) -> List[MissingTestCard]:
        """Generate missing tests only from MISSING_AUTOMATED_COVERAGE requirements.

        Args:
            requirements: List of classified requirement nodes
            match_table: Optional match table for diagnostics

        Returns:
            List of missing test cards

        Raises:
            MissingTestGenerationError: If hard fail gates are violated
        """
        self.missing_tests = []
        generated_req_ids = set()

        # Generate cards
        for req in requirements:
            # Malformed RequirementNode input check
            if not isinstance(req, RequirementNode):
                raise MissingTestGenerationError(
                    f"Hard fail: Input element is not a RequirementNode instance."
                )

            # Missing required schema fields check
            if not hasattr(req, 'requirement_id') or not req.requirement_id or not hasattr(req, 'title') or not req.title:
                raise MissingTestGenerationError(
                    f"Hard fail: Required schema fields (requirement_id/title) are missing from RequirementNode."
                )

            # Only generate from MISSING_AUTOMATED_COVERAGE
            if req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE:
                # Check for duplicate missing card for same requirement
                if req.requirement_id in generated_req_ids:
                    raise MissingTestGenerationError(
                        f"Hard fail: Duplicate missing card request for requirement_id '{req.requirement_id}'."
                    )
                generated_req_ids.add(req.requirement_id)

                # Apply hard fail gates
                self._validate_missing_test_generation(req, match_table)

                card = self._create_missing_test_card(req, match_table)
                
                # Validate why_missing explanation and diagnostic details
                if not card.why_missing or len(card.why_missing.strip()) == 0:
                    raise MissingTestGenerationError(
                        f"Hard fail: Requirement '{req.title}' generated an empty why_missing explanation."
                    )
                if match_table:
                    has_match_entry = any(entry.requirement_id == req.requirement_id for entry in match_table)
                    if has_match_entry and "best candidate" not in card.why_missing.lower():
                        raise MissingTestGenerationError(
                            f"Hard fail: Requirement '{req.title}' why_missing explanation does not contain "
                            f"best-candidate diagnostic details: '{card.why_missing}'."
                        )

                self.missing_tests.append(card)

        return self.missing_tests

    def _validate_missing_test_generation(self, req: RequirementNode, match_table: List[Any] = None):
        """Validate that missing test generation doesn't violate hard fail gates.

        Args:
            req: Requirement node classified as MISSING_AUTOMATED_COVERAGE
            match_table: Optional match table for diagnostics

        Raises:
            MissingTestGenerationError: If hard fail gates are violated
        """
        # Malformed RequirementNode input check
        if not isinstance(req, RequirementNode):
            raise MissingTestGenerationError(
                f"Hard fail: Input element is not a RequirementNode instance."
            )

        # Generated missing card for a non-missing requirement check
        if req.classification != EvidenceClassification.MISSING_AUTOMATED_COVERAGE:
            raise MissingTestGenerationError(
                f"Hard fail: Requirement '{req.title}' is classified as {req.classification} "
                f"but is being considered for missing test generation."
            )

        # Gate 7: Ensure why-missing explanation exists in match table
        # Relaxed: Allow missing requirements without match table entries (genuine no-match scenarios)
        # The why_missing explanation will be generated from the requirement itself

    def _create_missing_test_card(self, req: RequirementNode, match_table: List[Any] = None) -> MissingTestCard:
        """Create a missing test card from a requirement.

        Args:
            req: Requirement node classified as MISSING_AUTOMATED_COVERAGE
            match_table: Optional match table for diagnostics

        Returns:
            MissingTestCard
        """
        # Generate suggested test objective
        suggested_objective = self._generate_test_objective(req)

        # Determine suggested layer
        suggested_layer = self._determine_suggested_layer(req)

        # Generate risk if skipped
        risk_if_skipped = self._generate_risk_if_skipped(req)

        # Generate why missing with match table diagnostics
        why_missing = self._generate_why_missing(req, match_table)

        # Generate why existing tests don't cover with match table diagnostics
        why_existing_dont_cover = self._generate_why_existing_dont_cover(req, match_table)

        # Generate why current PR execution did not cover it
        why_current_pr_did_not_cover = self._generate_why_current_pr_did_not_cover(req, match_table)

        # Extract best rejected candidate metadata
        best_rejected_candidate, best_rejected_score, best_rejected_reason = self._extract_best_rejected_candidate(req, match_table)

        return MissingTestCard(
            requirement_id=req.requirement_id,
            readable_id=req.readable_id,
            requirement_title=req.title,
            flow=req.flow,
            suggested_test_objective=suggested_objective,
            suggested_layer=suggested_layer,
            risk_if_skipped=risk_if_skipped,
            why_missing=why_missing,
            why_existing_tests_dont_cover=why_existing_dont_cover,
            why_current_pr_execution_did_not_cover_it=why_current_pr_did_not_cover,
            best_rejected_candidate=best_rejected_candidate,
            best_rejected_candidate_score=best_rejected_score,
            best_rejected_candidate_rejection_reason=best_rejected_reason
        )

    def _generate_test_objective(self, req: RequirementNode) -> str:
        """Generate suggested test objective from requirement."""
        # Build objective from signature
        if req.scenario_signature:
            sig = req.scenario_signature
            parts = []
            
            if sig.condition and sig.condition != "unknown":
                parts.append(f"{sig.condition.replace('_', ' ')}")
            
            if sig.action and sig.action != "unknown":
                parts.append(f"{sig.action.replace('_', ' ')}")
            
            if sig.expected_outcome and sig.expected_outcome != "unknown":
                parts.append(f"{sig.expected_outcome.replace('_', ' ')}")
            
            if parts:
                return " ".join(parts).capitalize()

        # Fallback to title
        return req.title

    def _determine_suggested_layer(self, req: RequirementNode) -> str:
        """Determine suggested test layer from requirement."""
        if req.validation_layer and req.validation_layer != "unknown":
            return req.validation_layer.upper()

        # Default based on flow
        if "api" in req.title.lower() or "endpoint" in req.title.lower():
            return "API"
        elif "ui" in req.title.lower() or "interface" in req.title.lower():
            return "UI"
        elif "security" in req.title.lower() or "auth" in req.title.lower():
            return "SECURITY"

        return "INTEGRATION"

    def _generate_risk_if_skipped(self, req: RequirementNode) -> str:
        """Generate risk description if test is skipped."""
        risk_level = req.risk_level.upper()

        if risk_level == "HIGH":
            if "security" in req.title.lower() or "auth" in req.title.lower():
                return f"Security vulnerability: {req.title.lower()} may allow unauthorized access."
            return f"High risk: {req.title.lower()} may cause critical failures."

        elif risk_level == "MEDIUM":
            return f"Medium risk: {req.title.lower()} may cause functional issues."

        else:
            return f"Low risk: {req.title.lower()} may cause minor inconsistencies."

    def _generate_why_missing(self, req: RequirementNode, match_table: List[Any] = None) -> str:
        """Generate explanation of why this test is missing."""
        if req.match_score > 0:
            explanation = f"No current PR execution test matched this requirement above threshold (score: {req.match_score:.2f})."
        else:
            explanation = "No current PR execution test matched this requirement."

        # Add best candidate from match table if available
        if match_table:
            for entry in match_table:
                if entry.requirement_id == req.requirement_id:
                    if entry.decision == "REJECTED":
                        explanation += f" Best candidate '{entry.candidate_test_title}' was rejected (score: {entry.score:.2f}, reason: {entry.reason})."
                    elif entry.decision == "PARTIAL":
                        explanation += f" Best candidate '{entry.candidate_test_title}' was partial (score: {entry.score:.2f}, reason: {entry.reason})."
                    break

        return explanation

    def _generate_why_existing_dont_cover(self, req: RequirementNode, match_table: List[Any] = None) -> str:
        """Generate explanation of why existing tests don't cover this."""
        if req.matched_test_ids:
            explanation = f"Existing test matched but not executed in current PR (score: {req.match_score:.2f})."
        else:
            explanation = "No existing automated test found with sufficient match score."

        # Add best candidate from match table if available
        if match_table:
            for entry in match_table:
                if entry.requirement_id == req.requirement_id:
                    if entry.decision == "REJECTED":
                        explanation += f" Best candidate '{entry.candidate_test_title}' was rejected (score: {entry.score:.2f}, reason: {entry.reason})."
                    elif entry.decision == "PARTIAL":
                        explanation += f" Best candidate '{entry.candidate_test_title}' was partial (score: {entry.score:.2f}, reason: {entry.reason})."
                    break

        return explanation

    def _generate_why_current_pr_did_not_cover(self, req: RequirementNode, match_table: List[Any] = None) -> str:
        """Generate explanation of why current PR execution did not cover this requirement."""
        if req.matched_execution_ids:
            # This should not happen for MISSING_AUTOMATED_COVERAGE, but handle defensively
            return f"Requirement has matched current PR execution IDs: {req.matched_execution_ids}"
        
        if req.matched_test_ids:
            return f"Requirement has matched existing test(s) but they were not executed in current PR: {req.matched_test_ids}"
        
        # Check match table for current PR execution candidates
        if match_table:
            for entry in match_table:
                if entry.requirement_id == req.requirement_id:
                    if entry.current_pr_execution_id:
                        return f"Current PR execution exists but did not meet match threshold (score: {entry.score:.2f})"
                    elif entry.decision == "REJECTED":
                        return f"Current PR execution candidate was rejected due to contradiction: {entry.rejection_reason}"
                    break
        
        return "No current PR execution test matched this requirement"

    def _extract_best_rejected_candidate(self, req: RequirementNode, match_table: List[Any] = None) -> tuple:
        """Extract best rejected candidate metadata from match table.
        
        Returns:
            Tuple of (candidate_title, score, rejection_reason)
        """
        if not match_table:
            return "", 0.0, ""
        
        best_candidate = ""
        best_score = 0.0
        best_reason = ""
        
        for entry in match_table:
            if entry.requirement_id == req.requirement_id:
                if entry.decision == "REJECTED":
                    # This is a rejected candidate
                    if entry.score > best_score:
                        best_candidate = entry.candidate_test_title
                        best_score = entry.score
                        best_reason = entry.rejection_reason or entry.contradiction_rule_triggered or entry.reason
                elif entry.decision == "PARTIAL":
                    # Partial matches are also useful as rejected candidates
                    if entry.score > best_score:
                        best_candidate = entry.candidate_test_title
                        best_score = entry.score
                        best_reason = entry.reason
        
        return best_candidate, best_score, best_reason

    def clear_missing_tests(self):
        """Clear missing tests for a new classification run."""
        self.missing_tests = []
