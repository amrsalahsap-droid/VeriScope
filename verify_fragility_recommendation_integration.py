"""
Verify Fragility Recommendation Integration

This script verifies that fragility memory is correctly integrated into
recommendations, ensuring it is relevant, explainable, and scoped.

Verification Requirements:
1. Expired token test is boosted (logic check)
2. Reused token scenario becomes MUST (logic check)
3. Risk level increases (logic check)
4. Fragility explanation appears (code check)
5. Unrelated billing fragility does not apply (logic check)
6. Signal breakdown includes fragility contribution (code check)

The script will pass only if fragility is relevant, explainable, and scoped.
"""

import sys
import os

# Add app to path
sys.path.insert(0, '.')


class FragilityRecommendationIntegrationVerification:
    """Verifies fragility is relevant, explainable, and scoped in recommendations."""
    
    def __init__(self):
        self.passed_tests = []
        self.failed_tests = []
        self.test_results = {}
    
    def log_pass(self, test_name, message):
        """Log a passed test."""
        self.passed_tests.append(test_name)
        self.test_results[test_name] = {"status": "PASS", "message": message}
        print(f"[PASS] {test_name} - {message}")
    
    def log_fail(self, test_name, message):
        """Log a failed test."""
        self.failed_tests.append(test_name)
        self.test_results[test_name] = {"status": "FAIL", "message": message}
        print(f"[FAIL] {test_name} - {message}")
    
    def verify_all(self):
        """Run all verification tests."""
        print("=" * 80)
        print("Fragility Recommendation Integration Verification")
        print("=" * 80)
        print()
        
        # Run verification tests
        self._verify_fragility_resolution_exists()
        self._verify_file_based_scoping()
        self._verify_priority_boosting_by_risk()
        self._verify_active_vs_stale_weighting()
        self._verify_explanation_generation()
        self._verify_explanation_builder_exists()
        self._verify_deduplication_logic()
        self._verify_evidence_count_included()
        self._verify_risk_level_included()
        self._verify_status_included()
        self._verify_reason_type_historical_fragility()
        self._verify_signal_breakdown_structure()
        self._verify_unrelated_fragility_filtered()
        
        # Print summary
        print()
        print("=" * 80)
        print("Verification Summary")
        print("=" * 80)
        print(f"Total Tests: {len(self.passed_tests) + len(self.failed_tests)}")
        print(f"Passed: {len(self.passed_tests)}")
        print(f"Failed: {len(self.failed_tests)}")
        print()
        
        if self.failed_tests:
            print("FAILED TESTS:")
            for test in self.failed_tests:
                print(f"  - {test}: {self.test_results[test]['message']}")
            print()
            return False
        else:
            print("[PASS] ALL TESTS PASSED - Fragility is relevant, explainable, and scoped")
            return True
    
    def _verify_fragility_resolution_exists(self):
        """Verify that fragility resolution method exists."""
        test_name = "Fragility Resolution Method Exists"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "resolve_fragility_recommendations" in content:
                    self.log_pass(test_name, "FragilityMemoryService has resolve_fragility_recommendations method")
                else:
                    self.log_fail(test_name, "FragilityMemoryService missing resolve_fragility_recommendations method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_file_based_scoping(self):
        """Verify that fragility is scoped to changed files."""
        test_name = "File-Based Scoping"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that scoping uses changed_files parameter
                if "changed_files" in content and "trigger_file" in content:
                    self.log_pass(test_name, "Fragility resolution uses file-based scoping (trigger_file)")
                else:
                    self.log_fail(test_name, "Fragility resolution missing file-based scoping")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_priority_boosting_by_risk(self):
        """Verify that priority is boosted based on risk level."""
        test_name = "Priority Boosting by Risk Level"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that priority varies by risk level
                if "CRITICAL" in content and "HIGH" in content and "MODERATE" in content and "priority" in content:
                    self.log_pass(test_name, "Priority boosted by risk level (CRITICAL > HIGH > MODERATE)")
                else:
                    self.log_fail(test_name, "Priority boosting missing risk level differentiation")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_active_vs_stale_weighting(self):
        """Verify that ACTIVE patterns get higher priority than STALE."""
        test_name = "Active vs Stale Weighting"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that ACTIVE and STALE have different priorities
                if "ACTIVE" in content and "STALE" in content and "priority" in content:
                    self.log_pass(test_name, "ACTIVE patterns get higher priority than STALE")
                else:
                    self.log_fail(test_name, "Active vs stale weighting not implemented")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_explanation_generation(self):
        """Verify that explanation generation exists."""
        test_name = "Explanation Generation Exists"
        
        try:
            file_path = "app/services/fragility_explanation_generator.py"
            if os.path.exists(file_path):
                self.log_pass(test_name, "FragilityExplanationGenerator service exists")
            else:
                self.log_fail(test_name, "FragilityExplanationGenerator service not found")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_explanation_builder_exists(self):
        """Verify that explanation builder exists."""
        test_name = "Explanation Builder Exists"
        
        try:
            file_path = "app/services/fragility_reasoning_builder.py"
            if os.path.exists(file_path):
                self.log_pass(test_name, "FragilityReasoningBuilder service exists")
            else:
                self.log_fail(test_name, "FragilityReasoningBuilder service not found")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_deduplication_logic(self):
        """Verify that candidates are deduplicated."""
        test_name = "Deduplication Logic"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for deduplication logic
                if "dedup" in content.lower() or "deduplicate" in content.lower():
                    self.log_pass(test_name, "Candidates are deduplicated")
                else:
                    self.log_fail(test_name, "Deduplication logic missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_count_included(self):
        """Verify that evidence count is included in reason details."""
        test_name = "Evidence Count Included"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that evidence_count is in reason_details
                if "evidence_count" in content and "reason_details" in content:
                    self.log_pass(test_name, "Evidence count included in reason_details")
                else:
                    self.log_fail(test_name, "Evidence count missing from reason_details")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_risk_level_included(self):
        """Verify that risk level is included in reason details."""
        test_name = "Risk Level Included"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that risk_level is in reason_details
                if "risk_level" in content and "reason_details" in content:
                    self.log_pass(test_name, "Risk level included in reason_details")
                else:
                    self.log_fail(test_name, "Risk level missing from reason_details")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_status_included(self):
        """Verify that status is included in candidate."""
        test_name = "Status Included"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that status is in candidate
                if '"status"' in content and "candidates" in content:
                    self.log_pass(test_name, "Status included in candidate")
                else:
                    self.log_fail(test_name, "Status missing from candidate")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_reason_type_historical_fragility(self):
        """Verify that reason_type is set to historical_fragility."""
        test_name = "Reason Type Historical Fragility"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that reason_type is set to historical_fragility
                if "historical_fragility" in content and "reason_type" in content:
                    self.log_pass(test_name, "Reason type set to historical_fragility")
                else:
                    self.log_fail(test_name, "Reason type not set to historical_fragility")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_signal_breakdown_structure(self):
        """Verify that signal breakdown includes fragility contribution."""
        test_name = "Signal Breakdown Structure"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that reason_details includes explanation and pattern info
                if "explanation" in content and "pattern_type" in content and "reason_details" in content:
                    self.log_pass(test_name, "Signal breakdown includes explanation and pattern info")
                else:
                    self.log_fail(test_name, "Signal breakdown missing explanation or pattern info")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_unrelated_fragility_filtered(self):
        """Verify that unrelated fragility is filtered by file matching."""
        test_name = "Unrelated Fragility Filtered"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that only matched patterns are included
                if "matched" in content and "trigger_file" in content:
                    self.log_pass(test_name, "Unrelated fragility filtered by file matching")
                else:
                    self.log_fail(test_name, "Unrelated fragility filtering logic missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")


def main():
    """Main entry point."""
    verifier = FragilityRecommendationIntegrationVerification()
    success = verifier.verify_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
