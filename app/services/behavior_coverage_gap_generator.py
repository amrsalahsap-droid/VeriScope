from typing import List, Dict, Any, Optional


class BehaviorCoverageGapGenerator:
    """Generates precise, actionable coverage gaps from missing or partial behavior scenario coverage."""

    def __init__(self, db: Optional[Any] = None):
        """Initialize gap generator with optional database session."""
        self.db = db

    def generate_coverage_gaps(
        self,
        behavior_coverages: List[Dict[str, Any]],  # Output list from BehaviorCoverageAnalyzer containing behaviors and scenarios
    ) -> List[Dict[str, Any]]:
        """Identify and build actionable coverage gaps for all impacted behaviors."""
        gaps = []
        seen_scenarios = set()

        for bc in behavior_coverages:
            b_name = bc["behavior_name"]
            scenarios = bc.get("scenarios", [])

            for s in scenarios:
                s_id = s["scenario_id"]
                s_title = s["title"]
                status = s["coverage_status"]

                # Enforce Rule 1: No duplicate gaps for the same scenario
                if s_id in seen_scenarios:
                    continue

                gap_type = None
                suggested_action = None
                reason = s["reason"]
                confidence = s["confidence"]
                priority = s["priority"]

                # Extract relationships
                existing_tests = s.get("existing_tests", [])
                coverage_support = s.get("coverage_support", [])

                related_files = [cs["file_path"] for cs in coverage_support]
                existing_related_tests = [t["test_identifier"] for t in existing_tests]

                # Match status to gaps
                if status == "VERIFIED_ON_CURRENT_PR":
                    # Fully verified, no gap!
                    continue

                # Rule 2: Covered historically but not run on current PR -> RUN_EXISTING_TEST, not ADD_TEST
                elif status == "COVERED_BY_EXISTING_TEST":
                    gap_type = "NO_CURRENT_PR_EXECUTION"
                    suggested_action = f"RUN_EXISTING_TEST: Add {existing_related_tests[0]} to current PR test suite to verify scenario"
                    reason = f"Scenario is mapped to {len(existing_related_tests)} automated tests, but they were not executed in current PR"

                # Rule 3: File coverage only (partial)
                elif status == "PARTIALLY_COVERED":
                    gap_type = "PARTIAL_TEST_COVERAGE"
                    suggested_action = "BIND_EXISTING_TEST: Traces show coverage files, but explicit scenario test maps are missing"
                    reason = "Code coverage exists for related source files, but test-to-behavior mappings are loose / unlinked"

                # Rule 4: Manual validation recommendations
                elif status == "MANUAL_VALIDATION_RECOMMENDED":
                    gap_type = "NO_EXISTING_TEST"
                    suggested_action = s["suggested_action"]
                    reason = "High-priority business scenario missing automated tests; execute manual checkout validation"

                # Rule 5: Completely missing
                elif status == "MISSING_AUTOMATED_COVERAGE":
                    gap_type = "NO_EXISTING_TEST"
                    
                    # Scenario type specific classifications (Stage 5/6 fallback matching)
                    s_type = s.get("scenario_type", "FUNCTIONAL").upper()
                    if s_type == "EDGE":
                        gap_type = "MISSING_EDGE_CASE"
                    elif s_type == "SECURITY":
                        gap_type = "MISSING_SECURITY_CASE"

                    suggested_action = f"ADD_AUTOMATED_TEST: Implement automated test case covering: '{s_title}'"
                    reason = "No mapped automated tests or source code file coverage detected"

                if gap_type:
                    seen_scenarios.add(s_id)
                    gaps.append({
                        "behavior_name": b_name,
                        "scenario_title": s_title,
                        "gap_type": gap_type,
                        "priority": priority,
                        "reason": reason,
                        "suggested_action": suggested_action,
                        "related_changed_files": related_files,
                        "existing_related_tests": existing_related_tests,
                        "confidence": confidence,
                    })

        return gaps
