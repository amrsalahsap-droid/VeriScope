import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("veriscope.pilot_executive_summary_renderer")

class PilotExecutiveSummaryRenderer:
    """
    PilotExecutiveSummaryRenderer
    =============================
    Renders clean, enterprise-grade, and concise operational executive summaries.
    Strictly avoids marketing hype, emojis, giant markdown structures, and AI-like phrasing.
    """

    @classmethod
    def render(
        cls,
        report_data: Optional[Dict[str, Any]] = None,
        *,
        prs_analyzed: Optional[int] = None,
        average_full_regression_runtime: Optional[str] = None,
        average_veriscope_recommended_runtime: Optional[str] = None,
        estimated_time_saved: Optional[str] = None,
        escaped_defects: Optional[str] = None,
        most_fragile_modules: Optional[List[str]] = None
    ) -> str:
        """
        Render a highly structured, concise, and emojiless executive summary.
        Can consume either a structured report payload or explicit keyword arguments.
        """
        # Initialize dictionary to extract values from report_data
        data = report_data or {}

        # 1. Resolve PRs analyzed
        if prs_analyzed is None:
            prs_analyzed = (
                data.get("prs_analyzed")
                or data.get("pilot_summary", {}).get("total_prs_analyzed")
                or data.get("recommendation_trust_signals", {}).get("total_prs_analyzed")
                or data.get("total_prs_analyzed")
            )
            if prs_analyzed is None:
                # Fallback to trust signals total outcomes/runs if PRs analyzed is completely absent
                prs_analyzed = (
                    data.get("recommendation_trust_signals", {}).get("total_outcomes")
                    or data.get("recommendation_trust_signals", {}).get("total_runs")
                    or 0
                )

        # 2. Resolve Average Full Regression Runtime
        if average_full_regression_runtime is None:
            average_full_regression_runtime = (
                data.get("average_full_regression_runtime")
                or data.get("regression_efficiency", {}).get("average_full_suite_runtime")
                or "0s"
            )

        # 3. Resolve Average Veriscope Recommended Runtime
        if average_veriscope_recommended_runtime is None:
            average_veriscope_recommended_runtime = (
                data.get("average_veriscope_recommended_runtime")
                or data.get("regression_efficiency", {}).get("average_veriscope_runtime")
                or "0s"
            )

        # 4. Resolve Estimated Time Saved
        if estimated_time_saved is None:
            # Check for direct key
            direct_saved = data.get("estimated_time_saved")
            if direct_saved is not None:
                estimated_time_saved = str(direct_saved)
            else:
                efficiency = data.get("regression_efficiency", {})
                hours = efficiency.get("estimated_engineering_hours_saved")
                if hours is not None:
                    # Determine if pricing model is fixed monthly to use "/month" suffix
                    pricing_model = data.get("pilot_summary", {}).get("pricing_model")
                    if pricing_model == "FIXED_MONTHLY":
                        estimated_time_saved = f"{hours} engineering hours/month"
                    else:
                        estimated_time_saved = f"{hours} engineering hours"
                else:
                    estimated_time_saved = efficiency.get("estimated_engineering_hours_saved_str") or "0 engineering hours"

        # 5. Resolve Escaped Defects
        if escaped_defects is None:
            direct_defects = data.get("escaped_defects")
            if direct_defects is not None:
                escaped_defects = str(direct_defects)
            else:
                safety = data.get("escaped_defect_safety", {})
                safety_status = safety.get("safety_status")
                if safety_status == "STABLE":
                    escaped_defects = "No increase observed during pilot window"
                elif safety_status == "ATTENTION":
                    escaped_defects = "Attention required: production defects/rollbacks registered"
                elif safety_status == "INSUFFICIENT_DATA":
                    escaped_defects = "Insufficient data to establish safety trends"
                else:
                    escaped_defects = "No increase observed during pilot window"

        # 6. Resolve Most Fragile Modules
        if most_fragile_modules is None:
            direct_modules = data.get("most_fragile_modules")
            if isinstance(direct_modules, list):
                most_fragile_modules = [str(m) for m in direct_modules]
            else:
                fragility = data.get("fragility_intelligence", {})
                module_list = fragility.get("most_fragile_modules") or []
                most_fragile_modules = []
                for item in module_list:
                    if isinstance(item, dict):
                        name = item.get("title") or item.get("normalized_pattern_key")
                        if name:
                            # Strip out prefix if it exists in the name
                            if ":" in name:
                                name = name.split(":")[-1]
                            most_fragile_modules.append(name)
                    elif isinstance(item, str):
                        most_fragile_modules.append(item)

        # Build list lines for fragile modules
        if most_fragile_modules:
            modules_str = "\n".join(f"- {m}" for m in most_fragile_modules)
        else:
            modules_str = "- None registered"

        # Render summary strictly following formatting rules and example format
        summary = (
            f"PRs analyzed: {prs_analyzed}\n\n"
            f"Average full regression runtime:\n"
            f"{average_full_regression_runtime}\n\n"
            f"Average Veriscope recommended runtime:\n"
            f"{average_veriscope_recommended_runtime}\n\n"
            f"Estimated time saved:\n"
            f"{estimated_time_saved}\n\n"
            f"Escaped defects:\n"
            f"{escaped_defects}\n\n"
            f"Most fragile modules:\n"
            f"{modules_str}"
        )
        return summary
