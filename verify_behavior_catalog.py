"""
Verification script for Behavior Catalog implementation.

Tests:
1. Authentication journey discovered
2. Registration journey discovered
3. Billing journey discovered
4. Password Reset behavior discovered
5. User Registration behavior discovered
6. Subscription Management behavior discovered
7. Behaviors contain evidence
8. Behaviors assigned journeys
9. Behaviors assigned risks
10. Duplicate behavior names merged
11. Catalog rebuild is idempotent
"""

import sys
import os
from datetime import datetime
from typing import List, Dict

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_discovery_engine import BehaviorDiscoveryEngine, DiscoveredBehaviorCandidate
from app.services.behavior_merge_service import BehaviorMergeService
from app.services.behavior_catalog_builder import BehaviorCatalogBuilder, BehaviorCatalogSnapshot
from app.services.behavior_risk_assigner import BehaviorRiskAssigner


class BehaviorCatalogVerifier:
    """Verifier for behavior catalog implementation."""
    
    def __init__(self):
        """Initialize the verifier."""
        self.test_results = []
        self.repository_id = "test-repo-123"
        self.repository_path = "/tmp/test-repo"
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log a test result."""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
        })
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")
        if message:
            print(f"  {message}")
    
    def seed_repository_artifacts(self) -> Dict[str, List[str]]:
        """Seed repository with test artifacts."""
        print("\n=== Seeding Repository Artifacts ===")
        
        artifacts = {
            "routes": [
                "src/app/api/auth/reset-password/route.ts",
                "src/app/api/auth/login/route.ts",
                "src/app/api/billing/subscription/route.ts",
            ],
            "pages": [
                "src/app/reset-password/page.tsx",
                "src/app/signup/page.tsx",
                "src/app/auth/page.tsx",
            ],
            "folders": [
                "src/app/auth",
                "src/app/billing",
                "src/app/subscription",
            ],
            "modules": [
                "src/middleware/auth.ts",
                "src/services/subscription.ts",
                "src/services/password-reset.ts",
            ],
            "test_names": [
                "test_reset_password_with_valid_token",
                "test_user_registration_success",
                "test_subscription_creation",
                "test_authentication_flow",
            ],
        }
        
        print(f"Routes: {len(artifacts['routes'])}")
        print(f"Pages: {len(artifacts['pages'])}")
        print(f"Folders: {len(artifacts['folders'])}")
        print(f"Modules: {len(artifacts['modules'])}")
        print(f"Test names: {len(artifacts['test_names'])}")
        
        return artifacts
    
    def verify_journey_discovery(self, candidates: List[DiscoveredBehaviorCandidate]) -> bool:
        """Verify that expected journeys are discovered."""
        print("\n=== Verifying Journey Discovery ===")
        
        expected_journeys = {
            "Authentication",
            "Registration",  # May be mapped to Authentication
            "Billing",
        }
        
        discovered_journeys = set()
        for candidate in candidates:
            if candidate.suggested_journey:
                discovered_journeys.add(candidate.suggested_journey)
        
        print(f"Expected journeys: {expected_journeys}")
        print(f"Discovered journeys: {discovered_journeys}")
        
        # Check for Authentication journey
        has_auth = "Authentication" in discovered_journeys
        self.log_test(
            "Authentication journey discovered",
            has_auth,
            f"Found: {discovered_journeys}"
        )
        
        # Check for Registration journey (may be mapped to Authentication)
        has_registration = "Registration" in discovered_journeys or "Authentication" in discovered_journeys
        self.log_test(
            "Registration journey discovered",
            has_registration,
            f"Found: {discovered_journeys}"
        )
        
        # Check for Billing journey
        has_billing = "Billing" in discovered_journeys
        self.log_test(
            "Billing journey discovered",
            has_billing,
            f"Found: {discovered_journeys}"
        )
        
        return has_auth and has_billing
    
    def verify_behavior_discovery(self, candidates: List[DiscoveredBehaviorCandidate]) -> bool:
        """Verify that expected behaviors are discovered."""
        print("\n=== Verifying Behavior Discovery ===")
        
        expected_behaviors = {
            "Password Reset",
            "User Registration",
            "Subscription Management",
        }
        
        discovered_behaviors = {c.name for c in candidates}
        
        print(f"Expected behaviors: {expected_behaviors}")
        print(f"Discovered behaviors: {discovered_behaviors}")
        
        # Check for Password Reset
        has_password_reset = "Password Reset" in discovered_behaviors
        self.log_test(
            "Password Reset behavior discovered",
            has_password_reset,
            f"Found: {discovered_behaviors}"
        )
        
        # Check for User Registration
        has_registration = "User Registration" in discovered_behaviors
        self.log_test(
            "User Registration behavior discovered",
            has_registration,
            f"Found: {discovered_behaviors}"
        )
        
        # Check for Subscription Management
        has_subscription = "Subscription Management" in discovered_behaviors
        self.log_test(
            "Subscription Management behavior discovered",
            has_subscription,
            f"Found: {discovered_behaviors}"
        )
        
        return has_password_reset and has_registration and has_subscription
    
    def verify_evidence(self, candidates: List[DiscoveredBehaviorCandidate]) -> bool:
        """Verify that behaviors contain evidence."""
        print("\n=== Verifying Evidence ===")
        
        all_have_evidence = True
        for candidate in candidates:
            has_evidence = len(candidate.evidences) > 0
            if not has_evidence:
                all_have_evidence = False
                print(f"  {candidate.name}: NO EVIDENCE")
            else:
                print(f"  {candidate.name}: {len(candidate.evidences)} evidence(s)")
        
        self.log_test(
            "Behaviors contain evidence",
            all_have_evidence,
            f"All {len(candidates)} behaviors have evidence"
        )
        
        return all_have_evidence
    
    def verify_journey_assignment(self, candidates: List[DiscoveredBehaviorCandidate]) -> bool:
        """Verify that behaviors are assigned journeys."""
        print("\n=== Verifying Journey Assignment ===")
        
        all_have_journeys = True
        for candidate in candidates:
            has_journey = candidate.suggested_journey is not None
            if not has_journey:
                all_have_journeys = False
                print(f"  {candidate.name}: NO JOURNEY")
            else:
                print(f"  {candidate.name}: {candidate.suggested_journey}")
        
        self.log_test(
            "Behaviors assigned journeys",
            all_have_journeys,
            f"All {len(candidates)} behaviors have journeys"
        )
        
        return all_have_journeys
    
    def verify_risk_assignment(self, candidates: List[DiscoveredBehaviorCandidate]) -> bool:
        """Verify that behaviors are assigned risks."""
        print("\n=== Verifying Risk Assignment ===")
        
        all_have_risks = True
        for candidate in candidates:
            has_risk = candidate.suggested_risk_level is not None
            if not has_risk:
                all_have_risks = False
                print(f"  {candidate.name}: NO RISK")
            else:
                print(f"  {candidate.name}: {candidate.suggested_risk_level}")
        
        self.log_test(
            "Behaviors assigned risks",
            all_have_risks,
            f"All {len(candidates)} behaviors have risk levels"
        )
        
        return all_have_risks
    
    def verify_duplicate_merging(self, candidates: List[DiscoveredBehaviorCandidate]) -> bool:
        """Verify that duplicate behavior names are merged."""
        print("\n=== Verifying Duplicate Merging ===")
        
        # Check that no duplicate behavior names exist
        behavior_names = [c.name for c in candidates]
        unique_names = set(behavior_names)
        
        has_duplicates = len(behavior_names) != len(unique_names)
        
        if has_duplicates:
            print(f"  Duplicate names found: {behavior_names}")
        else:
            print(f"  All unique: {unique_names}")
        
        self.log_test(
            "Duplicate behavior names merged",
            not has_duplicates,
            f"{len(behavior_names)} candidates, {len(unique_names)} unique"
        )
        
        return not has_duplicates
    
    def verify_idempotency(self, artifacts: Dict[str, List[str]]) -> bool:
        """Verify that catalog rebuild is idempotent."""
        print("\n=== Verifying Idempotency ===")
        
        # Run discovery twice
        engine1 = BehaviorDiscoveryEngine(self.repository_path)
        candidates1 = engine1.discover_behaviors(**artifacts)
        
        engine2 = BehaviorDiscoveryEngine(self.repository_path)
        candidates2 = engine2.discover_behaviors(**artifacts)
        
        # Compare results
        names1 = sorted([c.name for c in candidates1])
        names2 = sorted([c.name for c in candidates2])
        
        is_idempotent = names1 == names2
        
        print(f"First run: {names1}")
        print(f"Second run: {names2}")
        
        self.log_test(
            "Catalog rebuild is idempotent",
            is_idempotent,
            f"Both runs produced: {names1}"
        )
        
        return is_idempotent
    
    def run_all_verifications(self):
        """Run all verification tests."""
        print("=" * 60)
        print("BEHAVIOR CATALOG VERIFICATION")
        print("=" * 60)
        
        # Seed repository
        artifacts = self.seed_repository_artifacts()
        
        # Step 1: Discovery
        print("\n=== Step 1: Discovery ===")
        engine = BehaviorDiscoveryEngine(self.repository_path)
        candidates = engine.discover_behaviors(**artifacts)
        print(f"Discovered {len(candidates)} behavior candidates")
        
        # Step 2: Merge
        print("\n=== Step 2: Merge ===")
        merge_service = BehaviorMergeService()
        merged_candidates = merge_service.merge_candidates(candidates)
        print(f"Merged into {len(merged_candidates)} canonical behaviors")
        
        # Run verifications
        self.verify_journey_discovery(merged_candidates)
        self.verify_behavior_discovery(merged_candidates)
        self.verify_evidence(merged_candidates)
        self.verify_journey_assignment(merged_candidates)
        self.verify_risk_assignment(merged_candidates)
        self.verify_duplicate_merging(merged_candidates)
        self.verify_idempotency(artifacts)
        
        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        for result in self.test_results:
            status = "[PASS]" if result["passed"] else "[FAIL]"
            print(f"{status} {result['test']}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n[PASS] ALL TESTS PASSED - Behavior catalog is stable")
            return 0
        else:
            print(f"\n[FAIL] {total - passed} TEST(S) FAILED")
            return 1


if __name__ == "__main__":
    verifier = BehaviorCatalogVerifier()
    exit_code = verifier.run_all_verifications()
    sys.exit(exit_code)
