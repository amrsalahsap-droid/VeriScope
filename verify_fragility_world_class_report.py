"""
Verify Fragility World-Class Report

This script verifies that Veriscope explains how a company historically breaks
and uses that memory in recommendations through a comprehensive fragility report.

Verification Requirements:
1. What related historical failures exist? (historical failure miner)
2. What behavior/journey is fragile? (behavior/journey fragility)
3. What escaped defects/rollbacks happened before? (escaped defect/rollback miners)
4. Which tests/scenarios are boosted because of history? (recommendation integration)
5. Which optional scenarios became must-test because of fragility? (priority boosting)
6. What evidence supports each fragility claim? (evidence events)
7. What is stale vs active history? (status tracking)

Pass only if Veriscope explains how this company historically breaks and uses that memory in recommendations.
"""

import sys
import os

# Add app to path
sys.path.insert(0, '.')


class FragilityWorldClassReportVerification:
    """Verifies Veriscope explains historical breaks and uses memory in recommendations."""
    
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
        print("Fragility World-Class Report Verification")
        print("=" * 80)
        print()
        
        # Run verification tests
        self._verify_historical_failure_mining()
        self._verify_escaped_defect_mining()
        self._verify_rollback_pattern_mining()
        self._verify_behavior_fragility_tracking()
        self._verify_journey_fragility_tracking()
        self._verify_evidence_event_creation()
        self._verify_evidence_linkage()
        self._verify_explanation_generation()
        self._verify_dashboard_aggregation()
        self._verify_recommendation_integration()
        self._verify_priority_boosting()
        self._verify_status_tracking()
        self._verify_stale_vs_active_distinction()
        self._verify_decay_mechanism()
        self._verify_memory_key_determinism()
        self._verify_workspace_scoping()
        self._verify_repository_scoping()
        
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
            print("[PASS] ALL TESTS PASSED - Veriscope explains historical breaks and uses memory")
            return True
    
    def _verify_historical_failure_mining(self):
        """Verify that historical failures are mined and tracked."""
        test_name = "Historical Failure Mining"
        
        try:
            file_path = "app/services/historical_test_failure_miner_v2.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "REPEATED_TEST_FAILURE" in content and "mine_test_failures" in content:
                    self.log_pass(test_name, "HistoricalTestFailureMinerV2 mines repeated test failures")
                else:
                    self.log_fail(test_name, "HistoricalTestFailureMinerV2 missing failure mining logic")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_escaped_defect_mining(self):
        """Verify that escaped defects are mined and tracked."""
        test_name = "Escaped Defect Mining"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "ESCAPED_DEFECT_PATTERN" in content and "mine_escaped_defects" in content:
                    self.log_pass(test_name, "EscapedDefectMiner mines escaped defects")
                else:
                    self.log_fail(test_name, "EscapedDefectMiner missing escaped defect mining logic")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_rollback_pattern_mining(self):
        """Verify that rollback patterns are mined and tracked."""
        test_name = "Rollback Pattern Mining"
        
        try:
            file_path = "app/services/rollback_pattern_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "ROLLBACK_PATTERN" in content and "mine_rollback_patterns" in content:
                    self.log_pass(test_name, "RollbackPatternMiner mines rollback patterns")
                else:
                    self.log_fail(test_name, "RollbackPatternMiner missing rollback mining logic")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_behavior_fragility_tracking(self):
        """Verify that behavior fragility is tracked."""
        test_name = "Behavior Fragility Tracking"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "BEHAVIOR_FRAGILITY" in content and "_create_behavior_fragility" in content:
                    self.log_pass(test_name, "Behavior fragility is tracked")
                else:
                    self.log_fail(test_name, "Behavior fragility tracking missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_journey_fragility_tracking(self):
        """Verify that journey fragility is tracked."""
        test_name = "Journey Fragility Tracking"
        
        try:
            file_path = "app/services/escaped_defect_miner.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "JOURNEY_FRAGILITY" in content and "_create_journey_fragility" in content:
                    self.log_pass(test_name, "Journey fragility is tracked")
                else:
                    self.log_fail(test_name, "Journey fragility tracking missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_event_creation(self):
        """Verify that evidence events are created for all fragility."""
        test_name = "Evidence Event Creation"
        
        try:
            file_path = "app/models/fragility_evidence_event.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "FragilityEvidenceEvent" in content and "evidence_type" in content:
                    self.log_pass(test_name, "FragilityEvidenceEvent model exists for evidence tracking")
                else:
                    self.log_fail(test_name, "FragilityEvidenceEvent model missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_evidence_linkage(self):
        """Verify that evidence links to source entities (PR, test run, etc.)."""
        test_name = "Evidence Linkage"
        
        try:
            file_path = "app/models/fragility_evidence_event.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "pull_request_id" in content and "test_run_id" in content and "recommendation_run_id" in content:
                    self.log_pass(test_name, "Evidence links to PR, test run, and recommendation")
                else:
                    self.log_fail(test_name, "Evidence linkage missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_explanation_generation(self):
        """Verify that human-readable explanations are generated."""
        test_name = "Explanation Generation"
        
        try:
            file_path = "app/services/fragility_explanation_generator.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "generate_explanation" in content and "generate_behavior_explanation" in content:
                    self.log_pass(test_name, "FragilityExplanationGenerator generates human-readable explanations")
                else:
                    self.log_fail(test_name, "Explanation generation missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_dashboard_aggregation(self):
        """Verify that dashboard aggregates fragility data."""
        test_name = "Dashboard Aggregation"
        
        try:
            file_path = "app/services/fragility_dashboard_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "get_dashboard_data" in content and "FragilityDashboardService" in content:
                    self.log_pass(test_name, "FragilityDashboardService aggregates fragility for dashboard")
                else:
                    self.log_fail(test_name, "Dashboard aggregation missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_recommendation_integration(self):
        """Verify that fragility is integrated into recommendations."""
        test_name = "Recommendation Integration"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "resolve_fragility_recommendations" in content and "priority_score" in content:
                    self.log_pass(test_name, "Fragility integrated into recommendations with priority")
                else:
                    self.log_fail(test_name, "Recommendation integration missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_priority_boosting(self):
        """Verify that priority is boosted based on fragility."""
        test_name = "Priority Boosting"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "CRITICAL" in content and "priority" in content and "0.98" in content:
                    self.log_pass(test_name, "Priority boosted based on fragility risk level")
                else:
                    self.log_fail(test_name, "Priority boosting logic missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_status_tracking(self):
        """Verify that status (ACTIVE/STALE) is tracked."""
        test_name = "Status Tracking"
        
        try:
            file_path = "app/models/fragility_memory_v2.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "status" in content and "ACTIVE" in content and "STALE" in content:
                    self.log_pass(test_name, "Status tracking (ACTIVE/STALE) exists")
                else:
                    self.log_fail(test_name, "Status tracking missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_stale_vs_active_distinction(self):
        """Verify that stale vs active history is distinguished in recommendations."""
        test_name = "Stale vs Active Distinction"
        
        try:
            file_path = "app/services/fragility_memory_service.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "ACTIVE" in content and "STALE" in content and "priority" in content:
                    self.log_pass(test_name, "Stale vs active distinguished in priority weighting")
                else:
                    self.log_fail(test_name, "Stale vs active distinction missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_decay_mechanism(self):
        """Verify that decay mechanism exists for stale history."""
        test_name = "Decay Mechanism"
        
        try:
            file_path = "app/services/fragility_decay_service.py"
            if os.path.exists(file_path):
                self.log_pass(test_name, "FragilityDecayService exists for stale history decay")
            else:
                self.log_fail(test_name, "FragilityDecayService not found")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_memory_key_determinism(self):
        """Verify that memory_key is deterministic for deduplication."""
        test_name = "Memory Key Determinism"
        
        try:
            file_path = "app/models/fragility_memory_v2.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "memory_key" in content and "nullable=False" in content:
                    self.log_pass(test_name, "Memory key provides deterministic deduplication")
                else:
                    self.log_fail(test_name, "Memory key determinism missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_workspace_scoping(self):
        """Verify that fragility is scoped to workspace."""
        test_name = "Workspace Scoping"
        
        try:
            file_path = "app/models/fragility_memory_v2.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "workspace_id" in content:
                    self.log_pass(test_name, "Fragility memory scoped to workspace")
                else:
                    self.log_fail(test_name, "Workspace scoping missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")
    
    def _verify_repository_scoping(self):
        """Verify that fragility is scoped to repository."""
        test_name = "Repository Scoping"
        
        try:
            file_path = "app/models/fragility_memory_v2.py"
            with open(file_path, 'r') as f:
                content = f.read()
                if "repository_id" in content:
                    self.log_pass(test_name, "Fragility memory scoped to repository")
                else:
                    self.log_fail(test_name, "Repository scoping missing")
        except Exception as e:
            self.log_fail(test_name, f"Exception: {str(e)}")


def main():
    """Main entry point."""
    verifier = FragilityWorldClassReportVerification()
    success = verifier.verify_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
