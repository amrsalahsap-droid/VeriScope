"""
Mismatched AC / JUnit regression test fixture.

Represents a real-world bad fixture where:
- 25 Acceptance Criteria span sign-up, update-password, reset-password, API validation, login, and atomicity.
- 18 JUnit test cases declare acceptance_criterion references that conflict with the actual test title/classname semantics.
"""

from typing import List, Dict, Any

# 25 Acceptance Criteria definitions
BAD_FIXTURE_25_ACS = [
    # Sign-up Flow (AC-01 .. AC-09)
    {"source_number": 1, "ac_number": 1, "stable_ac_key": "AC-KEY-SIGNUP-01", "identifier": "AC-01", "title": "Sign-up password length minimum 8 characters", "text": "System must enforce minimum password length of 8 characters during sign-up", "group": "Sign-up"},
    {"source_number": 2, "ac_number": 2, "stable_ac_key": "AC-KEY-SIGNUP-02", "identifier": "AC-02", "title": "Sign-up require uppercase letter", "text": "System must require at least one uppercase letter in passwords during sign-up", "group": "Sign-up"},
    {"source_number": 3, "ac_number": 3, "stable_ac_key": "AC-KEY-SIGNUP-03", "identifier": "AC-03", "title": "Sign-up require lowercase letter", "text": "System must require at least one lowercase letter in passwords during sign-up", "group": "Sign-up"},
    {"source_number": 4, "ac_number": 4, "stable_ac_key": "AC-KEY-SIGNUP-04", "identifier": "AC-04", "title": "Sign-up require number", "text": "System must require at least one number in passwords during sign-up", "group": "Sign-up"},
    {"source_number": 5, "ac_number": 5, "stable_ac_key": "AC-KEY-SIGNUP-05", "identifier": "AC-05", "title": "Sign-up require special character", "text": "System must require at least one special character in passwords during sign-up", "group": "Sign-up"},
    {"source_number": 6, "ac_number": 6, "stable_ac_key": "AC-KEY-SIGNUP-06", "identifier": "AC-06", "title": "Sign-up reject common weak passwords", "text": "System must reject passwords containing common weak patterns during sign-up", "group": "Sign-up"},
    {"source_number": 7, "ac_number": 7, "stable_ac_key": "AC-KEY-SIGNUP-07", "identifier": "AC-07", "title": "Sign-up password strength indicator", "text": "System must display password strength indicator during sign-up", "group": "Sign-up"},
    {"source_number": 8, "ac_number": 8, "stable_ac_key": "AC-KEY-SIGNUP-08", "identifier": "AC-08", "title": "Sign-up confirm password match", "text": "System must compare both password entries for exact match during sign-up", "group": "Sign-up"},
    {"source_number": 9, "ac_number": 9, "stable_ac_key": "AC-KEY-SIGNUP-09", "identifier": "AC-09", "title": "Sign-up prevent mismatch submission", "text": "System must prevent sign-up submission if passwords do not match", "group": "Sign-up"},

    # Update Password Flow (AC-10 .. AC-14)
    {"source_number": 10, "ac_number": 10, "stable_ac_key": "AC-KEY-UPDATE-10", "identifier": "AC-10", "title": "Update-password requires current password", "text": "System must require current password before allowing password change in update-password", "group": "Update password"},
    {"source_number": 11, "ac_number": 11, "stable_ac_key": "AC-KEY-UPDATE-11", "identifier": "AC-11", "title": "Update-password validate hash", "text": "System must validate current password matches stored hash in update-password", "group": "Update password"},
    {"source_number": 12, "ac_number": 12, "stable_ac_key": "AC-KEY-UPDATE-12", "identifier": "AC-12", "title": "Update-password invalidate active sessions", "text": "System must invalidate all active sessions after password change in update-password", "group": "Update password"},
    {"source_number": 13, "ac_number": 13, "stable_ac_key": "AC-KEY-UPDATE-13", "identifier": "AC-13", "title": "Update-password confirmation email", "text": "System must send confirmation email after successful password update", "group": "Update password"},
    {"source_number": 14, "ac_number": 14, "stable_ac_key": "AC-KEY-UPDATE-14", "identifier": "AC-14", "title": "Update-password complexity enforcement", "text": "System must enforce same complexity rules for password update", "group": "Update password"},

    # Reset Password Flow (AC-15 .. AC-19)
    {"source_number": 15, "ac_number": 15, "stable_ac_key": "AC-KEY-RESET-15", "identifier": "AC-15", "title": "Reset-password send reset link", "text": "System must send password reset link to user email in reset-password", "group": "Reset password"},
    {"source_number": 16, "ac_number": 16, "stable_ac_key": "AC-KEY-RESET-16", "identifier": "AC-16", "title": "Reset-password validate reset token", "text": "System must validate reset token before allowing password change in reset-password", "group": "Reset password"},
    {"source_number": 17, "ac_number": 17, "stable_ac_key": "AC-KEY-RESET-17", "identifier": "AC-17", "title": "Reset-password reject weak passwords", "text": "Weak passwords are rejected during reset-password", "group": "Reset password"},
    {"source_number": 18, "ac_number": 18, "stable_ac_key": "AC-KEY-RESET-18", "identifier": "AC-18", "title": "Reset-password invalidate old password", "text": "System must invalidate old password after successful reset in reset-password", "group": "Reset password"},
    {"source_number": 19, "ac_number": 19, "stable_ac_key": "AC-KEY-RESET-19", "identifier": "AC-19", "title": "Reset-password require re-login", "text": "System must require user to log in with new password after reset", "group": "Reset password"},

    # API Validation & Misc (AC-20 .. AC-25)
    {"source_number": 20, "ac_number": 20, "stable_ac_key": "AC-KEY-API-20", "identifier": "AC-20", "title": "API validation content-type header", "text": "API validation must enforce json content-type header", "group": "API validation"},
    {"source_number": 21, "ac_number": 21, "stable_ac_key": "AC-KEY-API-21", "identifier": "AC-21", "title": "API validation error payload", "text": "API validation returns 400 status with JSON error payload", "group": "API validation"},
    {"source_number": 22, "ac_number": 22, "stable_ac_key": "AC-KEY-LOGIN-22", "identifier": "AC-22", "title": "Login failure invalid credentials", "text": "Login fails with invalid credentials error message", "group": "Login"},
    {"source_number": 23, "ac_number": 23, "stable_ac_key": "AC-KEY-LOGIN-23", "identifier": "AC-23", "title": "Login success valid credentials", "text": "Login succeeds with valid credentials and issues auth token", "group": "Login"},
    {"source_number": 24, "ac_number": 24, "stable_ac_key": "AC-KEY-MISC-24", "identifier": "AC-24", "title": "Password change atomicity", "text": "Password changes must be atomic update or reset not both", "group": "Atomicity"},
    {"source_number": 25, "ac_number": 25, "stable_ac_key": "AC-KEY-LOGIN-25", "identifier": "AC-25", "title": "Login rate limiting", "text": "System must rate limit login attempts after 5 consecutive failures", "group": "Login"},
]


