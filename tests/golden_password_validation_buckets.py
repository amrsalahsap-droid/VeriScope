"""
Golden bucket mapping for password validation demo fixture.

This defines the expected coverage bucket for each AC based on the accepted golden truth.
"""

GOLDEN_BUCKETS = {
    # COVERED_BY_PASSED_PR_TEST (16 ACs)
    1: "COVERED_BY_PASSED_PR_TEST",  # Weak passwords rejected during sign-up
    2: "COVERED_BY_PASSED_PR_TEST",  # Strong passwords accepted during sign-up
    7: "COVERED_BY_PASSED_PR_TEST",  # Weak passwords rejected during reset-password
    8: "COVERED_BY_PASSED_PR_TEST",  # Strong passwords accepted during reset-password
    9: "COVERED_BY_PASSED_PR_TEST",  # Minimum password length >= 12
    10: "COVERED_BY_PASSED_PR_TEST", # Password complexity requirements
    11: "COVERED_BY_PASSED_PR_TEST", # Empty password input rejected
    12: "COVERED_BY_PASSED_PR_TEST", # Whitespace-only password rejected
    13: "COVERED_BY_PASSED_PR_TEST", # Leading/trailing spaces handled
    14: "COVERED_BY_PASSED_PR_TEST", # Password confirmation must match
    15: "COVERED_BY_PASSED_PR_TEST", # Backend/API validation mandatory
    16: "COVERED_BY_PASSED_PR_TEST", # Direct API weak-password requests rejected
    17: "COVERED_BY_PASSED_PR_TEST", # UI/API validation rules consistent
    18: "COVERED_BY_PASSED_PR_TEST", # Validation messages safe/clear/user-friendly
    19: "COVERED_BY_PASSED_PR_TEST", # Validation messages do not expose internal details
    20: "COVERED_BY_PASSED_PR_TEST", # Password is not updated when validation fails
    
    # PARTIALLY_SUPPORTED (2 ACs)
    4: "PARTIALLY_SUPPORTED",       # Strong passwords accepted during update-password
    21: "PARTIALLY_SUPPORTED",      # Valid unexpired reset token succeeds when new password is strong
    
    # MISSING_AUTOMATED_COVERAGE (7 ACs)
    3: "MISSING_AUTOMATED_COVERAGE", # Weak passwords rejected during update-password
    5: "MISSING_AUTOMATED_COVERAGE", # User can login with new password after successful update
    6: "MISSING_AUTOMATED_COVERAGE", # Old password rejected after successful update
    22: "MISSING_AUTOMATED_COVERAGE", # Expired reset token rejected
    23: "MISSING_AUTOMATED_COVERAGE", # Reused reset token rejected
    24: "MISSING_AUTOMATED_COVERAGE", # Existing valid login not broken
    25: "MISSING_AUTOMATED_COVERAGE", # Password update/reset operation atomic
}

EXPECTED_COUNTS = {
    "COVERED_BY_PASSED_PR_TEST": 16,
    "PARTIALLY_SUPPORTED": 2,
    "MISSING_AUTOMATED_COVERAGE": 7,
    "TRACEABILITY_REVIEW": 0
}

def get_expected_bucket(ac_number: int) -> str:
    """Get the expected bucket for a given AC number."""
    return GOLDEN_BUCKETS.get(ac_number, "MISSING_AUTOMATED_COVERAGE")

def verify_bucket_counts(actual_counts: dict) -> bool:
    """Verify that actual counts match expected golden counts."""
    for bucket, expected_count in EXPECTED_COUNTS.items():
        actual_count = actual_counts.get(bucket, 0)
        if actual_count != expected_count:
            print(f"Bucket mismatch: {bucket} expected {expected_count}, got {actual_count}")
            return False
    return True
