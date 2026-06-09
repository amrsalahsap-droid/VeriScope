import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.test_result import TestCase
from app.schemas.recommendation import HeuristicTestCandidate, HeuristicMappingBundle


class PathHeuristicResolver:
    @staticmethod
    def resolve_path_heuristics(
        db: Session,
        repository_id: uuid.UUID,
        changed_files: List[str]
    ) -> HeuristicMappingBundle:
        """
        Find plausible tests from naming/path conventions.
        """
        # Fetch all test cases for this repository
        test_cases = db.query(TestCase).filter(TestCase.repository_id == repository_id).all()

        heuristic_test_candidates = []
        unresolved_files = []
        reasons = []

        # Default cap parameter per changed file
        MAX_HEURISTIC_TESTS_PER_FILE = 5

        for file_path in changed_files:
            file_path_obj = Path(file_path)
            stem = file_path_obj.stem
            stem_lower = stem.lower()

            # Immediate parent directory name
            parent_dir_name = file_path_obj.parent.name
            parent_dir_lower = parent_dir_name.lower()

            file_candidates = []

            for tc in test_cases:
                matched_type = None
                confidence = None
                reason_text = None

                tc_test_name_lower = tc.test_name.lower()
                tc_norm_name_lower = tc.normalized_test_name.lower() if tc.normalized_test_name else ""
                tc_suite_name_lower = tc.suite_name.lower()

                # Rule 2 A: Match SAME_STEM (exact match case-insensitive)
                if tc_test_name_lower == stem_lower or tc_norm_name_lower == stem_lower:
                    matched_type = "SAME_STEM"
                    confidence = "MODERATE"
                    reason_text = f"Test name matches exact file stem '{stem}'."
                
                # Rule 2 B: Match TEST_PREFIX_SUFFIX
                elif any(x in tc_test_name_lower for x in (f"test_{stem_lower}", f"{stem_lower}_test", f"{stem_lower}.spec", f"{stem_lower}.test")) or \
                     (tc_norm_name_lower and any(x in tc_norm_name_lower for x in (f"test_{stem_lower}", f"{stem_lower}_test", f"{stem_lower}.spec", f"{stem_lower}.test"))):
                    matched_type = "TEST_PREFIX_SUFFIX"
                    confidence = "MODERATE"
                    reason_text = f"Test name contains prefix/suffix matching file stem '{stem}'."

                # Rule 2 C: Match MODULE_NAME_MATCH (suite_name containing stem)
                elif stem_lower in tc_suite_name_lower:
                    matched_type = "MODULE_NAME_MATCH"
                    confidence = "LOW"
                    reason_text = f"Suite name '{tc.suite_name}' contains file stem '{stem}'."

                # Rule 2 D: Match SAME_DIRECTORY (suite_name or test name containing parent directory name)
                elif parent_dir_name and parent_dir_lower not in ("", "src", "app", "lib", "test", "tests") and \
                     (parent_dir_lower in tc_suite_name_lower or parent_dir_lower in tc_test_name_lower):
                    matched_type = "SAME_DIRECTORY"
                    confidence = "LOW"
                    reason_text = f"Test matches parent directory name '{parent_dir_name}'."

                if matched_type:
                    file_candidates.append(
                        HeuristicTestCandidate(
                            source_file_path=file_path,
                            test_case_id=tc.id,
                            stable_identity=tc.stable_identity,
                            heuristic_type=matched_type,
                            confidence_score=confidence,
                            reason=reason_text
                        )
                    )

            if not file_candidates:
                unresolved_files.append(file_path)
            else:
                # Rule 5: Sort candidates deterministically for this file by confidence score and stable_identity
                # MODERATE before LOW
                def sort_key(c):
                    conf_val = 0 if c.confidence_score == "MODERATE" else 1
                    return (conf_val, c.stable_identity)

                file_candidates.sort(key=sort_key)

                # Rule 4: Do not create more than MAX_HEURISTIC_TESTS_PER_FILE default 5
                capped_candidates = file_candidates[:MAX_HEURISTIC_TESTS_PER_FILE]
                heuristic_test_candidates.extend(capped_candidates)

                # Record reasoning
                matched_names = ", ".join([c.stable_identity for c in capped_candidates])
                reasons.append(f"Resolved {len(capped_candidates)} heuristic candidate(s) for file '{file_path}': {matched_names}")

        # Deterministic sorting of the final overall candidates list:
        # 1. Confidence score (MODERATE comes first)
        # 2. stable_identity (alphabetical)
        # 3. source_file_path (alphabetical)
        def overall_sort_key(c):
            conf_val = 0 if c.confidence_score == "MODERATE" else 1
            return (conf_val, c.stable_identity, c.source_file_path)

        heuristic_test_candidates.sort(key=overall_sort_key)

        return HeuristicMappingBundle(
            heuristic_test_candidates=heuristic_test_candidates,
            reasons=reasons,
            unresolved_files=sorted(unresolved_files)
        )
