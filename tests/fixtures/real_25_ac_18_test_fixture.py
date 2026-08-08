"""
Real 25-AC / 18-Test Fixture for AC → Test Mapping AI Integration Regression.

Distribution:
- Total ACs: 25
- Evidence Verified Aligned: 2 (AC-01, AC-02)
- Metadata Conflict Semantic Match: 16 (AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-13, AC-14, AC-16, AC-17, AC-18, AC-20, AC-21, AC-22, AC-23, AC-24)
- Partial Support: 3 (AC-15, AC-19, AC-25)
- No Candidate: 4 (AC-03, AC-04, AC-05, AC-06)
- Total Tests: 18 (Passed: 18, Failed: 0, Errors: 0, Skipped: 0)
"""

from typing import List, Dict, Any

REAL_25_ACS: List[Dict[str, Any]] = [
    {"ac_number": 1, "identifier": "AC-01", "stable_ac_key": "AC-KEY-SIGNUP-01", "title": "Weak passwords are rejected during sign-up.", "text": "Weak passwords are rejected during sign-up.", "group": "Sign-up"},
    {"ac_number": 2, "identifier": "AC-02", "stable_ac_key": "AC-KEY-SIGNUP-02", "title": "Strong passwords are accepted during sign-up.", "text": "Strong passwords are accepted during sign-up.", "group": "Sign-up"},
    {"ac_number": 3, "identifier": "AC-03", "stable_ac_key": "AC-KEY-UPDATE-03", "title": "Weak passwords are rejected during update-password.", "text": "Weak passwords are rejected during update-password.", "group": "Update password"},
    {"ac_number": 4, "identifier": "AC-04", "stable_ac_key": "AC-KEY-UPDATE-04", "title": "Strong passwords are accepted during update-password.", "text": "Strong passwords are accepted during update-password.", "group": "Update password"},
    {"ac_number": 5, "identifier": "AC-05", "stable_ac_key": "AC-KEY-UPDATE-05", "title": "After successful password update, the user can log in using the new password.", "text": "After successful password update, the user can log in using the new password.", "group": "Update password"},
    {"ac_number": 6, "identifier": "AC-06", "stable_ac_key": "AC-KEY-UPDATE-06", "title": "After successful password update, the old password is rejected.", "text": "After successful password update, the old password is rejected.", "group": "Update password"},
    {"ac_number": 7, "identifier": "AC-07", "stable_ac_key": "AC-KEY-RESET-07", "title": "Weak passwords are rejected during reset-password.", "text": "Weak passwords are rejected during reset-password.", "group": "Reset password"},
    {"ac_number": 8, "identifier": "AC-08", "stable_ac_key": "AC-KEY-RESET-08", "title": "Strong passwords are accepted during reset-password.", "text": "Strong passwords are accepted during reset-password.", "group": "Reset password"},
    {"ac_number": 9, "identifier": "AC-09", "stable_ac_key": "AC-KEY-POLICY-09", "title": "Minimum password length is enforced: at least 12 characters.", "text": "Minimum password length is enforced: at least 12 characters.", "group": "Password Policy"},
    {"ac_number": 10, "identifier": "AC-10", "stable_ac_key": "AC-KEY-POLICY-10", "title": "Password complexity is enforced: uppercase, lowercase, number, and special character are required.", "text": "Password complexity is enforced: uppercase, lowercase, number, and special character are required.", "group": "Password Policy"},
    {"ac_number": 11, "identifier": "AC-11", "stable_ac_key": "AC-KEY-POLICY-11", "title": "Empty password input is rejected.", "text": "Empty password input is rejected.", "group": "Password Policy"},
    {"ac_number": 12, "identifier": "AC-12", "stable_ac_key": "AC-KEY-POLICY-12", "title": "Whitespace-only password input is rejected.", "text": "Whitespace-only password input is rejected.", "group": "Password Policy"},
    {"ac_number": 13, "identifier": "AC-13", "stable_ac_key": "AC-KEY-POLICY-13", "title": "Leading and trailing spaces are handled consistently according to the defined policy.", "text": "Leading and trailing spaces are handled consistently according to the defined policy.", "group": "Password Policy"},
    {"ac_number": 14, "identifier": "AC-14", "stable_ac_key": "AC-KEY-SIGNUP-14", "title": "Password confirmation must match the password field.", "text": "Password confirmation must match the password field.", "group": "Sign-up"},
    {"ac_number": 15, "identifier": "AC-15", "stable_ac_key": "AC-KEY-API-15", "title": "Backend/API validation is mandatory and cannot rely only on frontend validation.", "text": "Backend/API validation is mandatory and cannot rely only on frontend validation.", "group": "API Validation"},
    {"ac_number": 16, "identifier": "AC-16", "stable_ac_key": "AC-KEY-API-16", "title": "Direct API requests with weak passwords are rejected.", "text": "Direct API requests with weak passwords are rejected.", "group": "API Validation"},
    {"ac_number": 17, "identifier": "AC-17", "stable_ac_key": "AC-KEY-API-17", "title": "UI and API validation rules are consistent.", "text": "UI and API validation rules are consistent.", "group": "API Validation"},
    {"ac_number": 18, "identifier": "AC-18", "stable_ac_key": "AC-KEY-API-18", "title": "Validation error messages are safe, clear, and user-friendly.", "text": "Validation error messages are safe, clear, and user-friendly.", "group": "API Validation"},
    {"ac_number": 19, "identifier": "AC-19", "stable_ac_key": "AC-KEY-API-19", "title": "Validation error messages do not expose internal system details.", "text": "Validation error messages do not expose internal system details.", "group": "API Validation"},
    {"ac_number": 20, "identifier": "AC-20", "stable_ac_key": "AC-KEY-UPDATE-20", "title": "Password is not updated when validation fails.", "text": "Password is not updated when validation fails.", "group": "Update password"},
    {"ac_number": 21, "identifier": "AC-21", "stable_ac_key": "AC-KEY-RESET-21", "title": "Reset-password with a valid unexpired token succeeds when the new password is strong.", "text": "Reset-password with a valid unexpired token succeeds when the new password is strong.", "group": "Reset password"},
    {"ac_number": 22, "identifier": "AC-22", "stable_ac_key": "AC-KEY-RESET-22", "title": "Reset-password with an expired token is rejected.", "text": "Reset-password with an expired token is rejected.", "group": "Reset password"},
    {"ac_number": 23, "identifier": "AC-23", "stable_ac_key": "AC-KEY-RESET-23", "title": "Reset-password with a reused token is rejected.", "text": "Reset-password with a reused token is rejected.", "group": "Reset password"},
    {"ac_number": 24, "identifier": "AC-24", "stable_ac_key": "AC-KEY-LOGIN-24", "title": "Existing valid login behavior is not broken.", "text": "Existing valid login behavior is not broken.", "group": "Login"},
    {"ac_number": 25, "identifier": "AC-25", "stable_ac_key": "AC-KEY-ATOMIC-25", "title": "Password update/reset operation is atomic: either the full update succeeds or nothing changes.", "text": "Password update/reset operation is atomic: either the full update succeeds or nothing changes.", "group": "Atomicity"},
]

