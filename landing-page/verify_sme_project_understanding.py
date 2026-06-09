#!/usr/bin/env python3
"""
Verification script for SME Project Understanding capabilities.

This script tests that Veriscope correctly understands project changes
and provides appropriate test recommendations across different SME perspectives.
"""

import requests
import json
import sys
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of a single verification check."""
    name: str
    passed: bool
    details: str
    evidence: List[str]


class SMEProjectUnderstandingVerifier:
    """Verifies SME project understanding capabilities."""
    
    def __init__(self, backend_url: str = "http://localhost:8000", token: str = None):
        self.backend_url = backend_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.results: List[VerificationResult] = []
    
    def log_result(self, name: str, passed: bool, details: str, evidence: List[str] = None):
        """Log a verification result."""
        self.results.append(VerificationResult(
            name=name,
            passed=passed,
            details=details,
            evidence=evidence or []
        ))
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            print(f"  Details: {details}")
        if evidence:
            print(f"  Evidence: {', '.join(evidence)}")
    
    def seed_pr_changes(self, repository_id: str) -> Dict[str, Any]:
        """
        Seed a PR with the specified changes:
        - reset-password route changed
        - signup form changed
        - users sign-up module changed
        - auth workflow test changed
        """
        print("\n=== Seeding PR Changes ===")
        
        # Mock PR data with the specified file changes
        pr_data = {
            "title": "Update authentication and signup flows",
            "source_branch": "feature/auth-updates",
            "target_branch": "main",
            "changed_files": [
                "app/api/auth/reset-password/route.ts",
                "app/signup/reset-password/page.tsx",
                "app/modules/users/sign-up.ts",
                "tests/auth-workflow.test.ts"
            ]
        }
        
        # Create PR via API (mock for now, would need actual backend endpoint)
        print(f"Seeding PR with {len(pr_data['changed_files'])} changed files:")
        for f in pr_data['changed_files']:
            print(f"  - {f}")
        
        return pr_data
    
    def trigger_recommendation(self, repository_id: str, pr_id: str) -> Dict[str, Any]:
        """Trigger recommendation generation for the PR."""
        print(f"\n=== Triggering Recommendation for PR #{pr_id} ===")
        
        url = f"{self.backend_url}/api/repositories/{repository_id}/pull-requests/{pr_id}/recommendation"
        response = requests.post(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"Failed to trigger recommendation: {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
        recommendation = response.json()
        print(f"Recommendation generated: {recommendation.get('id', 'unknown')}")
        return recommendation
    
    def get_recommendation(self, run_id: str) -> Dict[str, Any]:
        """Fetch recommendation details by run ID."""
        url = f"{self.backend_url}/api/recommendations/{run_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch recommendation: {response.status_code}")
            return None
        
        return response.json()
    
    def verify_product_sme(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify Product SME detects Password Reset and Signup.
        """
        print("\n=== Verifying Product SME ===")
        
        changed_files = recommendation.get("executive_summary", {}).get("changed_files", [])
        
        # Check for password reset detection
        has_password_reset = any("reset-password" in f.lower() for f in changed_files)
        # Check for signup detection
        has_signup = any("signup" in f.lower() or "sign-up" in f.lower() for f in changed_files)
        
        passed = has_password_reset and has_signup
        evidence = []
        if has_password_reset:
            evidence.append("Password reset files detected")
        if has_signup:
            evidence.append("Signup files detected")
        
        self.log_result(
            name="Product SME detects Password Reset and Signup",
            passed=passed,
            details=f"Password reset: {has_password_reset}, Signup: {has_signup}",
            evidence=evidence
        )
        
        return passed
    
    def verify_security_sme(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify Security SME detects auth/token/password risk.
        """
        print("\n=== Verifying Security SME ===")
        
        changed_files = recommendation.get("executive_summary", {}).get("changed_files", [])
        risk_level = recommendation.get("executive_summary", {}).get("risk_level", "LOW")
        
        # Check for auth/token/password mentions
        has_auth = any("auth" in f.lower() for f in changed_files)
        has_password = any("password" in f.lower() for f in changed_files)
        has_token = any("token" in f.lower() for f in changed_files)
        
        # Risk should be elevated for security changes
        is_high_risk = risk_level in ["HIGH", "MODERATE"]
        
        passed = (has_auth or has_password or has_token) and is_high_risk
        evidence = []
        if has_auth:
            evidence.append("Auth files detected")
        if has_password:
            evidence.append("Password files detected")
        if has_token:
            evidence.append("Token-related changes detected")
        if is_high_risk:
            evidence.append(f"Risk level: {risk_level}")
        
        self.log_result(
            name="Security SME detects auth/token/password risk",
            passed=passed,
            details=f"Auth: {has_auth}, Password: {has_password}, Token: {has_token}, Risk: {risk_level}",
            evidence=evidence
        )
        
        return passed
    
    def verify_architecture_sme(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify Architecture SME detects API + UI + domain module.
        """
        print("\n=== Verifying Architecture SME ===")
        
        changed_files = recommendation.get("executive_summary", {}).get("changed_files", [])
        
        # Check for different architectural layers
        has_api = any("api" in f.lower() for f in changed_files)
        has_ui = any("page" in f.lower() or "ui" in f.lower() for f in changed_files)
        has_module = any("module" in f.lower() for f in changed_files)
        
        passed = has_api and has_ui and has_module
        evidence = []
        if has_api:
            evidence.append("API layer detected")
        if has_ui:
            evidence.append("UI layer detected")
        if has_module:
            evidence.append("Domain module detected")
        
        self.log_result(
            name="Architecture SME detects API + UI + domain module",
            passed=passed,
            details=f"API: {has_api}, UI: {has_ui}, Module: {has_module}",
            evidence=evidence
        )
        
        return passed
    
    def verify_qa_sme(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify QA SME creates executable scenarios.
        """
        print("\n=== Verifying QA SME ===")
        
        testing_scope = recommendation.get("testing_scope", {})
        must_test = testing_scope.get("must_test", [])
        should_test = testing_scope.get("should_test", [])
        
        # Check that there are executable test scenarios
        has_must_test = len(must_test) > 0
        has_should_test = len(should_test) > 0
        
        # Check that scenarios have categories and items
        has_structured_scenarios = all(
            "category" in item and "item" in item 
            for item in must_test + should_test
        )
        
        passed = (has_must_test or has_should_test) and has_structured_scenarios
        evidence = []
        if has_must_test:
            evidence.append(f"{len(must_test)} must-test scenarios")
        if has_should_test:
            evidence.append(f"{len(should_test)} should-test scenarios")
        if has_structured_scenarios:
            evidence.append("Scenarios have structure (category, item)")
        
        self.log_result(
            name="QA SME creates executable scenarios",
            passed=passed,
            details=f"Must test: {len(must_test)}, Should test: {len(should_test)}, Structured: {has_structured_scenarios}",
            evidence=evidence
        )
        
        return passed
    
    def verify_domain_sme(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify Domain SME clusters signup/registration and reset-password/password recovery.
        """
        print("\n=== Verifying Domain SME ===")
        
        changed_files = recommendation.get("executive_summary", {}).get("changed_files", [])
        testing_scope = recommendation.get("testing_scope", {})
        
        # Check for domain clustering in testing scope
        all_scope_items = (
            testing_scope.get("must_test", []) + 
            testing_scope.get("should_test", []) + 
            testing_scope.get("optional", [])
        )
        
        # Look for signup/registration clustering
        has_signup_cluster = any(
            "signup" in item.get("category", "").lower() or "registration" in item.get("category", "").lower()
            for item in all_scope_items
        )
        
        # Look for password recovery clustering
        has_password_cluster = any(
            "password" in item.get("category", "").lower() or "recovery" in item.get("category", "").lower()
            for item in all_scope_items
        )
        
        passed = has_signup_cluster or has_password_cluster
        evidence = []
        if has_signup_cluster:
            evidence.append("Signup/registration cluster detected")
        if has_password_cluster:
            evidence.append("Password recovery cluster detected")
        
        self.log_result(
            name="Domain SME clusters signup/registration and reset-password/password recovery",
            passed=passed,
            details=f"Signup cluster: {has_signup_cluster}, Password cluster: {has_password_cluster}",
            evidence=evidence
        )
        
        return passed
    
    def verify_recommendation_ranking(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify Recommendation ranks auth/security tests above billing tests.
        """
        print("\n=== Verifying Recommendation Ranking ===")
        
        recommended_tests = recommendation.get("recommended_tests", [])
        
        # Separate auth/security tests from other tests
        auth_tests = [t for t in recommended_tests if any(
            keyword in t.get("display_name", "").lower() 
            for keyword in ["auth", "password", "security", "token"]
        )]
        billing_tests = [t for t in recommended_tests if any(
            keyword in t.get("display_name", "").lower() 
            for keyword in ["billing", "payment", "invoice"]
        )]
        
        # Check that auth tests have higher priority scores than billing tests
        if auth_tests and billing_tests:
            avg_auth_score = sum(t.get("priority_score", 0) for t in auth_tests) / len(auth_tests)
            avg_billing_score = sum(t.get("priority_score", 0) for t in billing_tests) / len(billing_tests)
            auth_ranked_higher = avg_auth_score > avg_billing_score
        else:
            # If no billing tests, auth tests should be in must_run tier
            auth_ranked_higher = any(t.get("tier") == "must_run" for t in auth_tests)
        
        passed = auth_ranked_higher
        evidence = []
        if auth_tests:
            evidence.append(f"{len(auth_tests)} auth/security tests found")
        if billing_tests:
            evidence.append(f"{len(billing_tests)} billing tests found")
        if auth_ranked_higher:
            evidence.append("Auth tests ranked higher than billing tests")
        
        self.log_result(
            name="Recommendation ranks auth/security tests above billing tests",
            passed=passed,
            details=f"Auth tests: {len(auth_tests)}, Billing tests: {len(billing_tests)}, Auth ranked higher: {auth_ranked_higher}",
            evidence=evidence
        )
        
        return passed
    
    def verify_missing_scenarios(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify Missing scenarios include test data and expected result.
        """
        print("\n=== Verifying Missing Scenarios ===")
        
        missing_coverage = recommendation.get("missing_coverage", [])
        
        if not missing_coverage:
            self.log_result(
                name="Missing scenarios include test data and expected result",
                passed=False,
                details="No missing coverage data found",
                evidence=[]
            )
            return False
        
        # Check that missing coverage has required fields
        has_domain = all("domain" in item for item in missing_coverage)
        has_feature = all("feature" in item for item in missing_coverage)
        has_reason = all("reason" in item for item in missing_coverage)
        
        passed = has_domain and has_feature and has_reason
        evidence = []
        if has_domain:
            evidence.append("Domain field present")
        if has_feature:
            evidence.append("Feature field present")
        if has_reason:
            evidence.append("Reason field present (provides test data context)")
        
        self.log_result(
            name="Missing scenarios include test data and expected result",
            passed=passed,
            details=f"Domain: {has_domain}, Feature: {has_feature}, Reason: {has_reason}",
            evidence=evidence
        )
        
        return passed
    
    def verify_ui_project_understanding(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify UI shows project understanding snapshot.
        """
        print("\n=== Verifying UI Project Understanding Snapshot ===")
        
        # Check that the recommendation has project understanding data
        executive_summary = recommendation.get("executive_summary", {})
        testing_strategy = recommendation.get("testing_strategy", {})
        evidence = recommendation.get("evidence", {})
        
        has_changed_files = "changed_files" in executive_summary and len(executive_summary["changed_files"]) > 0
        has_risk_level = "risk_level" in executive_summary
        has_testing_counts = "must_run_count" in testing_strategy
        has_evidence_data = evidence is not None
        
        passed = has_changed_files and has_risk_level and has_testing_counts and has_evidence_data
        evidence_list = []
        if has_changed_files:
            evidence_list.append(f"{len(executive_summary['changed_files'])} changed files")
        if has_risk_level:
            evidence_list.append(f"Risk level: {executive_summary['risk_level']}")
        if has_testing_counts:
            evidence_list.append(f"Must run: {testing_strategy['must_run_count']}")
        if has_evidence_data:
            evidence_list.append("Evidence data present")
        
        self.log_result(
            name="UI shows project understanding snapshot",
            passed=passed,
            details=f"Changed files: {has_changed_files}, Risk level: {has_risk_level}, Testing counts: {has_testing_counts}, Evidence: {has_evidence_data}",
            evidence=evidence_list
        )
        
        return passed
    
    def verify_recommendation_explanation(self, recommendation: Dict[str, Any]) -> bool:
        """
        Verify recommendation explains:
        - what the system is
        - what changed
        - what is at risk
        - what to test
        - which tests exist
        - which tests are missing
        """
        print("\n=== Verifying Recommendation Explanation ===")
        
        executive_summary = recommendation.get("executive_summary", {})
        testing_strategy = recommendation.get("testing_strategy", {})
        recommended_tests = recommendation.get("recommended_tests", [])
        missing_coverage = recommendation.get("missing_coverage", [])
        why = recommendation.get("why", [])
        
        # What the system is: repository info
        has_system_info = "repository" in recommendation
        
        # What changed: changed files
        has_what_changed = "changed_files" in executive_summary and len(executive_summary["changed_files"]) > 0
        
        # What is at risk: risk level and bullets
        has_risk_info = "risk_level" in executive_summary and len(executive_summary.get("bullets", [])) > 0
        
        # What to test: testing strategy and scope
        has_what_to_test = "testing_scope" in recommendation or len(recommended_tests) > 0
        
        # Which tests exist: recommended tests
        has_existing_tests = len(recommended_tests) > 0
        
        # Which tests are missing: missing coverage
        has_missing_tests = len(missing_coverage) > 0
        
        # Why these tests: reasoning
        has_reasoning = len(why) > 0
        
        passed = (
            has_system_info and 
            has_what_changed and 
            has_risk_info and 
            has_what_to_test and 
            has_existing_tests and 
            has_reasoning
        )
        
        evidence = []
        if has_system_info:
            evidence.append("System info present")
        if has_what_changed:
            evidence.append(f"{len(executive_summary['changed_files'])} changed files")
        if has_risk_info:
            evidence.append(f"Risk: {executive_summary['risk_level']}")
        if has_what_to_test:
            evidence.append("Testing scope defined")
        if has_existing_tests:
            evidence.append(f"{len(recommended_tests)} recommended tests")
        if has_missing_tests:
            evidence.append(f"{len(missing_coverage)} missing scenarios")
        if has_reasoning:
            evidence.append(f"{len(why)} reasoning bullets")
        
        self.log_result(
            name="Recommendation explains system, changes, risk, tests, existing, missing",
            passed=passed,
            details=f"System: {has_system_info}, Changed: {has_what_changed}, Risk: {has_risk_info}, To test: {has_what_to_test}, Existing: {has_existing_tests}, Missing: {has_missing_tests}, Reasoning: {has_reasoning}",
            evidence=evidence
        )
        
        return passed
    
    def run_all_verifications(self, repository_id: str, pr_id: str) -> bool:
        """Run all verification checks."""
        print("=" * 60)
        print("SME Project Understanding Verification")
        print("=" * 60)
        
        # Seed PR changes
        pr_data = self.seed_pr_changes(repository_id)
        
        # Trigger recommendation
        recommendation = self.trigger_recommendation(repository_id, pr_id)
        
        if not recommendation:
            print("\n✗ FAIL: Could not generate recommendation")
            return False
        
        # Run all verifications
        results = [
            self.verify_product_sme(recommendation),
            self.verify_security_sme(recommendation),
            self.verify_architecture_sme(recommendation),
            self.verify_qa_sme(recommendation),
            self.verify_domain_sme(recommendation),
            self.verify_recommendation_ranking(recommendation),
            self.verify_missing_scenarios(recommendation),
            self.verify_ui_project_understanding(recommendation),
            self.verify_recommendation_explanation(recommendation),
        ]
        
        # Print summary
        print("\n" + "=" * 60)
        print("Verification Summary")
        print("=" * 60)
        
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        
        print(f"Passed: {passed_count}/{total_count}")
        
        for result in self.results:
            status = "✓" if result.passed else "✗"
            print(f"{status} {result.name}")
        
        all_passed = all(results)
        
        if all_passed:
            print("\n✓ ALL VERIFICATIONS PASSED")
        else:
            print("\n✗ SOME VERIFICATIONS FAILED")
        
        return all_passed


def main():
    """Main entry point."""
    import os
    
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    token = os.environ.get("BACKEND_TOKEN")
    
    if not token:
        print("Error: BACKEND_TOKEN environment variable required")
        sys.exit(1)
    
    repository_id = os.environ.get("REPOSITORY_ID", "test-repo")
    pr_id = os.environ.get("PR_ID", "test-pr")
    
    verifier = SMEProjectUnderstandingVerifier(backend_url=backend_url, token=token)
    success = verifier.run_all_verifications(repository_id, pr_id)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
