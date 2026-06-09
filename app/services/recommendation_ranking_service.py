import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.test_result import TestCase, TestResult
from app.schemas.recommendation import (
    RankingCandidateInput,
    RankedCandidateTest,
    RankedRecommendationBundle,
)


class RecommendationRankingService:
    @staticmethod
    def rank_candidates(
        db: Session,
        repository_id: uuid.UUID,
        candidate_tests: List[RankingCandidateInput],
        mode: str = "NORMAL",
        business_behavior_mappings: Optional[List[Any]] = None,
        ac_coverage_report: Optional[Any] = None,
        test_to_ac_mappings: Optional[Dict[str, List[str]]] = None
    ) -> RankedRecommendationBundle:
        """
        Rank recommended candidate tests by risk value divided by execution cost.
        """
        # If no candidates are provided, return early
        if not candidate_tests:
            return RankedRecommendationBundle(
                ranked_candidates=[],
                total_runtime_seconds=0.0,
                runtime_confidence="HIGH",
                reasons=["No candidate tests provided for ranking."]
            )

        # 1. Fetch all TestCase records for this repository
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id
        ).all()
        tc_map = {str(tc.id): tc for tc in test_cases}

        # 2. Combine duplicate candidate suggestions by test_case_id
        combined = {}
        for c in candidate_tests:
            tc_id_str = str(c.test_case_id)
            if tc_id_str not in combined:
                combined[tc_id_str] = {
                    "test_case_id": c.test_case_id,
                    "reasons": c.reasons.copy(),
                    "base_priority_score": c.base_priority_score,
                    "evidence_sources": set(c.evidence_sources),
                    "mapping_confidence": c.mapping_confidence,
                    "flaky_status": c.flaky_status,
                    "historical_failure_score": c.historical_failure_score
                }
            else:
                # Merge reasons preserving original order and uniqueness
                existing_reasons = combined[tc_id_str]["reasons"]
                for r in c.reasons:
                    if r not in existing_reasons:
                        existing_reasons.append(r)
                
                # Combine base_priority_score (max)
                combined[tc_id_str]["base_priority_score"] = max(
                    combined[tc_id_str]["base_priority_score"],
                    c.base_priority_score
                )
                
                # Union evidence_sources
                combined[tc_id_str]["evidence_sources"].update(c.evidence_sources)
                
                # Best mapping_confidence (Higher numeric score is better)
                def get_conf_val(c_str):
                    if not c_str:
                        return 0.0
                    try:
                        if "/" in c_str:
                            return float(c_str.split("/")[0])
                        return float(c_str)
                    except:
                        conf_order = {"HIGH": 80.0, "MODERATE": 50.0, "LOW": 20.0}
                        return conf_order.get(c_str, 0.0)

                existing_conf = combined[tc_id_str]["mapping_confidence"]
                new_conf = c.mapping_confidence
                if get_conf_val(new_conf) > get_conf_val(existing_conf):
                    combined[tc_id_str]["mapping_confidence"] = new_conf
                    
                # Flaky status (quarantined > unstable > stable/None)
                flaky_order = {"quarantined": 3, "unstable": 2, "stable": 1, None: 0}
                existing_flaky = combined[tc_id_str]["flaky_status"]
                new_flaky = c.flaky_status
                if flaky_order.get(new_flaky, 0) > flaky_order.get(existing_flaky, 0):
                    combined[tc_id_str]["flaky_status"] = new_flaky
                    
                # Combine historical_failure_score (max)
                if c.historical_failure_score is not None:
                    if combined[tc_id_str]["historical_failure_score"] is None:
                        combined[tc_id_str]["historical_failure_score"] = c.historical_failure_score
                    else:
                        combined[tc_id_str]["historical_failure_score"] = max(
                            combined[tc_id_str]["historical_failure_score"],
                            c.historical_failure_score
                        )

        # 3. Query grouped average execution durations for combined test case IDs in one query
        tc_ids = [uuid.UUID(tc_id_str) for tc_id_str in combined.keys()]
        avg_durations_db = db.query(
            TestResult.test_case_id,
            func.avg(TestResult.duration)
        ).filter(
            TestResult.test_case_id.in_(tc_ids)
        ).group_by(TestResult.test_case_id).all()

        duration_map = {
            str(row[0]): float(row[1]) for row in avg_durations_db if row[1] is not None
        }

        # Fetch all ModuleRiskProfile records for this repository
        from app.models.module_risk_profile import ModuleRiskProfile
        from app.models.coverage import FileTestLink
        from app.models.test_coverage_link import TestCoverageLink

        profiles = db.query(ModuleRiskProfile).filter(
            ModuleRiskProfile.repository_id == repository_id
        ).all()
        risk_map = {p.module_path: p.risk_score for p in profiles}

        # Fetch test-to-file coverage mappings
        ftl_mapping = db.query(FileTestLink.test_case_id, FileTestLink.file_path).filter(
            FileTestLink.test_case_id.in_(tc_ids)
        ).all()

        tcl_mapping = db.query(TestCase.id, TestCoverageLink.file_path).join(
            TestCoverageLink, TestCase.stable_identity == TestCoverageLink.test_identifier
        ).filter(
            TestCase.id.in_(tc_ids)
        ).all()

        tc_to_files = {}
        for tc_id, file_path in ftl_mapping + tcl_mapping:
            tc_to_files.setdefault(str(tc_id), set()).add(file_path)

        # 4. Construct RankedCandidateTest objects
        ranked_candidates = []

        for tc_id_str, item in combined.items():
            tc = tc_map.get(tc_id_str)
            stable_identity = tc.stable_identity if tc else tc_id_str

            # Prioritize historically fragile modules
            covered_files = tc_to_files.get(tc_id_str, set())
            max_risk_score = 0.0
            fragile_file = None
            for f in covered_files:
                score = risk_map.get(f, 0.0)
                if score > max_risk_score:
                    max_risk_score = score
                    fragile_file = f

            if max_risk_score > 0:
                if "HISTORICAL_FRAGILITY" not in item["evidence_sources"]:
                    item["evidence_sources"].add("HISTORICAL_FRAGILITY")

            # Risk value calculation
            risk_value = 0.0
            evidence_sources = list(item["evidence_sources"])


            for src in evidence_sources:
                s = src.lower().replace("_", " ").strip()
                if "direct file" in s or "direct coverage" in s or s == "direct":
                    risk_value += 0.95
                elif "dependency expansion level 1" in s or "dependency expansion l1" in s or s == "l1":
                    risk_value += 0.80
                elif "dependency expansion level 2" in s or "dependency expansion l2" in s or s == "l2":
                    risk_value += 0.75
                elif "dependency expansion level 3" in s or "dependency expansion l3" in s or s == "l3":
                    risk_value += 0.70
                elif "historical failure direct" in s or "failure direct" in s:
                    risk_value += 0.90
                elif "historical failure neighborhood" in s or "failure neighborhood" in s or "historical failure neighbourhood" in s:
                    risk_value += 0.80
                elif "heuristic naming" in s or "naming heuristic" in s:
                    risk_value += 0.60
                elif "heuristic path" in s or "path heuristic" in s:
                    risk_value += 0.45
                elif "historical fragility" in s or "fragility" in s:
                    risk_value += item["base_priority_score"]

            if max_risk_score > 0:
                risk_value += max_risk_score * 0.1
                item["reasons"].append(
                    f"Historically fragile module: {fragile_file} (risk score: {max_risk_score:.2f})"
                )

            # Critical / Business tags check (+1.0)
            has_critical = False
            for src in evidence_sources:
                if any(kw in src.lower() for kw in ("critical", "business", "tag")):
                    has_critical = True
            for r in item["reasons"]:
                if any(kw in r.lower() for kw in ("critical", "business", "tag")):
                    has_critical = True
            if tc:
                name_lower = tc.test_name.lower()
                suite_lower = tc.suite_name.lower()
                if any(kw in name_lower or kw in suite_lower for kw in ("critical", "billing", "security", "isolation", "smoke", "auth", "business")):
                    has_critical = True

            if has_critical:
                risk_value += 1.0
            
            # Business intent scoring boosts
            ac_boost = 0.0
            if business_behavior_mappings and test_to_ac_mappings:
                # Check if this test maps to any AC
                mapped_ac_ids = test_to_ac_mappings.get(tc_id_str, [])
                if mapped_ac_ids:
                    # Existing test maps to AC: +35
                    ac_boost += 0.35
                    item["reasons"].append(f"Test maps to {len(mapped_ac_ids)} acceptance criterion(s)")
                
                # Check if test maps to scenario that maps to AC
                for mapping in business_behavior_mappings:
                    if mapping.behavior_scenario_id:
                        # Check if this test covers the scenario
                        # This would require test-to-scenario mapping, which we can infer from AC mappings
                        if any(str(mapping.acceptance_criterion_id) in mapped_ac_ids for mapping in business_behavior_mappings if mapping.acceptance_criterion_id):
                            # Scenario maps to AC: +30
                            ac_boost += 0.30
                            item["reasons"].append("Test covers scenario mapped to acceptance criterion")
                            break
            
            # Check if behavior maps to explicit business intent
            if business_behavior_mappings:
                for mapping in business_behavior_mappings:
                    if mapping.acceptance_criterion_id:
                        # Behavior maps to explicit business intent: +25
                        ac_boost += 0.25
                        item["reasons"].append("Behavior maps to explicit business intent")
                        break
            
            # If no AC mappings, check if this is vague inferred-only behavior
            if ac_boost == 0 and business_behavior_mappings:
                # Vague inferred-only behavior: +5
                ac_boost += 0.05
                item["reasons"].append("Inferred behavior mapping (no explicit business intent)")
            
            risk_value += ac_boost

            risk_value = round(risk_value, 2)

            # Calculate execution cost
            avg_dur = duration_map.get(tc_id_str)
            is_historical = (avg_dur is not None and avg_dur > 0)
            execution_cost = avg_dur if is_historical else 5.0

            # Compute priority score (risk_value / execution_cost)
            priority_score = round(risk_value / execution_cost, 4)

            ranked_candidates.append(
                RankedCandidateTest(
                    test_case_id=item["test_case_id"],
                    stable_identity=stable_identity,
                    risk_value=risk_value,
                    execution_cost=execution_cost,
                    priority_score=priority_score,
                    reasons=item["reasons"],
                    evidence_sources=evidence_sources,
                    mapping_confidence=item["mapping_confidence"],
                    flaky_status=item["flaky_status"],
                    is_critical=has_critical,
                    is_excluded=(item["flaky_status"] == "quarantined")
                )
            )

        # 5. Separate non-excluded and excluded candidates
        executable = [t for t in ranked_candidates if not t.is_excluded]
        excluded = [t for t in ranked_candidates if t.is_excluded]

        # Sort executable candidates:
        # - priority_score desc
        # - risk_value desc
        # - execution_cost asc
        # - stable_identity asc
        def sort_key(t):
            return (-t.priority_score, -t.risk_value, t.execution_cost, t.stable_identity)

        executable.sort(key=sort_key)

        # 6. Apply Safety Capping Constraints without dropping critical tests
        cap = None
        if mode == "NORMAL":
            cap = 50
        elif mode == "NORMAL_CAP_2":
            cap = 2
        elif mode == "WIDENED":
            cap = 100
        elif mode == "SAFE_FALLBACK":
            cap = 200

        if cap is not None and len(executable) > cap:
            capped = executable[:cap]
            # Identify critical tests in the remaining part that would have been dropped
            remaining_critical = [t for t in executable[cap:] if t.is_critical]
            final_executable = capped + remaining_critical
        else:
            final_executable = executable

        # 7. Estimate Total Runtime and Label Confidence
        total_runtime_seconds = sum(t.execution_cost for t in final_executable)

        total_executable_count = len(final_executable)
        if total_executable_count > 0:
            historical_count = sum(1 for t in final_executable if str(t.test_case_id) in duration_map)
            pct = historical_count / total_executable_count
            if pct >= 0.90:
                runtime_confidence = "HIGH"
            elif pct >= 0.50:
                runtime_confidence = "MODERATE"
            else:
                runtime_confidence = "LOW"
        else:
            runtime_confidence = "HIGH"

        reasons = [
            f"Ranked {len(final_executable)} executable candidate(s) and excluded {len(excluded)} quarantined test(s). "
            f"Total estimated execution cost: {total_runtime_seconds:.2f}s with {runtime_confidence} confidence."
        ]

        # Final ranking list combines executable tests first, followed by excluded (quarantined) tests
        all_candidates = final_executable + excluded

        return RankedRecommendationBundle(
            ranked_candidates=all_candidates,
            total_runtime_seconds=total_runtime_seconds,
            runtime_confidence=runtime_confidence,
            reasons=reasons
        )
