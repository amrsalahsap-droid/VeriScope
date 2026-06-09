import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("veriscope.regression_savings_calculator")

class RegressionSavingsCalculator:
    """
    RegressionSavingsCalculator
    ===========================
    Computes conservative, transparent, and lineage-backed CI/regression-efficiency 
    savings. Avoids speculative ROI claims by relying strictly on verified execution.
    """

    @classmethod
    def format_duration(cls, seconds: float) -> str:
        """
        Convert raw seconds into a concise, human-readable duration string.
        Examples:
          - 7800.0 seconds -> "2h 10m"
          - 2460.0 seconds -> "41m"
          - 150.0 seconds  -> "2m 30s"
          - 30.0 seconds   -> "30s"
        """
        if seconds < 0.0:
            seconds = 0.0
        tot_sec = int(round(seconds))
        h = tot_sec // 3600
        m = (tot_sec % 3600) // 60
        s = tot_sec % 60

        if h > 0:
            return f"{h}h {m}m" if m > 0 else f"{h}h"
        if m > 0:
            return f"{m}m {s}s" if s > 0 else f"{m}m"
        return f"{s}s"

    @classmethod
    def calculate_savings(
        cls,
        full_suite_baseline_seconds: float,
        recommended_runtime_seconds: float,
        recommendation_frequency: int,
        execution_frequency: int,
        excluded_runs: int = 0,
        missing_runtime_data: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate conservative regression-efficiency savings using verified execution frequency.
        """
        # Clamp inputs
        full_suite_baseline_seconds = max(0.0, full_suite_baseline_seconds)
        recommended_runtime_seconds = max(0.0, recommended_runtime_seconds)
        recommendation_frequency = max(0, recommendation_frequency)
        execution_frequency = max(0, execution_frequency)

        # Only allow savings if baseline exceeds recommended runtime
        net_saving_seconds = max(0.0, full_suite_baseline_seconds - recommended_runtime_seconds)

        # 1. Reduction Ratio (percentage)
        if full_suite_baseline_seconds > 0.0:
            reduction_percent = (net_saving_seconds / full_suite_baseline_seconds) * 100.0
        else:
            reduction_percent = 0.0

        # 2. Conservative Hours Saved (strictly based on execution frequency)
        total_seconds_saved = net_saving_seconds * execution_frequency
        hours_saved = total_seconds_saved / 3600.0

        # 3. Small Sample Warning (Confidence Limitations)
        confidence_warning = None
        if recommendation_frequency < 5 or execution_frequency < 3:
            confidence_warning = (
                f"WARNING: Small dataset (recommendations = {recommendation_frequency}, "
                f"executions = {execution_frequency}). ROI estimates have low statistical reliability."
            )

        # 4. Formula Transparency
        formula_transparency = (
            "Savings Formula: Max(0, Full Suite Baseline - Recommended Runtime) * Execution Frequency. "
            "Only followed or partially-followed runs contribute to total execution frequency. "
            "Speculative, unrecorded, or overridden runs contribute strictly 0.0 savings to prevent ROI inflation."
        )

        return {
            "average_full_suite_runtime": cls.format_duration(full_suite_baseline_seconds),
            "average_veriscope_runtime": cls.format_duration(recommended_runtime_seconds),
            "estimated_runtime_reduction": f"{round(reduction_percent, 1)}%",
            "estimated_runtime_reduction_percent": round(reduction_percent, 2),
            "estimated_engineering_hours_saved": round(hours_saved, 1),
            "estimated_engineering_hours_saved_str": f"{round(hours_saved, 1)} hours",
            "recommendation_frequency": recommendation_frequency,
            "execution_frequency": execution_frequency,
            "excluded_runs_count": excluded_runs,
            "missing_runtime_data_runs_count": missing_runtime_data,
            "formula_transparency": formula_transparency,
            "confidence_warning": confidence_warning
        }
