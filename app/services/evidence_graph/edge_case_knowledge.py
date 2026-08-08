"""Central repository of common edge cases per flow for risk-based recommendations."""

EDGE_CASE_KNOWLEDGE = {
    "sign-up": [
        ("password same as email", "Rejection with 'password must differ from email'"),
        ("password with unicode characters", "Acceptance of unicode password"),
        ("password at maximum length boundary", "Acceptance at max, rejection at max+1"),
        ("SQL injection in password field", "Input sanitized, no SQL execution"),
        ("concurrent sign-up with same email", "One succeeds, other gets duplicate error"),
    ],
    "login": [
        ("login after 5 failed attempts", "Account locked or rate-limited"),
        ("login with deactivated account", "Rejection with appropriate message"),
        ("concurrent login from different IPs", "Session management correct"),
    ],
    "reset-password": [
        ("token used twice", "Second use rejected"),
        ("token expiration exactly at boundary", "At-expiry accepted, past-expiry rejected"),
        ("new password same as old password", "Rejection with policy message"),
    ],
    "update-password": [
        ("wrong current password", "Rejection, password unchanged"),
        ("new password same as current", "Rejection with appropriate message"),
    ],
}
