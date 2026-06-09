import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.flaky_test import FlakyTestProfile
from app.models.test_result import TestCase
from app.models.coverage import FileTestLink
from app.schemas.recommendation import (
    CandidateTestInput,
    AdjustedCandidateTest,
    FlakyAdjustmentBundle,
)


class FlakyAdjustmentService:
    @staticmethod
    def apply_flaky_adjustments(
        db: Session,
        repository_id: uuid.UUID,
        candidate_tests: List[CandidateTestInput]
    ) -> FlakyAdjustmentBundle:
        """
        Evaluate and adjust candidate recommended tests based on flakiness profiles
        without silently losing track of quarantined or unstable tests.
        """
        # 1. Fetch all FlakyTestProfile records for this repository
        profiles = db.query(FlakyTestProfile).filter(
            FlakyTestProfile.repository_id == repository_id
        ).all()
        profile_map = {str(p.test_case_id): p for p in profiles}

        # 2. Fetch all TestCase records for this repository
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id
        ).all()
        tc_map = {str(tc.id): tc for tc in test_cases}

        # 3. Fetch all FileTestLink records mapping test cases to source files
        links = db.query(FileTestLink).join(
            TestCase, FileTestLink.test_case_id == TestCase.id
        ).filter(
            TestCase.repository_id == repository_id
        ).all()

        tc_to_files = {}
        for link in links:
            tc_id_str = str(link.test_case_id)
            if tc_id_str not in tc_to_files:
                tc_to_files[tc_id_str] = set()
            tc_to_files[tc_id_str].add(link.file_path)

        # 4. Helper function to compute score for stable candidates relative to a target test
        def compute_alternative_score(stable_tc: TestCase, target_tc: TestCase) -> int:
            score = 0
            
            # Same Suite (+100 pts)
            if stable_tc.suite_name == target_tc.suite_name:
                score += 100

            target_tc_id_str = str(target_tc.id)
            stable_tc_id_str = str(stable_tc.id)

            target_files = tc_to_files.get(target_tc_id_str, set())
            stable_files = tc_to_files.get(stable_tc_id_str, set())
            overlapping = target_files & stable_files

            # Same File Mapping (+50 pts)
            if overlapping:
                score += 50

            # Same Directory / Module Namespace (+20 pts)
            target_dirs = {str(Path(f).parent) for f in target_files if Path(f).parent != Path(".")}
            stable_dirs = {str(Path(f).parent) for f in stable_files if Path(f).parent != Path(".")}

            target_suite_module = target_tc.suite_name.rsplit('.', 1)[0] if '.' in target_tc.suite_name else None
            stable_suite_module = stable_tc.suite_name.rsplit('.', 1)[0] if '.' in stable_tc.suite_name else None

            same_dir = bool(target_dirs & stable_dirs)
            if target_suite_module and stable_suite_module and target_suite_module == stable_suite_module:
                same_dir = True

            if same_dir:
                score += 20

            # Overlapping coverage (+10 pts per overlapping file)
            score += 10 * len(overlapping)

            return score

        # 5. Define stable test pool
        all_stable_tcs = []
        for tc_id_str, tc in tc_map.items():
            p = profile_map.get(tc_id_str)
            if not p or p.status == "stable":
                all_stable_tcs.append(tc)

        # 6. Categorize candidates
        input_tc_ids = {str(c.test_case_id) for c in candidate_tests}
        adjusted_candidates_map = {}

        unstable_candidates = []
        quarantined_candidates = []
        stable_candidates = []

        for c in candidate_tests:
            tc_id_str = str(c.test_case_id)
            tc = tc_map.get(tc_id_str)
            if not tc:
                # Fallback in case seeded test case is not in tc_map
                continue

            profile = profile_map.get(tc_id_str)
            if not profile or profile.status == "stable":
                stable_candidates.append(c)
            elif profile.status == "unstable":
                unstable_candidates.append((c, profile))
            elif profile.status == "quarantined":
                quarantined_candidates.append((c, profile))

        # 7. Process stable candidates
        for c in stable_candidates:
            tc_id_str = str(c.test_case_id)
            tc = tc_map[tc_id_str]
            adjusted_candidates_map[tc_id_str] = AdjustedCandidateTest(
                test_case_id=c.test_case_id,
                stable_identity=tc.stable_identity,
                priority_score=c.current_priority_score,
                reasons=c.reasons + ["Stable test case. No flaky adjustments applied."],
                is_excluded=False,
                is_flaky=False,
                status="stable",
                warnings=[],
                alternative_to_quarantined=None,
                quarantined_alternatives=None
            )

        # 8. Process quarantined candidates
        for c, profile in quarantined_candidates:
            tc_id_str = str(c.test_case_id)
            tc = tc_map[tc_id_str]

            # Find stable alternatives
            alt_scores = []
            for stable_tc in all_stable_tcs:
                # Do not recommend the quarantined test itself
                if str(stable_tc.id) == tc_id_str:
                    continue
                score = compute_alternative_score(stable_tc, tc)
                if score > 0:
                    alt_scores.append((score, stable_tc))

            # Rank by score descending, then by stable identity ascending
            alt_scores.sort(key=lambda x: (-x[0], x[1].stable_identity))

            # Select up to MAX_ALTERNATIVES_PER_QUARANTINED_TEST = 3
            selected_alts = alt_scores[:3]
            alt_uuids = [alt[1].id for alt in selected_alts]

            warnings = ["Warning: Test is quarantined due to high flakiness/instability."]
            reasons = c.reasons + [
                f"Quarantined test case (status: {profile.status}). Excluded from executable recommendation list. "
                f"Found {len(selected_alts)} stable alternative(s)."
            ]

            adjusted_candidates_map[tc_id_str] = AdjustedCandidateTest(
                test_case_id=c.test_case_id,
                stable_identity=tc.stable_identity,
                priority_score=c.current_priority_score,
                reasons=reasons,
                is_excluded=True,
                is_flaky=True,
                status="quarantined",
                warnings=warnings,
                alternative_to_quarantined=None,
                quarantined_alternatives=alt_uuids
            )

            # Recommend stable alternatives when found
            for score, alt_tc in selected_alts:
                alt_tc_id_str = str(alt_tc.id)
                # Recommended if it's not already in the input candidates list
                if alt_tc_id_str not in input_tc_ids:
                    if alt_tc_id_str in adjusted_candidates_map:
                        existing = adjusted_candidates_map[alt_tc_id_str]
                        if c.current_priority_score > existing.priority_score:
                            existing.priority_score = c.current_priority_score
                        existing.reasons.append(
                            f"Recommended as a stable alternative for quarantined test {tc.stable_identity}."
                        )
                    else:
                        adjusted_candidates_map[alt_tc_id_str] = AdjustedCandidateTest(
                            test_case_id=alt_tc.id,
                            stable_identity=alt_tc.stable_identity,
                            priority_score=c.current_priority_score,
                            reasons=[f"Recommended as a stable alternative for quarantined test {tc.stable_identity}."],
                            is_excluded=False,
                            is_flaky=False,
                            status="stable",
                            warnings=[],
                            alternative_to_quarantined=c.test_case_id,
                            quarantined_alternatives=None
                        )

        # 9. Process unstable candidates
        for c, profile in unstable_candidates:
            tc_id_str = str(c.test_case_id)
            tc = tc_map[tc_id_str]

            # Check if there is at least one stable alternative
            has_stable_alt = False
            for stable_tc in all_stable_tcs:
                if str(stable_tc.id) == tc_id_str:
                    continue
                score = compute_alternative_score(stable_tc, tc)
                if score > 0:
                    has_stable_alt = True
                    break

            priority_score = c.current_priority_score
            warnings = ["Warning: Test is unstable and flaky."]
            reasons = c.reasons.copy()

            # Reduce priority slightly (subtract 0.10, floor 0.50) only if stable alternatives exist
            if has_stable_alt:
                priority_score = round(max(0.50, c.current_priority_score - 0.10), 2)
                warnings.append("Reduced priority due to unstable status and existence of stable alternatives.")
                reasons.append("Unstable test case with stable alternatives available. Priority score reduced by 0.10.")
            else:
                reasons.append("Unstable test case, but no equivalent stable alternatives found in repository. Retained original priority.")

            adjusted_candidates_map[tc_id_str] = AdjustedCandidateTest(
                test_case_id=c.test_case_id,
                stable_identity=tc.stable_identity,
                priority_score=priority_score,
                reasons=reasons,
                is_excluded=False,
                is_flaky=True,
                status="unstable",
                warnings=warnings,
                alternative_to_quarantined=None,
                quarantined_alternatives=None
            )

        # 10. Degrade bundle evidence quality based on confidence_level (resolve worst-case)
        worst_case_degradation = "NONE"
        for c, profile in unstable_candidates:
            conf = (profile.confidence_level or "LOW").upper()
            if conf == "HIGH":
                worst_case_degradation = "ONE_TIER_DEGRADATION"
            elif conf == "MODERATE" and worst_case_degradation != "ONE_TIER_DEGRADATION":
                worst_case_degradation = "MILD_DEGRADATION"

        # 11. Generate explainability metadata for RecommendationReasoningEntry
        reasoning_entries = []

        # Quarantined decisions
        for c, profile in quarantined_candidates:
            tc = tc_map[str(c.test_case_id)]
            reasoning_entries.append({
                "id": uuid.uuid4(),
                "test_case_id": c.test_case_id,
                "reason_type": "flaky_test_warning",
                "source_entity": tc.stable_identity,
                "source_reference": "flaky_profile",
                "human_readable_reason": (
                    f"Quarantined test case '{tc.stable_identity}' was excluded from the recommendation list "
                    f"due to quarantine status."
                ),
                "confidence_level": profile.confidence_level or "HIGH",
                "evidence_priority": "CRITICAL",
                "metadata": {
                    "status": "quarantined",
                    "original_priority": c.current_priority_score,
                    "adjusted_priority": c.current_priority_score,
                    "is_excluded": True
                }
            })
            reasoning_entries.append({
                "id": uuid.uuid4(),
                "test_case_id": c.test_case_id,
                "reason_type": "quarantine_alternative_warning",
                "source_entity": tc.stable_identity,
                "source_reference": "flaky_profile",
                "human_readable_reason": (
                    f"Quarantined test case '{tc.stable_identity}' has stable alternatives recommended."
                ),
                "confidence_level": profile.confidence_level or "HIGH",
                "evidence_priority": "CRITICAL",
                "metadata": {
                    "status": "quarantined",
                    "original_priority": c.current_priority_score,
                    "adjusted_priority": c.current_priority_score,
                    "is_excluded": True
                }
            })

        # Unstable decisions
        for c, profile in unstable_candidates:
            tc = tc_map[str(c.test_case_id)]
            adjusted = adjusted_candidates_map[str(c.test_case_id)]
            reasoning_entries.append({
                "id": uuid.uuid4(),
                "test_case_id": c.test_case_id,
                "reason_type": "flaky_test_warning",
                "source_entity": tc.stable_identity,
                "source_reference": "flaky_profile",
                "human_readable_reason": (
                    f"Unstable test case '{tc.stable_identity}' was adjusted with warning. "
                    f"Priority score: {adjusted.priority_score} (originally {c.current_priority_score})."
                ),
                "confidence_level": profile.confidence_level or "LOW",
                "evidence_priority": "IMPORTANT",
                "metadata": {
                    "status": "unstable",
                    "original_priority": c.current_priority_score,
                    "adjusted_priority": adjusted.priority_score,
                    "is_excluded": False,
                    "confidence_level": profile.confidence_level
                }
            })

        # Stable alternatives decisions
        for adj in adjusted_candidates_map.values():
            if adj.alternative_to_quarantined is not None:
                quarantined_tc = tc_map.get(str(adj.alternative_to_quarantined))
                quarantined_identity = quarantined_tc.stable_identity if quarantined_tc else str(adj.alternative_to_quarantined)
                reasoning_entries.append({
                    "id": uuid.uuid4(),
                    "test_case_id": adj.test_case_id,
                    "reason_type": "quarantine_alternative_warning",
                    "source_entity": adj.stable_identity,
                    "source_reference": "flaky_profile",
                    "human_readable_reason": (
                        f"Recommended stable alternative test '{adj.stable_identity}' in place of quarantined test "
                        f"'{quarantined_identity}'."
                    ),
                    "confidence_level": "HIGH",
                    "evidence_priority": "IMPORTANT",
                    "metadata": {
                        "status": "stable_alternative",
                        "alternative_to_quarantined": str(adj.alternative_to_quarantined),
                        "priority_assigned": adj.priority_score
                    }
                })

        return FlakyAdjustmentBundle(
            adjusted_candidates=list(adjusted_candidates_map.values()),
            flaky_profiles_used=[
                {
                    "test_case_id": str(p.test_case_id),
                    "status": p.status,
                    "failure_rate": p.failure_rate,
                    "confidence_level": p.confidence_level
                }
                for p in profiles
            ],
            evidence_quality_impact=worst_case_degradation,
            reasoning_entries=[
                {
                    "id": str(e["id"]),
                    "test_case_id": str(e["test_case_id"]),
                    "reason_type": e["reason_type"],
                    "source_entity": e["source_entity"],
                    "source_reference": e["source_reference"],
                    "human_readable_reason": e["human_readable_reason"],
                    "confidence_level": e["confidence_level"],
                    "evidence_priority": e["evidence_priority"],
                    "metadata": e["metadata"]
                }
                for e in reasoning_entries
            ]
        )
