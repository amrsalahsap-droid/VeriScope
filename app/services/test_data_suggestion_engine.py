from typing import List, Dict, Any, Optional

class TestDataSuggestionEngine:
    """
    Generates deterministic, safe, and non-sensitive suggested test data for common domains/features.
    Enforces rules:
    - Labels data as suggested data
    - Explicitly declares that it is not verified against app validation rules unless evidence exists
    - Keeps data safe/non-sensitive
    - Ensures deterministic output
    """

    @classmethod
    def generate_test_data(
        cls,
        impact_profile: Dict[str, Any],
        risk_assessment: Optional[Any],
        changed_files: List[str],
        testing_scope: Dict[str, Any],
        domain_or_feature: str
    ) -> Dict[str, Any]:
        
        # Resolve target domain/feature string for matching
        target = (domain_or_feature or "").lower()

        # Build disclaimer/metadata to fulfill the verification and labeling rules
        metadata = {
            "label": "suggested data",
            "safe_data_declaration": "This suggested test data contains non-sensitive mock values.",
            "rule_validation_caveat": "Note: This test data is a reference suggestion for test scaffolding. It is not verified against local application runtime validation rules."
        }

        # Check for specific evidence (e.g., if we had specific coverage file checks, we could reference them, otherwise strictly state the caveat)
        has_evidence_of_complexity_rules = False
        for f in changed_files:
            if "validation" in f.lower() or "schema" in f.lower():
                # If changed files explicitly define validation/schemas, we can note that
                has_evidence_of_complexity_rules = True
        
        if has_evidence_of_complexity_rules:
            metadata["rule_validation_caveat"] = "Note: Suggested validation patterns are based on modified schema/validation file boundaries, but should be calibrated with local runtime rules."

        # 1. Password validation
        if "password validation" in target or "password_validation" in target or "password complexity" in target:
            return {
                "_metadata": metadata,
                "weak_password": "123456",
                "missing_uppercase": "password123!",
                "missing_number": "Password!",
                "valid_password": "StrongPass123!"
            }

        # 2. Reset password / Password reset
        elif "reset password" in target or "reset_password" in target or "password reset" in target:
            return {
                "_metadata": metadata,
                "expired_token": "expired-reset-token-999",
                "invalid_token": "invalid-token-111",
                "reused_token": "reused-token-222",
                "valid_token": "valid-reset-token-777"
            }

        # 3. Signup / User Registration
        elif "signup" in target or "sign-up" in target or "user registration" in target or "registration" in target:
            return {
                "_metadata": metadata,
                "existing_email": "existing@example.com",
                "invalid_email": "invalid-email",
                "weak_password": "123456",
                "valid_signup": {
                    "email": "newuser@example.com",
                    "password": "StrongPass123!"
                }
            }

        # 4. Fallback Generic Scenario Data
        else:
            return {
                "_metadata": metadata,
                "sample_payload": {
                    "id": "test-id-100",
                    "status": "draft",
                    "value": 100
                }
            }
