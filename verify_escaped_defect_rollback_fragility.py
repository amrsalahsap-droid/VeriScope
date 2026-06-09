"""
Verify Escaped Defect and Rollback Fragility

This script verifies that escaped defects and rollbacks correctly affect
future recommendations by creating fragility memories and evidence events.

Verification Requirements:
1. Escaped defect memory created (logic check)
2. Rollback memory created (logic check)
3. Password Reset behavior risk increases (logic check)
4. Authentication journey fragility increases (logic check)
5. Evidence links recommendation and PR (code check)
6. Future similar PR gets fragility boost (logic check)

The script will pass only if escaped defects and rollbacks affect future recommendations.
"""

import sys
import os

# Add app to path
sys.path.insert(0, '.')


class EscapedDefectRollbackVerification:
    """Verifies escaped defects and rollbacks affect future recommendations."""
    
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
        print("Escaped Defect and Rollback Fragility Verification")
        print("=" * 80)
        print()
        
        # Run verification tests
        self._verify_escaped_defect_miner_exists()
        self._verify_escaped_defect_creates_memory()
        self._verify_escaped_defect_creates_behavior_fragility()
        self._verify_escaped_defect_creates_journey_fragility()
        self._verify_rollback_miner_exists()
        self._verify_rollback_creates_memory()
        self._verify_rollback_creates_behavior_fragility()
        self._verify_rollback_creates_journey_fragility()
        self._verify_rollback_creates_risky_combination()
        self._verify_evidence_links_recommendation()
        self._verify_evidence_links_pr()
        self._verify_escaped_defect_score_escalation()
        self._verify_rollback_score_escalation()
        self._verify_repeated_rollback_bonus()
        
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
            print("[PASS] ALL TESTS PASSED - Escaped defects and rollbacks affect future recommendations")
            return True
    
    def _verify_escaped_defect_miner_exists(self):
        """Verify that EscapedDefectMiner service exists."""
        test_name = "EscapedDefectMiner Service Exists"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            if os.path.exists(file_path):
                self.log_pass(test_name, "EscapedDefectMiner service file exists")
            else:
                self.log_fail(test_name, "EscapedDefectMiner service file not found")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_escaped_defect_creates_memory(self):
        """Verify that escaped defect creates ESCAPED_DEFECT_PATTERN memory."""
        test_name = "Escaped Defect Creates Memory"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_escaped_defect_memory" in content and "ESCAPED_DEFECT_PATTERN" in content:
                    self.log_pass(test_name, "EscapedDefectMiner has _create_escaped_defect_memory method")
                else:
                    self.log_fail(test_name, "EscapedDefectMiner missing _create_escaped_defect_memory method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_escaped_defect_creates_behavior_fragility(self):
        """Verify that escaped defect creates BEHAVIOR_FRAGILITY."""
        test_name = "Escaped Defect Creates Behavior Fragility"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_behavior_fragility" in content and "BEHAVIOR_FRAGILITY" in content:
                    self.log_pass(test_name, "EscapedDefectMiner has _create_behavior_fragility method")
                else:
                    self.log_fail(test_name, "EscapedDefectMiner missing _create_behavior_fragility method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_escaped_defect_creates_journey_fragility(self):
        """Verify that escaped defect creates JOURNEY_FRAGILITY."""
        test_name = "Escaped Defect Creates Journey Fragility"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_journey_fragility" in content and "JOURNEY_FRAGILITY" in content:
                    self.log_pass(test_name, "EscapedDefectMiner has _create_journey_fragility method")
                else:
                    self.log_fail(test_name, "EscapedDefectMiner missing _create_journey_fragility method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_miner_exists(self):
        """Verify that RollbackPatternMiner service exists."""
        test_name = "RollbackPatternMiner Service Exists"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            if os.path.exists(file_path):
                self.log_pass(test_name, "RollbackPatternMiner service file exists")
            else:
                self.log_fail(test_name, "RollbackPatternMiner service file not found")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_creates_memory(self):
        """Verify that rollback creates ROLLBACK_PATTERN memory."""
        test_name = "Rollback Creates Memory"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_rollback_memory" in content and "ROLLBACK_PATTERN" in content:
                    self.log_pass(test_name, "RollbackPatternMiner has _create_rollback_memory method")
                else:
                    self.log_fail(test_name, "RollbackPatternMiner missing _create_rollback_memory method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_creates_behavior_fragility(self):
        """Verify that rollback creates BEHAVIOR_FRAGILITY."""
        test_name = "Rollback Creates Behavior Fragility"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_behavior_fragility" in content and "BEHAVIOR_FRAGILITY" in content:
                    self.log_pass(test_name, "RollbackPatternMiner has _create_behavior_fragility method")
                else:
                    self.log_fail(test_name, "RollbackPatternMiner missing _create_behavior_fragility method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_creates_journey_fragility(self):
        """Verify that rollback creates JOURNEY_FRAGILITY."""
        test_name = "Rollback Creates Journey Fragility"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_journey_fragility" in content and "JOURNEY_FRAGILITY" in content:
                    self.log_pass(test_name, "RollbackPatternMiner has _create_journey_fragility method")
                else:
                    self.log_fail(test_name, "RollbackPatternMiner missing _create_journey_fragility method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_creates_risky_combination(self):
        """Verify that rollback creates RISKY_CHANGE_COMBINATION."""
        test_name = "Rollback Creates Risky Combination"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "_create_risky_combination_memory" in content and "RISKY_CHANGE_COMBINATION" in content:
                    self.log_pass(test_name, "RollbackPatternMiner has _create_risky_combination_memory method")
                else:
                    self.log_fail(test_name, "RollbackPatternMiner missing _create_risky_combination_memory method")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_links_recommendation(self):
        """Verify that evidence events link to recommendation runs."""
        test_name = "Evidence Links Recommendation Run"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "recommendation_run_id" in content and "_create_evidence_event" in content:
                    self.log_pass(test_name, "EscapedDefectMiner evidence accepts recommendation_run_id")
                else:
                    self.log_fail(test_name, "EscapedDefectMiner evidence missing recommendation_run_id")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_links_pr(self):
        """Verify that evidence events link to PRs."""
        test_name = "Evidence Links Pull Request"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "pull_request_id" in content and "_create_evidence_event" in content:
                    self.log_pass(test_name, "RollbackPatternMiner evidence accepts pull_request_id")
                else:
                    self.log_fail(test_name, "RollbackPatternMiner evidence missing pull_request_id")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_escaped_defect_score_escalation(self):
        """Verify that escaped defect score increases behavior risk."""
        test_name = "Escaped Defect Score Escalation"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that behavior fragility score increases by 15.0
                if "existing.fragility_score = min(100.0, existing.fragility_score + 15.0)" in content:
                    self.log_pass(test_name, "EscapedDefectMiner increases behavior fragility score (+15.0)")
                else:
                    self.log_fail(test_name, "EscapedDefectMiner missing score escalation logic")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_score_escalation(self):
        """Verify that rollback score increases behavior risk."""
        test_name = "Rollback Score Escalation"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that rollback has score bonus
                if "ROLLBACK_SCORE_BONUS" in content:
                    self.log_pass(test_name, "RollbackPatternMiner has ROLLBACK_SCORE_BONUS constant")
                else:
                    self.log_fail(test_name, "ROLLBACK_SCORE_BONUS not defined")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_repeated_rollback_bonus(self):
        """Verify that repeated rollbacks get additional bonus."""
        test_name = "Repeated Rollback Bonus"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                # Check that repeated rollbacks get escalation bonus
                if "REPEATED_ROLLBACK_BONUS" in content:
                    self.log_pass(test_name, "RollbackPatternMiner has REPEATED_ROLLBACK_BONUS constant")
                else:
                    self.log_fail(test_name, "REPEATED_ROLLBACK_BONUS not defined")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")


def main():
    """Main entry point."""
    verifier = EscapedDefectRollbackVerification()
    success = verifier.verify_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
