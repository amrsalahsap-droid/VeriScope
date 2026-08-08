from typing import List, Dict, Any, Optional
import uuid


class BehaviorCoverageAnalyzer:
    """Analyzes and calculates precise scenario-level coverage truth for business behaviors."""

    def __init__(self, db: Optional[Any] = None):
        """Initialize analyzer with optional database session."""
        self.db = db

    def analyze_behavior_coverage(
        self,
        impacted_behaviors: List[Dict[str, Any]],     # List of impacted behaviors from impact analyzer
        scenarios: List[BehaviorScenario],             # Full scenario catalog
        test_mappings: List[Dict[str, Any]],           # Output from ExistingTestToBehaviorScenarioMapper
        coverage_supports: List[Dict[str, Any]],       # Output from CoverageFileBehaviorSupportMapper
        current_pr_runs: Optional[List[Dict[str, Any]]] = None, # Current PR executions e.g., [{"test_name": "...", "status": "passed"}]
    ) -> Dict[str, Any]:
        """Generate BehaviorCoverageSnapshot calculating scenario-level coverage truth."""
        behavior_coverages = []
        all_scenarios_out = []

        pr_runs = current_pr_runs or []

        # Index scenarios and support mappings
        scenarios_by_behavior = {}
        for s in scenarios:
            b_id = str(s.behavior_id)
            if b_id not in scenarios_by_behavior:
                scenarios_by_behavior[b_id] = []
            scenarios_by_behavior[b_id].append(s)

        mappings_by_scenario = {}
        for m in test_mappings:
            s_id = m["behavior_scenario_id"]
            if s_id not in mappings_by_scenario:
                mappings_by_scenario[s_id] = []
            mappings_by_scenario[s_id].append(m)

        supports_by_scenario = {}
        for cs in coverage_supports:
            s_id = cs.get("behavior_scenario_id")
            if s_id:
                if s_id not in supports_by_scenario:
                    supports_by_scenario[s_id] = []
                supports_by_scenario[s_id].append(cs)

        # Process each impacted behavior
        for b in impacted_behaviors:
            b_id = b["behavior_id"]
            b_name = b["behavior_name"]
            b_scenarios = scenarios_by_behavior.get(b_id, [])

            total_scenarios = len(b_scenarios)
            covered_scenarios = 0
            partially_covered_scenarios = 0
            missing_scenarios = 0
            verified_on_current_pr = 0

            behavior_scenarios_out = []

            for scenario in b_scenarios:
                s_id = str(scenario.id)
                s_mappings = mappings_by_scenario.get(s_id, [])
                s_supports = supports_by_scenario.get(s_id, [])

                # Determine coverage status:
                coverage_status = "MISSING_AUTOMATED_COVERAGE"
                confidence = "LOW"
                reason_parts = []
                suggested_action = "Automate Scenario validation"

                # Gather existing test cases mapped (ignore LOW confidence mappings)
                existing_tests = [
                    {"test_identifier": m["test_identifier"], "confidence": m["confidence"], "source_signal": m["source_signal"]}
                    for m in s_mappings if m["confidence"] in ["HIGH", "MEDIUM"]
                ]

                # Check if current PR executed and verified this scenario (via mapped tests or token match)
                has_pr_verification = False
                for run in pr_runs:
                    run_name = run.get("test_name", "").lower()
                    
                    # Direct check against mapped tests
                    is_mapped_match = False
                    for ext_test in existing_tests:
                        ext_id_lower = ext_test["test_identifier"].lower()
                        if run_name in ext_id_lower or ext_id_lower in run_name:
                            is_mapped_match = True
                            break
                            
                    # If mapped match or specific unique token match
                    if is_mapped_match or (
                        any(tok in run_name for tok in scenario.title.lower().split() if len(tok) > 3 and tok not in ["password", "reset", "login"])
                    ):
                        if run.get("status") == "passed":
                            has_pr_verification = True
                            break

                # Gather file coverage supports
                coverage_support = [
                    {"file_path": cs["coverage_file_path"], "support_type": cs["support_type"], "confidence": cs["confidence"]}
                    for cs in s_supports
                ]

                # Precedence Rule 1: Current PR verification outranks everything
                if has_pr_verification:
                    coverage_status = "VERIFIED_ON_CURRENT_PR"
                    verified_on_current_pr += 1
                    covered_scenarios += 1
                    confidence = "HIGH"
                    reason_parts.append("Successfully executed and verified on current PR build")
                    suggested_action = "None (Fully Verified)"

                # Precedence Rule 2: Existing tests without current execution run = covered historically
                elif existing_tests:
                    coverage_status = "COVERED_BY_EXISTING_TEST"
                    covered_scenarios += 1
                    
                    # Confidence derived from existing test confidence
                    max_test_conf = "LOW"
                    if any(t["confidence"] == "HIGH" for t in existing_tests):
                        max_test_conf = "HIGH"
                    elif any(t["confidence"] == "MEDIUM" for t in existing_tests):
                        max_test_conf = "MODERATE"
                        
                    confidence = max_test_conf
                    reason_parts.append(f"Covered historically by {len(existing_tests)} existing automated tests, but not executed in current PR")
                    suggested_action = "Add test to current PR run scope"

                # Precedence Rule 3: File coverage only (no explicit mapped test) = partial support
                elif coverage_support:
                    coverage_status = "PARTIALLY_COVERE"
                    coverage_status = "PARTIALLY_COVERED"
                    partially_covered_scenarios += 1
                    confidence = "MODERATE" if any(cs["confidence"] == "HIGH" for cs in coverage_support) else "LOW"
                    reason_parts.append(f"Supporting source code files have active coverage metrics, but no matching scenario test cases were found")
                    suggested_action = "Bind existing tests or automate scenario"

                # Precedence Rule 4: Missing means no mapped test or trace
                else:
                    coverage_status = "MISSING_AUTOMATED_COVERAGE"
                    missing_scenarios += 1
                    confidence = "LOW"
                    reason_parts.append("No automated test mapping or supporting file coverage traced")

                    # Crucial Rule: Missing high-risk scenario must generate high fidelity suggested action
                    if scenario.priority in ["BLOCKER", "MUST"] or b.get("impact_level") in ["CRITICAL", "HIGH"]:
                        coverage_status = "MANUAL_VALIDATION_RECOMMENDED"
                        suggested_action = f"Execute Manual Checkout Validation: Verify '{scenario.title}' immediately in isolated environment."
                        reason_parts.append("High-priority missing coverage; manual validation recommended for safety")
                    else:
                        suggested_action = f"Add automated test case covering: {scenario.title}"

                # Format reason
                reason = " / ".join(reason_parts)

                scenario_dict = {
                    "scenario_id": s_id,
                    "title": scenario.title,
                    "priority": scenario.priority,
                    "coverage_status": coverage_status,
                    "confidence": confidence,
                    "existing_tests": existing_tests,
                    "coverage_support": coverage_support,
                    "suggested_action": suggested_action,
                    "reason": reason,
                }
                behavior_scenarios_out.append(scenario_dict)
                all_scenarios_out.append(scenario_dict)

            # Calculate precise behavior-level coverage score in [0, 100]%
            coverage_score = 0.0
            if total_scenarios > 0:
                # Verified/covered = 100% weight, partially covered = 50% weight
                coverage_score = ((covered_scenarios + (partially_covered_scenarios * 0.5)) / total_scenarios) * 100.0

            # Determine aggregate behavior coverage confidence
            b_confidence = "LOW"
            if total_scenarios > 0:
                high_sc_count = sum(1 for s in behavior_scenarios_out if s["confidence"] == "HIGH")
                if high_sc_count / total_scenarios >= 0.7:
                    b_confidence = "HIGH"
                elif high_sc_count / total_scenarios >= 0.4:
                    b_confidence = "MODERATE"

            # Generate explainable coverage reason
            levels = []
            if verified_on_current_pr > 0:
                levels.append(f"{verified_on_current_pr} verified on current PR")
            if (covered_scenarios - verified_on_current_pr) > 0:
                levels.append(f"{(covered_scenarios - verified_on_current_pr)} covered historically")
            if partially_covered_scenarios > 0:
                levels.append(f"{partially_covered_scenarios} partially covered")
            if missing_scenarios > 0:
                levels.append(f"{missing_scenarios} missing coverage")

            b_reason = f"Behavior has {total_scenarios} scenarios ({', '.join(levels) if levels else 'none'}). Coverage score is {coverage_score:.1f}%."

            # Calculate Sufficiency using BehaviorCoverageSufficiencyRules
            from app.services.behavior_coverage_sufficiency_rules import BehaviorCoverageSufficiencyRules
            suff_envelope = BehaviorCoverageSufficiencyRules.evaluate_sufficiency(
                behavior_name=b_name,
                behavior_risk_level=b.get("risk_level", "MEDIUM") if isinstance(b, dict) else (b.risk_level if hasattr(b, "risk_level") else "MEDIUM"),
                impact_level=b.get("impact_level", "MEDIUM") if isinstance(b, dict) else "MEDIUM",
                scenarios=behavior_scenarios_out,
                coverage_confidence=b_confidence,
                has_direct_code_coverage_only=all(s["coverage_status"] == "PARTIALLY_COVERED" for s in behavior_scenarios_out) if behavior_scenarios_out else False,
            )

            behavior_coverages.append({
                "behavior_id": b_id,
                "behavior_name": b_name,
                "total_scenarios": total_scenarios,
                "covered_scenarios": covered_scenarios,
                "partially_covered_scenarios": partially_covered_scenarios,
                "missing_scenarios": missing_scenarios,
                "verified_on_current_pr": verified_on_current_pr,
                "coverage_score": coverage_score,
                "coverage_confidence": b_confidence,
                "coverage_reason": b_reason,
                "sufficiency": suff_envelope["sufficiency"],
                "sufficiency_reason": suff_envelope["sufficiency_reason"],
                "scenarios": behavior_scenarios_out,
            })

        return {
            "behavior_coverages": behavior_coverages,
            "all_scenarios": all_scenarios_out,
        }
