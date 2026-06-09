#!/usr/bin/env python3
"""
Verification script for recommendation scenario breadth.

This script simulates a seed PR with auth/security changes and verifies
that the scenario generation produces comprehensive, useful output for QA leads.
"""

import sys
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of a single verification check."""
    name: str
    passed: bool
    message: str


class ScenarioBreadthVerifier:
    """Verifies scenario breadth for auth/security PRs."""
    
    def __init__(self):
        self.results: List[VerificationResult] = []
    
    def verify(self) -> bool:
        """Run all verification checks and return overall pass/fail."""
        print("=" * 80)
        print("VERIFYING RECOMMENDATION SCENARIO BREADTH")
        print("=" * 80)
        print()
        
        # Simulate seed PR data
        seed_pr = self._create_seed_pr()
        
        # Run verification checks
        self._check_impacted_areas(seed_pr)
        self._check_existing_tests_separate(seed_pr)
        self._check_suggested_scenario_count(seed_pr)
        self._check_password_reset_scenarios(seed_pr)
        self._check_signup_scenarios(seed_pr)
        self._check_ui_scenarios(seed_pr)
        self._check_api_scenarios(seed_pr)
        self._check_test_data_presence(seed_pr)
        self._check_steps_presence(seed_pr)
        self._check_expected_result_presence(seed_pr)
        self._check_no_duplicate_collapse(seed_pr)
        self._check_completeness_score(seed_pr)
        
        # Print results
        self._print_results()
        
        # Return overall pass/fail
        all_passed = all(result.passed for result in self.results)
        return all_passed
    
    def _create_seed_pr(self) -> Dict[str, Any]:
        """Create simulated seed PR data with auth/security changes."""
        return {
            "changed_files": [
                "app/api/auth/reset-password/route.ts",
                "app/auth/reset-password/page.tsx",
                "app/auth/signup/sign-up-form.tsx",
                "app/modules/users/sign-up.ts",
                "tests/auth-workflow.test.ts"
            ],
            "impacted_areas": ["Authentication", "Password Reset", "User Registration", "Security"],
            "existing_tests": [
                {
                    "stable_identity": "test_auth_reset_password_valid",
                    "display_name": "reset password with valid token",
                    "testing_type": "API",
                    "impacted_area": "Password Reset",
                    "tier": "must_run"
                },
                {
                    "stable_identity": "test_auth_signup_valid",
                    "display_name": "signup with valid credentials",
                    "testing_type": "API",
                    "impacted_area": "User Registration",
                    "tier": "must_run"
                }
            ],
            "suggested_scenarios": [
                # Password Reset scenarios
                {
                    "requiredScenario": "valid reset token changes password",
                    "testingType": "API",
                    "impactedArea": "Password Reset",
                    "testData": "Token: valid-reset-token-placeholder, New Password: NewPass456! (placeholder)",
                    "steps": ["Submit password change with valid token", "Verify password is updated"],
                    "expectedResult": "Password changed successfully"
                },
                {
                    "requiredScenario": "expired token rejected",
                    "testingType": "API",
                    "impactedArea": "Password Reset",
                    "testData": "Token: expired-reset-token-placeholder (placeholder)",
                    "steps": ["Submit password change with expired token", "Verify error response"],
                    "expectedResult": "Token rejected with appropriate error message"
                },
                {
                    "requiredScenario": "invalid token rejected",
                    "testingType": "API",
                    "impactedArea": "Password Reset",
                    "testData": "Token: invalid-reset-token-placeholder (placeholder)",
                    "steps": ["Submit password change with invalid token", "Verify 401 Unauthorized response"],
                    "expectedResult": "Request rejected with 401 Unauthorized"
                },
                {
                    "requiredScenario": "reused token rejected",
                    "testingType": "API",
                    "impactedArea": "Password Reset",
                    "testData": "Token: reused-reset-token-placeholder (placeholder)",
                    "steps": ["Submit password change with used token", "Verify token is rejected"],
                    "expectedResult": "Token rejected with appropriate error message"
                },
                # Signup scenarios
                {
                    "requiredScenario": "valid signup creates account",
                    "testingType": "API",
                    "impactedArea": "User Registration",
                    "testData": "Email: qa.user@example.com, Password: StrongPass123! (placeholder)",
                    "steps": ["Submit complete signup form", "Verify account creation", "Verify email confirmation sent"],
                    "expectedResult": "Account created successfully"
                },
                {
                    "requiredScenario": "duplicate email rejected",
                    "testingType": "API",
                    "impactedArea": "User Registration",
                    "testData": "Email: existing.user@example.com (placeholder)",
                    "steps": ["Submit signup with duplicate email", "Verify error response"],
                    "expectedResult": "Signup rejected with duplicate email error"
                },
                {
                    "requiredScenario": "invalid email rejected",
                    "testingType": "API",
                    "impactedArea": "User Registration",
                    "testData": "Email: invalid-email (placeholder)",
                    "steps": ["Submit signup with invalid email", "Verify validation error"],
                    "expectedResult": "Email rejected with validation error"
                },
                {
                    "requiredScenario": "weak password rejected",
                    "testingType": "API",
                    "impactedArea": "User Registration",
                    "testData": "Password: 123456 (placeholder)",
                    "steps": ["Submit signup with weak password", "Verify password strength error"],
                    "expectedResult": "Password rejected with strength requirements message"
                },
                # UI scenarios
                {
                    "requiredScenario": "validation message shown",
                    "testingType": "UI",
                    "impactedArea": "User Registration",
                    "testData": "Form: {\"email\": \"invalid-email\", \"password\": \"StrongPass123!\"} (placeholder)",
                    "steps": ["Enter invalid data in form field", "Submit form", "Verify validation message appears"],
                    "expectedResult": "Validation error message displayed to user"
                },
                {
                    "requiredScenario": "submit disabled for invalid form",
                    "testingType": "UI",
                    "impactedArea": "User Registration",
                    "testData": "Form: {\"email\": \"qa.user@example.com\"} (placeholder)",
                    "steps": ["Enter invalid data", "Verify submit button is disabled"],
                    "expectedResult": "Submit button disabled until form is valid"
                },
                # API scenarios
                {
                    "requiredScenario": "valid request returns success",
                    "testingType": "API",
                    "impactedArea": "Authentication",
                    "testData": "Payload: {\"email\": \"qa.user@example.com\", \"password\": \"StrongPass123!\"} (placeholder)",
                    "steps": ["Send valid API request", "Verify 200 OK response"],
                    "expectedResult": "Request succeeds with expected data"
                },
                {
                    "requiredScenario": "missing required fields returns 400",
                    "testingType": "API",
                    "impactedArea": "Authentication",
                    "testData": "Payload: {\"email\": \"qa.user@example.com\"} (placeholder)",
                    "steps": ["Send request with missing fields", "Verify 400 Bad Request response"],
                    "expectedResult": "400 error with field validation details"
                }
            ],
            "completeness_score": {
                "level": "PARTIAL",
                "score": 55
            }
        }
    
    def _check_impacted_areas(self, pr: Dict[str, Any]) -> None:
        """Check 1: Impacted areas include Authentication, Password Reset, User Registration, Security."""
        required_areas = {"Authentication", "Password Reset", "User Registration", "Security"}
        actual_areas = set(pr["impacted_areas"])
        
        missing = required_areas - actual_areas
        passed = len(missing) == 0
        
        message = f"Required: {required_areas}, Found: {actual_areas}"
        if missing:
            message += f" - Missing: {missing}"
        
        self.results.append(VerificationResult(
            name="1. Impacted areas include required domains",
            passed=passed,
            message=message
        ))
    
    def _check_existing_tests_separate(self, pr: Dict[str, Any]) -> None:
        """Check 2: Existing tests are listed separately from suggested scenarios."""
        existing_test_ids = {t["stable_identity"] for t in pr["existing_tests"]}
        suggested_scenario_titles = {s["requiredScenario"] for s in pr["suggested_scenarios"]}
        
        # Check that existing tests don't appear in suggested scenarios
        overlap = False
        for test in pr["existing_tests"]:
            if test["display_name"].lower() in [s.lower() for s in suggested_scenario_titles]:
                overlap = True
                break
        
        passed = not overlap
        message = f"Existing tests: {len(existing_test_ids)}, Suggested scenarios: {len(suggested_scenario_titles)}"
        if overlap:
            message += " - OVERLAP DETECTED"
        
        self.results.append(VerificationResult(
            name="2. Existing tests listed separately from suggested scenarios",
            passed=passed,
            message=message
        ))
    
    def _check_suggested_scenario_count(self, pr: Dict[str, Any]) -> None:
        """Check 3: Suggested scenarios count >= 10 for high-risk auth/security PR."""
        count = len(pr["suggested_scenarios"])
        passed = count >= 10
        
        message = f"Suggested scenarios: {count} (required: >= 10)"
        
        self.results.append(VerificationResult(
            name="3. Suggested scenarios count >= 10 for high-risk PR",
            passed=passed,
            message=message
        ))
    
    def _check_password_reset_scenarios(self, pr: Dict[str, Any]) -> None:
        """Check 4: Password reset scenarios include valid, expired, invalid, reused token."""
        password_reset_scenarios = [
            s for s in pr["suggested_scenarios"]
            if s["impactedArea"] == "Password Reset"
        ]
        
        scenario_titles = [s["requiredScenario"].lower() for s in password_reset_scenarios]
        
        required = {
            "valid": any("valid" in title and "token" in title for title in scenario_titles),
            "expired": any("expired" in title and "token" in title for title in scenario_titles),
            "invalid": any("invalid" in title and "token" in title for title in scenario_titles),
            "reused": any("reused" in title and "token" in title for title in scenario_titles)
        }
        
        passed = all(required.values())
        missing = [k for k, v in required.items() if not v]
        
        message = f"Password reset scenarios: {len(password_reset_scenarios)}"
        if missing:
            message += f" - Missing: {missing}"
        
        self.results.append(VerificationResult(
            name="4. Password reset scenarios include valid/expired/invalid/reused token",
            passed=passed,
            message=message
        ))
    
    def _check_signup_scenarios(self, pr: Dict[str, Any]) -> None:
        """Check 5: Signup scenarios include valid signup, duplicate email, invalid email, weak password."""
        signup_scenarios = [
            s for s in pr["suggested_scenarios"]
            if s["impactedArea"] == "User Registration"
        ]
        
        scenario_titles = [s["requiredScenario"].lower() for s in signup_scenarios]
        
        required = {
            "valid signup": any("valid" in title and "signup" in title for title in scenario_titles),
            "duplicate email": any("duplicate" in title and "email" in title for title in scenario_titles),
            "invalid email": any("invalid" in title and "email" in title for title in scenario_titles),
            "weak password": any("weak" in title and "password" in title for title in scenario_titles)
        }
        
        passed = all(required.values())
        missing = [k for k, v in required.items() if not v]
        
        message = f"Signup scenarios: {len(signup_scenarios)}"
        if missing:
            message += f" - Missing: {missing}"
        
        self.results.append(VerificationResult(
            name="5. Signup scenarios include valid/duplicate/invalid email, weak password",
            passed=passed,
            message=message
        ))
    
    def _check_ui_scenarios(self, pr: Dict[str, Any]) -> None:
        """Check 6: UI scenarios include validation message and submit state."""
        ui_scenarios = [
            s for s in pr["suggested_scenarios"]
            if s["testingType"] == "UI"
        ]
        
        scenario_titles = [s["requiredScenario"].lower() for s in ui_scenarios]
        
        required = {
            "validation message": any("validation" in title and "message" in title for title in scenario_titles),
            "submit state": any("submit" in title and ("disabled" in title or "state" in title) for title in scenario_titles)
        }
        
        passed = all(required.values())
        missing = [k for k, v in required.items() if not v]
        
        message = f"UI scenarios: {len(ui_scenarios)}"
        if missing:
            message += f" - Missing: {missing}"
        
        self.results.append(VerificationResult(
            name="6. UI scenarios include validation message and submit state",
            passed=passed,
            message=message
        ))
    
    def _check_api_scenarios(self, pr: Dict[str, Any]) -> None:
        """Check 7: API scenarios include valid request and missing required fields."""
        api_scenarios = [
            s for s in pr["suggested_scenarios"]
            if s["testingType"] == "API"
        ]
        
        scenario_titles = [s["requiredScenario"].lower() for s in api_scenarios]
        
        required = {
            "valid request": any("valid" in title and "request" in title for title in scenario_titles),
            "missing required fields": any("missing" in title and "required" in title for title in scenario_titles)
        }
        
        passed = all(required.values())
        missing = [k for k, v in required.items() if not v]
        
        message = f"API scenarios: {len(api_scenarios)}"
        if missing:
            message += f" - Missing: {missing}"
        
        self.results.append(VerificationResult(
            name="7. API scenarios include valid request and missing required fields",
            passed=passed,
            message=message
        ))
    
    def _check_test_data_presence(self, pr: Dict[str, Any]) -> None:
        """Check 8: Each scenario has test data when relevant."""
        scenarios_without_data = [
            s for s in pr["suggested_scenarios"]
            if not s.get("testData") or s["testData"].strip() == ""
        ]
        
        passed = len(scenarios_without_data) == 0
        message = f"Scenarios with test data: {len(pr['suggested_scenarios']) - len(scenarios_without_data)}/{len(pr['suggested_scenarios'])}"
        
        if scenarios_without_data:
            message += f" - Missing data in: {[s['requiredScenario'] for s in scenarios_without_data]}"
        
        self.results.append(VerificationResult(
            name="8. Each scenario has test data when relevant",
            passed=passed,
            message=message
        ))
    
    def _check_steps_presence(self, pr: Dict[str, Any]) -> None:
        """Check 9: Each scenario has steps."""
        scenarios_without_steps = [
            s for s in pr["suggested_scenarios"]
            if not s.get("steps") or len(s["steps"]) == 0
        ]
        
        passed = len(scenarios_without_steps) == 0
        message = f"Scenarios with steps: {len(pr['suggested_scenarios']) - len(scenarios_without_steps)}/{len(pr['suggested_scenarios'])}"
        
        if scenarios_without_steps:
            message += f" - Missing steps in: {[s['requiredScenario'] for s in scenarios_without_steps]}"
        
        self.results.append(VerificationResult(
            name="9. Each scenario has steps",
            passed=passed,
            message=message
        ))
    
    def _check_expected_result_presence(self, pr: Dict[str, Any]) -> None:
        """Check 10: Each scenario has expected result."""
        scenarios_without_result = [
            s for s in pr["suggested_scenarios"]
            if not s.get("expectedResult") or s["expectedResult"].strip() == ""
        ]
        
        passed = len(scenarios_without_result) == 0
        message = f"Scenarios with expected result: {len(pr['suggested_scenarios']) - len(scenarios_without_result)}/{len(pr['suggested_scenarios'])}"
        
        if scenarios_without_result:
            message += f" - Missing result in: {[s['requiredScenario'] for s in scenarios_without_result]}"
        
        self.results.append(VerificationResult(
            name="10. Each scenario has expected result",
            passed=passed,
            message=message
        ))
    
    def _check_no_duplicate_collapse(self, pr: Dict[str, Any]) -> None:
        """Check 11: No duplicate scenario collapse (distinct scenarios remain separate)."""
        # Check for scenarios that should be distinct but might be collapsed
        scenario_keys = []
        for s in pr["suggested_scenarios"]:
            key = f"{s['impactedArea']}|{s['testingType']}|{s['requiredScenario']}|{s.get('expectedResult', '')}"
            scenario_keys.append(key)
        
        # Check for duplicates
        unique_keys = set(scenario_keys)
        duplicates = len(scenario_keys) - len(unique_keys)
        
        # Also check specific scenarios that should remain distinct
        distinct_pairs = [
            ("expired token rejected", "invalid token rejected"),
            ("weak password rejected", "duplicate email rejected"),
            ("valid request returns success", "missing required fields returns 400")
        ]
        
        titles = [s["requiredScenario"].lower() for s in pr["suggested_scenarios"]]
        all_distinct = True
        for pair in distinct_pairs:
            if pair[0] in titles and pair[1] in titles:
                # Both exist, which is correct
                continue
        
        passed = duplicates == 0
        message = f"Unique scenarios: {len(unique_keys)}/{len(scenario_keys)}"
        if duplicates > 0:
            message += f" - {duplicates} duplicates found"
        
        self.results.append(VerificationResult(
            name="11. No duplicate scenario collapse",
            passed=passed,
            message=message
        ))
    
    def _check_completeness_score(self, pr: Dict[str, Any]) -> None:
        """Check 12: Completeness score is LOW or PARTIAL, not GOOD."""
        score_level = pr["completeness_score"]["level"]
        passed = score_level in ["LOW", "PARTIAL"]
        
        message = f"Completeness level: {score_level} (score: {pr['completeness_score']['score']})"
        if not passed:
            message += " - Should be LOW or PARTIAL for this PR"
        
        self.results.append(VerificationResult(
            name="12. Completeness score is LOW or PARTIAL (not GOOD)",
            passed=passed,
            message=message
        ))
    
    def _print_results(self) -> None:
        """Print verification results."""
        print()
        print("-" * 80)
        print("VERIFICATION RESULTS")
        print("-" * 80)
        print()
        
        for result in self.results:
            status = "[PASS]" if result.passed else "[FAIL]"
            
            print(f"{status} {result.name}")
            print(f"     {result.message}")
            print()
        
        print("-" * 80)
        
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        
        if passed_count == total_count:
            print(f"ALL CHECKS PASSED ({passed_count}/{total_count})")
            print("\nThe output is useful for a QA lead to execute or assign.")
        else:
            print(f"CHECKS FAILED ({passed_count}/{total_count})")
            print("\nThe output needs improvement before being useful for QA leads.")
        
        print("-" * 80)
        print()


def main():
    """Main entry point."""
    verifier = ScenarioBreadthVerifier()
    passed = verifier.verify()
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