# 18 JUnit test cases XML with MISMATCHED / CONFLICTED AC refs
BAD_FIXTURE_18_JUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="com.example.auth.ResetPasswordTest" tests="4">
    <!-- CONFLICT 1: Reset password test declares update-password AC-10 -->
    <testcase name="test_weak_password_rejection_during_reset" classname="com.example.auth.ResetPasswordTest">
      <properties>
        <property name="title" value="Weak passwords are rejected during reset-password" />
        <property name="acceptance_criterion" value="AC-10" />
        <property name="business_flow" value="Reset password" />
      </properties>
    </testcase>
    <!-- CONFLICT 2: Reset password test declares update-password AC-12 -->
    <testcase name="test_invalidate_old_password_after_reset" classname="com.example.auth.ResetPasswordTest">
      <properties>
        <property name="title" value="Invalidate old password after reset" />
        <property name="acceptance_criterion" value="AC-12" />
        <property name="business_flow" value="Reset password" />
      </properties>
    </testcase>
    <!-- CONFLICT 3: Reset password test declares update-password AC-11 -->
    <testcase name="test_validate_reset_token" classname="com.example.auth.ResetPasswordTest">
      <properties>
        <property name="title" value="Validate reset token before reset-password" />
        <property name="acceptance_criterion" value="AC-11" />
        <property name="business_flow" value="Reset password" />
      </properties>
    </testcase>
    <!-- VALID MATCH: Reset password test declares AC-15 -->
    <testcase name="test_send_reset_link" classname="com.example.auth.ResetPasswordTest">
      <properties>
        <property name="title" value="Send password reset link to email" />
        <property name="acceptance_criterion" value="AC-15" />
        <property name="business_flow" value="Reset password" />
      </properties>
    </testcase>
  </testsuite>

  <testsuite name="com.example.auth.SignUpTest" tests="6">
    <!-- VALID MATCHES for sign-up -->
    <testcase name="test_signup_min_length" classname="com.example.auth.SignUpTest">
      <properties>
        <property name="title" value="Sign-up password length minimum 8 characters" />
        <property name="acceptance_criterion" value="AC-01" />
        <property name="business_flow" value="Sign-up" />
      </properties>
    </testcase>
    <testcase name="test_signup_uppercase" classname="com.example.auth.SignUpTest">
      <properties>
        <property name="title" value="Sign-up require uppercase letter" />
        <property name="acceptance_criterion" value="AC-02" />
        <property name="business_flow" value="Sign-up" />
      </properties>
    </testcase>
    <testcase name="test_signup_lowercase" classname="com.example.auth.SignUpTest">
      <properties>
        <property name="title" value="Sign-up require lowercase letter" />
        <property name="acceptance_criterion" value="AC-03" />
        <property name="business_flow" value="Sign-up" />
      </properties>
    </testcase>
    <testcase name="test_signup_number" classname="com.example.auth.SignUpTest">
      <properties>
        <property name="title" value="Sign-up require number" />
        <property name="acceptance_criterion" value="AC-04" />
        <property name="business_flow" value="Sign-up" />
      </properties>
    </testcase>
    <testcase name="test_signup_special_char" classname="com.example.auth.SignUpTest">
      <properties>
        <property name="title" value="Sign-up require special character" />
        <property name="acceptance_criterion" value="AC-05" />
        <property name="business_flow" value="Sign-up" />
      </properties>
    </testcase>
    <testcase name="test_signup_reject_weak" classname="com.example.auth.SignUpTest">
      <properties>
        <property name="title" value="Sign-up reject common weak passwords" />
        <property name="acceptance_criterion" value="AC-06" />
        <property name="business_flow" value="Sign-up" />
      </properties>
    </testcase>
  </testsuite>

  <testsuite name="com.example.auth.UpdatePasswordTest" tests="4">
    <!-- CONFLICT 4: Update password test declares sign-up AC-08 -->
    <testcase name="test_update_password_requires_current" classname="com.example.auth.UpdatePasswordTest">
      <properties>
        <property name="title" value="Update password requires current password" />
        <property name="acceptance_criterion" value="AC-08" />
        <property name="business_flow" value="Update password" />
      </properties>
    </testcase>
    <!-- VALID MATCHES for update-password -->
    <testcase name="test_update_password_hash_check" classname="com.example.auth.UpdatePasswordTest">
      <properties>
        <property name="title" value="Update password validate hash" />
        <property name="acceptance_criterion" value="AC-11" />
        <property name="business_flow" value="Update password" />
      </properties>
    </testcase>
    <testcase name="test_update_password_invalidate_sessions" classname="com.example.auth.UpdatePasswordTest">
      <properties>
        <property name="title" value="Update password invalidate active sessions" />
        <property name="acceptance_criterion" value="AC-12" />
        <property name="business_flow" value="Update password" />
      </properties>
    </testcase>
    <testcase name="test_update_password_send_email" classname="com.example.auth.UpdatePasswordTest">
      <properties>
        <property name="title" value="Update password confirmation email" />
        <property name="acceptance_criterion" value="AC-13" />
        <property name="business_flow" value="Update password" />
      </properties>
    </testcase>
  </testsuite>

  <testsuite name="com.example.auth.ApiAndLoginTest" tests="4">
    <!-- VALID MATCHES for API & Login -->
    <testcase name="test_api_content_type" classname="com.example.auth.ApiAndLoginTest">
      <properties>
        <property name="title" value="API validation content-type header" />
        <property name="acceptance_criterion" value="AC-20" />
        <property name="business_flow" value="API validation" />
      </properties>
    </testcase>
    <testcase name="test_api_400_json" classname="com.example.auth.ApiAndLoginTest">
      <properties>
        <property name="title" value="API validation error payload" />
        <property name="acceptance_criterion" value="AC-21" />
        <property name="business_flow" value="API validation" />
      </properties>
    </testcase>
    <testcase name="test_login_failure" classname="com.example.auth.ApiAndLoginTest">
      <properties>
        <property name="title" value="Login failure invalid credentials" />
        <property name="acceptance_criterion" value="AC-22" />
        <property name="business_flow" value="Login" />
      </properties>
    </testcase>
    <testcase name="test_login_success" classname="com.example.auth.ApiAndLoginTest">
      <properties>
        <property name="title" value="Login success valid credentials" />
        <property name="acceptance_criterion" value="AC-23" />
        <property name="business_flow" value="Login" />
      </properties>
    </testcase>
  </testsuite>
</testsuites>
"""
