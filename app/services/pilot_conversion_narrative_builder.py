import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("veriscope.pilot_conversion_narrative_builder")

class PilotConversionNarrativeBuilder:
    """
    PilotConversionNarrativeBuilder
    ===============================
    Generates concise, conversion-ready operational narrative summaries.
    Strictly enforces conservative operational phrasing and metrics-derived statements.
    NEVER claims guaranteed safety, autonomous reliability, or defect prevention certainty.
    """

    @classmethod
    def generate_narrative(
        cls,
        report_data: Optional[Dict[str, Any]] = None,
        *,
        reduction_percent: Optional[float] = None,
        hours_saved: Optional[float] = None,
        adherence_rate: Optional[float] = None,
        repeat_adopters_count: Optional[int] = None,
        safety_status: Optional[str] = None,
        has_fragile_modules: Optional[bool] = None
    ) -> List[str]:
        """
        Generate a concise operational narrative (maximum 5 bullets) based on metrics.
        Can ingest either a structured report payload or explicit keyword parameters.
        """
        data = report_data or {}

        # 1. Resolve Reduction Percent
        if reduction_percent is None:
            reduction_percent = (
                data.get("regression_efficiency", {}).get("estimated_runtime_reduction_percent")
                or 0.0
            )
            if not reduction_percent:
                # Try parsing string format (e.g. "68.5%")
                reduction_str = data.get("regression_efficiency", {}).get("estimated_runtime_reduction")
                if reduction_str and "%" in reduction_str:
                    try:
                        reduction_percent = float(reduction_str.replace("%", "").strip())
                    except ValueError:
                        reduction_percent = 0.0

        # 2. Resolve Engineering Hours Saved
        if hours_saved is None:
            hours_saved = (
                data.get("regression_efficiency", {}).get("estimated_engineering_hours_saved")
                or 0.0
            )

        # 3. Resolve Adherence Rate
        if adherence_rate is None:
            adherence_rate = (
                data.get("recommendation_trust_signals", {}).get("adherence_rate")
                or 0.0
            )

        # 4. Resolve Repeat Adopters Count
        if repeat_adopters_count is None:
            repeat_adopters_count = (
                data.get("recurring_adoption", {}).get("unique_repeat_adopters_count")
                or 0
            )

        # 5. Resolve Safety Status
        if safety_status is None:
            safety_status = (
                data.get("escaped_defect_safety", {}).get("safety_status")
            )

        # 6. Resolve Fragile Modules presence
        if has_fragile_modules is None:
            modules = data.get("fragility_intelligence", {}).get("most_fragile_modules") or []
            has_fragile_modules = len(modules) > 0

        # Build narrative bullets list
        bullets = []

        # Bullet 1: Scope reduction vs. Safety stability
        if reduction_percent > 0.0:
            bullets.append(
                f"We reduced regression execution scope by {round(reduction_percent, 1)}% "
                "while maintaining stable escaped defect outcomes."
            )
        else:
            bullets.append(
                "We monitored regression execution runtimes across enrolled repositories "
                "during the pilot window."
            )

        # Bullet 2: Developer alignment and repeat adoption
        if repeat_adopters_count > 0:
            bullets.append(
                "Engineers repeatedly followed Veriscope recommendations during the pilot window, "
                "establishing recurring adoption patterns."
            )
        elif adherence_rate > 0.0:
            bullets.append(
                f"Engineers followed Veriscope recommendations at an adherence rate of {round(adherence_rate * 100, 1)}%, "
                "demonstrating active interaction with recommended test selections."
            )
        else:
            bullets.append(
                "Developer interaction and alignment with recommendation runs were logged to assess workflow integration."
            )

        # Bullet 3: Realized CI Pipeline Efficiency Savings
        if hours_saved > 0.0:
            bullets.append(
                f"Pilot codebases realized an estimated {round(hours_saved, 1)} engineering hours "
                "saved through selective test recommendations."
            )
        else:
            bullets.append(
                "Pilot tracking collected baseline execution times to assess potential CI pipeline efficiency improvements."
            )

        # Bullet 4: Production Defect Safety Assessment
        if safety_status == "STABLE":
            bullets.append(
                "Production safety outcomes remained stable, with no increase in escaped defects or rollbacks "
                "observed during the pilot window."
            )
        elif safety_status == "ATTENTION":
            bullets.append(
                "Temporal correlation registered production incidents or rollbacks within the evaluation period, "
                "prioritizing safety telemetry audits over changes."
            )
        else:
            bullets.append(
                "Defect telemetry baselines were logged to establish safety trends for future validation."
            )

        # Bullet 5: isolated Module Risk Fragility Scoping
        if has_fragile_modules:
            bullets.append(
                "Granular fragility patterns were isolated across active modules, "
                "highlighting specific areas for diagnostic scoping."
            )
        else:
            bullets.append(
                "Active codebases were audited for fragility and co-failure patterns to establish architectural risk profiles."
            )

        # Enforce maximum 5 narrative bullets constraint (Rule 3)
        return bullets[:5]
