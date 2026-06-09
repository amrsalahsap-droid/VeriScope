from typing import List, Dict, Any

class RecommendationQualityEvaluator:
    @classmethod
    def evaluate_quality(cls, recommendations: List[Any]) -> Dict[str, Any]:
        """
        Evaluate the overall quality of a recommendation run based on targeted metrics.
        Returns a dictionary containing score, tier, is_weak, and individual metric breakdowns.
        """
        total = len(recommendations)
        if total == 0:
            return {
                "score": 0,
                "tier": "POOR",
                "is_weak": True,
                "breakdown": {
                    "coverage_contribution": 0.0,
                    "graph_contribution": 0.0,
                    "domain_contribution": 0.0,
                    "fallback_ratio": 0.0,
                    "evidence_completeness": 0.0
                }
            }

        def get_signal(item: Any) -> str:
            if isinstance(item, dict):
                return item.get("source_signal") or "UNKNOWN"
            return getattr(item, "source_signal", "UNKNOWN")

        cov_count = sum(1 for t in recommendations if get_signal(t) == "DIRECT_COVERAGE")
        graph_count = sum(1 for t in recommendations if get_signal(t) == "TEST_COVERAGE_GRAPH")
        domain_count = sum(1 for t in recommendations if get_signal(t) == "DOMAIN_MATCH")
        fallback_count = sum(1 for t in recommendations if get_signal(t) == "HISTORICAL_FAILURE_FALLBACK")
        other_count = total - (cov_count + graph_count + domain_count + fallback_count)

        cov_contrib = cov_count / total
        graph_contrib = graph_count / total
        domain_contrib = domain_count / total
        fallback_ratio = fallback_count / total
        completeness = 1.0 - fallback_ratio
        other_ratio = other_count / total

        # Weighted quality score calculation (0 - 100)
        evidence_sum = cov_contrib + graph_contrib + domain_contrib + other_ratio
        if evidence_sum > 0:
            evidence_score = (cov_contrib * 100.0 + graph_contrib * 85.0 + domain_contrib * 70.0 + other_ratio * 80.0) / evidence_sum
            score = int(round(completeness * evidence_score))
        else:
            score = 0

        # Map score to tier
        if score >= 75:
            tier = "STRONG"
        elif score >= 50:
            tier = "GOOD"
        elif score >= 25:
            tier = "FAIR"
        else:
            tier = "POOR"

        is_weak = tier in ("POOR", "FAIR")

        return {
            "score": score,
            "tier": tier,
            "is_weak": is_weak,
            "breakdown": {
                "coverage_contribution": round(cov_contrib, 4),
                "graph_contribution": round(graph_contrib, 4),
                "domain_contribution": round(domain_contrib, 4),
                "fallback_ratio": round(fallback_ratio, 4),
                "evidence_completeness": round(completeness, 4)
            }
        }
