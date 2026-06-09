from typing import Dict, Any, List

class DegradationEngine:
    @staticmethod
    def evaluate_evidence(changed_files: List[str], repo_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate evidence status and determine:
        1. evidence_quality: "HIGH", "MODERATE", "LOW", or "UNKNOWN"
        2. active_rules: List[str] containing names of applied degradation rules
        3. run_all_tests: bool (safe-fallback mode)
        4. expansion_levels: int (number of levels of transitiveness)
        5. widening_mode: bool (widen scope aggressively)
        6. evidence_quality_logic: str description of the quality outcome
        """
        has_coverage_map = repo_context.get("has_coverage_map", True)
        coverage_is_partial = repo_context.get("coverage_is_partial", False)
        weak_dependency_data = repo_context.get("weak_dependency_data", False)
        insufficient_evidence = repo_context.get("insufficient_evidence", False)

        evidence_quality = "HIGH"
        active_rules = []
        run_all_tests = False
        expansion_levels = 1
        widening_mode = False
        evidence_quality_logic = "Standard high-precision recommendation matching."

        # Rule 4: Insufficient Evidence or no changed files -> Trigger Safe-Fallback Mode
        if insufficient_evidence or not changed_files:
            evidence_quality = "UNKNOWN"
            run_all_tests = True
            active_rules.append("INSUFFICIENT_EVIDENCE_SAFE_FALLBACK")
            evidence_quality_logic = "Insufficient evidence or metadata detected. Optimization disabled; running full regression suite."
            return {
                "evidence_quality": evidence_quality,
                "active_rules": active_rules,
                "run_all_tests": run_all_tests,
                "expansion_levels": expansion_levels,
                "widening_mode": widening_mode,
                "evidence_quality_logic": evidence_quality_logic
            }

        # Rule 1: Missing Coverage Map -> Widen recommendation scope aggressively
        if not has_coverage_map:
            evidence_quality = "LOW"
            widening_mode = True
            active_rules.append("MISSING_COVERAGE_MAP_SCOPE_WIDENING")
            evidence_quality_logic = "Missing coverage mapping. Scope widened aggressively to include parent folder match heuristics."

        # Rule 2: Partial Mappings -> Disable aggressive optimization filters
        elif coverage_is_partial:
            evidence_quality = "MODERATE"
            expansion_levels = 2
            active_rules.append("PARTIAL_MAPPING_TRANSITIVE_EXPANSION")
            evidence_quality_logic = "Partial coverage mappings. Transitive dependency expansion expanded up by +1 level."

        # Rule 3: Weak Dependency Data -> Full-chain transitive expansion
        if weak_dependency_data:
            evidence_quality = "LOW"
            expansion_levels = 999  # full transitive import expansion
            active_rules.append("WEAK_DEPENDENCY_DATA_FULL_TRANSITIVE_EXPANSION")
            evidence_quality_logic = "Weak static dependency metadata. Performing full import chain expansion."

        # Rule 5: Flaky Test Warning & non-linear degradation readiness
        flaky_tests = repo_context.get("flaky_tests", [])
        if flaky_tests:
            active_rules.append("FLAKY_TEST_DETECTED_CONFIDENCE_DEGRADATION")
            has_high_or_moderate_flaky = False
            flaky_names = []
            
            for ft in flaky_tests:
                conf = getattr(ft, "confidence_level", None) or (ft.get("confidence_level") if isinstance(ft, dict) else "LOW")
                # Fallback to test case's custom representations
                name = getattr(ft, "test_name", None) or (ft.get("test_name") if isinstance(ft, dict) else None)
                if not name:
                    tc = getattr(ft, "test_case", None)
                    if tc:
                        name = getattr(tc, "test_name", None)
                if not name:
                    name = "Unknown Test"
                flaky_names.append(name)
                
                if conf in ("HIGH", "MODERATE"):
                    has_high_or_moderate_flaky = True
            
            names_str = ", ".join(flaky_names[:5])
            if len(flaky_names) > 5:
                names_str += f" and {len(flaky_names) - 5} more"

            if has_high_or_moderate_flaky:
                # Degrade evidence_quality by one tier
                if evidence_quality == "HIGH":
                    evidence_quality = "MODERATE"
                elif evidence_quality == "MODERATE":
                    evidence_quality = "LOW"
                
                evidence_quality_logic += f" [Degraded due to moderate/high confidence flaky tests: {names_str}]"
            else:
                # All flaky tests are LOW confidence
                evidence_quality_logic += f" [Warning - Low confidence flaky tests detected: {names_str}]"

        return {
            "evidence_quality": evidence_quality,
            "active_rules": active_rules,
            "run_all_tests": run_all_tests,
            "expansion_levels": expansion_levels,
            "widening_mode": widening_mode,
            "evidence_quality_logic": evidence_quality_logic
        }
