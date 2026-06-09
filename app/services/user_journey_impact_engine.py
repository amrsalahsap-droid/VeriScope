from typing import Dict, List, Any
from sqlalchemy.orm import Session
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest

class UserJourneyImpactEngine:
    """
    UserJourneyImpactEngine translates technical codebase changes into high-level
    user journeys at risk (e.g. Login, Signup, Password Reset, Checkout, Subscription).
    """

    @classmethod
    def detect_journeys(
        cls,
        db: Session,
        run: RecommendationRun,
        changed_files: List[str]
    ) -> List[Dict[str, str]]:
        """
        Dynamically maps modified file paths to affected UserJourneys.
        Outputs a list of AffectedJourneys, each containing: journey, severity, and reason.
        """
        affected = []

        has_auth = False
        has_password = False
        has_billing = False

        for f in changed_files:
            f_lower = f.lower()
            if "auth/" in f_lower or "auth_change" in f_lower or any(kw in f_lower for kw in ("login", "signin", "session", "jwt")):
                has_auth = True
            if "password" in f_lower or "reset-password" in f_lower:
                has_password = True
            if "billing/" in f_lower or "checkout" in f_lower or any(kw in f_lower for kw in ("payment", "stripe", "subscription", "invoice")):
                has_billing = True

        # Mapping rules
        if has_auth:
            affected.append({
                "journey": "Login",
                "severity": "HIGH",
                "reason": "Authentication logic modified, potentially impacting signin flow stability."
            })
            affected.append({
                "journey": "Signup",
                "severity": "MODERATE",
                "reason": "Shared authentication module modified, carrying user registration flow risks."
            })

        if has_password:
            affected.append({
                "journey": "Password Reset",
                "severity": "HIGH",
                "reason": "Password reset flow logic modified, affecting account recovery workflows."
            })
            # If auth wasn't already triggered, add a moderate login warning
            if not has_auth:
                affected.append({
                    "journey": "Login",
                    "severity": "MODERATE",
                    "reason": "Credential and password validation rules changed, carrying signin path regression risks."
                })

        if has_billing:
            affected.append({
                "journey": "Checkout",
                "severity": "HIGH",
                "reason": "Billing checkouts modified, carrying direct payment transaction execution risks."
            })
            affected.append({
                "journey": "Subscription",
                "severity": "HIGH",
                "reason": "Subscription lifecycle and invoice processing modified."
            })

        # Safe Fallback (Acceptance rule: always show user-facing impact)
        if not affected:
            affected.append({
                "journey": "General Experience",
                "severity": "LOW",
                "reason": "Core module logic modified. Baseline user journey regression checks recommended."
            })

        # Deduplicate journeys keeping highest severity
        severity_weight = {"HIGH": 3, "MODERATE": 2, "LOW": 1}
        journey_map = {}
        for item in affected:
            j = item["journey"]
            if j not in journey_map or severity_weight[item["severity"]] > severity_weight[journey_map[j]["severity"]]:
                journey_map[j] = item

        # Sort journeys: HIGH severity first, then MODERATE, then LOW
        result = list(journey_map.values())
        result.sort(key=lambda x: -severity_weight[x["severity"]])

        return result
