import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.project_context_index import ProjectContextIndex

class QALeadSMEAnalyzer:
    """
    QALeadSMEAnalyzer converts product impact assessments and risk metrics
    into a high-fidelity, executable QA scope assessment.
    
    Rules:
    - Scenarios must be executable (clear title, expected result, suggested test data).
    - Includes expected result and suggested test data when applicable.
    - Sets is_automated to True ONLY if matching tests exist in the database or context index.
    - Gracefully falls back when no capabilities are identified.
    """

    CAPABILITY_KEYWORDS = {
        "signup": ("signup", "sign-up", "register", "registration", "onboarding"),
        "login": ("login", "signin", "sign-in", "auth", "session", "jwt", "token"),
        "password reset": ("reset-password", "reset_password", "forgot-password", "forgot_password", "password/reset", "password-reset"),
        "checkout": ("checkout", "payment", "stripe", "checkout-form", "pay"),
        "subscription": ("subscription", "subscribe", "plan", "invoice", "billing"),
        "notifications": ("notification", "notify", "email", "mail", "sms", "alert"),
        "profile/account": ("profile", "account", "user-profile", "avatar", "settings/profile"),
        "admin/settings": ("admin", "settings", "control-panel", "configuration", "system-settings")
    }

    @classmethod
    def _test_exists(
        cls,
        db: Optional[Session],
        repository_id: Optional[uuid.UUID],
        context_index: Optional[ProjectContextIndex],
        capability: str
    ) -> bool:
        """
        Deterministically checks if automated tests exist for the given capability.
        Traces back to actual test cases in the DB or ProjectContextIndex test assets.
        No speculative or AI guesses.
        """
        keywords = cls.CAPABILITY_KEYWORDS.get(capability, (capability,))
        
        # 1. Search database TestCase if db and repository_id are provided
        if db is not None and repository_id is not None:
            try:
                from app.models.test_result import TestCase
                query = db.query(TestCase).filter(TestCase.repository_id == repository_id)
                for tc in query.all():
                    tc_str = f"{tc.stable_identity} {tc.test_name} {tc.suite_name}".lower()
                    if any(kw in tc_str for kw in keywords):
                        return True
            except Exception:
                pass

        # 2. Search context_index test_assets if context_index is provided
        if context_index is not None and context_index.test_assets:
            for asset in context_index.test_assets:
                asset_str = f"{asset.get('name', '')} {' '.join(asset.get('source_files', []))}".lower()
                if any(kw in asset_str for kw in keywords):
                    return True

        return False

    @classmethod
    def analyze(
        cls,
        product_impact: Dict[str, Any],
        risk_assessment: Optional[Any],
        changed_files: List[str],
        context_index: Optional[ProjectContextIndex] = None,
        db: Optional[Session] = None,
        repository_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Translates ProductImpact capabilities and risk levels into executable QAScopeAssessment.
        """
        # Resolve risk level from potential formats
        risk_level = "LOW"
        if risk_assessment is not None:
            if isinstance(risk_assessment, str):
                risk_level = risk_assessment
            elif isinstance(risk_assessment, dict):
                risk_level = risk_assessment.get("risk_level", "LOW")
            elif hasattr(risk_assessment, "risk_level"):
                risk_level = getattr(risk_assessment, "risk_level", "LOW")

        affected_capabilities = product_impact.get("affected_capabilities", [])
        
        must_test: List[Dict[str, Any]] = []
        should_test: List[Dict[str, Any]] = []
        optional_test: List[Dict[str, Any]] = []
        negative_cases: List[Dict[str, Any]] = []
        regression_areas: List[Dict[str, Any]] = []
        missing_test_scenarios: List[Dict[str, Any]] = []

        # Fallback to unknown if empty or strictly unknown
        is_unknown = not affected_capabilities or (len(affected_capabilities) == 1 and affected_capabilities[0] == "unknown")

        if is_unknown:
            # Determine is_automated for regression fallback based on existence of tests
            has_existing_tests = False
            if db is not None and repository_id is not None:
                try:
                    from app.models.test_result import TestCase
                    has_existing_tests = db.query(TestCase).filter(TestCase.repository_id == repository_id).count() > 0
                except Exception:
                    pass
            if not has_existing_tests and context_index is not None and context_index.test_assets:
                has_existing_tests = len(context_index.test_assets) > 0

            must_test.append({
                "scenario": "Verify changed file paths for basic regression",
                "expected_result": "Code changes compile successfully and do not cause syntax errors or crash during execution.",
                "suggested_test_data": None,
                "is_automated": has_existing_tests
            })
            should_test.append({
                "scenario": "Execute downstream integration tests for changed areas",
                "expected_result": "All neighboring modules integrate without errors.",
                "suggested_test_data": None,
                "is_automated": False
            })
            optional_test.append({
                "scenario": "Verify static code analysis rules and linter compliance",
                "expected_result": "Linter reports zero errors or warnings on changed files.",
                "suggested_test_data": None,
                "is_automated": False
            })
            negative_cases.append({
                "scenario": "Submit malformed or empty parameters to modified modules",
                "expected_result": "Modified code handles invalid parameters gracefully without throwing unhandled exceptions.",
                "suggested_test_data": None,
                "is_automated": False
            })
            regression_areas.append({
                "area": "Changed modules regression",
                "description": "Ensure modified file paths do not introduce breaking bugs in surrounding legacy code.",
                "is_automated": has_existing_tests
            })
        else:
            for cap in affected_capabilities:
                if cap == "unknown":
                    continue

                automated = cls._test_exists(db, repository_id, context_index, cap)

                if cap == "signup":
                    must_test.extend([
                        {
                            "scenario": "Register user with valid registration details and unique email",
                            "expected_result": "User is successfully created in database, activation email is dispatched, and redirect to onboarding is triggered.",
                            "suggested_test_data": {"email": "new_user_123@example.com", "password": "StrongPass123!", "name": "Jane Doe"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Enforce password validation rules during signup",
                            "expected_result": "Passwords not meeting length, character complexity, or digit requirements are blocked with appropriate UI helper text.",
                            "suggested_test_data": {"weak_passwords": ["123456", "no_digits!", "NOCAPS123"], "strong_password": "StrongPass123!"},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Verify activation email dispatch retry under high queue load",
                        "expected_result": "Signup is not blocked by email latency; notification task is offloaded to queue and successfully retries.",
                        "suggested_test_data": {"email": "new_user_queue@example.com"},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Autofill and autofocus signup fields for accessibility",
                        "expected_result": "Fields support autocomplete attributes and can be fully navigated using keyboard tab stops.",
                        "suggested_test_data": None,
                        "is_automated": automated
                    })
                    negative_cases.extend([
                        {
                            "scenario": "Attempt registration using a pre-existing email address",
                            "expected_result": "Registration is rejected with a validation error stating the email is already in use; no duplicate user is created.",
                            "suggested_test_data": {"email": "existing@example.com", "password": "StrongPass123!"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Attempt registration with malformed email strings",
                            "expected_result": "Browser or API validates email format and blocks submission.",
                            "suggested_test_data": {"invalid_emails": ["missing_at.com", "user@", "@domain.com"]},
                            "is_automated": automated
                        }
                    ])
                    regression_areas.append({
                        "area": "User Registration",
                        "description": "Verify existing registration logic is unaffected by new user constraints.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated validation for user registration signup rules",
                            "expected_result": "SignUp integration tests enforce password length and address formatting restrictions.",
                            "suggested_test_data": {"test_suite_path": "tests/test_signup_rules.py"},
                            "is_automated": False
                        })

                elif cap == "login":
                    must_test.extend([
                        {
                            "scenario": "Verify login authentication with valid credentials",
                            "expected_result": "User successfully authenticated, JWT/Session cookie generated with secure/httpOnly flags, and redirect to dashboard occurs.",
                            "suggested_test_data": {"email": "user@example.com", "password": "StrongPass123!"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Verify session timeout and token expiration validation",
                            "expected_result": "Expired tokens or inactive sessions are correctly invalidated; user is redirected to login page on subsequent requests.",
                            "suggested_test_data": {"session_expiry_minutes": 15},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Verify concurrent logins from different devices",
                        "expected_result": "Concurrent sessions are active simultaneously, or prior sessions are terminated based on security configurations.",
                        "suggested_test_data": {"devices": ["Desktop-Chrome", "Mobile-Safari"]},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Verify post-login redirection to originally requested path",
                        "expected_result": "User is routed directly to the bookmarked protected route they tried to access before being forced to login.",
                        "suggested_test_data": {"redirect_target": "/settings/billing"},
                        "is_automated": automated
                    })
                    negative_cases.extend([
                        {
                            "scenario": "Submit authentication with incorrect password",
                            "expected_result": "Authentication rejected with a generic 'Invalid email or password' message to prevent email harvesting.",
                            "suggested_test_data": {"email": "user@example.com", "incorrect_password": "WrongPassword123"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Enforce account lockout after multiple consecutive failed attempts",
                            "expected_result": "Account is temporarily locked or CAPTCHA is triggered after 5 failed login attempts to prevent brute-forcing.",
                            "suggested_test_data": {"email": "user@example.com", "failed_attempts_count": 5},
                            "is_automated": automated
                        }
                    ])
                    regression_areas.append({
                        "area": "Authentication State",
                        "description": "Ensure login session cookie integrity and valid token authorization remain stable.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated integration verification for session generation and JWT issuance",
                            "expected_result": "Tokens generated post-auth are validated for algorithm strength and claims structure.",
                            "suggested_test_data": {"test_suite_path": "tests/test_auth_tokens.py"},
                            "is_automated": False
                        })

                elif cap == "password reset":
                    must_test.extend([
                        {
                            "scenario": "Request password reset with valid email",
                            "expected_result": "Time-bound, single-use reset token generated and sent to the user email; database records creation and expiration timestamp.",
                            "suggested_test_data": {"email": "user@example.com"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Verify password reset with a valid token",
                            "expected_result": "New password is saved, old session tokens are invalidated, and login with new password succeeds.",
                            "suggested_test_data": {"valid_token": "valid-reset-token-777", "new_password": "NewStrongPass123!"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Verify old password rejected after successful reset",
                            "expected_result": "Attempting login with the prior password fails immediately with standard authentication error.",
                            "suggested_test_data": {"email": "user@example.com", "old_password": "StrongPass123!"},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Verify password reset token expiration rules",
                        "expected_result": "Using the token after the expiration window (e.g. 1 hour) yields an invalid token error.",
                        "suggested_test_data": {"expired_token": "expired-reset-token-999"},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Verify password reset email styling and links responsiveness",
                        "expected_result": "Reset link button is fully readable and functional on mobile, tablet, and desktop viewports.",
                        "suggested_test_data": None,
                        "is_automated": automated
                    })
                    negative_cases.extend([
                        {
                            "scenario": "Attempt password reset request for non-existent email",
                            "expected_result": "System returns success notification to prevent user enumeration, but sends no email.",
                            "suggested_test_data": {"email": "unknown@example.com"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Attempt password reset with an invalid or reused token",
                            "expected_result": "Submission is rejected with clear error; password remains unchanged, and token reuse is flagged or blocked.",
                            "suggested_test_data": {"invalid_token": "invalid-token-111", "reused_token": "reused-token-222"},
                            "is_automated": automated
                        }
                    ])
                    regression_areas.append({
                        "area": "Credential Management",
                        "description": "Verify old password rejection and reset link generation do not regress.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated boundary check for password reset token generation expiration",
                            "expected_result": "Unit tests assert that reset tokens cannot be executed exactly 3601 seconds post-generation.",
                            "suggested_test_data": {"test_suite_path": "tests/test_reset_boundaries.py"},
                            "is_automated": False
                        })

                elif cap == "checkout":
                    must_test.extend([
                        {
                            "scenario": "Execute checkout with valid payment card details",
                            "expected_result": "Stripe/Payment gateway processes transaction successfully; order record is created and payment receipt is generated.",
                            "suggested_test_data": {"card_number": "4242_4242_4242_4242", "cvc": "123", "expiry": "12/28"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Verify order inventory validation prior to checkout completion",
                            "expected_result": "Items are temporarily reserved during checkout; out-of-stock items block completion and update cart gracefully.",
                            "suggested_test_data": {"cart_items": [{"id": "item-001", "quantity": 1}]},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Verify currency conversion formatting on checkout summary",
                        "expected_result": "Pricing totals match localized format matching the currency symbol and decimal formatting.",
                        "suggested_test_data": {"currency": "USD", "subtotal": 99.00},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Verify coupon code application discount calculations",
                        "expected_result": "Valid discount percentage/amount subtracted from order total before passing to payment gateway.",
                        "suggested_test_data": {"coupon": "SUMMER50", "discount_percentage": 50},
                        "is_automated": automated
                    })
                    negative_cases.extend([
                        {
                            "scenario": "Attempt checkout with declined payment card",
                            "expected_result": "Transaction fails gracefully with friendly user error; cart contents are preserved.",
                            "suggested_test_data": {"card_number": "4000_0000_0000_0002", "decline_code": "card_declined"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Attempt checkout with empty cart or zero values",
                            "expected_result": "Checkout request is blocked on client and API layers; redirects user back to catalog or cart.",
                            "suggested_test_data": {"cart_items": []},
                            "is_automated": automated
                        }
                    ])
                    regression_areas.append({
                        "area": "Payment Gateways",
                        "description": "Validate existing checkout flows continue to charge cards correctly.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated endpoint validation for checkout card declines",
                            "expected_result": "API endpoints throw expected 402 Payment Required for known mock gateway failure payloads.",
                            "suggested_test_data": {"test_suite_path": "tests/test_checkout_declines.py"},
                            "is_automated": False
                        })

                elif cap == "subscription":
                    must_test.extend([
                        {
                            "scenario": "Verify subscription creation and trial period allocation",
                            "expected_result": "Billing plan successfully registered; user access is immediately provisioned, and next billing date is offset by trial length.",
                            "suggested_test_data": {"plan_id": "pro-monthly", "trial_days": 14},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Process automatic subscription billing renewal cycle",
                            "expected_result": "Recurring invoice generated, payment gateway executes charge, and notification of charge is generated.",
                            "suggested_test_data": {"subscription_id": "sub_xyz123", "amount": 29.00},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Upgrade subscription plan mid-cycle with proration calculation",
                        "expected_result": "Billing difference is computed, prorated invoice item created, and plan features upgraded immediately.",
                        "suggested_test_data": {"current_plan": "basic-monthly", "new_plan": "pro-monthly"},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Downgrade plan features and defer billing updates to next cycle",
                        "expected_result": "Plan downgrade is scheduled; existing features remain active until current period ends.",
                        "suggested_test_data": {"target_plan": "basic-monthly"},
                        "is_automated": automated
                    })
                    negative_cases.extend([
                        {
                            "scenario": "Attempt subscription creation with expired credit card",
                            "expected_result": "Registration blocked, subscription marked incomplete or past_due, and credit card update prompt is shown.",
                            "suggested_test_data": {"card_number": "4242_4242_4242_4242", "expiry": "01/22"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Process failed renewal billing recovery workflow (Dunning)",
                            "expected_result": "Card failures trigger retry schedule over 3, 5, and 7 days before suspending user subscription access.",
                            "suggested_test_data": {"failed_billing_retries": 3},
                            "is_automated": automated
                        }
                    ])
                    regression_areas.append({
                        "area": "Billing & Subscriptions",
                        "description": "Ensure trial period and subscription upgrades are preserved.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated scheduler test for recurring billing renewal charges",
                            "expected_result": "Durable billing checks assert proper billing intervals for monthly and annual tiers.",
                            "suggested_test_data": {"test_suite_path": "tests/test_subscription_billing.py"},
                            "is_automated": False
                        })

                elif cap == "notifications":
                    must_test.extend([
                        {
                            "scenario": "Trigger email dispatch upon key lifecycle events",
                            "expected_result": "Email is successfully formatted and sent via SMTP/SES gateway; delivery log record created.",
                            "suggested_test_data": {"event": "user.signup", "recipient": "user@example.com"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Verify user notification delivery channel preferences",
                            "expected_result": "Dispatched alerts strictly respect configured preferences (e.g. email enabled, SMS disabled).",
                            "suggested_test_data": {"preferences": {"email": True, "sms": False}},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Verify dead-letter queue routing for offline SMTP server failures",
                        "expected_result": "SMTP connection timeouts do not drop notifications; failures are routed to retry queue and safely retry up to limit.",
                        "suggested_test_data": {"smtp_status": "offline"},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Verify email template HTML rendering across dark and light client themes",
                        "expected_result": "Readability is preserved with clear contrast backgrounds and correctly sized action buttons.",
                        "suggested_test_data": None,
                        "is_automated": automated
                    })
                    negative_cases.append({
                        "scenario": "Attempt email dispatch to invalid and bounced addresses",
                        "expected_result": "Bounces are captured via webhooks, and recipient address is flagged as invalid or blacklisted to protect sender score.",
                        "suggested_test_data": {"email": "bounce@example.com"},
                        "is_automated": automated
                    })
                    regression_areas.append({
                        "area": "Notification Dispatch Queue",
                        "description": "Verify that email and SMS alerts dispatch normally.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated delivery logging retry limit integration validation",
                            "expected_result": "SMTP failover integration suite validates retry queuing behavior under latency.",
                            "suggested_test_data": {"test_suite_path": "tests/test_notifications.py"},
                            "is_automated": False
                        })

                elif cap == "profile/account":
                    must_test.extend([
                        {
                            "scenario": "Update profile text fields and display name",
                            "expected_result": "New profile fields successfully updated in database and reflected instantly on dashboard.",
                            "suggested_test_data": {"name": "Jane Smith", "job_title": "Staff Engineer"},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Upload profile avatar image with file validation",
                            "expected_result": "Supported formats (JPEG, PNG) are resized, stored securely in storage bucket, and profile URL is updated.",
                            "suggested_test_data": {"file_type": "image/png", "file_size_bytes": 204800},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Change user registered primary email address",
                        "expected_result": "Email change requires verification of the new address; old email remains active until verified.",
                        "suggested_test_data": {"new_email": "jane.smith@example.com"},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Verify timezone and localization changes impact timestamp displays",
                        "expected_result": "Timestamps are localized dynamically based on selected timezone formatting.",
                        "suggested_test_data": {"timezone": "Europe/London"},
                        "is_automated": automated
                    })
                    negative_cases.extend([
                        {
                            "scenario": "Attempt avatar upload exceeding maximum size limit",
                            "expected_result": "Upload is blocked with clear validation warning explaining file size limits (e.g., max 5MB).",
                            "suggested_test_data": {"file_size_bytes": 10485760},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Attempt account details modification without active session authentication",
                            "expected_result": "Request blocked immediately with 401 Unauthorized status, and redirect to login.",
                            "suggested_test_data": {"unauthorized_request": True},
                            "is_automated": automated
                        }
                    ])
                    regression_areas.append({
                        "area": "Profile Administration",
                        "description": "Ensure avatar images and details update regularly.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated validation of avatar upload file size restrictions",
                            "expected_result": "Payload limits for binary attachments are validated on API gateways and routes.",
                            "suggested_test_data": {"test_suite_path": "tests/test_profile_uploads.py"},
                            "is_automated": False
                        })

                elif cap == "admin/settings":
                    must_test.extend([
                        {
                            "scenario": "Update system settings as administrator",
                            "expected_result": "System configurations updated in database, cache is invalidated, and updated settings are applied immediately.",
                            "suggested_test_data": {"maintenance_mode": False, "max_login_retries": 5},
                            "is_automated": automated
                        },
                        {
                            "scenario": "Enforce RBAC rules to prevent non-admins accessing administrative features",
                            "expected_result": "Administrative endpoints and pages block standard users, returning 403 Forbidden.",
                            "suggested_test_data": {"user_role": "member"},
                            "is_automated": automated
                        }
                    ])
                    should_test.append({
                        "scenario": "Verify system audit logging for setting changes",
                        "expected_result": "An audit trail entry is created recording the admin user ID, change type, and old vs new settings values.",
                        "suggested_test_data": {"admin_id": "admin-123", "action": "update_settings"},
                        "is_automated": automated
                    })
                    optional_test.append({
                        "scenario": "Export system configurations to CSV/JSON format",
                        "expected_result": "File is correctly generated containing all current configurations.",
                        "suggested_test_data": None,
                        "is_automated": automated
                    })
                    negative_cases.append({
                        "scenario": "Attempt administrative configuration updates using malformed parameters",
                        "expected_result": "Database validation blocks updates; displays error details without breaking current settings.",
                        "suggested_test_data": {"max_login_retries": -10},
                        "is_automated": automated
                    })
                    regression_areas.append({
                        "area": "Administrative Access Controls",
                        "description": "Verify RBAC controls remain strict across system settings.",
                        "is_automated": automated
                    })
                    if not automated:
                        missing_test_scenarios.append({
                            "scenario": "Automated role-based access control (RBAC) authorization check",
                            "expected_result": "Tests verify every route decorated with admin auth blocks basic tier sessions.",
                            "suggested_test_data": {"test_suite_path": "tests/test_admin_auth.py"},
                            "is_automated": False
                        })

        # Deduplicate list elements dynamically while preserving stable ordering
        def dedup_by_key(lst: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
            seen = set()
            res = []
            for item in lst:
                val = item.get(key)
                if val not in seen:
                    seen.add(val)
                    res.append(item)
            return res

        return {
            "must_test": dedup_by_key(must_test, "scenario"),
            "should_test": dedup_by_key(should_test, "scenario"),
            "optional_test": dedup_by_key(optional_test, "scenario"),
            "negative_cases": dedup_by_key(negative_cases, "scenario"),
            "regression_areas": dedup_by_key(regression_areas, "area"),
            "missing_test_scenarios": dedup_by_key(missing_test_scenarios, "scenario")
        }