REAL_18_JUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="trustdesk-password-validation-regression" tests="18" failures="0" errors="0" skipped="0" time="7.231">
  <testsuite name="Password Validation Acceptance Criteria" tests="18" failures="0" errors="0" skipped="0" time="7.231" timestamp="2026-06-04T15:30:00Z">
    <properties>
      <property name="repository" value="amrsalahsap-droid/trustdesk"/>
      <property name="branch" value="branch-one"/>
      <property name="pull_request" value="1"/>
      <property name="feature" value="modern password validation rules"/>
      <property name="valid_password" value="StrongPass#2026"/>
      <property name="invalid_passwords" value="short1!, password123!, PASSWORD123!, PasswordOnly, Password123, Password!, 123456789012!, whitespace-only, empty"/>
    </properties>

    <!-- 1 & 2: Evidence Verified Aligned -->
    <testcase classname="auth.signup.password_policy" name="should_reject_weak_password_during_signup" time="0.312">
      <properties>
        <property name="title" value="Weak passwords are rejected during sign-up"/>
        <property name="acceptance_criterion" value="AC-01"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.signup.password_policy" name="should_accept_strong_password_during_signup" time="0.323">
      <properties>
        <property name="title" value="Strong passwords are accepted during sign-up"/>
        <property name="acceptance_criterion" value="AC-02"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <!-- 3 to 18: Metadata Conflict Semantic Match (and partial support triggers) -->
    <testcase classname="auth.reset_password.password_policy" name="should_reject_weak_password_during_password_reset" time="0.334">
      <properties>
        <property name="title" value="Weak passwords are rejected during reset-password"/>
        <property name="acceptance_criterion" value="AC-03"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.reset_password.password_policy" name="should_accept_strong_password_during_password_reset" time="0.345">
      <properties>
        <property name="title" value="Strong passwords are accepted during reset-password"/>
        <property name="acceptance_criterion" value="AC-04"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_reject_password_shorter_than_minimum_length" time="0.356">
      <properties>
        <property name="title" value="Minimum password length is enforced: at least 12 characters"/>
        <property name="acceptance_criterion" value="AC-05"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_reject_password_missing_required_complexity" time="0.367">
      <properties>
        <property name="title" value="Password complexity is enforced: uppercase, lowercase, number, and special character are required"/>
        <property name="acceptance_criterion" value="AC-06"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_reject_empty_password" time="0.466">
      <properties>
        <property name="title" value="Empty password input is rejected"/>
        <property name="acceptance_criterion" value="AC-15"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_reject_whitespace_only_password" time="0.477">
      <properties>
        <property name="title" value="Whitespace-only password input is rejected"/>
        <property name="acceptance_criterion" value="AC-16"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_reject_or_normalize_leading_and_trailing_spaces_consistently" time="0.488">
      <properties>
        <property name="title" value="Leading and trailing spaces are handled consistently according to the defined policy"/>
        <property name="acceptance_criterion" value="AC-17"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.signup.password_policy" name="should_reject_password_confirmation_mismatch" time="0.411">
      <properties>
        <property name="title" value="Password confirmation must match the password field"/>
        <property name="acceptance_criterion" value="AC-10"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.api.password_policy" name="should_reject_weak_password_when_frontend_validation_is_bypassed" time="0.389">
      <properties>
        <property name="title" value="Direct API requests with weak passwords are rejected"/>
        <property name="acceptance_criterion" value="AC-08"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_apply_same_validation_rules_in_ui_and_api" time="0.378">
      <properties>
        <property name="title" value="UI and API validation rules are consistent"/>
        <property name="acceptance_criterion" value="AC-07"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.password_policy" name="should_return_safe_user_friendly_validation_message" time="0.400">
      <properties>
        <property name="title" value="Validation error messages are safe, clear, and user-friendly"/>
        <property name="acceptance_criterion" value="AC-09"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.reset_password.password_policy" name="should_not_update_password_when_validation_fails" time="0.499">
      <properties>
        <property name="title" value="Password is not updated when validation fails"/>
        <property name="acceptance_criterion" value="AC-18"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.reset_password.token" name="should_accept_valid_unexpired_reset_token_with_strong_password" time="0.433">
      <properties>
        <property name="title" value="Reset-password with a valid unexpired token succeeds when the new password is strong"/>
        <property name="acceptance_criterion" value="AC-12"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.reset_password.token" name="should_reject_expired_reset_token" time="0.444">
      <properties>
        <property name="title" value="Reset-password with an expired token is rejected"/>
        <property name="acceptance_criterion" value="AC-13"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.reset_password.token" name="should_reject_reused_reset_token" time="0.455">
      <properties>
        <property name="title" value="Reset-password with a reused token is rejected"/>
        <property name="acceptance_criterion" value="AC-14"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

    <testcase classname="auth.login" name="should_keep_existing_valid_login_working" time="0.422">
      <properties>
        <property name="title" value="Existing valid login behavior is not broken"/>
        <property name="acceptance_criterion" value="AC-11"/>
        <property name="testing_type" value="Regression/Security"/>
        <property name="execution_layer" value="API/UI"/>
      </properties>
    </testcase>

  </testsuite>
</testsuites>
"""
