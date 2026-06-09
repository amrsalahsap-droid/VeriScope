import math
from typing import Dict, Any, List
from app.models.recommendation import RecommendationRun

class RecommendationExplanationBuilder:
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Deterministic duration formatting:
        - If duration < 60 minutes: e.g., "18 min"
        - If duration >= 60 minutes: e.g., "2h 14m"
        """
        minutes = max(1, int(round(seconds / 60.0))) if seconds > 0 else 0
        if minutes >= 60:
            h = minutes // 60
            m = minutes % 60
            return f"{h}h {m}m"
        return f"{minutes} min"

    @classmethod
    def build_recommendation_summary(cls, run: RecommendationRun) -> Dict[str, Any]:
        """Generate concise deterministic recommendation summaries from a RecommendationRun."""
        # 1. Tests counts
        recommended_tests_count = len(run.tests)
        skipped_count = run.skipped_count or 0
        total_tests_count = recommended_tests_count + skipped_count

        # 2. Runtime calculations in minutes
        estimated_runtime_seconds = run.estimated_runtime_seconds or 0.0
        full_suite_runtime_seconds = run.full_suite_runtime_seconds
        
        # Fallback for full suite runtime if missing (10x of estimated)
        if full_suite_runtime_seconds is None:
            full_suite_runtime_seconds = estimated_runtime_seconds * 10.0

        estimated_runtime_minutes = max(1, int(round(estimated_runtime_seconds / 60.0))) if estimated_runtime_seconds > 0 else 0
        full_suite_runtime_minutes = max(1, int(round(full_suite_runtime_seconds / 60.0))) if full_suite_runtime_seconds > 0 else 0

        # 3. Coverage confidence mapping
        raw_quality = (run.evidence_quality or "LOW").upper()
        if raw_quality in ("HIGH", "MODERATE", "LOW"):
            coverage_confidence = raw_quality
        else:
            # Fallback to LOW if unknown/stale
            coverage_confidence = "LOW"

        # 4. Recommendation Mode
        recommendation_mode = run.recommendation_mode or "NORMAL"

        # 5. Runtime Formatting for Summary Lines
        estimated_formatted = cls.format_duration(estimated_runtime_seconds)
        full_suite_formatted = cls.format_duration(full_suite_runtime_seconds)

        # 6. Generate deterministic concise summary lines
        summary_lines = [
            "Recommended Regression Suite",
            f"Run {recommended_tests_count} tests out of {total_tests_count}",
            f"Estimated runtime: {estimated_formatted} vs {full_suite_formatted} full suite"
        ]

        return {
            "recommended_tests_count": recommended_tests_count,
            "total_tests_count": total_tests_count,
            "estimated_runtime_minutes": estimated_runtime_minutes,
            "full_suite_runtime_minutes": full_suite_runtime_minutes,
            "coverage_confidence": coverage_confidence,
            "recommendation_mode": recommendation_mode,
            "summary_lines": summary_lines
        }
