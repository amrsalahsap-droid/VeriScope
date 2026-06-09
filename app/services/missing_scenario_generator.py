from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.test_result import TestCase
import re

class MissingScenarioGenerator:
    """
    Generates actionable Suggested Scenarios for each missing coverage item.
    Rules:
    - Does not invent existing tests
    - Marks as Suggested Scenario, not Existing Test
    - Groups separately from Recommended Existing Tests
    """

    CAPABILITY_MAPPING = {
        "signup": ["signup", "sign-up", "register", "registration", "onboarding"],
        "login": ["login", "signin", "sign-in", "auth", "session", "token", "jwt"],
        "password reset": ["password reset", "password", "reset-password", "reset_password", "forgot-password", "forgot_password", "password/reset", "password-reset", "recovery", "recover"],
        "checkout": ["checkout", "payment", "stripe", "checkout-form", "pay"],
        "subscription": ["subscription", "subscribe", "plan", "invoice", "billing"],
        "notifications": ["notification", "notify", "email", "mail", "sms", "alert"],
        "profile/account": ["profile", "account", "user-profile", "avatar", "settings/profile"],
        "admin/settings": ["admin", "settings", "control-panel", "configuration", "system-settings"]
    }

    JOURNEY_MAPPING = {
        "signup": "User Registration Flow",
        "login": "User Authentication Flow",
        "password reset": "Password Recovery Flow",
        "checkout": "Payment Checkout Flow",
        "subscription": "Subscription Billing Flow",
        "notifications": "Notification Dispatch Flow",
        "profile/account": "User Profile Modification Flow",
        "admin/settings": "Administrative Control Flow",
        "General": "General Platform Flow"
    }

    HIGH_FIDELITY_TEMPLATES = {
        "password reset": {
            "title": "Validate password reset expired token rejection",
            "testing_type": "API / Security",
            "impacted_area": "Authentication",
            "risk_category": "Security",
            "suggested_automation_layer": "API / Security",
            "test_data": {
                "expired_token": "expired-reset-token-999",
                "valid_new_password": "StrongPass123!"
            },
            "preconditions": [
                "registered user exists",
                "password reset token is expired"
            ],
            "steps": [
                "Navigate to password reset endpoint/page using an expired token",
                "Submit a request to reset the password with a valid new password",
                "Verify that the API rejects the token and the password remains unchanged"
            ],
            "expected_result": "API rejects token and password remains unchanged."
        },
        "signup": {
            "title": "Validate user signup flow password complexity rules",
            "testing_type": "Security / UI",
            "impacted_area": "User Registration",
            "risk_category": "Security",
            "suggested_automation_layer": "Security / UI",
            "test_data": {
                "weak_password": "123456",
                "valid_password": "StrongPass123!"
            },
            "preconditions": [
                "Signup page is accessible",
                "Email address is not registered in the system"
            ],
            "steps": [
                "Navigate to registration page",
                "Enter email and a weak password '123456'",
                "Verify registration is blocked with a clear validation error",
                "Enter email and a strong password 'StrongPass123!' and click signup",
                "Verify registration completes successfully"
            ],
            "expected_result": "Registration is blocked for weak password with clear error message; successful for strong password."
        },
        "password validation": {
            "title": "Validate password validation rules",
            "testing_type": "Security / UI",
            "impacted_area": "Authentication",
            "risk_category": "Security",
            "suggested_automation_layer": "Security / UI",
            "test_data": {
                "weak_password": "123456",
                "missing_uppercase": "password123!",
                "missing_number": "Password!",
                "valid_password": "StrongPass123!"
            },
            "preconditions": ["signup or password change page is active"],
            "steps": [
                "Attempt to submit password '123456' (weak)",
                "Attempt to submit password 'password123!' (missing uppercase)",
                "Attempt to submit password 'Password!' (missing number)",
                "Attempt to submit password 'StrongPass123!' (valid)"
            ],
            "expected_result": "Weak passwords are blocked with validation error text; valid password passes validation."
        },
        "login": {
            "title": "Validate login and session management",
            "testing_type": "API / Security",
            "impacted_area": "Authentication",
            "risk_category": "Security",
            "suggested_automation_layer": "API / Security",
            "test_data": {
                "valid_username": "user@example.com",
                "valid_password": "StrongPass123!"
            },
            "preconditions": ["registered user exists"],
            "steps": [
                "Submit login request with valid credentials",
                "Verify successful login and session token return",
                "Attempt access to protected route with the token"
            ],
            "expected_result": "Session is successfully created and access is authorized."
        },
        "checkout": {
            "title": "Validate checkout and payment gateway interaction",
            "testing_type": "Integration / UI",
            "impacted_area": "Billing",
            "risk_category": "Functional",
            "suggested_automation_layer": "Integration / UI",
            "test_data": {
                "card_number": "4242_4242_4242_4242",
                "expiry": "12/28",
                "cvc": "123"
            },
            "preconditions": [
                "User has items in shopping cart",
                "Payment gateway is in test mode"
            ],
            "steps": [
                "Navigate to subscription checkout page",
                "Enter Visa payment card details",
                "Click purchase subscription",
                "Verify checkout successfully triggers payment gateway webhook and processes payment"
            ],
            "expected_result": "Subscription successfully created; invoice generated and sent securely."
        },
        "subscription": {
            "title": "Validate subscription billing invoice triggers",
            "testing_type": "Integration / UI",
            "impacted_area": "Billing",
            "risk_category": "Functional",
            "suggested_automation_layer": "Integration / UI",
            "test_data": {
                "plan_id": "premium-monthly",
                "card_number": "4242_4242_4242_4242"
            },
            "preconditions": [
                "User is logged in",
                "Subscription plan selected"
            ],
            "steps": [
                "Navigate to subscription checkout page",
                "Enter Visa payment card details",
                "Click purchase subscription",
                "Verify local state triggers webhook receipt and creates invoice entry"
            ],
            "expected_result": "Subscription successfully created; invoice generated and sent securely."
        },
        "notifications": {
            "title": "Validate email dispatch retry limit bounds",
            "testing_type": "Integration",
            "impacted_area": "Notifications",
            "risk_category": "Regression",
            "suggested_automation_layer": "Integration",
            "test_data": {
                "smtp_offline": True,
                "max_retries": 3
            },
            "preconditions": ["SMTP server is offline or unreachable"],
            "steps": [
                "Trigger notification event (e.g. signup confirmation)",
                "Observe notification dispatch queue status",
                "Verify retries follow backoff rules",
                "Verify message moves to dead-letter queue after maximum retries"
            ],
            "expected_result": "Email delivery retries fail safely and log to dead-letter queue."
        },
        "profile/account": {
            "title": "Validate profile details update validation",
            "testing_type": "UI",
            "impacted_area": "User Profile",
            "risk_category": "Functional",
            "suggested_automation_layer": "UI",
            "test_data": {
                "new_display_name": "New Name",
                "invalid_avatar_url": "ftp://bad-url"
            },
            "preconditions": ["User is logged in"],
            "steps": [
                "Navigate to user account profile settings",
                "Update display name and click save",
                "Attempt saving invalid avatar image url"
            ],
            "expected_result": "Display name successfully updated; invalid avatar url triggers UI validation error."
        },
        "admin/settings": {
            "title": "Validate administrative access controls",
            "testing_type": "API / Security",
            "impacted_area": "Administrative Control",
            "risk_category": "Security",
            "suggested_automation_layer": "API / Security",
            "test_data": {
                "non_admin_token": "regular_user_token_abc"
            },
            "preconditions": ["Admin control panel endpoint is active"],
            "steps": [
                "Attempt administrative endpoint access with non-admin authentication token",
                "Verify API returns HTTP 403 Forbidden"
            ],
            "expected_result": "Access is strictly blocked; regular users cannot access administrative endpoints."
        }
    }

    @classmethod
    def generate_missing_scenarios(
        cls,
        potential_missing_coverage: List[Dict[str, str]],
        recommended_scope: Dict[str, Any],
        impacted_areas: List[str],
        project_understanding_snapshot: Optional[Dict[str, Any]] = None,
        domain_vocab: Optional[Dict[str, Any]] = None,
        changed_files: Optional[List[str]] = None,
        db: Optional[Session] = None,
        repository_id: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        scenarios: List[Dict[str, Any]] = []

        # Extract snapshot information
        touched_layers = []
        affected_journeys = []
        if project_understanding_snapshot:
            touched_layers = project_understanding_snapshot.get("touched_layers", [])
            affected_journeys = project_understanding_snapshot.get("affected_journeys", [])

        for item in potential_missing_coverage:
            domain = item.get("domain", "General")
            feature = item.get("feature", "General")
            reason = item.get("reason", "")

            reason_lower = reason.lower()
            feature_lower = feature.lower()
            domain_lower = domain.lower()

            # 1. Resolve standard capability key
            resolved_cap = "General"
            for cap, keywords in cls.CAPABILITY_MAPPING.items():
                match = False
                for kw in keywords:
                    pattern = rf"\b{re.escape(kw)}\b"
                    if (re.search(pattern, reason_lower) or 
                        re.search(pattern, feature_lower) or 
                        re.search(pattern, domain_lower)):
                        match = True
                        break
                if match:
                    resolved_cap = cap
                    break
            
            # Special case for password validation feature
            if resolved_cap == "password reset" and "validation" in reason_lower:
                resolved_cap = "password validation"

            # 2. Fetch scenario template
            template = cls.HIGH_FIDELITY_TEMPLATES.get(resolved_cap)
            
            # 3. If no template exists, create generic but structured fallback
            if not template:
                template = {
                    "title": f"Validate {feature.replace('-', ' ').lower()} functionality",
                    "testing_type": "Integration / Regression",
                    "risk_category": "Functional",
                    "suggested_automation_layer": "Integration / Regression",
                    "test_data": {},
                    "preconditions": ["System is in default operational state"],
                    "steps": [
                        "Identify code entrypoint for the modified flow",
                        "Deploy to isolated staging environment",
                        "Execute flow validation checks"
                    ],
                    "expected_result": "Flow executes successfully, validating boundaries and handling errors gracefully."
                }

            # Map Journey & Layer
            journey = cls.JOURNEY_MAPPING.get(resolved_cap, "General Platform Flow")
            
            # Check if actual snapshot journey matches
            if affected_journeys:
                for j_item in affected_journeys:
                    j_name = j_item.get("journey") if isinstance(j_item, dict) else str(j_item)
                    if resolved_cap in j_name.lower() or any(kw in j_name.lower() for kw in cls.CAPABILITY_MAPPING.get(resolved_cap, [])):
                        journey = j_name
                        break

            # Map Impacted Layer
            layer = "API"
            if "UI" in template["testing_type"] or "UI" in template["title"]:
                layer = "UI"
            elif "Service" in template["testing_type"]:
                layer = "Service"
            elif "Integration" in template["testing_type"]:
                layer = "Integration"

            # Check if actual snapshot layer matches
            if touched_layers:
                for tl in touched_layers:
                    if layer.lower() in tl.lower():
                        layer = tl.replace(" Layer", "")
                        break

            # Mapped files and actual existing tests
            related_files = []
            kws = cls.CAPABILITY_MAPPING.get(resolved_cap, [])
            if changed_files:
                for f in changed_files:
                    f_lower = f.lower()
                    if any(kw in f_lower for kw in kws) or resolved_cap == "General":
                        related_files.append(f)

            existing_tests = []
            
            # 1. Try to get from vocab
            t_map = None
            if domain_vocab:
                t_map = domain_vocab.get("test_term_map")
            elif project_understanding_snapshot:
                vocab = project_understanding_snapshot.get("domain_vocabulary") or {}
                t_map = vocab.get("test_term_map")
            
            if t_map and resolved_cap in t_map:
                existing_tests = t_map[resolved_cap]
                
            # 2. Try to get from database
            if not existing_tests and db and repository_id:
                try:
                    from app.services.domain_sme_analyzer import DomainSMEAnalyzer
                    all_tcs = db.query(TestCase).filter(TestCase.repository_id == repository_id).all()
                    for tc in all_tcs:
                        tc_cluster = DomainSMEAnalyzer.get_canonical_cluster(tc.stable_identity)
                        if tc_cluster == resolved_cap:
                            existing_tests.append(tc.stable_identity)
                except Exception:
                    pass
            
            existing_tests = sorted(list(set(existing_tests)))

            # Populate rich scenario structure
            scenario = {
                "title": template["title"],
                "testing_type": template["testing_type"],
                "impacted_area": template.get("impacted_area", domain if domain != "General" else journey),
                "priority": "HIGH" if (domain in impacted_areas or any(domain.lower() in area.lower() or area.lower() in domain.lower() for area in impacted_areas)) else "MEDIUM",
                "preconditions": template["preconditions"],
                "steps": template["steps"],
                "expected_result": template["expected_result"],
                "automation_candidate": True,
                "reason": reason,
                "confidence": "HIGH",
                "source_signal": "MISSING_AUTOMATED_COVERAGE",
                
                # Rich SME snapshot fields
                "affected_journey": journey,
                "impacted_layer": layer,
                "risk_category": template["risk_category"],
                "test_data": template["test_data"],
                "suggested_automation_layer": template["suggested_automation_layer"],
                "related_changed_files": related_files,
                "related_existing_tests": existing_tests
            }

            scenarios.append(scenario)

        return scenarios
