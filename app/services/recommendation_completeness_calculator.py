from typing import Dict, Any, List, Optional


class RecommendationCompletenessCalculator:
    """
    Calculates a completeness score for a recommendation run based on:
    - Behavior coverage: How many impacted behaviors have recommended tests
    - Journey coverage: How many impacted journeys have recommended tests
    - Scenario coverage: How many scenarios are covered vs missing
    - Evidence quality: How strong the underlying evidence is
    - Signal diversity: How many different signal types contributed
    
    Score range: 0-100 with breakdown by dimension.
    """

    @classmethod
    def calculate(
        cls,
        impact_profile: Optional[Dict[str, Any]],
        recommended_tests: List[Dict[str, Any]],
        suggested_scenarios: List[Dict[str, Any]],
        evidence_quality: str = "UNKNOWN",
        recommendation_mode: str = "NORMAL",
    ) -> Dict[str, Any]:
        """
        Returns a completeness assessment with overall score and per-dimension breakdown.
        """
        if not impact_profile:
            return cls._empty_result()

        # 1. Behavior Coverage Dimension (0-20 points)
        behavior_score, behavior_details = cls._calculate_behavior_coverage(
            impact_profile, recommended_tests
        )

        # 2. Journey Coverage Dimension (0-20 points)
        journey_score, journey_details = cls._calculate_journey_coverage(
            impact_profile, recommended_tests
        )

        # 3. Scenario Coverage Dimension (0-20 points)
        scenario_score, scenario_details = cls._calculate_scenario_coverage(
            impact_profile, recommended_tests, suggested_scenarios
        )

        # 4. Evidence Quality Dimension (0-15 points)
        evidence_score, evidence_details = cls._calculate_evidence_quality(
            evidence_quality, recommendation_mode
        )

        # 5. Signal Diversity Dimension (0-10 points)
        signal_score, signal_details = cls._calculate_signal_diversity(
            recommended_tests
        )

        # 6. Acceptance Criteria Dimension (0-15 points)
        ac_score, ac_details = cls._calculate_acceptance_criteria_coverage(
            impact_profile
        )

        total_score = behavior_score + journey_score + scenario_score + evidence_score + signal_score + ac_score
        total_score = min(100, max(0, total_score))

        # Determine completeness grade
        if total_score >= 85:
            grade = "EXCELLENT"
        elif total_score >= 70:
            grade = "GOOD"
        elif total_score >= 50:
            grade = "MODERATE"
        elif total_score >= 30:
            grade = "WEAK"
        else:
            grade = "INSUFFICIENT"

        # Build actionable gaps
        gaps = []
        if behavior_details.get("uncovered_behaviors"):
            gaps.append({
                "dimension": "behavior_coverage",
                "gap": f"{len(behavior_details['uncovered_behaviors'])} impacted behaviors lack test coverage",
                "severity": "HIGH" if behavior_score < 12 else "MEDIUM",
                "suggestion": "Add tests that validate the uncovered business behaviors.",
            })
        if journey_details.get("uncovered_journeys"):
            gaps.append({
                "dimension": "journey_coverage",
                "gap": f"{len(journey_details['uncovered_journeys'])} impacted journeys lack test coverage",
                "severity": "HIGH" if journey_score < 12 else "MEDIUM",
                "suggestion": "Add tests that cover the user journeys affected by this change.",
            })
        if scenario_details.get("missing_count", 0) > 0:
            gaps.append({
                "dimension": "scenario_coverage",
                "gap": f"{scenario_details['missing_count']} scenarios missing automated coverage",
                "severity": "MEDIUM",
                "suggestion": "Review suggested test scenarios and automate high-priority gaps.",
            })
        if evidence_score < 10:
            gaps.append({
                "dimension": "evidence_quality",
                "gap": "Evidence quality is below threshold for confident recommendations",
                "severity": "HIGH" if evidence_score < 5 else "MEDIUM",
                "suggestion": "Improve code coverage reports and test history data.",
            })
        if ac_details.get("missing_ac"):
            gaps.append({
                "dimension": "acceptance_criteria",
                "gap": "No acceptance criteria provided for requirement validation",
                "severity": "HIGH",
                "suggestion": "Paste acceptance criteria to improve requirement coverage and recommendation accuracy.",
            })

        return {
            "overall_score": round(total_score, 1),
            "grade": grade,
            "dimensions": {
                "behavior_coverage": {
                    "score": round(behavior_score, 1),
                    "max": 20,
                    "details": behavior_details,
                },
                "journey_coverage": {
                    "score": round(journey_score, 1),
                    "max": 20,
                    "details": journey_details,
                },
                "scenario_coverage": {
                    "score": round(scenario_score, 1),
                    "max": 20,
                    "details": scenario_details,
                },
                "evidence_quality": {
                    "score": round(evidence_score, 1),
                    "max": 15,
                    "details": evidence_details,
                },
                "signal_diversity": {
                    "score": round(signal_score, 1),
                    "max": 10,
                    "details": signal_details,
                },
                "acceptance_criteria": {
                    "score": round(ac_score, 1),
                    "max": 15,
                    "details": ac_details,
                },
            },
            "gaps": gaps,
        }

    @classmethod
    def _calculate_behavior_coverage(
        cls,
        impact_profile: Dict[str, Any],
        recommended_tests: List[Dict[str, Any]],
    ) -> tuple:
        behavior_impact = impact_profile.get("behavior_impact", {})
        impacted_behaviors = behavior_impact.get("impacted_behaviors", [])

        if not impacted_behaviors:
            return 20.0, {"total": 0, "covered": 0, "uncovered_behaviors": [], "ratio": 1.0}

        # Build set of behavior names/slugs from recommended tests
        test_tokens = set()
        for t in recommended_tests:
            tid = (t.get("test_identifier") or t.get("stable_identity") or "").lower()
            tname = (t.get("test_name") or t.get("display_name") or "").lower()
            test_tokens.update(tid.replace("::", " ").replace("_", " ").replace("-", " ").split())
            test_tokens.update(tname.replace("_", " ").replace("-", " ").split())

        covered = []
        uncovered = []
        for ib in impacted_behaviors:
            b_name = ib.get("behavior_name", "").lower()
            b_tokens = set(b_name.replace("-", " ").replace("_", " ").split())
            if b_tokens & test_tokens:
                covered.append(ib.get("behavior_name"))
            else:
                uncovered.append(ib.get("behavior_name"))

        total = len(impacted_behaviors)
        ratio = len(covered) / total if total > 0 else 1.0
        score = ratio * 20.0

        return score, {
            "total": total,
            "covered": len(covered),
            "uncovered_behaviors": uncovered,
            "ratio": round(ratio, 3),
        }

    @classmethod
    def _calculate_journey_coverage(
        cls,
        impact_profile: Dict[str, Any],
        recommended_tests: List[Dict[str, Any]],
    ) -> tuple:
        journey_intelligence = impact_profile.get("journey_intelligence", {})
        affected_journeys = journey_intelligence.get("affected_journeys", [])

        if not affected_journeys:
            return 20.0, {"total": 0, "covered": 0, "uncovered_journeys": [], "ratio": 1.0}

        test_tokens = set()
        for t in recommended_tests:
            tid = (t.get("test_identifier") or t.get("stable_identity") or "").lower()
            tname = (t.get("test_name") or t.get("display_name") or "").lower()
            test_tokens.update(tid.replace("::", " ").replace("_", " ").replace("-", " ").split())
            test_tokens.update(tname.replace("_", " ").replace("-", " ").split())

        covered = []
        uncovered = []
        for aj in affected_journeys:
            j_name = aj.get("journey_name", "").lower()
            j_tokens = set(j_name.replace("-", " ").replace("_", " ").split())
            if j_tokens & test_tokens:
                covered.append(aj.get("journey_name"))
            else:
                uncovered.append(aj.get("journey_name"))

        total = len(affected_journeys)
        ratio = len(covered) / total if total > 0 else 1.0
        score = ratio * 20.0

        return score, {
            "total": total,
            "covered": len(covered),
            "uncovered_journeys": uncovered,
            "ratio": round(ratio, 3),
        }

    @classmethod
    def _calculate_scenario_coverage(
        cls,
        impact_profile: Dict[str, Any],
        recommended_tests: List[Dict[str, Any]],
        suggested_scenarios: List[Dict[str, Any]],
    ) -> tuple:
        bcm = impact_profile.get("behavior_coverage_matrix", [])

        if not bcm:
            return 20.0, {"total": 0, "covered": 0, "missing_count": 0, "ratio": 1.0}

        total = len(bcm)
        covered = sum(
            1 for entry in bcm
            if entry.get("coverage_status") in (
                "VERIFIED_ON_CURRENT_PR",
                "COVERED_BY_EXISTING_TEST",
            )
        )
        partially = sum(
            1 for entry in bcm
            if entry.get("coverage_status") == "PARTIALLY_COVERED"
        )
        missing = sum(
            1 for entry in bcm
            if entry.get("coverage_status") in (
                "MISSING_AUTOMATED_COVERAGE",
                "MANUAL_VALIDATION_RECOMMENDED",
            )
        )

        ratio = (covered + 0.5 * partially) / total if total > 0 else 1.0
        score = ratio * 20.0

        return score, {
            "total": total,
            "covered": covered,
            "partially_covered": partially,
            "missing_count": missing,
            "suggested_scenarios_count": len(suggested_scenarios),
            "ratio": round(ratio, 3),
        }

    @classmethod
    def _calculate_evidence_quality(cls, evidence_quality: str, recommendation_mode: str) -> tuple:
        quality_scores = {"HIGH": 15, "MODERATE": 10, "LOW": 5, "UNKNOWN": 3, "MISSING": 0}
        mode_penalties = {
            "NORMAL": 0, "WIDENED": -2, "SAFE_FALLBACK": -5,
            "CONSERVATIVE": -5, "FULL_REGRESSION": -8, "CRITICAL": -10,
        }

        base = quality_scores.get(evidence_quality.upper(), 3)
        penalty = mode_penalties.get(recommendation_mode, 0)
        score = max(0, base + penalty)

        return score, {
            "evidence_quality": evidence_quality,
            "recommendation_mode": recommendation_mode,
            "base_score": base,
            "mode_penalty": penalty,
        }

    @classmethod
    def _calculate_signal_diversity(cls, recommended_tests: List[Dict[str, Any]]) -> tuple:
        all_signals = set()
        for t in recommended_tests:
            rd = t.get("reason_details", {})
            for key, val in rd.items():
                if isinstance(val, (int, float)) and val > 0 and key not in ("total", "runtime_cost"):
                    all_signals.add(key)

        signal_count = len(all_signals)
        # 1 signal = 2pts, 2 = 4, 3 = 6, 4 = 8, 5+ = 10
        score = min(10, signal_count * 2)

        return score, {
            "unique_signals": sorted(list(all_signals)),
            "signal_count": signal_count,
        }

    @classmethod
    def _calculate_acceptance_criteria_coverage(cls, impact_profile: Dict[str, Any]) -> tuple:
        """Calculate acceptance criteria coverage score (0-15 points)."""
        signal_breakdown = impact_profile.get("business_intent_signal_breakdown", {})
        business_intent_signals = signal_breakdown.get("business_intent_signals", {})

        has_ac = business_intent_signals.get("has_acceptance_criteria", False)
        ac_count = business_intent_signals.get("acceptance_criteria_count", 0)

        if not has_ac or ac_count == 0:
            return 0.0, {
                "has_acceptance_criteria": False,
                "acceptance_criteria_count": 0,
                "missing_ac": True,
                "ratio": 0.0,
            }

        # Check AC coverage from business intent matrix
        matrix = business_intent_signals.get("business_intent_matrix", {})
        total_intents = matrix.get("total_intents", 0)
        covered = matrix.get("covered", 0)
        verified = matrix.get("verified", 0)

        if total_intents == 0:
            total_intents = ac_count

        # Score based on coverage ratio: 15 points for full coverage
        ratio = (covered + 0.5 * verified) / total_intents if total_intents > 0 else 0
        score = ratio * 15.0

        return score, {
            "has_acceptance_criteria": True,
            "acceptance_criteria_count": ac_count,
            "total_intents": total_intents,
            "covered": covered,
            "verified": verified,
            "missing_ac": False,
            "ratio": round(ratio, 3),
        }

    @classmethod
    def refresh_acceptance_criteria_dimension(
        cls,
        historical_assessment: Dict[str, Any],
        current_ac_count: int,
    ) -> Dict[str, Any]:
        """
        Refresh only the acceptance_criteria dimension of a completeness assessment
        using a live AC count, without mutating the historical record.

        Returns a copy of the assessment with:
        - updated acceptance_criteria dimension score/details
        - acceptance_criteria gap removed if ACs now exist
        - overall_score and grade recalculated
        """
        if not historical_assessment:
            return cls._empty_result()

        import copy
        refreshed = copy.deepcopy(historical_assessment)

        has_ac = current_ac_count > 0

        # Recompute AC dimension
        if not has_ac:
            ac_score = 0.0
            ac_details = {
                "has_acceptance_criteria": False,
                "acceptance_criteria_count": 0,
                "missing_ac": True,
                "ratio": 0.0,
            }
        else:
            # Use existing business_intent_matrix values if available.
            # These are historical evidence counts and must not be reinterpreted.
            existing_details = (
                refreshed.get("dimensions", {})
                .get("acceptance_criteria", {})
                .get("details", {})
            )
            total_intents = existing_details.get("total_intents", 0)
            covered = existing_details.get("covered", 0)
            verified = existing_details.get("verified", 0)

            # Validate that historical counts are non-negative and logically bounded.
            # Reject incompatible historical counts instead of reusing them blindly.
            counts_valid = (
                isinstance(covered, (int, float))
                and isinstance(verified, (int, float))
                and isinstance(total_intents, (int, float))
                and covered >= 0
                and verified >= 0
                and total_intents > 0
                and covered <= total_intents
                and verified <= total_intents
                and (covered > 0 or verified > 0)
            )

            if current_ac_count != total_intents:
                # AC count has changed since generation; historical coverage counts
                # are no longer compatible with the current AC set.
                counts_valid = False

            if counts_valid:
                coverage_known = True
                ratio = (covered + 0.5 * verified) / total_intents
                ac_score = ratio * 15.0
            else:
                # ACs exist, but no compatible coverage/verification evidence is
                # available to this calculator. Do not fabricate coverage credit.
                coverage_known = False
                total_intents = current_ac_count
                covered = 0
                verified = 0
                ratio = 0.0
                ac_score = 0.0

            ac_details = {
                "has_acceptance_criteria": True,
                "acceptance_criteria_count": current_ac_count,
                "total_intents": total_intents,
                "covered": covered,
                "verified": verified,
                "missing_ac": False,
                "coverage_known": coverage_known,
                "ratio": round(ratio, 3),
            }

        # Update AC dimension
        if "dimensions" in refreshed:
            refreshed["dimensions"]["acceptance_criteria"] = {
                "score": round(ac_score, 1),
                "max": 15,
                "details": ac_details,
            }

        # Remove acceptance_criteria gap if ACs now exist
        if has_ac:
            refreshed["gaps"] = [
                g for g in refreshed.get("gaps", [])
                if g.get("dimension") != "acceptance_criteria"
            ]
        else:
            # Ensure the gap exists if ACs are missing
            existing_gap = any(
                g.get("dimension") == "acceptance_criteria"
                for g in refreshed.get("gaps", [])
            )
            if not existing_gap:
                refreshed.setdefault("gaps", []).append({
                    "dimension": "acceptance_criteria",
                    "gap": "No acceptance criteria provided for requirement validation",
                    "severity": "HIGH",
                    "suggestion": "Paste acceptance criteria to improve requirement coverage and recommendation accuracy.",
                })

        # Recalculate overall score
        dims = refreshed.get("dimensions", {})
        total_score = sum(
            dims.get(d, {}).get("score", 0)
            for d in ("behavior_coverage", "journey_coverage", "scenario_coverage",
                      "evidence_quality", "signal_diversity", "acceptance_criteria")
        )
        refreshed["overall_score"] = round(min(100, max(0, total_score)), 1)

        if refreshed["overall_score"] >= 85:
            refreshed["grade"] = "EXCELLENT"
        elif refreshed["overall_score"] >= 70:
            refreshed["grade"] = "GOOD"
        elif refreshed["overall_score"] >= 50:
            refreshed["grade"] = "MODERATE"
        elif refreshed["overall_score"] >= 30:
            refreshed["grade"] = "WEAK"
        else:
            refreshed["grade"] = "INSUFFICIENT"

        return refreshed

    @classmethod
    def _empty_result(cls) -> Dict[str, Any]:
        return {
            "overall_score": 0,
            "grade": "INSUFFICIENT",
            "dimensions": {
                "behavior_coverage": {"score": 0, "max": 20, "details": {}},
                "journey_coverage": {"score": 0, "max": 20, "details": {}},
                "scenario_coverage": {"score": 0, "max": 20, "details": {}},
                "evidence_quality": {"score": 0, "max": 15, "details": {}},
                "signal_diversity": {"score": 0, "max": 10, "details": {}},
                "acceptance_criteria": {"score": 0, "max": 15, "details": {}},
            },
            "gaps": [{"dimension": "all", "gap": "No impact profile available", "severity": "HIGH", "suggestion": "Ensure PR has changed files and repository has discovered behaviors."}],
        }
