"""Regression Evidence Classifier.

Canonical source of truth for mapping requirements to test evidence,
distinguishing between verified tests, missing tests, and coverage gaps.
"""
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime


class EvidenceClassification(Enum):
    """Final evidence classification buckets."""
    VERIFIED_BY_CURRENT_PR_EXECUTION = "VERIFIED_BY_CURRENT_PR_EXECUTION"
    FAILED_IN_CURRENT_PR_EXECUTION = "FAILED_IN_CURRENT_PR_EXECUTION"
    SKIPPED_IN_CURRENT_PR_EXECUTION = "SKIPPED_IN_CURRENT_PR_EXECUTION"
    EXISTING_TEST_NOT_RUN_IN_CURRENT_PR = "EXISTING_TEST_NOT_RUN_IN_CURRENT_PR"
    MISSING_AUTOMATED_COVERAGE = "MISSING_AUTOMATED_COVERAGE"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    COVERAGE_GAP_ONLY = "COVERAGE_GAP_ONLY"
    OPTIONAL_IMPROVEMENT = "OPTIONAL_IMPROVEMENT"
    NOT_MAPPED_TRACEABILITY_RISK = "NOT_MAPPED_TRACEABILITY_RISK"
    EXCLUDED_FRAGMENT_OR_TEST_DATA = "EXCLUDED_FRAGMENT_OR_TEST_DATA"


class ValidationLayer(Enum):
    """Testing/validation layer."""
    API = "API"
    UI = "UI"
    E2E = "E2E"
    SECURITY = "SECURITY"
    SESSION = "SESSION"
    DATA = "DATA"
    UNIT = "UNIT"
    INTEGRATION = "INTEGRATION"


