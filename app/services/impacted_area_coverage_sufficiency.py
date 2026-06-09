from typing import List, Dict, Any, Optional

class ImpactedAreaCoverageSufficiency:
    """
    Evaluates whether the existing automated tests and code coverage are sufficient
    to protect each key impacted area (Auth, Password Reset, User Registration, Security Validation).
    """

    KEYWORDS = {
        "Auth": ["auth", "login", "jwt", "token", "session", "middleware"],
        "Password Reset": ["password", "reset-password", "reset_password", "recovery"],
        "User Registration": ["signup", "sign-up", "register", "registration", "onboarding", "users"],
        "Security Validation": ["security", "permission", "access", "lockout", "admin"]
    }

    @classmethod
    def _matches_area(cls, text: Optional[str], area: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        for kw in cls.KEYWORDS[area]:
            if kw in text_lower:
                return True
        return False

    @classmethod
    def _matches_area_name(cls, area_name: str, target_area: str) -> bool:
        if not area_name:
            return False
        if target_area == "Auth" and area_name in ("Auth", "Authentication"):
            return True
        return area_name.lower() == target_area.lower()

    @classmethod
    def evaluate(
        cls,
        impacted_areas: List[str],
        changed_files: List[str],
        existing_test_inventory: List[Any],
        recommended_tests: List[Any],
        coverage_file_entries: List[Any],
        knowledge_graph_links: List[Any],
        suggested_scenarios: List[Any],
        coverage_confidence: str = "HIGH"
    ) -> List[Dict[str, Any]]:
        """
        Evaluates test coverage sufficiency for key areas.
        
        Returns a list of dicts, each containing:
        - area (str)
        - changed_files (List[str])
        - existing_tests (List[str])
        - recommended_existing_tests (List[str])
        - coverage_status (str: DIRECT / INDIRECT / NONE)
        - sufficiency (str: SUFFICIENT / PARTIAL / MISSING)
        - reason (str)
        - required_scenario_count (int)
        """
        results = []

        # Standardize coverage confidence input
        confidence_upper = (coverage_confidence or "HIGH").upper()

        def get_test_id(t: Any) -> str:
            if isinstance(t, str):
                return t
            if hasattr(t, "stable_identity") and getattr(t, "stable_identity"):
                return getattr(t, "stable_identity")
            if hasattr(t, "test_case_id") and getattr(t, "test_case_id"):
                return getattr(t, "test_case_id")
            if hasattr(t, "test_identifier") and getattr(t, "test_identifier"):
                return getattr(t, "test_identifier")
            if hasattr(t, "test_name") and getattr(t, "test_name"):
                return getattr(t, "test_name")
            if isinstance(t, dict):
                return t.get("stable_identity") or t.get("test_case_id") or t.get("test_identifier") or t.get("test_name") or ""
            return ""

        def get_link_info(link: Any) -> tuple:
            link_path = ""
            test_case_id = ""
            mapping_type = ""
            if isinstance(link, dict):
                link_path = link.get("file_path") or ""
                test_case_id = link.get("test_case_id") or link.get("test_id") or ""
                mapping_type = link.get("mapping_type") or link.get("source") or ""
            elif hasattr(link, "file_path"):
                link_path = getattr(link, "file_path") or ""
                test_case_id = getattr(link, "test_case_id", None) or getattr(link, "test_id", None) or ""
                mapping_type = getattr(link, "mapping_type", None) or getattr(link, "source", None) or ""
            return link_path, test_case_id, mapping_type

        def get_coverage_file_path(entry: Any) -> str:
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                return entry.get("file_path") or ""
            if hasattr(entry, "file_path"):
                return getattr(entry, "file_path") or ""
            return ""

        # Extract all covered file paths
        covered_files = set()
        for entry in coverage_file_entries:
            cp = get_coverage_file_path(entry)
            if cp:
                covered_files.add(cp)

        for area in ["Auth", "Password Reset", "User Registration", "Security Validation"]:
            # 1. Filter changed files for this area
            area_changed_files = []
            for f in changed_files:
                file_path = f if isinstance(f, str) else (f.get("file_path") or f.get("filename") or "")
                if cls._matches_area(file_path, area):
                    area_changed_files.append(file_path)

            # 2. Extract links corresponding to changed files in this area
            linked_tests_for_area = set()
            direct_linked_tests_for_area = set()
            indirect_linked_tests_for_area = set()
            
            for link in knowledge_graph_links:
                lp, tid, mtype = get_link_info(link)
                if lp and lp in area_changed_files:
                    if tid:
                        linked_tests_for_area.add(tid)
                        if (mtype or "").upper() in ("DIRECT", "STATIC", "DYNAMIC"):
                            direct_linked_tests_for_area.add(tid)
                        else:
                            indirect_linked_tests_for_area.add(tid)

            # 3. Filter existing tests
            area_existing_tests = []
            for t in existing_test_inventory:
                t_str = get_test_id(t)
                if t_str and (cls._matches_area(t_str, area) or t_str in linked_tests_for_area):
                    area_existing_tests.append(t_str)

            # Deduplicate and sort existing tests
            area_existing_tests = sorted(list(set(area_existing_tests)))

            # 4. Filter recommended tests
            area_recommended_tests = []
            for t in recommended_tests:
                t_str = get_test_id(t)
                if t_str and (cls._matches_area(t_str, area) or t_str in linked_tests_for_area):
                    area_recommended_tests.append(t_str)

            area_recommended_tests = sorted(list(set(area_recommended_tests)))

            # Check coverage mapping for files in this area
            area_covered_files = [f for f in area_changed_files if f in covered_files]

            has_direct_tests = False
            for t_str in area_existing_tests + area_recommended_tests:
                if t_str in direct_linked_tests_for_area:
                    has_direct_tests = True
                    break

            has_coverage = len(area_covered_files) > 0

            # Determine coverage status (DIRECT, INDIRECT, NONE)
            if has_coverage or has_direct_tests:
                coverage_status = "DIRECT"
            elif len(area_existing_tests) > 0 or len(area_recommended_tests) > 0:
                coverage_status = "INDIRECT"
            else:
                coverage_status = "NONE"

            # Determine Sufficiency status (SUFFICIENT, PARTIAL, MISSING)
            if not area_changed_files:
                # If no files changed, it is technically sufficient by default
                sufficiency = "SUFFICIENT"
                reason = f"No modified files detected in the {area} area. Existing protection is sufficient."
            elif coverage_status == "NONE":
                sufficiency = "MISSING"
                reason = f"Critical files in the {area} area were modified, but no directly or indirectly linked automated tests were found."
            elif coverage_status == "INDIRECT":
                sufficiency = "PARTIAL"
                reason = f"Modified files in the {area} area are protected by generic or matching domain tests, but lack exact direct statement-level coverage mappings."
            else:  # DIRECT
                # Must have BOTH direct tests and coverage mapping for SUFFICIENT
                if has_direct_tests and has_coverage:
                    sufficiency = "SUFFICIENT"
                    reason = f"Modified files in the {area} area are fully covered by direct automated tests with validated execution mappings."
                else:
                    sufficiency = "PARTIAL"
                    reason = f"Modified files in the {area} area have direct tests or coverage entries, but lack the complete combination of direct statement-level coverage and deterministic test execution traces."

            # Calculate required suggested scenario count
            if sufficiency == "SUFFICIENT":
                required_scenario_count = 0
            elif sufficiency == "PARTIAL":
                required_scenario_count = 2
            else:  # MISSING
                required_scenario_count = 3

            # Low/Unknown coverage confidence escalates required scenarios
            if confidence_upper in ("LOW", "UNKNOWN"):
                required_scenario_count += 1

            results.append({
                "area": area,
                "changed_files": area_changed_files,
                "existing_tests": area_existing_tests,
                "recommended_existing_tests": area_recommended_tests,
                "coverage_status": coverage_status,
                "sufficiency": sufficiency,
                "reason": reason,
                "required_scenario_count": required_scenario_count
            })

        return results
