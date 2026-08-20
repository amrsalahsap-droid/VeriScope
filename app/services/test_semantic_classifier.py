import os
import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.test_result import TestCase
from app.models.behavior import Behavior

logger = logging.getLogger(__name__)

class TestSemanticClassifier:
    SEMANTIC_CLASSIFIER_VERSION = "v1.0.0"

    def __init__(self, db: Session):
        self.db = db

    def classify_test_case(self, test_case: TestCase, use_ai: bool = False) -> TestCase:
        """
        Enriches a TestCase with semantic product-aware classification.
        Fails fast with configuration error if AI is requested/enabled.
        Uses deterministic regex classification otherwise.
        """
        # Fail-fast check for AI configuration
        ai_enabled_env = os.getenv("TEST_SEMANTIC_AI_ENABLED", "False").lower() in ("true", "1", "yes")
        if use_ai or ai_enabled_env:
            raise ValueError("AI provider is not configured. Failing fast under TEST_SEMANTIC_AI_ENABLED=true.")

        # Baseline system metadata
        test_case.semantic_classifier_version = self.SEMANTIC_CLASSIFIER_VERSION
        test_case.classified_at = datetime.utcnow()
        test_case.classification_source = "RULE_BASED"
        test_case.classification_confidence = 1.0
        test_case.classification_review_status = "PENDING"
        test_case.classified_by = "system"

        # Read fields for deterministic regex mapping
        name = (test_case.test_name or "").lower()
        suite = (test_case.suite_name or "").lower()
        ext_ref = (test_case.external_ac_ref or "").lower()

        # Helper flags
        is_signup = any(kw in name or kw in suite for kw in ["signup", "sign_up", "register"])
        is_reset = any(kw in name or kw in suite for kw in ["reset", "token"])
        is_password = any(kw in name or kw in suite for kw in ["password", "pwd"])
        is_weak = any(kw in name or kw in suite for kw in ["weak", "reject", "invalid"])

        candidate_slug = None

        if is_signup and is_weak and is_password:
            # 1. Sign-up weak password scenario
            test_case.product_area = "Authentication"
            test_case.business_flow = "Sign-up"
            test_case.scenario_intent = "Verify weak passwords are rejected during sign-up"
            test_case.scenario_type = "Negative Validation"
            test_case.validation_target = "Password Strength"
            test_case.risk_dimensions = {"security": "high"}
            test_case.regression_role = "Functional Regression"
            test_case.must_run_condition = "Always"
            candidate_slug = "password-validation"

        elif is_reset and is_weak and is_password and "token" not in name and "token" not in suite:
            # 2. Reset password weak password
            test_case.product_area = "Authentication"
            test_case.business_flow = "Reset Password"
            test_case.scenario_intent = "Verify weak passwords are rejected during password reset"
            test_case.scenario_type = "Negative Validation"
            test_case.validation_target = "Password Strength"
            test_case.risk_dimensions = {"security": "high"}
            test_case.regression_role = "Functional Regression"
            test_case.must_run_condition = "Always"
            candidate_slug = "password-validation"

        elif is_password and any(kw in name or kw in suite for kw in ["complexity", "length", "shorter", "missing_required"]):
            # 3. Shared password complexity
            test_case.product_area = "Authentication"
            test_case.business_flow = "Shared Policy"
            test_case.scenario_intent = "Verify password complexity and length requirements"
            test_case.scenario_type = "Negative Validation"
            test_case.validation_target = "Password Complexity"
            test_case.risk_dimensions = {"security": "medium"}
            test_case.regression_role = "Functional Regression"
            test_case.must_run_condition = "Always"
            candidate_slug = "password-validation"

        elif any(kw in name or kw in suite for kw in ["same_validation", "consistent", "ui_and_api", "parity"]):
            # 4. UI/API validation consistency
            test_case.product_area = "Authentication"
            test_case.business_flow = "Validation Consistency"
            test_case.scenario_intent = "Verify password validation is consistent between UI and API"
            test_case.scenario_type = "Consistency Check"
            test_case.validation_target = "API and UI parity"
            test_case.risk_dimensions = {"consistency": "medium"}
            test_case.regression_role = "Integration Regression"
            test_case.must_run_condition = "Always"
            candidate_slug = "password-validation"

        elif any(kw in name or kw in suite for kw in ["bypass", "frontend_validation"]):
            # 5. Frontend bypass negative security validation
            test_case.product_area = "Authentication"
            test_case.business_flow = "Security Gate"
            test_case.scenario_intent = "Verify API rejects weak passwords when UI validation is bypassed"
            test_case.scenario_type = "Negative Security Validation"
            test_case.validation_target = "API Enforcement"
            test_case.risk_dimensions = {"security": "critical"}
            test_case.regression_role = "Security Regression"
            test_case.must_run_condition = "Always"
            candidate_slug = "password-validation"

        elif is_reset and any(kw in name or kw in suite for kw in ["token", "expired", "reused"]):
            # 6. Reset token expiration
            test_case.product_area = "Authentication"
            test_case.business_flow = "Reset Password"
            test_case.scenario_intent = "Verify reset token expiration and reuse policy"
            test_case.scenario_type = "Negative Validation"
            test_case.validation_target = "Token Expiration"
            test_case.risk_dimensions = {"security": "high"}
            test_case.regression_role = "Functional Regression"
            test_case.must_run_condition = "Always"
            candidate_slug = "password-validation"

        elif "login" in name or "login" in suite:
            # 7. Login smoke test
            test_case.product_area = "Authentication"
            test_case.business_flow = "Login"
            test_case.scenario_intent = "Verify existing valid login behavior is not broken"
            test_case.scenario_type = "Smoke Test"
            test_case.validation_target = "Core Login Flow"
            test_case.risk_dimensions = {"availability": "high"}
            test_case.regression_role = "Smoke Test"
            test_case.must_run_condition = "Always"
            candidate_slug = "login"

        else:
            # No matching rules
            test_case.product_area = None
            test_case.business_flow = None
            test_case.scenario_intent = None
            test_case.scenario_type = None
            test_case.validation_target = None
            test_case.risk_dimensions = None
            test_case.regression_role = None
            test_case.must_run_condition = None

        # Resolve behavior catalog match and handle fallback status
        if candidate_slug:
            # Search candidate slugs (with fallback aliases to remain robust)
            slugs = [candidate_slug]
            if candidate_slug == "password-validation":
                slugs.extend(["sign-up-validation", "signup-validation", "password-policy", "password-complexity"])

            behavior = self.db.query(Behavior).filter(
                Behavior.repository_id == test_case.repository_id,
                Behavior.slug.in_(slugs),
                Behavior.is_deleted == False
            ).first()

            if behavior:
                test_case.behavior_key = behavior.slug
                test_case.behavior_mapping_status = "mapped_to_behavior_catalog"
            else:
                test_case.behavior_key = None
                test_case.behavior_mapping_status = "classifier_generated_unmapped"
        else:
            test_case.behavior_key = None
            test_case.behavior_mapping_status = "unmapped"

        # Populate JSON payload
        test_case.semantic_classification_json = {
            "product_area": test_case.product_area,
            "business_flow": test_case.business_flow,
            "scenario_intent": test_case.scenario_intent,
            "scenario_type": test_case.scenario_type,
            "validation_target": test_case.validation_target,
            "risk_dimensions": test_case.risk_dimensions,
            "regression_role": test_case.regression_role,
            "must_run_condition": test_case.must_run_condition,
            "classifier_version": test_case.semantic_classifier_version,
            "behavior_mapping_status": test_case.behavior_mapping_status,
        }

        return test_case

    @classmethod
    def reclassify_all_existing_tests(cls, db: Session, repository_id: uuid.UUID) -> int:
        """
        Reclassifies all existing active tests for a repository.
        """
        classifier = cls(db)
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            TestCase.is_active == True
        ).all()
        for tc in test_cases:
            classifier.classify_test_case(tc)
        db.commit()
        return len(test_cases)