class Polarity(Enum):
    """Expected outcome polarity."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class TestType(Enum):
    """Test classification."""
    API = "API"
    UI = "UI"
    E2E = "E2E"
    UNIT = "unit"
    INTEGRATION = "integration"
    MANUAL = "manual"


class AutomationStatus(Enum):
    """Automation status."""
    EXISTING_AUTOMATED = "existing_automated"
    EXISTING_MANUAL = "existing_manual"
    MISSING_SUGGESTED = "missing_suggested"


class CoverageStrength(Enum):
    """Coverage evidence strength."""
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"
    UNRELATED = "unrelated"


@dataclass
class ScenarioSignature:
    """Canonical scenario signature for matching."""
    flow: str
    action: str
    condition: str
    expected_outcome: str
    subject: str = ""  # Renamed from entity for clarity
    validation_layer: str = ""
    polarity: str = "neutral"
    security_context: str = ""
    data_category: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "flow": self.flow,
            "action": self.action,
            "condition": self.condition,
            "expected_outcome": self.expected_outcome,
            "subject": self.subject,
            "validation_layer": self.validation_layer,
            "polarity": self.polarity,
            "security_context": self.security_context,
            "data_category": self.data_category,
        }


@dataclass
class RequirementNode:
    """Represents one real acceptance criterion or inferred required behavior."""
    requirement_id: str
    readable_id: str = ""
    title: str = ""
    flow: str = ""
    actor: str = ""
    action: str = ""
    condition: str = ""
    expected_outcome: str = ""
    polarity: str = "neutral"
    validation_layer: str = ""
    risk_level: str = "medium"
    source: str = "acceptance_criteria"  # acceptance_criteria, inferred_from_diff, coverage_gap, business_rule
    is_real_testable_requirement: bool = True
    parent_requirement_id: Optional[str] = None
    scenario_signature: Optional[ScenarioSignature] = None
    classification: EvidenceClassification = EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK
    classification_reason: str = ""
    matched_test_ids: List[str] = field(default_factory=list)
    matched_execution_ids: List[str] = field(default_factory=list)
    match_score: float = 0.0
    match_diagnostics: Dict[str, Any] = field(default_factory=dict)
    node_type: str = "PARENT_REQUIREMENT"
    linked_test_data: List[str] = field(default_factory=list)
    child_rules: List[Any] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    source_hash: Optional[str] = None
    source_number: Optional[int] = None  # Phase 6.4: Add source_number for manual evidence matching
    database_ac_id: Optional[str] = None  # Phase 6: Add database AC ID for evidence overlay cross-reference

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "readable_id": self.readable_id,
            "title": self.title,
            "flow": self.flow,
            "actor": self.actor,
            "action": self.action,
            "condition": self.condition,
            "expected_outcome": self.expected_outcome,
            "polarity": self.polarity,
            "validation_layer": self.validation_layer,
            "risk_level": self.risk_level,
            "source": self.source,
            "is_real_testable_requirement": self.is_real_testable_requirement,
            "parent_requirement_id": self.parent_requirement_id,
            "scenario_signature": self.scenario_signature.to_dict() if self.scenario_signature else None,
            "classification": self.classification.value,
            "classification_reason": self.classification_reason,
            "matched_test_ids": self.matched_test_ids,
            "matched_execution_ids": self.matched_execution_ids,
            "match_score": self.match_score,
            "match_diagnostics": self.match_diagnostics,
            "node_type": self.node_type,
            "linked_test_data": self.linked_test_data,
            "child_rules": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.child_rules],
            "notes": self.notes,
            "source_hash": self.source_hash,
        }


@dataclass
class TestNode:
    """Represents one existing automated/manual test or suggested missing test."""
    test_id: str
    title: str
    normalized_title: str = ""
    classname: str = ""
    file_path: str = ""
    test_type: str = "unit"  # API, UI, E2E, unit, integration, manual
    automation_status: str = "existing_automated"  # existing_automated, existing_manual, missing_suggested
    mapped_requirement_ids: List[str] = field(default_factory=list)
    scenario_signature: Optional[ScenarioSignature] = None
    scenario_signature_hash: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    acceptance_criterion_metadata: Optional[Dict[str, Any]] = None
    declared_ac_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "title": self.title,
            "normalized_title": self.normalized_title,
            "classname": self.classname,
            "file_path": self.file_path,
            "test_type": self.test_type,
            "automation_status": self.automation_status,
            "mapped_requirement_ids": self.mapped_requirement_ids,
            "scenario_signature": self.scenario_signature.to_dict() if self.scenario_signature else None,
            "scenario_signature_hash": self.scenario_signature_hash,
            "properties": self.properties,
            "acceptance_criterion_metadata": self.acceptance_criterion_metadata,
            "declared_ac_id": self.declared_ac_id,
        }


@dataclass
class ExecutionNode:
    """Represents current PR execution evidence."""
    test_id: str
    test_name: str
    classname: str
    status: str  # passed, failed, skipped, error
    duration: float
    pull_request_id: str
    head_sha: str
    source_file: str = ""
    mapped_test_node_id: Optional[str] = None
    mapped_requirement_ids: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    acceptance_criterion_metadata: Optional[Dict[str, Any]] = None
    declared_ac_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "classname": self.classname,
            "status": self.status,
            "duration": self.duration,
            "pull_request_id": self.pull_request_id,
            "head_sha": self.head_sha,
            "source_file": self.source_file,
            "mapped_test_node_id": self.mapped_test_node_id,
            "mapped_requirement_ids": self.mapped_requirement_ids,
            "properties": self.properties,
            "acceptance_criterion_metadata": self.acceptance_criterion_metadata,
            "declared_ac_id": self.declared_ac_id,
        }


@dataclass
class CoverageNode:
    """Represents coverage evidence."""
    file_path: str
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    uncovered_lines: List[int] = field(default_factory=list)
    covered_lines: List[int] = field(default_factory=list)
    coverage_report_id: str = ""
    partially_covered_branches: List[str] = field(default_factory=list)
    related_flows: List[str] = field(default_factory=list)
    related_requirement_ids: List[str] = field(default_factory=list)
    coverage_strength: str = "weak"
    code_area: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_coverage": self.line_coverage,
            "branch_coverage": self.branch_coverage,
            "uncovered_lines": self.uncovered_lines,
            "covered_lines": self.covered_lines,
            "coverage_report_id": self.coverage_report_id,
            "partially_covered_branches": self.partially_covered_branches,
            "related_flows": self.related_flows,
            "related_requirement_ids": self.related_requirement_ids,
            "coverage_strength": self.coverage_strength,
            "code_area": self.code_area,
        }


@dataclass
class ClassificationReport:
    """Final classification report with executive counts."""
    verified_by_current_pr_execution: int = 0
    failed_in_current_pr_execution: int = 0
    skipped_in_current_pr_execution: int = 0
    existing_test_not_run_in_current_pr: int = 0
    missing_automated_coverage: int = 0
    partially_covered: int = 0
    coverage_gap_only: int = 0
    optional_improvement: int = 0
    not_mapped_traceability_risk: int = 0
    excluded_fragment_or_test_data: int = 0
    total_requirements: int = 0
    uploaded_pr_tests_passed: int = 0
    uploaded_pr_tests_failed: int = 0
    uploaded_pr_tests_skipped: int = 0
    uploaded_pr_tests_total: int = 0
    ui_decision_copy: str = ""
    requirement_nodes: List[RequirementNode] = field(default_factory=list)
    excluded_fragments: List[Dict[str, Any]] = field(default_factory=list)
    junit_to_requirement_mapping: List[Dict[str, Any]] = field(default_factory=list)
    coverage_gap_mapping: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified_by_current_pr_execution": self.verified_by_current_pr_execution,
            "failed_in_current_pr_execution": self.failed_in_current_pr_execution,
            "skipped_in_current_pr_execution": self.skipped_in_current_pr_execution,
            "existing_test_not_run_in_current_pr": self.existing_test_not_run_in_current_pr,
            "missing_automated_coverage": self.missing_automated_coverage,
            "partially_covered": self.partially_covered,
            "coverage_gap_only": self.coverage_gap_only,
            "optional_improvement": self.optional_improvement,
            "not_mapped_traceability_risk": self.not_mapped_traceability_risk,
            "excluded_fragment_or_test_data": self.excluded_fragment_or_test_data,
            "total_requirements": self.total_requirements,
            "uploaded_pr_tests_passed": self.uploaded_pr_tests_passed,
            "uploaded_pr_tests_failed": self.uploaded_pr_tests_failed,
            "uploaded_pr_tests_skipped": self.uploaded_pr_tests_skipped,
            "uploaded_pr_tests_total": self.uploaded_pr_tests_total,
            "ui_decision_copy": self.ui_decision_copy,
            "requirement_nodes": [r.to_dict() for r in self.requirement_nodes],
            "excluded_fragments": self.excluded_fragments,
            "junit_to_requirement_mapping": self.junit_to_requirement_mapping,
            "coverage_gap_mapping": self.coverage_gap_mapping,
        }


class ScenarioSignatureGenerator:
    """Generates canonical scenario signatures from text."""

    @classmethod
    def generate_signature(cls, text: str, context: Dict[str, Any] = None) -> ScenarioSignature:
        """Generate a canonical scenario signature from text."""
        if context is None:
            context = {}

        text_lower = text.lower().replace("_", " ").replace("-", " ")

        # Extract flow
        flow = cls._extract_flow(text_lower, context.get("flow", ""))

        # Extract action
        action = cls._extract_action(text_lower, context.get("action", ""))

        # Extract condition
        condition = cls._extract_condition(text_lower, context.get("condition", ""))

        # Extract expected outcome
        expected_outcome = cls._extract_expected_outcome(text_lower, context.get("expected_outcome", ""))

        # Determine polarity
        polarity = cls._determine_polarity(expected_outcome)

        # Extract entity
        entity = cls._extract_entity(text_lower, context.get("entity", ""))

        # Determine validation layer
        validation_layer = cls._determine_validation_layer(text_lower, context.get("validation_layer", ""))

        # Extract security context
        security_context = cls._extract_security_context(text_lower, context.get("security_context", ""))

        # Extract data category
        data_category = cls._extract_data_category(text_lower, context.get("data_category", ""))

        return ScenarioSignature(
            flow=flow,
            action=action,
            condition=condition,
            expected_outcome=expected_outcome,
            subject=entity,
            validation_layer=validation_layer,
            polarity=polarity,
            security_context=security_context,
            data_category=data_category,
        )

    @classmethod
    def _extract_flow(cls, text_lower: str, context_flow: str) -> str:
        """Extract the flow from text."""
        if "atomic" in text_lower or "atomicity" in text_lower:
            return "account_security_validation"
        if "shared" in text_lower or "aligned" in text_lower or "shared/aligned" in text_lower:
            return "shared_password_policy"
        if "ui and api" in text_lower or "ui/api" in text_lower or "ui & api" in text_lower or "consistency" in text_lower or "consistent" in text_lower:
            return "ui_api_consistency"
        if "reset" in text_lower:
            return "password_reset"
        if "signup" in text_lower or "sign up" in text_lower:
            return "sign_up"
        if "update" in text_lower:
            return "update_password"
        if "login" in text_lower or "signin" in text_lower:
            return "login_after_password_change"

        if context_flow and context_flow.lower() not in ("general", "unknown"):
            mapped = context_flow.lower().replace("-", "_")
            if mapped == "signup":
                return "sign_up"
            elif mapped == "password_reset":
                return "password_reset"
            return mapped

        return "account_security_validation"

    @classmethod
    def _extract_action(cls, text_lower: str, context_action: str) -> str:
        """Extract the action from text."""
        if "atomic" in text_lower or "atomicity" in text_lower or "not update" in text_lower:
            return "preserve_atomicity"
        if "confirm" in text_lower or "confirmation" in text_lower or "mismatch" in text_lower:
            return "compare_confirmation"
        if "message" in text_lower or "friendly" in text_lower or "expose" in text_lower:
            return "validate_error_message"
        if "login" in text_lower or "signin" in text_lower:
            return "login"
        if "reject" in text_lower or "weak" in text_lower or "empty" in text_lower or "whitespace" in text_lower or "shorter" in text_lower:
            return "reject"
        if "reset" in text_lower:
            return "password_reset"
        if "update" in text_lower:
            return "update_password"
        if "token" in text_lower:
            if "expired" in text_lower or "reused" in text_lower or "reject" in text_lower:
                return "reject_token"
            return "accept_token"
        if "spaces" in text_lower or "leading" in text_lower or "trailing" in text_lower:
            return "reject"
        return "accept"

    @classmethod
    def _extract_condition(cls, text_lower: str, context_condition: str) -> str:
        """Extract the condition from text."""
        if "weak" in text_lower:
            if "api" in text_lower or "frontend" in text_lower or "bypass" in text_lower:
                return "direct_api_weak_password_request"
            return "weak_password"
        if "strong" in text_lower:
            return "strong_password"
        if "empty" in text_lower:
            return "empty_password"
        if "whitespace" in text_lower:
            return "whitespace"
        if "leading" in text_lower or "trailing" in text_lower:
            return "leading_trailing_spaces"
        if "confirm" in text_lower or "mismatch" in text_lower or "confirmation" in text_lower:
            return "confirmation_mismatch"
        if "valid unexpired" in text_lower or ("valid" in text_lower and "unexpired" in text_lower):
            return "valid_unexpired_token"
        if "expired" in text_lower:
            return "expired"
        if "reused" in text_lower:
            return "reused"
        if "login" in text_lower or "working" in text_lower or "broken" in text_lower:
            return "existing_valid_login"
        if "validation fails" in text_lower or "validation failing" in text_lower or ("validation" in text_lower and "fails" in text_lower):
            return "validation_failure"
        if "expose" in text_lower or "internal" in text_lower:
            return "internal_details_exposure"
        if "atomic" in text_lower or "atomicity" in text_lower:
            return "atomic_update_reset"
        return "strong_password"

    @classmethod
    def _extract_expected_outcome(cls, text_lower: str, context_outcome: str) -> str:
        """Extract the expected outcome from text."""
        if "atomic" in text_lower or "atomicity" in text_lower:
            return "operation_atomic"
        if "consistent" in text_lower or "consistency" in text_lower or "same" in text_lower:
            return "consistent"
        if "confirm" in text_lower or "confirmation" in text_lower or "mismatch" in text_lower:
            return "rejected"
        if "not update" in text_lower or "nothing changes" in text_lower:
            return "password_not_updated"
        if "updated" in text_lower:
            return "password_updated"
        if "login" in text_lower:
            if "succeed" in text_lower or "working" in text_lower or "login using" in text_lower or "can log in" in text_lower or "keep" in text_lower or "not broken" in text_lower:
                return "login_succeeds"
            return "login_fails"
        if "message" in text_lower:
            if "safe" in text_lower:
                return "error_message_safe"
            if "clear" in text_lower or "friendly" in text_lower:
                return "error_message_clear"
            if "expose" in text_lower or "internal" in text_lower:
                return "no_internal_details_exposed"
        if "reject" in text_lower or "shorter" in text_lower or "mismatch" in text_lower or "empty" in text_lower or "whitespace" in text_lower:
            return "rejected"
        if "token" in text_lower:
            if "succeed" in text_lower or "accept" in text_lower:
                return "token_accepted"
            return "token_rejected"
        return "accepted"

    @classmethod
    def _determine_polarity(cls, expected_outcome: str) -> str:
        """Determine polarity from expected outcome."""
        pos = {"accepted", "token_accepted", "login_succeeds", "password_updated", "consistent", "error_message_safe", "error_message_clear", "no_internal_details_exposed", "operation_atomic"}
        neg = {"rejected", "token_rejected", "login_fails", "password_not_updated"}
        if expected_outcome in pos:
            return "positive"
        elif expected_outcome in neg:
            return "negative"
        return "neutral"

    @classmethod
    def _extract_entity(cls, text_lower: str, context_entity: str) -> str:
        """Extract the entity from text."""
        if "new password" in text_lower:
            return "new_password"
        if "old password" in text_lower:
            return "old_password"
        if "password" in text_lower:
            return "password"
        if "token" in text_lower:
            return "reset_token"
        if "spaces" in text_lower or "leading" in text_lower or "trailing" in text_lower:
            return "password"
        if "api" in text_lower or "frontend" in text_lower or "bypass" in text_lower:
            if "rules" in text_lower or "same" in text_lower or "ui and api" in text_lower:
                return "ui_api_rules"
            return "api_request"
        if "confirm" in text_lower or "confirmation" in text_lower:
            return "confirmation_field"
        if "message" in text_lower or "expose" in text_lower:
            return "validation_message"
        if "policy" in text_lower or "shared" in text_lower or "aligned" in text_lower:
            return "password_policy"
        return "password"

    @classmethod
    def _determine_validation_layer(cls, text_lower: str, context_layer: str) -> str:
        """Determine the validation layer."""
        if "ui and api" in text_lower or "ui/api" in text_lower:
            return "cross_layer"
        if "api" in text_lower or "bypass" in text_lower or "frontend" in text_lower:
            if "rules" in text_lower or "same" in text_lower or "ui and api" in text_lower:
                return "cross_layer"
            return "api"
        if "ui" in text_lower:
            return "ui"
        if "e2e" in text_lower:
            return "e2e"
        if "unit" in text_lower:
            return "unit"
        if "integration" in text_lower:
            return "integration"
        return "backend"

    @classmethod
    def _extract_security_context(cls, text_lower: str, context_security: str) -> str:
        """Extract security context."""
        if "token" in text_lower:
            return "token"
        elif "password" in text_lower:
            return "password"
        elif "session" in text_lower:
            return "session"
        return ""

    @classmethod
    def _extract_data_category(cls, text_lower: str, context_data: str) -> str:
        """Extract data category."""
        if "password" in text_lower:
            return "password"
        elif "email" in text_lower:
            return "email"
        elif "username" in text_lower:
            return "username"
        return ""

    @classmethod
    def compute_signature_hash(cls, signature: ScenarioSignature) -> str:
        """Compute a hash for the signature for comparison."""
        import hashlib
        signature_dict = signature.to_dict()
        signature_str = "|".join(str(v) for v in signature_dict.values())
        return hashlib.sha256(signature_str.encode()).hexdigest()


import hashlib


class RequirementMatcher:
    """6-layer matching pipeline for requirements to tests."""

    # Normalization: remove filler words
    FILLER_WORDS = {
        "should", "verify", "test", "validation", "create", "must", "shall",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
        "be", "is", "are"
    }

    # High-value term weights
    TERM_WEIGHTS = {
        "expired": 0.15, "reused": 0.15, "valid": 0.12, "invalid": 0.12,
        "weak": 0.10, "strong": 0.10, "empty": 0.08, "whitespace": 0.08,
        "confirmation": 0.10, "mismatch": 0.10, "ui": 0.05, "api": 0.05,
        "bypass": 0.12, "reset": 0.08, "signup": 0.08, "update": 0.08,
        "login": 0.08, "token": 0.12, "session": 0.10
    }

    # Contradiction penalties
    OUTCOME_CONTRADICTION_PENALTY = 0.50
    CONDITION_CONTRADICTION_PENALTY = 0.40
    FLOW_CONTRADICTION_PENALTY = 0.25

    # Matching thresholds
    AUTO_MATCH_THRESHOLD = 0.85
    PROBABLE_MATCH_THRESHOLD = 0.65

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """Normalize title for comparison."""
        # Lowercase
        normalized = title.lower()
        # Remove leading numbering/prefixes like "7.", "AC-07", "07 -", "1 -"
        normalized = re.sub(r'^(?:ac[- ]*\d+|\d+)[-.\s]*', '', normalized, flags=re.IGNORECASE)
        # Remove punctuation
        normalized = re.sub(r'[^\w\s-]', ' ', normalized)
        # Replace underscores/hyphens with spaces
        normalized = re.sub(r'[_-]', ' ', normalized)
        # Split camelCase
        normalized = re.sub(r'([a-z])([A-Z])', r'\1 \2', normalized)
        
        # Simple stemming map
        stem_map = {
            "rejection": "rejected", "rejects": "rejected", "reject": "rejected",
            "accepted": "accepted", "acceptance": "accepted", "accepts": "accepted", "accept": "accepted",
            "reused": "reused", "reuses": "reused", "reuse": "reused",
            "validating": "validation", "validated": "validation", "validate": "validation",
            "failed": "failed", "failure": "failed", "failures": "failed", "fails": "failed", "fail": "failed",
            "skipped": "skipped", "skips": "skipped", "skip": "skipped",
            "tested": "test", "testing": "test", "tests": "test"
        }
        
        words = []
        for w in normalized.split():
            if w in cls.FILLER_WORDS:
                continue
            words.append(stem_map.get(w, w))
        return ' '.join(words)

    @classmethod
    def match_requirement_to_test(
        cls,
        requirement: RequirementNode,
        test: TestNode,
        execution: Optional[ExecutionNode] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """Match a requirement to a test using 6-layer pipeline.

        Returns:
            Tuple of (score, diagnostics)
        """
        diagnostics = {
            "layer_scores": {},
            "penalties": [],
            "signals": []
        }

        # Check if the test case has a declared_ac_id value
        declared_ac_id = getattr(test, "declared_ac_id", None)
        if not declared_ac_id and test.acceptance_criterion_metadata:
            declared_ac_id = test.acceptance_criterion_metadata.get("acceptance_criterion_id") or test.acceptance_criterion_metadata.get("ac_id")

        if declared_ac_id is not None:
            from app.db.session import SessionLocal
            from app.models.acceptance_criterion import AcceptanceCriterion
            from sqlalchemy import func, or_
            
            matched_ac = None
            try:
                with SessionLocal() as db:
                    curr_ac = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == requirement.requirement_id).first()
                    if curr_ac:
                        repo_id = curr_ac.repository_id
                        val = str(declared_ac_id).lower()
                        
                        model_cols = [c.name for c in AcceptanceCriterion.__table__.columns]
                        filters = []
                        if "normalized_key" in model_cols:
                            filters.append(func.lower(AcceptanceCriterion.normalized_key) == val)
                            filters.append(func.lower(AcceptanceCriterion.normalized_key).contains(val))
                        if "external_id" in model_cols:
                            filters.append(func.lower(AcceptanceCriterion.external_id) == val)
                            filters.append(func.lower(AcceptanceCriterion.external_id).contains(val))
                        if "label" in model_cols:
                            filters.append(func.lower(AcceptanceCriterion.label) == val)
                            filters.append(func.lower(AcceptanceCriterion.label).contains(val))
                        if "text" in model_cols:
                            filters.append(func.lower(AcceptanceCriterion.text) == val)
                            filters.append(func.lower(AcceptanceCriterion.text).contains(val))
                            
                        matched_ac = db.query(AcceptanceCriterion).filter(
                            AcceptanceCriterion.repository_id == repo_id,
                            or_(*filters)
                        ).first()
            except Exception:
                pass
                
            if matched_ac:
                if str(matched_ac.id) == str(requirement.requirement_id):
                    diagnostics["signals"].append("Direct ID match")
                    diagnostics["layer_scores"]["direct_id"] = 1.0
                    diagnostics["mapping_type"] = "DIRECT_AC_ID"
                    return 1.0, diagnostics
                else:
                    return 0.0, diagnostics
            else:
                # Fallback to local python object matching if database query failed or returned None
                val = str(declared_ac_id).lower()
                if (val == requirement.requirement_id.lower() or
                    val in requirement.requirement_id.lower() or
                    val == requirement.readable_id.lower() or
                    val in requirement.readable_id.lower() or
                    val == requirement.title.lower() or
                    val in requirement.title.lower()):
                    diagnostics["signals"].append("Direct ID match")
                    diagnostics["layer_scores"]["direct_id"] = 1.0
                    diagnostics["mapping_type"] = "DIRECT_AC_ID"
                    return 1.0, diagnostics

        total_score = 0.0

        # Layer 1: Direct IDs
        direct_id_score = cls._layer1_direct_id(requirement, test)
        diagnostics["layer_scores"]["direct_id"] = direct_id_score
        if direct_id_score >= 1.0:
            total_score = 1.0
            diagnostics["signals"].append("Direct ID match")
            return total_score, diagnostics
        total_score += direct_id_score * 0.3

        # Layer 2: Exact normalized title
        title_score = cls._layer2_title_match(requirement, test)
        diagnostics["layer_scores"]["title"] = title_score
        
        # Layer 3: Signature match
        signature_score, signature_diagnostics = cls._layer3_signature_match(requirement, test)
        diagnostics["layer_scores"]["signature"] = signature_score
        diagnostics["signature_diagnostics"] = signature_diagnostics
        
        if title_score >= 0.95:
            diagnostics["signals"].append("Exact title match")
            return 1.0, diagnostics
        total_score += title_score * 0.3
        total_score += signature_score * 0.65

        # Apply contradiction penalties from signature layer
        if signature_diagnostics.get("outcome_contradiction"):
            total_score -= cls.OUTCOME_CONTRADICTION_PENALTY
            diagnostics["penalties"].append(f"Outcome contradiction: -{cls.OUTCOME_CONTRADICTION_PENALTY}")
        if signature_diagnostics.get("condition_contradiction"):
            total_score -= cls.CONDITION_CONTRADICTION_PENALTY
            diagnostics["penalties"].append(f"Condition contradiction: -{cls.CONDITION_CONTRADICTION_PENALTY}")
        if signature_diagnostics.get("flow_contradiction"):
            total_score -= cls.FLOW_CONTRADICTION_PENALTY
            diagnostics["penalties"].append(f"Flow contradiction: -{cls.FLOW_CONTRADICTION_PENALTY}")

        # Layer 4: Path hints
        path_score = cls._layer4_path_hints(requirement, test)
        diagnostics["layer_scores"]["path"] = path_score
        total_score += path_score * 0.20

        # Layer 5: Keyword scoring
        keyword_score = cls._layer5_keyword_scoring(requirement, test)
        diagnostics["layer_scores"]["keyword"] = keyword_score
        total_score += keyword_score * 0.15

        # Cap at 1.0
        total_score = min(1.0, max(0.0, total_score))

        return total_score, diagnostics

    @classmethod
    def _layer1_direct_id(cls, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 1: Direct ID matching."""
        # Check if test is explicitly mapped to requirement
        if requirement.requirement_id in test.mapped_requirement_ids:
            return 1.0
        return 0.0

    @classmethod
    def _layer2_title_match(cls, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 2: Exact normalized title matching."""
        req_normalized = cls.normalize_title(requirement.title)
        test_normalized = cls.normalize_title(test.title)

        if req_normalized == test_normalized:
            return 1.0

        # Check for partial overlap
        req_words = set(req_normalized.split())
        test_words = set(test_normalized.split())

        if req_words and test_words:
            overlap = len(req_words & test_words) / len(req_words | test_words)
            return overlap

        return 0.0

    @classmethod
    def _layer3_signature_match(cls, requirement: RequirementNode, test: TestNode) -> Tuple[float, Dict[str, Any]]:
        """Layer 3: Signature matching."""
        if not requirement.scenario_signature or not test.scenario_signature:
            return 0.0, {}

        req_sig = requirement.scenario_signature
        test_sig = test.scenario_signature

        diagnostics = {
            "outcome_contradiction": False,
            "condition_contradiction": False,
            "flow_contradiction": False
        }

        score = 0.0

        # Check expected outcome (highest weight)
        if req_sig.expected_outcome == test_sig.expected_outcome:
            score += 0.4
        elif cls._are_outcomes_contradictory(req_sig.expected_outcome, test_sig.expected_outcome):
            diagnostics["outcome_contradiction"] = True

        # Check condition
        if req_sig.condition == test_sig.condition:
            score += 0.25
        elif cls._are_conditions_contradictory(req_sig.condition, test_sig.condition):
            diagnostics["condition_contradiction"] = True

        # Check flow
        if req_sig.flow == test_sig.flow:
            score += 0.2
        elif req_sig.flow != "unknown" and test_sig.flow != "unknown":
            # Different flows - penalty unless it's a global rule
            diagnostics["flow_contradiction"] = True

        # Check action
        if req_sig.action == test_sig.action:
            score += 0.15

        return score, diagnostics

    @classmethod
    def _are_outcomes_contradictory(cls, outcome1: str, outcome2: str) -> bool:
        """Check if two outcomes are contradictory."""
        contradictory_pairs = [
            ("accepted", "rejected"),
            ("allowed", "blocked"),
            ("success", "failure"),
            ("verified", "error"),
        ]
        for o1, o2 in contradictory_pairs:
            if (outcome1 == o1 and outcome2 == o2) or (outcome1 == o2 and outcome2 == o1):
                return True
        return False

    @classmethod
    def _are_conditions_contradictory(cls, condition1: str, condition2: str) -> bool:
        """Check if two conditions are contradictory."""
        contradictory_pairs = [
            ("valid", "invalid"),
            ("expired", "unexpired"),
            ("reused", "first-use"),
            ("weak", "strong"),
            ("empty", "non-empty"),
            ("old", "new"),
            ("expired", "valid"),
            ("reused", "valid"),
        ]
        for c1, c2 in contradictory_pairs:
            if (condition1 == c1 and condition2 == c2) or (condition1 == c2 and condition2 == c1):
                return True
        return False

    @classmethod
    def _layer4_path_hints(cls, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 4: Path/classname hints."""
        score = 0.0

        # Check classname for flow hints
        test_class_lower = test.classname.lower()
        req_flow_lower = requirement.flow.lower()

        # Flow-specific path hints
        flow_hints = {
            "password_reset": ["reset", "password", "reset-password"],
            "sign_up": ["signup", "sign-up", "register", "registration"],
            "update_password": ["update", "password", "change"],
            "login": ["login", "auth", "authentication"],
        }

        if req_flow_lower in flow_hints:
            for hint in flow_hints[req_flow_lower]:
                if hint in test_class_lower or hint in test.file_path.lower():
                    score = 1.0
                    break

        return score

    @classmethod
    def _layer5_keyword_scoring(cls, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 5: Keyword/intent scoring."""
        req_text_lower = requirement.title.lower()
        test_text_lower = test.title.lower()

        score = 0.0

        # Score based on high-value terms
        for term, weight in cls.TERM_WEIGHTS.items():
            if term in req_text_lower and term in test_text_lower:
                score += weight

        return min(1.0, score)


class RegressionEvidenceClassifier:
    """Main classifier service - canonical source of truth."""

    def __init__(self):
        self.signature_generator = ScenarioSignatureGenerator()
        self.matcher = RequirementMatcher()

    def classify(
        self,
        requirements: List[RequirementNode],
        tests: List[TestNode],
        executions: List[ExecutionNode],
        coverage_nodes: List[CoverageNode],
        excluded_fragments: List[Dict[str, Any]]
    ) -> ClassificationReport:
        """Classify all requirements into evidence buckets.

        This is the canonical entry point for regression evidence classification.
        """
        report = ClassificationReport()
        report.excluded_fragments = excluded_fragments
        report.total_requirements = len(requirements)

        # Count PR execution stats
        report.uploaded_pr_tests_total = len(executions)
        report.uploaded_pr_tests_passed = sum(1 for e in executions if e.status == "passed")
        report.uploaded_pr_tests_failed = sum(1 for e in executions if e.status == "failed")
        report.uploaded_pr_tests_skipped = sum(1 for e in executions if e.status == "skipped")

        # Build test and execution maps
        test_map = {t.test_id: t for t in tests}
        execution_map = {e.test_id: e for e in executions}

        # Generate signatures for all requirements and tests
        for req in requirements:
            if not req.scenario_signature:
                req.scenario_signature = self.signature_generator.generate_signature(req.title)

        for test in tests:
            if not test.scenario_signature:
                test.scenario_signature = self.signature_generator.generate_signature(test.title)
                test.scenario_signature_hash = ScenarioSignatureGenerator.compute_signature_hash(test.scenario_signature)

        # Classify each requirement
        for req in requirements:
            classification = self._classify_single_requirement(
                req, test_map, execution_map, coverage_nodes
            )
            report.requirement_nodes.append(req)

            # Update counts
            if req.classification == EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION:
                report.verified_by_current_pr_execution += 1
            elif req.classification == EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION:
                report.failed_in_current_pr_execution += 1
            elif req.classification == EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION:
                report.skipped_in_current_pr_execution += 1
            elif req.classification == EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR:
                report.existing_test_not_run_in_current_pr += 1
            elif req.classification == EvidenceClassification.MISSING_AUTOMATED_COVERAGE:
                report.missing_automated_coverage += 1
            elif req.classification == EvidenceClassification.PARTIALLY_COVERED:
                report.partially_covered += 1
            elif req.classification == EvidenceClassification.COVERAGE_GAP_ONLY:
                report.coverage_gap_only += 1
            elif req.classification == EvidenceClassification.OPTIONAL_IMPROVEMENT:
                report.optional_improvement += 1
            elif req.classification == EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK:
                report.not_mapped_traceability_risk += 1
            elif req.classification == EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA:
                report.excluded_fragment_or_test_data += 1

        # Generate JUnit to requirement mapping
        report.junit_to_requirement_mapping = self._generate_junit_mapping(requirements, executions)

        # Generate coverage gap mapping
        report.coverage_gap_mapping = self._generate_coverage_mapping(requirements, coverage_nodes)

        # Generate UI decision copy
        report.ui_decision_copy = self._generate_ui_decision_copy(report)

        return report

    def _classify_single_requirement(
        self,
        req: RequirementNode,
        test_map: Dict[str, TestNode],
        execution_map: Dict[str, ExecutionNode],
        coverage_nodes: List[CoverageNode]
    ) -> EvidenceClassification:
        """Classify a single requirement according to the rules."""
        # Rule: Exclude fragments
        if not req.is_real_testable_requirement:
            req.classification = EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
            req.classification_reason = "Not a real testable requirement (fragment or test data)"
            return req.classification

        # Find best matching test
        best_match_score = 0.0
        best_match_test_id = None
        best_match_diagnostics = {}

        for test_id, test in test_map.items():
            score, diagnostics = self.matcher.match_requirement_to_test(req, test)
            if score > best_match_score:
                best_match_score = score
                best_match_test_id = test_id
                best_match_diagnostics = diagnostics

        req.match_score = best_match_score
        req.match_diagnostics = best_match_diagnostics

        # Check if any execution matches this requirement
        matched_execution = None
        for exec_id, execution in execution_map.items():
            if best_match_test_id and execution.mapped_test_node_id == best_match_test_id:
                matched_execution = execution
                req.matched_execution_ids.append(exec_id)
                break

        # Rule 1: If current PR execution maps and status=passed
        if matched_execution and matched_execution.status == "passed":
            if best_match_score >= RequirementMatcher.AUTO_MATCH_THRESHOLD:
                req.classification = EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION
                req.classification_reason = f"Verified by current PR execution (score: {best_match_score:.2f})"
                req.matched_test_ids = [best_match_test_id]
                return req.classification

        # Rule 2: If current PR execution maps and status=failed/error
        if matched_execution and matched_execution.status in ("failed", "error"):
            req.classification = EvidenceClassification.FAILED_IN_CURRENT_PR_EXECUTION
            req.classification_reason = f"Failed in current PR execution: {matched_execution.status}"
            req.matched_test_ids = [best_match_test_id]
            return req.classification

        # Rule 3: If current PR execution maps and status=skipped
        if matched_execution and matched_execution.status == "skipped":
            req.classification = EvidenceClassification.SKIPPED_IN_CURRENT_PR_EXECUTION
            req.classification_reason = f"Skipped in current PR execution"
            req.matched_test_ids = [best_match_test_id]
            return req.classification

        # Rule 4: If existing automated test maps but no current PR execution
        if best_match_test_id and best_match_score >= RequirementMatcher.AUTO_MATCH_THRESHOLD:
            test = test_map[best_match_test_id]
            if test.automation_status == "existing_automated":
                req.classification = EvidenceClassification.EXISTING_TEST_NOT_RUN_IN_CURRENT_PR
                req.classification_reason = f"Existing automated test matches (score: {best_match_score:.2f}) but not executed in current PR"
                req.matched_test_ids = [best_match_test_id]
                return req.classification

        # Rule 5: If no current PR execution and no existing automated test maps
        if not best_match_test_id or best_match_score < RequirementMatcher.PROBABLE_MATCH_THRESHOLD:
            # Check if there's coverage evidence
            has_coverage = self._check_coverage_evidence(req, coverage_nodes)
            if has_coverage:
                req.classification = EvidenceClassification.PARTIALLY_COVERED
                req.classification_reason = "Only coverage evidence exists, no test match above threshold"
            else:
                req.classification = EvidenceClassification.MISSING_AUTOMATED_COVERAGE
                req.classification_reason = "No existing automated test or current PR execution found"
            return req.classification

        # Rule 8: If it's a real AC but mapper cannot confidently connect it
        req.classification = EvidenceClassification.NOT_MAPPED_TRACEABILITY_RISK
        req.classification_reason = f"Real AC but no confident match (score: {best_match_score:.2f})"
        return req.classification

    def _check_coverage_evidence(self, req: RequirementNode, coverage_nodes: List[CoverageNode]) -> bool:
        """Check if there's coverage evidence for this requirement."""
        for coverage in coverage_nodes:
            if req.requirement_id in coverage.related_requirement_ids:
                return True
            if req.flow in coverage.related_flows:
                return True
        return False

    def _generate_junit_mapping(self, requirements: List[RequirementNode], executions: List[ExecutionNode]) -> List[Dict[str, Any]]:
        """Generate JUnit to requirement mapping table."""
        mapping = []
        for exec_node in executions:
            mapped_reqs = [req for req in requirements if exec_node.test_id in req.matched_execution_ids]
            mapping.append({
                "test_id": exec_node.test_id,
                "test_name": exec_node.test_name,
                "status": exec_node.status,
                "mapped_requirement_ids": [req.requirement_id for req in mapped_reqs],
                "mapped_requirement_titles": [req.title for req in mapped_reqs],
            })
        return mapping

    def _generate_coverage_mapping(self, requirements: List[RequirementNode], coverage_nodes: List[CoverageNode]) -> List[Dict[str, Any]]:
        """Generate coverage gap mapping table."""
        mapping = []
        for coverage in coverage_nodes:
            mapped_reqs = [req for req in requirements if req.requirement_id in coverage.related_requirement_ids]
            mapping.append({
                "file_path": coverage.file_path,
                "line_coverage": coverage.line_coverage,
                "branch_coverage": coverage.branch_coverage,
                "coverage_strength": coverage.coverage_strength,
                "related_requirement_ids": [req.requirement_id for req in mapped_reqs],
                "related_requirement_titles": [req.title for req in mapped_reqs],
            })
        return mapping

    def _generate_ui_decision_copy(self, report: ClassificationReport) -> str:
        """Generate user-facing decision copy based on classification results."""
        # Never say "No remaining tests" unless all gaps are zero
        if (report.missing_automated_coverage == 0 and
            report.existing_test_not_run_in_current_pr == 0 and
            report.failed_in_current_pr_execution == 0 and
            report.skipped_in_current_pr_execution == 0 and
            report.coverage_gap_only == 0 and
            report.partially_covered == 0 and
            report.not_mapped_traceability_risk == 0):

            return "All required regression evidence is covered. No remaining existing tests or missing automated scenarios were found."

        # If missing automated coverage exists
        if report.missing_automated_coverage > 0:
            if report.uploaded_pr_tests_passed > 0:
                return f"Current PR execution passed all {report.uploaded_pr_tests_passed} uploaded tests. Veriscope found {report.missing_automated_coverage} missing automated scenarios."
            else:
                return f"Veriscope found {report.missing_automated_coverage} missing automated scenarios."

        # If required existing tests were not included in execution
        if report.existing_test_not_run_in_current_pr > 0:
            return f"Current PR execution passed {report.uploaded_pr_tests_passed} tests. {report.existing_test_not_run_in_current_pr} required existing tests were not included in this run."

        # If only optional gaps remain
        if report.optional_improvement > 0:
            return f"Current PR execution passed all selected tests. Only optional coverage improvements remain."

        # Default
        return f"Current PR execution passed {report.uploaded_pr_tests_passed} tests. Additional verification may be required."
