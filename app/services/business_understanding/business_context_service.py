"""
Business context service for generating business understanding annotations.

This service generates businessContext objects for requirements and scope items
using deterministic semantic analysis. It does not use LLMs in Phase 2.0.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from app.services.business_understanding.business_risk_rules import (
    BusinessRiskRules,
    RiskLevel,
    Priority
)


class BusinessContext:
    """Business context annotation for requirements and scope items."""
    
    def __init__(
        self,
        capability: str,
        user_journey: str,
        actor: str,
        business_action: str,
        protected_outcome: str,
        failure_mode: str,
        user_impact: str,
        business_impact: str,
        risk_level: str,
        risk_reasons: List[str],
        priority: str,
        confidence: str,
        evidence_references: List[str],
        derived_from: List[str],
        matched_semantic_signals: List[str] = None,
        triggered_rule: Optional[str] = None,
        risk_origin: Optional[str] = None,
        is_deterministic: bool = False,
        what_would_lower_risk: Optional[str] = None,
        what_would_make_release_safe: Optional[str] = None
    ):
        self.capability = capability
        self.user_journey = user_journey
        self.actor = actor
        self.business_action = business_action
        self.protected_outcome = protected_outcome
        self.failure_mode = failure_mode
        self.user_impact = user_impact
        self.business_impact = business_impact
        self.risk_level = risk_level
        self.risk_reasons = risk_reasons
        self.priority = priority
        self.confidence = confidence
        self.evidence_references = evidence_references
        self.derived_from = derived_from
        self.matched_semantic_signals = matched_semantic_signals or []
        self.triggered_rule = triggered_rule
        self.risk_origin = risk_origin
        self.is_deterministic = is_deterministic
        self.what_would_lower_risk = what_would_lower_risk
        self.what_would_make_release_safe = what_would_make_release_safe
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "capability": self.capability,
            "userJourney": self.user_journey,
            "actor": self.actor,
            "businessAction": self.business_action,
            "protectedOutcome": self.protected_outcome,
            "failureMode": self.failure_mode,
            "userImpact": self.user_impact,
            "businessImpact": self.business_impact,
            "riskLevel": self.risk_level,
            "riskReasons": self.risk_reasons,
            "priority": self.priority,
            "confidence": self.confidence,
            "evidenceReferences": self.evidence_references,
            "derivedFrom": self.derived_from,
            "matchedSemanticSignals": self.matched_semantic_signals,
            "triggeredRule": self.triggered_rule,
            "riskOrigin": self.risk_origin,
            "isDeterministic": self.is_deterministic,
            "whatWouldLowerRisk": self.what_would_lower_risk,
            "whatWouldMakeReleaseSafe": self.what_would_make_release_safe
        }


class BusinessContextService:
    """
    Service for generating business context annotations.
    
    This service uses deterministic semantic analysis to generate business
    understanding annotations without using LLMs.
    """
    
    def __init__(self):
        self.risk_rules = BusinessRiskRules()
    
    def generate_business_context(
        self,
        requirement_text: str,
        requirement_title: str = "",
        requirement_id: str = "",
        matched_tests: List[str] = None,
        pr_title: str = "",
        pr_description: str = "",
        changed_files: List[str] = None
    ) -> BusinessContext:
        """
        Generate business context for a requirement.
        
        Args:
            requirement_text: The full requirement text
            requirement_title: Optional requirement title/readable ID
            requirement_id: Internal requirement ID for evidence references
            matched_tests: List of matched test names
            pr_title: Pull request title
            pr_description: Pull request description
            changed_files: List of changed files in the PR
            
        Returns:
            BusinessContext object with semantic annotations
        """
        matched_tests = matched_tests or []
        changed_files = changed_files or []
        
        try:
            # Assess risk using semantic rules
            risk_level, priority, risk_reasons = self.risk_rules.assess_risk(
                requirement_text,
                requirement_title
            )
            
            # Infer semantic attributes
            capability = self.risk_rules.infer_capability(requirement_text)
            user_journey = self.risk_rules.infer_user_journey(requirement_text)
            actor = self.risk_rules.infer_actor(requirement_text)
            business_action = self.risk_rules.infer_business_action(requirement_text)
            
            # Build protected outcome and failure mode based on requirement
            protected_outcome, failure_mode = self._infer_outcomes(
                requirement_text,
                business_action
            )
            
            # Build impact statements
            user_impact, business_impact = self._build_impact_statements(
                risk_level,
                requirement_text,
                business_action
            )
            
            # Build evidence references
            evidence_references = self._build_evidence_references(
                requirement_id,
                matched_tests,
                changed_files
            )
            
            # Build derived from list
            derived_from = self._build_derived_from(
                requirement_text,
                pr_title,
                pr_description
            )
            
            # Confidence based on semantic clarity
            confidence = self._assess_confidence(
                risk_level,
                len(risk_reasons),
                len(matched_tests)
            )
            
            # Matched semantic signals
            combined_text = f"{requirement_title} {requirement_text}".lower()
            matched_signals = []
            for pattern, _ in (self.risk_rules.CRITICAL_P0_PATTERNS + 
                               self.risk_rules.HIGH_P1_PATTERNS + 
                               self.risk_rules.MEDIUM_P2_PATTERNS + 
                               self.risk_rules.LOW_P3_PATTERNS):
                if pattern in combined_text:
                    matched_signals.append(pattern)
            
            # Determine triggered rule and determinism (controlled values)
            is_cosmetic = any(p in combined_text for p in ["cosmetic", "display", "color", "button", "theme", "style", "design system"])
            is_ux_or_message = any(p in combined_text for p in ["message", "user-friendly", "clarity", "ux", "user experience", "friendly", "safe", "expose", "internal"])
            
            if is_cosmetic:
                triggered_rule = "COSMETIC_DOWNGRADE_RULE"
                is_deterministic = True
            elif is_ux_or_message:
                triggered_rule = "UX_MESSAGING_DOWNGRADE_RULE"
                is_deterministic = True
            elif risk_level == RiskLevel.CRITICAL:
                triggered_rule = "CRITICAL_SCORE_RULE"
                is_deterministic = True
            elif risk_level == RiskLevel.HIGH:
                triggered_rule = "HIGH_SCORE_RULE"
                is_deterministic = True
            elif risk_level == RiskLevel.MEDIUM:
                triggered_rule = "MEDIUM_SCORE_RULE"
                is_deterministic = True
            elif risk_level == RiskLevel.LOW:
                triggered_rule = "LOW_SCORE_RULE"
                is_deterministic = True
            else:
                triggered_rule = "FALLBACK_DEFAULT_RULE"
                is_deterministic = False
                
            # Determine risk origin (controlled values)
            if matched_tests:
                risk_origin = "MATCHED_EVIDENCE"
            else:
                text_lower = requirement_text.lower()
                if any(k in text_lower for k in ["if ", "unless ", "whether ", "only when ", "condition "]):
                    risk_origin = "CONDITION"
                elif any(k in text_lower for k in ["after ", "before ", "when ", "flow ", "then ", "step "]):
                    risk_origin = "FLOW"
                elif any(k in text_lower for k in ["update", "reset", "change", "login", "authenticate", "authorize", "reject", "accept", "validate"]):
                    risk_origin = "ACTION"
                else:
                    risk_origin = "REQUIREMENT_TEXT"
                    
            # What would lower risk / what would make release safe
            if risk_level == RiskLevel.CRITICAL:
                what_would_lower_risk = "Implement multi-factor authentication, add backend validation, or enforce strict old-password validation during updates."
                what_would_make_release_safe = "Verify that at least one direct automated test executes successfully against this security requirement, and perform a QA lead review of the authorization flow."
            elif risk_level == RiskLevel.HIGH:
                what_would_lower_risk = "Align validation schemas between frontend and backend, and add comprehensive integration tests."
                what_would_make_release_safe = "Provide passed integration or unit test evidence, and verify API response consistency."
            elif risk_level == RiskLevel.MEDIUM:
                what_would_lower_risk = "Improve user feedback and validation message clarity, and verify UX flow consistency."
                what_would_make_release_safe = "Verify that error messaging UX is user-friendly and doesn't expose internal stack traces under boundary conditions."
            elif risk_level == RiskLevel.LOW:
                what_would_lower_risk = "Validate cosmetic consistency against the design system, and ensure non-blocking layout errors are logged."
                what_would_make_release_safe = "Pass standard regression suite execution and confirm visual correctness."
            else:
                what_would_lower_risk = "Enrich the requirement text with explicit access rules, flow conditions, and expected behaviors."
                what_would_make_release_safe = "Provide automated test coverage or obtain explicit sign-off from the QA lead."
                
            return BusinessContext(
                capability=capability,
                user_journey=user_journey,
                actor=actor,
                business_action=business_action,
                protected_outcome=protected_outcome,
                failure_mode=failure_mode,
                user_impact=user_impact,
                business_impact=business_impact,
                risk_level=risk_level.value,
                risk_reasons=risk_reasons,
                priority=priority.value,
                confidence=confidence,
                evidence_references=evidence_references,
                derived_from=derived_from,
                matched_semantic_signals=matched_signals,
                triggered_rule=triggered_rule,
                risk_origin=risk_origin,
                is_deterministic=is_deterministic,
                what_would_lower_risk=what_would_lower_risk,
                what_would_make_release_safe=what_would_make_release_safe
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to generate business context: {e}")
            # Fallback values according to rule 9
            return BusinessContext(
                capability="General",
                user_journey="General",
                actor="User",
                business_action="Perform action",
                protected_outcome="System behaves correctly",
                failure_mode="System behaves incorrectly",
                user_impact="Impact unclear due to context generation failure",
                business_impact="Business impact unclear due to context generation failure",
                risk_level="UNKNOWN",
                risk_reasons=["Fallback Explanation: Business context generation failed during semantic analysis."],
                priority="UNKNOWN",
                confidence="LOW",
                evidence_references=self._build_evidence_references(requirement_id, matched_tests, changed_files),
                derived_from=["fallback_handling"],
                matched_semantic_signals=[],
                triggered_rule="FALLBACK_DEFAULT_RULE",
                risk_origin="REQUIREMENT_TEXT",
                is_deterministic=False,
                what_would_lower_risk="Enrich the requirement text with explicit access rules, flow conditions, and expected behaviors.",
                what_would_make_release_safe="Provide automated test coverage or obtain explicit sign-off from the QA lead."
            )
    
    def _infer_outcomes(self, requirement_text: str, business_action: str) -> tuple:
        """Infer protected outcome and failure mode from requirement."""
        text_lower = requirement_text.lower()
        
        # Password-specific outcomes
        if "password" in text_lower and "old" in text_lower:
            return (
                "Old credentials can no longer access the account",
                "Old password remains valid after password update"
            )
        elif "password" in text_lower and "new" in text_lower:
            return (
                "New password meets security requirements",
                "Weak password accepted or new password not enforced"
            )
        elif "password" in text_lower and "confirm" in text_lower:
            return (
                "Password confirmation matches new password",
                "Password confirmation mismatch allows inconsistent state"
            )
        
        # Generic outcomes
        if "valid" in text_lower or "validate" in text_lower:
            return (
                f"{business_action} meets validation requirements",
                f"{business_action} bypasses validation or accepts invalid input"
            )
        elif "reject" in text_lower or "invalid" in text_lower:
            return (
                f"Invalid {business_action.lower()} is rejected",
                f"Invalid {business_action.lower()} is accepted"
            )
        else:
            return (
                f"{business_action} succeeds correctly",
                f"{business_action} fails or produces incorrect result"
            )
    
    def _build_impact_statements(
        self,
        risk_level: RiskLevel,
        requirement_text: str,
        business_action: str
    ) -> tuple:
        """Build user and business impact statements based on risk level."""
        text_lower = requirement_text.lower()
        
        if risk_level == RiskLevel.CRITICAL:
            if "password" in text_lower or "credential" in text_lower:
                user_impact = "Account takeover risk if credentials are compromised"
                business_impact = "Security control failure leading to unauthorized access"
            elif "data" in text_lower or "loss" in text_lower:
                user_impact = "Data loss or corruption affecting user experience"
                business_impact = "Data integrity failure with potential compliance impact"
            else:
                user_impact = "Critical functionality failure affecting core user journey"
                business_impact = "Core business capability failure with significant impact"
        
        elif risk_level == RiskLevel.HIGH:
            user_impact = "Important user journey may fail or behave incorrectly"
            business_impact = "Validation inconsistency may lead to invalid state"
        
        elif risk_level == RiskLevel.MEDIUM:
            user_impact = "User experience degraded by unclear or inconsistent behavior"
            business_impact = "UX inconsistency may affect user trust"
        
        elif risk_level == RiskLevel.LOW:
            user_impact = "Minor cosmetic or display issue"
            business_impact = "Non-blocking display or formatting issue"
        
        else:  # UNKNOWN
            user_impact = "Impact unclear from requirement semantics"
            business_impact = "Business impact unclear from requirement semantics"
        
        return user_impact, business_impact
    
    def _build_evidence_references(
        self,
        requirement_id: str,
        matched_tests: List[str],
        changed_files: List[str]
    ) -> List[str]:
        """Build evidence references for traceability."""
        references = []
        
        if requirement_id:
            references.append(f"requirement:{requirement_id}")
        
        for test in matched_tests[:3]:  # Limit to first 3 tests
            references.append(f"test:{test}")
        
        for file in changed_files[:2]:  # Limit to first 2 files
            references.append(f"file:{file}")
        
        return references
    
    def _build_derived_from(
        self,
        requirement_text: str,
        pr_title: str,
        pr_description: str
    ) -> List[str]:
        """Build derived from list for transparency."""
        derived = ["requirement_semantics"]
        
        if pr_title:
            derived.append("pr_title")
        
        if pr_description:
            derived.append("pr_description")
        
        return derived
    
    def _assess_confidence(
        self,
        risk_level: RiskLevel,
        num_reasons: int,
        num_matched_tests: int
    ) -> str:
        """Assess confidence in the business context assessment."""
        if risk_level == RiskLevel.UNKNOWN:
            return "LOW"
        elif num_reasons >= 2:
            return "HIGH"
        elif num_reasons == 1:
            return "MEDIUM"
        elif num_matched_tests > 0:
            return "MEDIUM"
        else:
            return "LOW"
    
    def generate_batch_business_context(
        self,
        requirements: List[Dict[str, Any]],
        pr_title: str = "",
        pr_description: str = "",
        changed_files: List[str] = None
    ) -> List[BusinessContext]:
        """
        Generate business context for a batch of requirements.
        
        Args:
            requirements: List of requirement dictionaries with keys:
                - text: requirement text
                - title: optional title
                - id: optional internal ID
                - matched_tests: optional list of matched test names
            pr_title: Pull request title
            pr_description: Pull request description
            changed_files: List of changed files in the PR
            
        Returns:
            List of BusinessContext objects
        """
        contexts = []
        
        for req in requirements:
            context = self.generate_business_context(
                requirement_text=req.get("text", ""),
                requirement_title=req.get("title", ""),
                requirement_id=req.get("id", ""),
                matched_tests=req.get("matched_tests", []),
                pr_title=pr_title,
                pr_description=pr_description,
                changed_files=changed_files
            )
            contexts.append(context)
        
        return contexts

    def attach_to_requirement_item(self, item: Any) -> Any:
        """
        Generate business context and attach it to a requirement item.
        Works with both dictionaries and objects (including Pydantic models).
        """
        if isinstance(item, dict):
            text = item.get("title") or item.get("text") or ""
            title = item.get("readable_id") or item.get("readableId") or ""
            req_id = item.get("requirement_id") or item.get("requirementId") or item.get("internal_requirement_id") or ""
        else:
            text = getattr(item, "title", None) or getattr(item, "text", None) or ""
            title = getattr(item, "readable_id", None) or getattr(item, "readableId", None) or ""
            req_id = getattr(item, "requirement_id", None) or getattr(item, "requirementId", None) or getattr(item, "internal_requirement_id", None) or ""
            
        context = self.generate_business_context(
            requirement_text=text,
            requirement_title=title,
            requirement_id=req_id
        )
        
        if isinstance(item, dict):
            item["businessContext"] = context.to_dict()
        else:
            setattr(item, "businessContext", context.to_dict())
            
        return item

    def attach_to_scope_item(self, item: Any) -> Any:
        """
        Generate business context and attach it to a scope item.
        Works with both dictionaries and objects (including Pydantic models).
        """
        if isinstance(item, dict):
            text = item.get("title") or ""
            title = item.get("readable_id") or item.get("readableId") or ""
            req_id = item.get("source_requirement_id") or item.get("requirementId") or ""
        else:
            text = getattr(item, "title", "") or ""
            title = getattr(item, "readable_id", "") or getattr(item, "readableId", "") or ""
            req_id = getattr(item, "source_requirement_id", "") or getattr(item, "requirementId", "") or ""
            
        context = self.generate_business_context(
            requirement_text=text,
            requirement_title=title,
            requirement_id=req_id
        )
        
        if isinstance(item, dict):
            item["businessContext"] = context.to_dict()
        else:
            setattr(item, "businessContext", context.to_dict())
            
        return item
