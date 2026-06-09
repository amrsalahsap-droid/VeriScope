import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.recommendation import RecommendationRun, RecommendationOutcome

class RecommendationAnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_outcome_analytics(self, repository_id: uuid.UUID) -> Dict[str, Any]:
        """
        Compute high-fidelity trust calibration index and recommendation outcomes analytics
        to guide future test prediction models and calibrate engineer alignment.
        """
        # Fetch all recommendation outcomes for this repository
        outcomes = (
            self.db.query(RecommendationOutcome)
            .join(RecommendationRun)
            .filter(RecommendationRun.repository_id == repository_id)
            .order_by(desc(RecommendationOutcome.created_at))
            .all()
        )

        total_outcomes = len(outcomes)
        if total_outcomes == 0:
            return {
                "repository_id": str(repository_id),
                "total_recommendations": 0,
                "trust_adherence_rate": 1.0,
                "escaped_defect_rate": 0.0,
                "rollback_rate": 0.0,
                "override_rate": 0.0,
                "trust_calibration_score": 1.0,
                "outcome_classification_latency_avg_seconds": 0.0,
                "override_frequency": 0.0,
                "escaped_defect_linkage_rate": 0.0,
                "rollback_linkage_rate": 0.0,
                "ignored_recommendation_rate": 0.0,
                "feedback_distribution": {
                    "useful": 0,
                    "not_useful": 0,
                    "missing_tests": 0
                },
                "calibration_rationale": "No recommendations recorded with outcomes. Trust calibration baseline is 1.0 (perfect initial trust)."
            }

        followed_count = 0
        escaped_defects = 0
        rollbacks = 0
        overridden_count = 0
        ignored_count = 0
        total_latency_seconds = 0.0
        classified_count = 0

        feedback_counts = {
            "useful": 0,
            "not_useful": 0,
            "missing_tests": 0
        }

        total_calibration_value = 0.0

        for o in outcomes:
            # 1. Evaluate general adherence
            if o.was_followed:
                followed_count += 1

            # 2. Evaluate override rates (any developer manual intervention)
            has_overrides = len(o.manually_added_tests or []) > 0 or len(o.manually_removed_tests or []) > 0
            if has_overrides:
                overridden_count += 1

            # 3. Evaluate critical failure signals
            if o.escaped_defect:
                escaped_defects += 1
            if o.rollback_occurred:
                rollbacks += 1

            # 4. Evaluate ignored status
            if o.outcome_status == "IGNORED" or o.classification == "ignored":
                ignored_count += 1

            # 5. Evaluate classification latency
            if o.outcome_status and o.outcome_status != "PENDING":
                classified_count += 1
                if o.updated_at and o.created_at:
                    latency = (o.updated_at - o.created_at).total_seconds()
                    total_latency_seconds += max(0.0, latency)

            # 6. Evaluate feedback state
            f_state = (o.feedback or "").lower()
            if "useful" in f_state:
                if "not_useful" in f_state or "not useful" in f_state:
                    feedback_counts["not_useful"] += 1
                else:
                    feedback_counts["useful"] += 1
            elif "not_useful" in f_state or "not useful" in f_state:
                feedback_counts["not_useful"] += 1
            elif "missing_tests" in f_state or "missing tests" in f_state:
                feedback_counts["missing_tests"] += 1

            # 7. Advanced calibration score calculus per run:
            # Start with a base rating of 1.0
            run_score = 1.0

            # Penalize if not followed
            if not o.was_followed:
                run_score -= 0.3

            # Penalize slightly for minor overrides (even if mostly followed)
            if has_overrides:
                run_score -= 0.1

            # Major penalties for escape defects and rollbacks
            if o.escaped_defect:
                run_score -= 0.5
            if o.rollback_occurred:
                run_score -= 0.5

            # Clamp score between 0.0 and 1.0
            run_score = max(0.0, min(1.0, run_score))
            total_calibration_value += run_score

        # Aggregated indicators
        trust_adherence_rate = followed_count / total_outcomes
        escaped_defect_rate = escaped_defects / total_outcomes
        rollback_rate = rollbacks / total_outcomes
        override_rate = overridden_count / total_outcomes
        trust_calibration_score = total_calibration_value / total_outcomes
        ignored_recommendation_rate = ignored_count / total_outcomes
        outcome_classification_latency_avg_seconds = total_latency_seconds / max(classified_count, 1)

        # Draft a calibration explanation
        if trust_calibration_score >= 0.85:
            rationale = (
                f"Excellent trust index ({int(trust_calibration_score * 100)}%). Recommendations are widely "
                f"adhered to ({int(trust_adherence_rate * 100)}% followed) with low defect leakage."
            )
        elif trust_calibration_score >= 0.65:
            rationale = (
                f"Moderate trust index ({int(trust_calibration_score * 100)}%). Review partial overrides "
                f"({int(override_rate * 100)}% customized by devs) or minor defect leakages."
            )
        else:
            rationale = (
                f"Low trust index ({int(trust_calibration_score * 100)}%). Urgent trust calibrator review required! "
                f"High rate of overrides ({int(override_rate * 100)}%) or defect/rollback leaks."
            )

        return {
            "repository_id": str(repository_id),
            "total_recommendations": total_outcomes,
            "trust_adherence_rate": round(trust_adherence_rate, 3),
            "escaped_defect_rate": round(escaped_defect_rate, 3),
            "rollback_rate": round(rollback_rate, 3),
            "override_rate": round(override_rate, 3),
            "trust_calibration_score": round(trust_calibration_score, 3),
            "outcome_classification_latency_avg_seconds": round(outcome_classification_latency_avg_seconds, 3),
            "override_frequency": round(override_rate, 3),
            "escaped_defect_linkage_rate": round(escaped_defect_rate, 3),
            "rollback_linkage_rate": round(rollback_rate, 3),
            "ignored_recommendation_rate": round(ignored_recommendation_rate, 3),
            "feedback_distribution": feedback_counts,
            "calibration_rationale": rationale
        }

    def get_learning_diagnostics(self, repository_id: uuid.UUID) -> Dict[str, Any]:
        """
        Compute rich, evidence-backed organizational learning insights.
        Includes taxonomy distributions, failure rate breakdown by taxonomy, override reasoning frequencies,
        top manually added/removed tests, and conservative suite expansion recommendations.
        """
        # Fetch all outcomes for this repository
        outcomes = (
            self.db.query(RecommendationOutcome)
            .join(RecommendationRun)
            .filter(RecommendationRun.repository_id == repository_id)
            .all()
        )

        total_outcomes = len(outcomes)
        if total_outcomes == 0:
            return {
                "repository_id": str(repository_id),
                "total_recommendations": 0,
                "trust_adherence_rate": 1.0,
                "taxonomy_distribution": {
                    "trusted": 0,
                    "ignored": 0,
                    "widened": 0,
                    "narrowed": 0,
                    "overridden": 0
                },
                "failure_signals": {
                    "escaped_defect_rate": 0.0,
                    "rollback_rate": 0.0,
                    "by_taxonomy": {
                        "trusted": {"escaped_defects": 0, "rollbacks": 0, "count": 0},
                        "ignored": {"escaped_defects": 0, "rollbacks": 0, "count": 0},
                        "widened": {"escaped_defects": 0, "rollbacks": 0, "count": 0},
                        "narrowed": {"escaped_defects": 0, "rollbacks": 0, "count": 0},
                        "overridden": {"escaped_defects": 0, "rollbacks": 0, "count": 0}
                    }
                },
                "override_insights": {
                    "reason_distribution": {},
                    "top_manually_added_tests": [],
                    "top_manually_removed_tests": []
                },
                "conservative_learning_recommendations": []
            }

        taxonomy_counts = {
            "trusted": 0,
            "ignored": 0,
            "widened": 0,
            "narrowed": 0,
            "overridden": 0
        }
        
        escaped_defects_count = 0
        rollbacks_count = 0
        followed_count = 0

        by_taxonomy_stats = {
            k: {"escaped_defects": 0, "rollbacks": 0, "count": 0} for k in taxonomy_counts
        }

        override_reasons = {}
        added_test_counts = {}
        removed_test_counts = {}

        for o in outcomes:
            # 1. Taxonomy classification
            cls_name = o.classification
            taxonomy_counts[cls_name] = taxonomy_counts.get(cls_name, 0) + 1
            by_taxonomy_stats[cls_name]["count"] += 1

            # 2. General Followed Adherence
            if o.was_followed:
                followed_count += 1

            # 3. Failures & leakage
            if o.escaped_defect:
                escaped_defects_count += 1
                by_taxonomy_stats[cls_name]["escaped_defects"] += 1
            if o.rollback_occurred:
                rollbacks_count += 1
                by_taxonomy_stats[cls_name]["rollbacks"] += 1

            # 4. Reason frequencies
            if o.override_reason:
                override_reasons[o.override_reason] = override_reasons.get(o.override_reason, 0) + 1

            # 5. Overridden test cases frequency
            for test in (o.manually_added_tests or []):
                added_test_counts[test] = added_test_counts.get(test, 0) + 1
            for test in (o.manually_removed_tests or []):
                removed_test_counts[test] = removed_test_counts.get(test, 0) + 1

        # Calculate rates
        trust_adherence_rate = followed_count / total_outcomes
        escaped_defect_rate = escaped_defects_count / total_outcomes
        rollback_rate = rollbacks_count / total_outcomes

        # Sorting added and removed test frequencies
        sorted_added = sorted(
            [{"test_case_id": k, "count": v} for k, v in added_test_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        sorted_removed = sorted(
            [{"test_case_id": k, "count": v} for k, v in removed_test_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )

        # Generate conservative learning recommendations (suite expansion)
        # Suggest tests added manually by engineers in >= 20% of overridden/customized outcomes or >= 2 times total
        suite_expansion = []
        total_custom_runs = sum(
            taxonomy_counts[k] for k in ["widened", "narrowed", "overridden"]
        )

        for item in sorted_added:
            test_id = item["test_case_id"]
            count = item["count"]
            
            custom_ratio = count / total_custom_runs if total_custom_runs > 0 else 0.0
            if count >= 2 or custom_ratio >= 0.20:
                suite_expansion.append({
                    "test_case_id": test_id,
                    "manual_addition_count": count,
                    "reason": f"Test case '{test_id}' is frequently added manually by engineers ({count} times). Suggest reviewing source-to-test mapping or dependency expansion strategies for potential gaps."
                })

        return {
            "repository_id": str(repository_id),
            "total_recommendations": total_outcomes,
            "trust_adherence_rate": round(trust_adherence_rate, 3),
            "taxonomy_distribution": taxonomy_counts,
            "failure_signals": {
                "escaped_defect_rate": round(escaped_defect_rate, 3),
                "rollback_rate": round(rollback_rate, 3),
                "by_taxonomy": by_taxonomy_stats
            },
            "override_insights": {
                "reason_distribution": override_reasons,
                "top_manually_added_tests": sorted_added[:10],
                "top_manually_removed_tests": sorted_removed[:10]
            },
            "conservative_learning_recommendations": suite_expansion
        }

