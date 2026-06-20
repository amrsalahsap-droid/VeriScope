"""Scenario Signature Service - Generates canonical scenario signatures.

This service generates normalized scenario signatures for matching
requirements to tests and executions.
"""
import hashlib
from typing import Dict, Any
from dataclasses import dataclass

from app.services.regression_evidence_classifier import ScenarioSignature


@dataclass
class SignatureGenerationResult:
    """Result of signature generation."""
    signature: ScenarioSignature
    hash: str


class ScenarioSignatureService:
    """Service for generating canonical scenario signatures."""

    # High-value terms for extraction
    HIGH_VALUE_TERMS = {
        "expired", "reused", "valid", "invalid", "weak", "strong", "empty",
        "whitespace", "confirmation", "mismatch", "ui", "api", "bypass",
        "reset", "signup", "update", "login", "token", "session"
    }

    # Flow keywords
    FLOW_KEYWORDS = {
        "password_reset", "reset_password", "sign_up", "signup", "sign-up",
        "update_password", "login", "authentication", "authorization"
    }

    # Action keywords
    ACTION_KEYWORDS = {
        "reject", "accept", "validate", "verify", "check", "ensure", "confirm",
        "display", "show", "hide", "render", "return", "send", "receive",
        "allow", "enable", "disable", "prevent", "block", "permit",
        "enforce", "require", "support", "provide", "implement"
    }

    # Condition keywords
    CONDITION_KEYWORDS = {
        "expired", "valid", "invalid", "unexpired", "reused", "first-use",
        "weak", "strong", "empty", "whitespace", "mismatch", "confirmation"
    }

    # Expected outcome keywords
    OUTCOME_KEYWORDS = {
        "rejected", "accepted", "allowed", "blocked", "success", "failure",
        "error", "displayed", "shown", "hidden", "returned", "sent", "received",
        "enforced", "required", "verified", "validated", "checked", "ensured"
    }

    # Polarity mapping
    POSITIVE_OUTCOMES = {"accepted", "allowed", "success", "verified", "validated", "checked", "ensured"}
    NEGATIVE_OUTCOMES = {"rejected", "blocked", "failure", "error", "prevented", "disabled"}

    def generate_signature(self, text: str, context: Dict[str, Any] = None) -> SignatureGenerationResult:
        """Generate a canonical scenario signature from text.

        Args:
            text: Input text to generate signature from
            context: Optional context for field extraction

        Returns:
            SignatureGenerationResult with signature and hash
        """
        if context is None:
            context = {}

        text_lower = text.lower()

        # Extract fields
        flow = self._extract_flow(text_lower, context.get("flow", ""))
        action = self._extract_action(text_lower, context.get("action", ""))
        condition = self._extract_condition(text_lower, context.get("condition", ""))
        expected_outcome = self._extract_expected_outcome(text_lower, context.get("expected_outcome", ""))
        polarity = self._determine_polarity(expected_outcome)
        subject = self._extract_subject(text_lower, context.get("subject", ""))
        validation_layer = self._determine_validation_layer(text_lower, context.get("validation_layer", ""))
        security_context = self._extract_security_context(text_lower, context.get("security_context", ""))
        data_category = self._extract_data_category(text_lower, context.get("data_category", ""))

        signature = ScenarioSignature(
            flow=flow,
            action=action,
            condition=condition,
            expected_outcome=expected_outcome,
            subject=subject,
            validation_layer=validation_layer,
            polarity=polarity,
            security_context=security_context,
            data_category=data_category,
        )

        hash_value = self._compute_signature_hash(signature)

        return SignatureGenerationResult(signature=signature, hash=hash_value)

    def _extract_flow(self, text_lower: str, context_flow: str) -> str:
        """Extract the flow from text."""
        if context_flow:
            return context_flow.lower()

        # Handle specific common aliases first
        if "reset password" in text_lower or "password reset" in text_lower or "reset-password" in text_lower or "password-reset" in text_lower:
            return "password_reset"
        if "update password" in text_lower or "password update" in text_lower or "update-password" in text_lower or "password-update" in text_lower:
            return "update_password"
        if "sign up" in text_lower or "signup" in text_lower or "sign-up" in text_lower:
            return "sign_up"

        for flow_keyword in self.FLOW_KEYWORDS:
            variants = [
                flow_keyword,
                flow_keyword.replace("_", ""),
                flow_keyword.replace("_", " "),
                flow_keyword.replace("_", "-")
            ]
            if any(var in text_lower for var in variants):
                return flow_keyword

        return "unknown"

    def _extract_action(self, text_lower: str, context_action: str) -> str:
        """Extract the action from text."""
        if context_action:
            return context_action.lower()

        for action_keyword in self.ACTION_KEYWORDS:
            if action_keyword in text_lower:
                return action_keyword

        return "unknown"

    def _extract_condition(self, text_lower: str, context_condition: str) -> str:
        """Extract the condition from text."""
        if context_condition:
            return context_condition.lower()

        for condition_keyword in self.CONDITION_KEYWORDS:
            if condition_keyword in text_lower:
                return condition_keyword

        return "unknown"

    def _extract_expected_outcome(self, text_lower: str, context_outcome: str) -> str:
        """Extract the expected outcome from text."""
        if context_outcome:
            return context_outcome.lower()

        for outcome_keyword in self.OUTCOME_KEYWORDS:
            if outcome_keyword in text_lower:
                return outcome_keyword

        return "unknown"

    def _determine_polarity(self, expected_outcome: str) -> str:
        """Determine polarity from expected outcome."""
        if expected_outcome in self.POSITIVE_OUTCOMES:
            return "positive"
        elif expected_outcome in self.NEGATIVE_OUTCOMES:
            return "negative"
        return "neutral"

    def _extract_subject(self, text_lower: str, context_subject: str) -> str:
        """Extract the subject from text."""
        if context_subject:
            return context_subject.lower()

        if "password" in text_lower:
            return "password"
        elif "token" in text_lower:
            return "token"
        elif "user" in text_lower:
            return "user"
        elif "session" in text_lower:
            return "session"
        elif "confirmation" in text_lower:
            return "confirmation"
        elif "message" in text_lower:
            return "message"

        return "unknown"

    def _determine_validation_layer(self, text_lower: str, context_layer: str) -> str:
        """Determine the validation layer."""
        if context_layer:
            return context_layer.lower()

        if "api" in text_lower:
            return "api"
        elif "ui" in text_lower or "interface" in text_lower:
            return "ui"
        elif "security" in text_lower or "auth" in text_lower:
            return "security"

        return "unknown"

    def _extract_security_context(self, text_lower: str, context_security: str) -> str:
        """Extract security context."""
        if context_security:
            return context_security.lower()

        if "token" in text_lower:
            return "token"
        elif "password" in text_lower:
            return "password"
        elif "session" in text_lower:
            return "session"

        return ""

    def _extract_data_category(self, text_lower: str, context_data: str) -> str:
        """Extract data category."""
        if context_data:
            return context_data.lower()

        if "password" in text_lower:
            return "password"
        elif "email" in text_lower:
            return "email"
        elif "username" in text_lower:
            return "username"

        return ""

    def _compute_signature_hash(self, signature: ScenarioSignature) -> str:
        """Compute a hash for the signature for comparison."""
        signature_dict = signature.to_dict()
        signature_str = "|".join(str(v) for v in signature_dict.values())
        return hashlib.sha256(signature_str.encode()).hexdigest()
