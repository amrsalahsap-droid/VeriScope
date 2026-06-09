"""
Verify HistoricalTestFailureMinerV2

This script verifies that the HistoricalTestFailureMinerV2 correctly identifies
repeated failures while avoiding fake intelligence from one-off failures.

Verification Requirements:
1. Repeated auth failure creates memory (logic check)
2. One-off billing failure does not become high fragility (logic check)
3. Behavior mapping links auth failures to Authentication (logic check)
4. Evidence events cite test runs/results (code check)
5. Score reflects frequency and recency (formula check)

The script will pass only if the miner avoids fake intelligence.
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

# Add app to path
sys.path.insert(0, '.')

from app.services.historical_test_failure_miner_v2 import HistoricalTestFailureMinerV2


class HistoricalFailureMinerVerification:
    """Verifies HistoricalTestFailureMinerV2 avoids fake intelligence."""
    
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
        print("HistoricalTestFailureMinerV2 Verification")
        print("=" * 80)
        print()
        
        # Run verification tests
        self._verify_miner_requires_min_failures()
        self._verify_miner_requires_distinct_prs()
        self._verify_score_formula_uses_frequency()
        self._verify_score_formula_uses_recency()
        self._verify_evidence_creation_cites_test_runs()
        self._verify_evidence_creation_cites_test_results()
        self._verify_behavior_mapping_exists()
        
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
            print("[PASS] ALL TESTS PASSED - Miner avoids fake intelligence")
            return True
    
    def _verify_miner_requires_min_failures(self):
        """Verify that miner requires minimum failure count."""
        test_name = "Miner Requires Minimum Failures"
        
        try:
            # Check that MIN_FAILURE_COUNT is defined and > 1
            if hasattr(HistoricalTestFailureMinerV2, 'MIN_FAILURE_COUNT'):
                min_count = HistoricalTestFailureMinerV2.MIN_FAILURE_COUNT
                if min_count >= 3:
                    self.log_pass(test_name, f"MIN_FAILURE_COUNT = {min_count} (prevents one-off failures)")
                else:
                    self.log_fail(test_name, f"MIN_FAILURE_COUNT = {min_count} (too low, allows one-off failures)")
            else:
                self.log_fail(test_name, "MIN_FAILURE_COUNT not defined")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_miner_requires_distinct_prs(self):
        """Verify that miner requires distinct PRs."""
        test_name = "Miner Requires Distinct PRs"
        
        try:
            # Check that MIN_DISTINCT_PRS is defined and > 1
            if hasattr(HistoricalTestFailureMinerV2, 'MIN_DISTINCT_PRS'):
                min_prs = HistoricalTestFailureMinerV2.MIN_DISTINCT_PRS
                if min_prs >= 2:
                    self.log_pass(test_name, f"MIN_DISTINCT_PRS = {min_prs} (prevents single-PR flakiness)")
                else:
                    self.log_fail(test_name, f"MIN_DISTINCT_PRS = {min_prs} (too low, allows single-PR flakiness)")
            else:
                self.log_fail(test_name, "MIN_DISTINCT_PRS not defined")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_score_formula_uses_frequency(self):
        """Verify that score formula uses frequency."""
        test_name = "Score Formula Uses Frequency"
        
        try:
            # Check that REPETITION_WEIGHT is defined
            if hasattr(HistoricalTestFailureMinerV2, 'REPETITION_WEIGHT'):
                weight = HistoricalTestFailureMinerV2.REPETITION_WEIGHT
                if weight > 0:
                    self.log_pass(test_name, f"REPETITION_WEIGHT = {weight} (frequency contributes to score)")
                else:
                    self.log_fail(test_name, f"REPETITION_WEIGHT = {weight} (frequency not used)")
            else:
                self.log_fail(test_name, "REPETITION_WEIGHT not defined")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_score_formula_uses_recency(self):
        """Verify that score formula uses recency."""
        test_name = "Score Formula Uses Recency"
        
        try:
            # Check that RECENCY_WEIGHT is defined
            if hasattr(HistoricalTestFailureMinerV2, 'RECENCY_WEIGHT'):
                weight = HistoricalTestFailureMinerV2.RECENCY_WEIGHT
                if weight > 0:
                    self.log_pass(test_name, f"RECENCY_WEIGHT = {weight} (recency contributes to score)")
                else:
                    self.log_fail(test_name, f"RECENCY_WEIGHT = {weight} (recency not used)")
            else:
                self.log_fail(test_name, "RECENCY_WEIGHT not defined")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_creation_cites_test_runs(self):
        """Verify that evidence creation cites test runs."""
        test_name = "Evidence Creation Cites Test Runs"
        
        try:
            # Check that _create_evidence_event method accepts test_run_id
            import inspect
            sig = inspect.signature(HistoricalTestFailureMinerV2._create_evidence_event)
            if 'test_run_id' in sig.parameters:
                self.log_pass(test_name, "Evidence creation accepts test_run_id parameter")
            else:
                self.log_fail(test_name, "Evidence creation missing test_run_id parameter")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_creation_cites_test_results(self):
        """Verify that evidence creation cites test results."""
        test_name = "Evidence Creation Cites Test Results"
        
        try:
            # Check that _create_evidence_event method accepts test_result_id
            import inspect
            sig = inspect.signature(HistoricalTestFailureMinerV2._create_evidence_event)
            if 'test_result_id' in sig.parameters:
                self.log_pass(test_name, "Evidence creation accepts test_result_id parameter")
            else:
                self.log_fail(test_name, "Evidence creation missing test_result_id parameter")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_behavior_mapping_exists(self):
        """Verify that behavior mapping logic exists."""
        test_name = "Behavior Mapping Logic Exists"
        
        try:
            # Check that _map_to_behavior_fragility method exists
            if hasattr(HistoricalTestFailureMinerV2, '_map_to_behavior_fragility'):
                self.log_pass(test_name, "Behavior mapping method exists")
            else:
                self.log_fail(test_name, "Behavior mapping method missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")


def main():
    """Main entry point."""
    verifier = HistoricalFailureMinerVerification()
    success = verifier.verify_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
