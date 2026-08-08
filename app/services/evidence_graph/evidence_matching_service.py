"""Evidence Matching Service - Matches requirements to tests and executions.

This service implements the 6-layer matching pipeline with scoring
and contradiction detection.
"""
import re
from typing import Dict, Any, Tuple, List
from dataclasses import dataclass, field

from app.services.regression_evidence_classifier import (
    RequirementNode,
    TestNode,
    ExecutionNode,
    ScenarioSignature,
)


@dataclass
class MatchResult:
    """Result of matching a requirement to a test."""
    score: float
    diagnostics: Dict[str, Any]
    test_id: str


@dataclass
class MatchTableEntry:
    """Entry in the match table for diagnostics."""
    requirement_id: str
    requirement_title: str
    candidate_test_title: str
    score: float
    decision: str
    reason: str
    contradiction_penalty: float
    rejection_reason: str = ""
    contradiction_rule_triggered: str = ""
    matching_dimensions: Dict[str, Any] = field(default_factory=dict)
    current_pr_execution_id: str = ""
    mapping_type: str = "FUZZY"
class EvidenceMatchingService:
    """Service for matching requirements to evidence using 6-layer pipeline."""

    # Normalization: remove filler words
    FILLER_WORDS = {
        "should", "verify", "test", "validation", "create", "check", "ensure", "scenario"
    }

    # Domain terms to preserve (not remove)
    DOMAIN_TERMS = {
        "weak", "strong", "password", "signup", "sign-up", "update", "reset", "token",
        "expired", "reused", "valid", "invalid", "empty", "whitespace", "confirmation",
        "mismatch", "api", "ui", "bypass", "login", "old password", "new password"
    }

    # Verb normalization map
    VERB_NORMALIZATION = {
        "rejected": "reject",
        "rejects": "reject",
        "rejecting": "reject",
        "accepted": "accept",
        "accepts": "accept",
        "accepting": "accept",
        "succeeds": "success",
        "successful": "success",
        "fails": "fail",
        "failure": "fail",
        "updated": "update",
        "update": "update"
    }

    # High-value term weights
    TERM_WEIGHTS = {
        "expired": 0.15, "reused": 0.15, "valid": 0.12, "invalid": 0.12,
        "weak": 0.10, "strong": 0.10, "empty": 0.08, "whitespace": 0.08,
        "confirmation": 0.10, "mismatch": 0.10, "ui": 0.05, "api": 0.05,
        "bypass": 0.12, "reset": 0.08, "signup": 0.08, "update": 0.08,
        "login": 0.08, "token": 0.12, "session": 0.10,
        "old password": 0.15, "new password": 0.15, "atomic": 0.10, "error message": 0.10,
        "minimum": 0.10, "length": 0.10, "complexity": 0.25
    }

    # Contradiction penalties
    OUTCOME_CONTRADICTION_PENALTY = 1.0
    CONDITION_CONTRADICTION_PENALTY = 1.0
    FLOW_CONTRADICTION_PENALTY = 1.0

    # Flow contradiction pairs
    FLOW_CONTRADICTIONS = [
        ("sign_up", "password_reset"),
        ("sign_up", "update_password"),
        ("password_reset", "update_password"),
        ("password_reset", "login"),
        ("update_password", "login"),
    ]

    # Matching thresholds (as specified)
    AUTO_MATCH_THRESHOLD = 0.85
    PROBABLE_MATCH_THRESHOLD = 0.65

    def _norm(self, value: str) -> str:
        """Internal casing normalization helper."""
        if not value:
            return ""
        return value.strip().upper()

    def _norm_set(self, values: Any) -> set:
        """Internal casing normalization set helper."""
        if not values:
            return set()
        return {self._norm(v) for v in values if v}

    def __init__(self):
        self.match_table: List[MatchTableEntry] = []

    def match_requirement_to_test(
        self,
        requirement: RequirementNode,
        test: TestNode,
        execution: ExecutionNode = None
    ) -> MatchResult:
        """Match a requirement to a test using layered scoring with hard contradiction gate."""
        diagnostics = {
            "layer_scores": {},
            "penalties": [],
            "signals": [],
            "matching_dimensions": {}
        }

        # Step 1: Hard Contradiction Gate - reject before any scoring
        contradiction_result = self._check_hard_contradictions(requirement, test)
        if contradiction_result["is_contradiction"]:
            diagnostics["rejection_reason"] = contradiction_result["reason"]
            diagnostics["contradiction_rule_triggered"] = contradiction_result["rule"]
            diagnostics["matching_dimensions"] = contradiction_result["dimensions"]
            diagnostics["signature_diagnostics"] = {
                "outcome_contradiction": "OUTCOME" in contradiction_result["rule"] or "ACCEPTED" in contradiction_result["rule"],
                "condition_contradiction": "CONDITION" in contradiction_result["rule"] or "PASSWORD" in contradiction_result["rule"] or "TOKEN" in contradiction_result["rule"],
                "flow_contradiction": "FLOW" in contradiction_result["rule"] or "SIGN_UP" in contradiction_result["rule"] or "RESET" in contradiction_result["rule"] or "UPDATE" in contradiction_result["rule"],
                "contradiction_penalty": 1.0
            }
            
            # Flag JUNIT_AC_ID_MISMATCH diagnostic
            meta = test.acceptance_criterion_metadata
            if meta:
                ac_id = meta.get("acceptance_criterion_id") or meta.get("ac_id")
                if ac_id and (requirement.readable_id == ac_id or requirement.requirement_id == ac_id):
                    diagnostics["JUNIT_AC_ID_MISMATCH"] = True
                    diagnostics["rejection_reason"] = f"JUnit AC ID mismatch: test claims {ac_id} but contradicts its definition."
            
            return MatchResult(score=0.0, diagnostics=diagnostics, test_id=test.test_id)

        # Step 2: Exact Signature Match
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
                    diagnostics["matching_dimensions"] = self._get_matching_dimensions(requirement, test)
                    return MatchResult(score=1.0, diagnostics=diagnostics, test_id=test.test_id)
                else:
                    return MatchResult(score=0.0, diagnostics=diagnostics, test_id=test.test_id)
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
                    diagnostics["matching_dimensions"] = self._get_matching_dimensions(requirement, test)
                    return MatchResult(score=1.0, diagnostics=diagnostics, test_id=test.test_id)

        exact_match_score = self._check_exact_signature_match(requirement, test)
        diagnostics["layer_scores"]["exact_signature"] = exact_match_score
        if exact_match_score >= 1.0:
            diagnostics["signals"].append("Exact signature match")
            diagnostics["matching_dimensions"] = self._get_matching_dimensions(requirement, test)
            return MatchResult(score=1.0, diagnostics=diagnostics, test_id=test.test_id)

        # Step 3: Layer 1 - Direct ID Match
        direct_id_score = self._layer1_direct_id(requirement, test)
        diagnostics["layer_scores"]["direct_id"] = direct_id_score
        if direct_id_score >= 1.0:
            diagnostics["signals"].append("Direct ID match")
            diagnostics["matching_dimensions"] = self._get_matching_dimensions(requirement, test)
            return MatchResult(score=1.0, diagnostics=diagnostics, test_id=test.test_id)

        # Step 4: Layer 2 - Normalized Title Match
        title_score = self._layer2_title_match(requirement, test)
        normalized_title_score = title_score * 0.30
        diagnostics["layer_scores"]["title"] = title_score
        diagnostics["layer_scores"]["normalized_title_score"] = normalized_title_score

        # Step 5: Layer 3 - Flow Match
        flow_score = 0.20 if (requirement.scenario_signature and test.scenario_signature and self._norm(requirement.scenario_signature.flow) == self._norm(test.scenario_signature.flow) and self._norm(requirement.scenario_signature.flow) != "UNKNOWN") else 0.0
        diagnostics["layer_scores"]["flow_score"] = flow_score

        # Step 6: Layer 4 - Action Match
        action_score = 0.15 if (requirement.scenario_signature and test.scenario_signature and self._norm(requirement.scenario_signature.action) == self._norm(test.scenario_signature.action) and self._norm(requirement.scenario_signature.action) != "UNKNOWN") else 0.0
        diagnostics["layer_scores"]["action_score"] = action_score

        # Step 7: Layer 5 - Condition Match
        condition_score = 0.15 if (requirement.scenario_signature and test.scenario_signature and self._norm(requirement.scenario_signature.condition) == self._norm(test.scenario_signature.condition) and self._norm(requirement.scenario_signature.condition) != "UNKNOWN") else 0.0
        diagnostics["layer_scores"]["condition_score"] = condition_score

        # Step 8: Layer 6 - Expected Outcome Match
        outcome_score = 0.15 if (requirement.scenario_signature and test.scenario_signature and self._norm(requirement.scenario_signature.expected_outcome) == self._norm(test.scenario_signature.expected_outcome) and self._norm(requirement.scenario_signature.expected_outcome) != "UNKNOWN") else 0.0
        diagnostics["layer_scores"]["outcome_score"] = outcome_score

        # Step 9: Layer 7 - Validation Layer Compatibility
        validation_layer_score = self._check_validation_layer_compatibility(requirement, test)
        diagnostics["layer_scores"]["validation_layer_score"] = validation_layer_score

        # Step 10: Layer 8 - Subject Compatibility
        subject_score = self._check_subject_compatibility(requirement, test)
        diagnostics["layer_scores"]["subject_score"] = subject_score

        # Step 11: Layer 9 - Path hints
        path_hint_score = self._layer4_path_hints(requirement, test) * 0.05
        diagnostics["layer_scores"]["path_hint_score"] = path_hint_score

        # Step 12: Layer 10 - Keyword scoring
        keyword_score = self._layer5_keyword_scoring(requirement, test) * 0.10
        diagnostics["layer_scores"]["keyword_score"] = keyword_score

        # Step 13: Layer 11 - Semantic similarity (only after all above)
        semantic_score = self._calculate_semantic_similarity(requirement, test) * 0.05
        diagnostics["layer_scores"]["semantic_score"] = semantic_score

        # Compute total score
        total_score = direct_id_score + normalized_title_score + flow_score + action_score + condition_score + outcome_score + validation_layer_score + subject_score + path_hint_score + keyword_score + semantic_score
        total_score = min(1.0, max(0.0, total_score))

        # Store matching dimensions
        diagnostics["matching_dimensions"] = self._get_matching_dimensions(requirement, test)

        # Preserve signature_diagnostics format for existing code/tests
        diagnostics["signature_diagnostics"] = {
            "outcome_contradiction": False,
            "condition_contradiction": False,
            "flow_contradiction": False,
            "contradiction_penalty": 0.0
        }

        return MatchResult(score=total_score, diagnostics=diagnostics, test_id=test.test_id)

    def find_best_match(
        self,
        requirement: RequirementNode,
        tests: List[TestNode],
        execution: ExecutionNode = None
    ) -> Tuple[MatchResult, bool]:
        """Find the best matching test for a requirement."""
        best_score = 0.0
        best_result = None
        best_test = None

        for test in tests:
            result = self.match_requirement_to_test(requirement, test, execution)
            if result.score > best_score:
                best_score = result.score
                best_result = result
                best_test = test

        # Add to match table
        if best_result and best_test:
            decision = "ACCEPTED" if best_score >= self.AUTO_MATCH_THRESHOLD else (
                "PARTIAL" if best_score >= self.PROBABLE_MATCH_THRESHOLD else "REJECTED"
            )
            reason = self._get_match_reason(best_result)

            rejection_reason = best_result.diagnostics.get("rejection_reason", "")
            contradiction_rule = best_result.diagnostics.get("contradiction_rule_triggered", "")
            matching_dimensions = best_result.diagnostics.get("matching_dimensions", {})
            execution_id = execution.test_id if execution else ""
            mapping_type = best_result.diagnostics.get("mapping_type", "FUZZY")

            self.match_table.append(MatchTableEntry(
                requirement_id=requirement.requirement_id,
                requirement_title=requirement.title,
                candidate_test_title=best_test.title,
                score=best_score,
                decision=decision,
                reason=reason,
                contradiction_penalty=0.0,  # Already handled by hard gate
                rejection_reason=rejection_reason,
                contradiction_rule_triggered=contradiction_rule,
                matching_dimensions=matching_dimensions,
                current_pr_execution_id=execution_id,
                mapping_type=mapping_type
            ))

        is_confident = best_score >= self.AUTO_MATCH_THRESHOLD if best_result else False
        return best_result, is_confident

    def _layer1_direct_id(self, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 1: Direct ID matching with source hash constraints."""
        meta = test.acceptance_criterion_metadata
        if meta:
            ac_id = meta.get("acceptance_criterion_id") or meta.get("ac_id")
            source_hash = meta.get("source_hash") or meta.get("hash")
            
            if ac_id and (requirement.readable_id == ac_id or requirement.requirement_id == ac_id):
                # Reject if meaning contradicts current AC definition
                contradiction_result = self._check_hard_contradictions(requirement, test)
                if contradiction_result["is_contradiction"]:
                    return 0.0
                
                # Verify source hash / catalog ID match
                if source_hash and requirement.source_hash and source_hash == requirement.source_hash:
                    # Strong evidence, subject to contradiction gates (already checked)
                    return 1.0
                else:
                    # Missing/mismatched source hash: weak hint, signature compatibility required
                    return 0.5

        if requirement.requirement_id == test.test_id:
            return 1.0
        if test.mapped_requirement_ids:
            if requirement.requirement_id in test.mapped_requirement_ids:
                return 1.0
            if requirement.readable_id and requirement.readable_id in test.mapped_requirement_ids:
                return 1.0
        return 0.0

    def _layer2_title_match(self, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 2: Exact normalized title matching."""
        req_normalized = self.normalize_title(requirement.title)
        test_normalized = self.normalize_title(test.title)

        if req_normalized == test_normalized:
            return 1.0

        req_words = set(req_normalized.split())
        test_words = set(test_normalized.split())

        if req_words and test_words:
            overlap = len(req_words & test_words) / len(req_words | test_words)
            if overlap >= 0.7:
                return min(0.95, overlap + 0.2)
            return overlap

        return 0.0

    def _check_hard_contradictions(self, requirement: RequirementNode, test: TestNode) -> Dict[str, Any]:
        """Check hard contradiction rules case-insensitively - reject match if any contradiction exists."""
        req_sig = requirement.scenario_signature
        test_sig = test.scenario_signature
        
        if not req_sig or not test_sig:
            return {"is_contradiction": False, "reason": "", "rule": "", "dimensions": {}}

        req_norm = self.normalize_title(requirement.title)
        test_norm = self.normalize_title(test.title)

        def in_title(title_str, phrase):
            return f" {phrase} " in f" {title_str} "

        contradictions = []

        req_flow = self._norm(req_sig.flow)
        test_flow = self._norm(test_sig.flow)
        req_action = self._norm(req_sig.action)
        test_action = self._norm(test_sig.action)
        req_condition = self._norm(req_sig.condition)
        test_condition = self._norm(test_sig.condition)
        req_outcome = self._norm(req_sig.expected_outcome)
        test_outcome = self._norm(test_sig.expected_outcome)
        req_subject = self._norm(req_sig.subject)
        test_subject = self._norm(test_sig.subject)
        req_val_layer = self._norm(req_sig.validation_layer)
        test_val_layer = self._norm(test_sig.validation_layer)

        # 1. ACCEPTED vs REJECTED
        is_accepted_vs_rejected = False
        if (in_title(req_norm, "accept") and in_title(test_norm, "reject")) or \
           (in_title(req_norm, "reject") and in_title(test_norm, "accept")) or \
           (req_outcome == "ACCEPTED" and test_outcome == "REJECTED") or \
           (req_outcome == "REJECTED" and test_outcome == "ACCEPTED"):
            is_accepted_vs_rejected = True
        
        policy_keywords = {"enforce", "enforced", "mandatory", "require", "required", "policy", "consistency", "consistent"}
        if is_accepted_vs_rejected:
            if any(kw in req_norm for kw in policy_keywords) or any(kw in test_norm for kw in policy_keywords):
                is_accepted_vs_rejected = False
                
        if is_accepted_vs_rejected:
            contradictions.append("ACCEPTED vs REJECTED")

        # 2. STRONG_PASSWORD vs WEAK_PASSWORD
        if (in_title(req_norm, "strong") and in_title(test_norm, "weak")) or \
           (in_title(req_norm, "weak") and in_title(test_norm, "strong")) or \
           (req_condition == "STRONG_PASSWORD" and test_condition == "WEAK_PASSWORD") or \
           (req_condition == "WEAK_PASSWORD" and test_condition == "STRONG_PASSWORD"):
            contradictions.append("STRONG_PASSWORD vs WEAK_PASSWORD")

        # 3. VALID_TOKEN vs EXPIRED_TOKEN
        if (in_title(req_norm, "valid") and in_title(test_norm, "expired")) or \
           (in_title(req_norm, "expired") and in_title(test_norm, "valid")) or \
           (req_condition == "VALID_TOKEN" and test_condition == "EXPIRED_TOKEN") or \
           (req_condition == "EXPIRED_TOKEN" and test_condition == "VALID_TOKEN") or \
           (req_condition == "VALID_UNEXPIRED_TOKEN" and test_condition == "EXPIRED_TOKEN") or \
           (req_condition == "EXPIRED_TOKEN" and test_condition == "VALID_UNEXPIRED_TOKEN"):
            contradictions.append("VALID_TOKEN vs EXPIRED_TOKEN")

        # 4. VALID_TOKEN vs REUSED_TOKEN
        if (in_title(req_norm, "valid") and in_title(test_norm, "reused")) or \
           (in_title(req_norm, "reused") and in_title(test_norm, "valid")) or \
           (req_condition == "VALID_TOKEN" and test_condition == "REUSED_TOKEN") or \
           (req_condition == "REUSED_TOKEN" and test_condition == "VALID_TOKEN") or \
           (req_condition == "VALID_UNEXPIRED_TOKEN" and test_condition == "REUSED_TOKEN") or \
           (req_condition == "REUSED_TOKEN" and test_condition == "VALID_UNEXPIRED_TOKEN"):
            contradictions.append("VALID_TOKEN vs REUSED_TOKEN")

        # 5. EXPIRED_TOKEN vs REUSED_TOKEN
        if (in_title(req_norm, "expired") and in_title(test_norm, "reused")) or \
           (in_title(req_norm, "reused") and in_title(test_norm, "expired")) or \
           (req_condition == "EXPIRED_TOKEN" and test_condition == "REUSED_TOKEN") or \
           (req_condition == "REUSED_TOKEN" and test_condition == "EXPIRED_TOKEN"):
            contradictions.append("EXPIRED_TOKEN vs REUSED_TOKEN")

        # 6. SIGN_UP vs RESET_PASSWORD
        if (req_flow == "SIGN_UP" and test_flow == "PASSWORD_RESET") or \
           (req_flow == "PASSWORD_RESET" and test_flow == "SIGN_UP") or \
           (in_title(req_norm, "sign") and in_title(test_norm, "reset")) or \
           (in_title(req_norm, "reset") and in_title(test_norm, "sign")):
            contradictions.append("SIGN_UP vs RESET_PASSWORD")

        # 7. SIGN_UP vs UPDATE_PASSWORD
        if (req_flow == "SIGN_UP" and test_flow == "UPDATE_PASSWORD") or \
           (req_flow == "UPDATE_PASSWORD" and test_flow == "SIGN_UP") or \
           (in_title(req_norm, "sign") and in_title(test_norm, "update")) or \
           (in_title(req_norm, "update") and in_title(test_norm, "sign")):
            contradictions.append("SIGN_UP vs UPDATE_PASSWORD")

        # 8. RESET_PASSWORD vs UPDATE_PASSWORD
        if (req_flow == "PASSWORD_RESET" and test_flow == "UPDATE_PASSWORD") or \
           (req_flow == "UPDATE_PASSWORD" and test_flow == "PASSWORD_RESET") or \
           (in_title(req_norm, "reset") and in_title(test_norm, "update")) or \
           (in_title(req_norm, "update") and in_title(test_norm, "reset")):
            contradictions.append("RESET_PASSWORD vs UPDATE_PASSWORD")

        # 8.5. ACCOUNT_SECURITY_VALIDATION vs SCOPED_FLOW
        scoped_flows = {"SIGN_UP", "PASSWORD_RESET", "UPDATE_PASSWORD", "LOGIN_AFTER_PASSWORD_CHANGE"}
        if (req_flow == "ACCOUNT_SECURITY_VALIDATION" and test_flow in scoped_flows) or \
           (test_flow == "ACCOUNT_SECURITY_VALIDATION" and req_flow in scoped_flows):
            contradictions.append("ACCOUNT_SECURITY_VALIDATION vs SCOPED_FLOW")

        # 9. OLD_PASSWORD vs NEW_PASSWORD
        if (in_title(req_norm, "old password") and in_title(test_norm, "new password")) or \
           (in_title(req_norm, "new password") and in_title(test_norm, "old password")) or \
           (req_subject == "OLD_PASSWORD" and test_subject == "NEW_PASSWORD") or \
           (req_subject == "NEW_PASSWORD" and test_subject == "OLD_PASSWORD"):
            contradictions.append("OLD_PASSWORD vs NEW_PASSWORD")

        # 10. TOKEN behavior vs LOGIN behavior
        if (in_title(req_norm, "token") and in_title(test_norm, "login")) or \
           (in_title(test_norm, "token") and in_title(req_norm, "login")) or \
           (req_subject in ("TOKEN", "RESET_TOKEN") and test_action == "LOGIN") or \
           (test_subject in ("TOKEN", "RESET_TOKEN") and req_action == "LOGIN"):
            contradictions.append("TOKEN behavior vs LOGIN behavior")

        # 11. UI-only validation vs backend mandatory validation
        if (req_val_layer == "UI" and test_val_layer == "BACKEND" and "mandatory" in test_norm) or \
           (test_val_layer == "UI" and req_val_layer == "BACKEND" and "mandatory" in req_norm):
            contradictions.append("UI-only validation vs backend mandatory validation")

        # 12. confirmation mismatch vs password complexity
        if (in_title(req_norm, "confirmation") and in_title(test_norm, "complexity")) or \
           (in_title(test_norm, "confirmation") and in_title(req_norm, "complexity")):
            contradictions.append("confirmation mismatch vs password complexity")

        # 13. error-message safety vs password acceptance
        if (in_title(req_norm, "error message") and in_title(test_norm, "accept")) or \
           (in_title(test_norm, "error message") and in_title(req_norm, "accept")):
            contradictions.append("error-message safety vs password acceptance")

        # 14. Scoped token/password compatibility (no blanket contradiction)
        req_is_token = (
            "token" in req_norm or
            req_subject in ("RESET_TOKEN", "TOKEN") or
            req_condition in ("EXPIRED", "REUSED", "VALID_UNEXPIRED_TOKEN", "EXPIRED_TOKEN", "REUSED_TOKEN", "VALID_TOKEN", "VALID")
        )
        test_is_token = (
            "token" in test_norm or
            test_subject in ("RESET_TOKEN", "TOKEN") or
            test_condition in ("EXPIRED", "REUSED", "VALID_UNEXPIRED_TOKEN", "EXPIRED_TOKEN", "REUSED_TOKEN", "VALID_TOKEN", "VALID")
        )

        pwd_keywords = {"password", "length", "complexity", "uppercase", "lowercase", "digit", "number", "special", "empty", "whitespace", "spaces", "confirm"}
        req_is_pwd = (
            any(kw in req_norm for kw in pwd_keywords) or
            req_condition in ("WEAK_PASSWORD", "STRONG_PASSWORD", "EMPTY_PASSWORD", "WHITESPACE_ONLY_PASSWORD", "LEADING_TRAILING_SPACES", "CONFIRMATION_MISMATCH", "WEAK", "STRONG", "EMPTY", "WHITESPACE") or
            req_action in ("REJECT_PASSWORD", "ACCEPT_PASSWORD", "COMPARE_CONFIRMATION") or
            req_subject in ("PASSWORD", "NEW_PASSWORD", "OLD_PASSWORD", "CONFIRMATION_FIELD")
        )
        test_is_pwd = (
            any(kw in test_norm for kw in pwd_keywords) or
            test_condition in ("WEAK_PASSWORD", "STRONG_PASSWORD", "EMPTY_PASSWORD", "WHITESPACE_ONLY_PASSWORD", "LEADING_TRAILING_SPACES", "CONFIRMATION_MISMATCH", "WEAK", "STRONG", "EMPTY", "WHITESPACE") or
            test_action in ("REJECT_PASSWORD", "ACCEPT_PASSWORD", "COMPARE_CONFIRMATION") or
            test_subject in ("PASSWORD", "NEW_PASSWORD", "OLD_PASSWORD", "CONFIRMATION_FIELD")
        )

        req_token_only = req_is_token and not req_is_pwd
        req_pwd_only = req_is_pwd and not req_is_token

        test_token_only = test_is_token and not test_is_pwd
        test_pwd_only = test_is_pwd and not test_is_token

        if (test_token_only and req_pwd_only) or (test_pwd_only and req_token_only):
            contradictions.append("SCOPED_TOKEN_PASSWORD_MISMATCH")

        if contradictions:
            return {
                "is_contradiction": True,
                "reason": f"Hard contradiction: {', '.join(contradictions)}",
                "rule": contradictions[0],
                "dimensions": self._get_matching_dimensions(requirement, test)
            }

        return {"is_contradiction": False, "reason": "", "rule": "", "dimensions": {}}

    def _check_exact_signature_match(self, requirement: RequirementNode, test: TestNode) -> float:
        """Check if scenario signatures match exactly."""
        req_sig = requirement.scenario_signature
        test_sig = test.scenario_signature
        
        if not req_sig or not test_sig:
            return 0.0

        # Check all signature fields match case-insensitively
        if (self._norm(req_sig.flow) == self._norm(test_sig.flow) and
            self._norm(req_sig.action) == self._norm(test_sig.action) and
            self._norm(req_sig.condition) == self._norm(test_sig.condition) and
            self._norm(req_sig.expected_outcome) == self._norm(test_sig.expected_outcome) and
            self._norm(req_sig.subject) == self._norm(test_sig.subject) and
            self._norm(req_sig.validation_layer) == self._norm(test_sig.validation_layer) and
            self._norm(req_sig.polarity) == self._norm(test_sig.polarity)):
            return 1.0

        return 0.0

    def _check_validation_layer_compatibility(self, requirement: RequirementNode, test: TestNode) -> float:
        """Check validation layer compatibility."""
        req_sig = requirement.scenario_signature
        test_sig = test.scenario_signature
        
        if not req_sig or not test_sig:
            return 0.0

        req_layer = self._norm(req_sig.validation_layer)
        test_layer = self._norm(test_sig.validation_layer)

        # Exact match
        if req_layer == test_layer and req_layer != "UNKNOWN":
            return 0.10

        # Cross-layer compatibility (if explicitly marked as cross-layer)
        if req_layer == "CROSS_LAYER" or test_layer == "CROSS_LAYER":
            return 0.08

        # E2E tests can cover multiple layers
        if req_layer == "E2E" or test_layer == "E2E":
            return 0.06

        return 0.0

    def _check_subject_compatibility(self, requirement: RequirementNode, test: TestNode) -> float:
        """Check subject compatibility."""
        req_sig = requirement.scenario_signature
        test_sig = test.scenario_signature
        
        if not req_sig or not test_sig:
            return 0.0

        req_subject = self._norm(req_sig.subject)
        test_subject = self._norm(test_sig.subject)

        # Exact match
        if req_subject == test_subject and req_subject != "UNKNOWN":
            return 0.10

        # Compatible subjects
        compatible_subjects = {
            "PASSWORD": {"OLD_PASSWORD", "NEW_PASSWORD"},
            "OLD_PASSWORD": {"PASSWORD"},
            "NEW_PASSWORD": {"PASSWORD"},
            "TOKEN": {"RESET_TOKEN"},
            "RESET_TOKEN": {"TOKEN"}
        }

        if req_subject in compatible_subjects and test_subject in compatible_subjects[req_subject]:
            return 0.05

        return 0.0

    def _calculate_semantic_similarity(self, requirement: RequirementNode, test: TestNode) -> float:
        """Calculate semantic similarity as a fallback."""
        req_norm = self.normalize_title(requirement.title)
        test_norm = self.normalize_title(test.title)

        req_words = set(req_norm.split())
        test_words = set(test_norm.split())

        if not req_words or not test_words:
            return 0.0

        # Jaccard similarity
        intersection = req_words & test_words
        union = req_words | test_words
        jaccard = len(intersection) / len(union) if union else 0.0

        return jaccard

    def _get_matching_dimensions(self, requirement: RequirementNode, test: TestNode) -> Dict[str, Any]:
        """Get matching dimensions for diagnostics."""
        req_sig = requirement.scenario_signature
        test_sig = test.scenario_signature
        
        dimensions = {
            "requirement_readable_id": requirement.readable_id,
            "requirement_title": requirement.title,
            "test_title": test.title,
            "test_source": test.file_path or test.classname or "unknown"
        }

        if req_sig and test_sig:
            dimensions.update({
                "flow_match": self._norm(req_sig.flow) == self._norm(test_sig.flow),
                "requirement_flow": req_sig.flow,
                "test_flow": test_sig.flow,
                "action_match": self._norm(req_sig.action) == self._norm(test_sig.action),
                "requirement_action": req_sig.action,
                "test_action": test_sig.action,
                "condition_match": self._norm(req_sig.condition) == self._norm(test_sig.condition),
                "requirement_condition": req_sig.condition,
                "test_condition": test_sig.condition,
                "outcome_match": self._norm(req_sig.expected_outcome) == self._norm(test_sig.expected_outcome),
                "requirement_outcome": req_sig.expected_outcome,
                "test_outcome": test_sig.expected_outcome,
                "subject_match": self._norm(req_sig.subject) == self._norm(test_sig.subject),
                "requirement_subject": req_sig.subject,
                "test_subject": test_sig.subject,
                "validation_layer_match": self._norm(req_sig.validation_layer) == self._norm(test_sig.validation_layer),
                "requirement_validation_layer": req_sig.validation_layer,
                "test_validation_layer": test_sig.validation_layer,
                "polarity_match": self._norm(req_sig.polarity) == self._norm(test_sig.polarity),
                "requirement_polarity": req_sig.polarity,
                "test_polarity": test_sig.polarity
            })

        return dimensions

    def _calculate_contradiction_penalty(self, requirement: RequirementNode, test: TestNode) -> float:
        """Legacy method - kept for backward compatibility. Use _check_hard_contradictions instead."""
        contradiction_result = self._check_hard_contradictions(requirement, test)
        return 1.0 if contradiction_result["is_contradiction"] else 0.0

    def _layer4_path_hints(self, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 4: Path/classname hints."""
        score = 0.0
        test_class_lower = (test.classname or "").lower()
        req_flow_lower = (requirement.flow or "").lower()

        flow_hints = {
            "password_reset": ["reset", "password", "reset-password"],
            "sign_up": ["signup", "sign-up", "register", "registration"],
            "update_password": ["update", "password", "change"],
            "login": ["login", "auth", "authentication"],
        }

        if req_flow_lower in flow_hints:
            for hint in flow_hints[req_flow_lower]:
                if hint in test_class_lower or hint in (test.file_path or "").lower():
                    score = 1.0
                    break
        return score

    def _layer5_keyword_scoring(self, requirement: RequirementNode, test: TestNode) -> float:
        """Layer 5: Keyword/intent scoring."""
        req_text_lower = requirement.title.lower()
        test_text_lower = test.title.lower()
        score = 0.0
        for term, weight in self.TERM_WEIGHTS.items():
            if term in req_text_lower and term in test_text_lower:
                score += weight
        return min(1.0, score)

    def normalize_title(self, title: str) -> str:
        """Normalize title for comparison with verb normalization and domain term preservation."""
        # Split camelCase first (using the original title's casing)
        normalized = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)
        # Remove leading numbering/prefixes like "7.", "AC-07", "07 -", "1 -"
        normalized = re.sub(r'^(?:ac[- ]*\d+|\d+)[-.\s]*', '', normalized, flags=re.IGNORECASE)
        normalized = normalized.lower()
        normalized = re.sub(r'[_-]', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        words = normalized.split()
        normalized_words = []

        for word in words:
            if word in self.FILLER_WORDS:
                continue
            if word in self.VERB_NORMALIZATION:
                word = self.VERB_NORMALIZATION[word]
            normalized_words.append(word)

        return ' '.join(normalized_words)

    def _get_match_reason(self, result: MatchResult) -> str:
        """Get human-readable reason for match decision."""
        if result.score >= self.AUTO_MATCH_THRESHOLD:
            return "High confidence match above threshold"
        elif result.score >= self.PROBABLE_MATCH_THRESHOLD:
            return "Probable match, below auto-match threshold"
        else:
            return "Low confidence, below probable match threshold"

    def clear_match_table(self):
        """Clear the match table for a new classification run."""
        self.match_table = []
