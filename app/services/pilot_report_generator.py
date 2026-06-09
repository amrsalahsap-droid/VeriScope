import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.pilot import (
    PilotWorkspaceProfile,
    PilotRepositoryEnrollment,
)
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTest,
)
from app.models.fragility_pattern import FragilityPattern

from app.services.pilot_metrics_aggregator import PilotMetricsAggregator
from app.services.regression_savings_calculator import RegressionSavingsCalculator
from app.services.fragility_pilot_summary_builder import FragilityPilotSummaryBuilder
from app.services.escaped_defect_safety_analyzer import EscapedDefectSafetyAnalyzer
from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

logger = logging.getLogger("veriscope.pilot_report_generator")

class PilotReportGenerator:
    """
    PilotReportGenerator
    ====================
    Deterministic one-page operational pilot report orchestrator.
    Ties together all Phase 7 services to generate rich report packages
    in JSON, Markdown, and print-ready PDF HTML formats.
    """

    @classmethod
    def _format_fragility_list(cls, patterns: List[Dict[str, Any]]) -> str:
        """Helper to format list of fragility patterns concisely in Markdown."""
        if not patterns:
            return "- No active validated patterns registered."
        lines = []
        for p in patterns:
            lines.append(f"- **{p['title'] or p['normalized_pattern_key']}** (score: {p['fragility_score']}): {p['explanation']}")
        return "\n".join(lines)

    @classmethod
    def generate_report(
        cls,
        db: Session,
        pilot_profile_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        is_incident_lineage_complete: bool = True
    ) -> Dict[str, Any]:
        """
        Orchestrate pilot metrics, savings, fragility risk, safety analysis, and concrete next steps.
        """
        # 1. Fetch Organization and Profile details
        profile = db.query(PilotWorkspaceProfile).filter(
            PilotWorkspaceProfile.id == pilot_profile_id
        ).first()
        if not profile:
            raise ValueError(f"PilotWorkspaceProfile with ID {pilot_profile_id} not found.")

        workspace = db.query(Workspace).filter(Workspace.id == profile.workspace_id).first()
        workspace_name = workspace.name if workspace else "Unknown Workspace"

        # 2. Fetch Active Enrolled Repositories
        enrollments = db.query(PilotRepositoryEnrollment).filter(
            PilotRepositoryEnrollment.pilot_profile_id == pilot_profile_id,
            PilotRepositoryEnrollment.enrollment_status == "ACTIVE"
        ).all()
        repository_ids = [e.repository_id for e in enrollments]

        repos = db.query(Repository).filter(Repository.id.in_(repository_ids)).all() if repository_ids else []
        repo_names = [r.full_name for r in repos]

        # 3. Call Metrics Aggregator
        metrics = PilotMetricsAggregator.aggregate_metrics(db, repository_ids, start_date, end_date)

        # 4. Resolve exact followed/overridden/ignored outcome counts from database context
        runs = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id.in_(repository_ids),
            RecommendationRun.created_at >= start_date,
            RecommendationRun.created_at <= end_date
        ).all() if repository_ids else []
        run_ids = [run.id for run in runs]

        followed_count = 0
        overridden_count = 0
        ignored_count = 0
        
        if run_ids:
            outcomes = db.query(RecommendationOutcome).filter(
                RecommendationOutcome.recommendation_run_id.in_(run_ids)
            ).all()
            for outcome in outcomes:
                has_overrides = (
                    len(outcome.manually_added_tests or []) > 0 or
                    len(outcome.manually_removed_tests or []) > 0 or
                    outcome.outcome_status == "OVERRIDDEN"
                )
                if has_overrides:
                    overridden_count += 1
                elif outcome.outcome_status == "IGNORED":
                    ignored_count += 1
                else:
                    followed_count += 1

        total_runs = metrics["total_recommendation_runs"]
        total_outcomes = followed_count + overridden_count + ignored_count
        adherence_rate = followed_count / max(total_outcomes, 1) if total_outcomes > 0 else 0.0

        # Trust confidence bounds
        lower_bound, upper_bound = RecommendationIgnoreDetector.calculate_wilson_score_interval(
            followed_count,
            total_outcomes,
            confidence_level=0.90
        )

        # 5. Call Savings Calculator
        missing_full = metrics["excluded_data_counts"]["missing_full_suite_runtime"]
        missing_rec = metrics["excluded_data_counts"]["missing_recommended_runtime"]
        missing_out = metrics["excluded_data_counts"]["missing_outcome"]
        total_full_suite = metrics["total_full_suite_runtime_seconds"]
        total_recommended = metrics["total_recommended_runtime_seconds"]

        runs_with_full = total_runs - missing_full
        runs_with_rec = total_runs - missing_rec

        avg_full = total_full_suite / max(runs_with_full, 1) if runs_with_full > 0 else 0.0
        avg_rec = total_recommended / max(runs_with_rec, 1) if runs_with_rec > 0 else 0.0

        savings = RegressionSavingsCalculator.calculate_savings(
            full_suite_baseline_seconds=avg_full,
            recommended_runtime_seconds=avg_rec,
            recommendation_frequency=total_runs,
            execution_frequency=followed_count,
            excluded_runs=missing_out,
            missing_runtime_data=missing_full
        )

        # 6. Call Fragility Pilot Summary Builder (collated across enrolled repos)
        fragility_patterns = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id.in_(repository_ids),
            FragilityPattern.status == "ACTIVE"
        ).all() if repository_ids else []

        groups = {
            "most_fragile_modules": [],
            "most_repeated_co_failure_patterns": [],
            "rollback_linked_fragility_patterns": [],
            "unstable_dependency_neighborhoods": [],
            "high_churn_modules": []
        }
        for pat in fragility_patterns:
            pt = pat.pattern_type
            cat_key = None
            if pt == "UNSTABLE_MODULE":
                cat_key = "most_fragile_modules"
            elif pt == "CO_FAILURE_PATTERN":
                cat_key = "most_repeated_co_failure_patterns"
            elif pt == "ROLLBACK_INVOLVEMENT":
                cat_key = "rollback_linked_fragility_patterns"
            elif pt == "DEPENDENCY_PROXIMITY":
                cat_key = "unstable_dependency_neighborhoods"
            elif pt == "FILE_FAILURE_FREQUENCY":
                cat_key = "high_churn_modules"
            if cat_key:
                groups[cat_key].append(pat)

        fragility_summary = {
            "most_fragile_modules": [],
            "most_repeated_co_failure_patterns": [],
            "rollback_linked_fragility_patterns": [],
            "unstable_dependency_neighborhoods": [],
            "high_churn_modules": []
        }
        for cat_key, pat_list in groups.items():
            sorted_pats = sorted(pat_list, key=lambda x: x.fragility_score or 0.0, reverse=True)
            top_5 = sorted_pats[:5]
            for pat in top_5:
                fragility_summary[cat_key].append({
                    "pattern_id": str(pat.id),
                    "normalized_pattern_key": pat.normalized_pattern_key,
                    "title": pat.title or "",
                    "explanation": pat.explanation or "",
                    "fragility_score": round(pat.fragility_score or 0.0, 2),
                    "risk_level": pat.risk_level or "LOW"
                })

        # 7. Call Safety Analyzer
        safety_analysis = EscapedDefectSafetyAnalyzer.analyze_safety(
            total_outcomes=total_outcomes,
            escaped_defects_count=metrics["escaped_defect_linked_outcomes"],
            rollbacks_count=metrics["rollback_linked_outcomes"],
            is_incident_lineage_complete=is_incident_lineage_complete,
            recommendation_frequency=total_runs
        )

        # 8. Dynamic recommended Next Step selection
        if safety_analysis["safety_status"] == "ATTENTION":
            next_step = "Initiate escaped defect safety audit. Analyze the temporal correlation of production incidents with recommendation outcomes and update degradation policy parameters to widen ruleset coverage."
        elif profile.pilot_status == "ACTIVE" and adherence_rate >= 0.80 and safety_analysis["safety_status"] == "STABLE":
            next_step = "Transition to Commercial Production tier. Recommend expanding repository enrollment to remaining organization codebases under a fixed monthly or commercial model."
        elif profile.pilot_status == "ACTIVE" and adherence_rate < 0.65:
            next_step = f"Initiate ruleset review and alignment session. Developer manual overrides are currently at {round(metrics['override_frequency'] * 100, 1)}%. Tune the rulesets and filters to better match developer preferences."
        else:
            next_step = f"Maintain active pilot tracking. Continue monitoring developer adherence rates (currently {round(adherence_rate * 100, 1)}%) and safety telemetry indicators."

        # 9. Format Markdown Report
        md = f"""# Veriscope Operational Pilot Report
**Workspace**: {workspace_name}
**Pilot Name**: {profile.pilot_name}
**Pilot Window**: {start_date.date()} to {end_date.date()}
**Report Finalized At**: {datetime.utcnow().isoformat()}

---

## 1. Executive Summary
- **Pricing Tier**: {profile.pricing_model} (Monthly USD: {f"${profile.monthly_price_usd:.2f}" if profile.monthly_price_usd else "N/A"})
- **Enrollment Scope**: {len(repo_names)} repository/repositories active ({", ".join(repo_names) if repo_names else "None"})
- **Pilot Status**: {profile.pilot_status} (Repository Limit: {profile.repo_limit or "Unlimited"})

## 2. Regression Efficiency & Savings (ROI)
- **Average Full Suite Runtime**: {savings['average_full_suite_runtime']}
- **Average Veriscope Runtime**: {savings['average_veriscope_runtime']}
- **Net CI Execution Time Reduction**: {savings['estimated_runtime_reduction']}
- **Estimated Engineering Savings**: {savings['estimated_engineering_hours_saved_str']}
- **Lineage Exclusions**: {savings['excluded_runs_count']} runs excluded due to missing outcomes; {savings['missing_runtime_data_runs_count']} runs excluded due to missing baseline runtimes.

## 3. Fragility & Risk Intelligence
### Top Module Fragility
{cls._format_fragility_list(fragility_summary['most_fragile_modules'])}

### Common Co-Failure Risks
{cls._format_fragility_list(fragility_summary['most_repeated_co_failure_patterns'])}

### Rollback-Linked Patterns
{cls._format_fragility_list(fragility_summary['rollback_linked_fragility_patterns'])}

## 4. Trust Signals & Developer Adherence
- **Total Recommendation Runs**: {total_runs}
- **Outcomes Evaluated**: {total_outcomes}
- **Developer Adherence Rate**: {round(adherence_rate * 100, 1)}%
- **Wilson Score Trust Bounds (90% Confidence)**: [{round(lower_bound * 100, 1)}%, {round(upper_bound * 100, 1)}%]

## 5. Escaped Defect Safety Assessment
- **Safety Status**: {safety_analysis['safety_status']} (Incident Rate: {round(safety_analysis['escaped_defect_rate_percent'], 1)}%, Rollback Rate: {round(safety_analysis['rollback_rate_percent'], 1)}%)
- **Assessment**: {safety_analysis['safety_assessment']}
- **Warnings**: {safety_analysis['incomplete_lineage_warning'] or 'None'}

## 6. Recommended Next Steps
- {next_step}""".strip()

        # 10. Future PDF-ready structure with semantic print A4 template and styles
        pdf_ready = {
            "document_metadata": {
                "title": f"Veriscope Pilot Report - {workspace_name}",
                "dates": f"{start_date.date()} to {end_date.date()}",
                "logo_url": "veriscope_logo_black_and_white",
                "client": workspace_name,
                "generation_timestamp": datetime.utcnow().isoformat()
            },
            "css_styles": (
                "body { font-family: 'Inter', sans-serif; color: #1f2937; padding: 40px; margin: 0; box-sizing: border-box; }\n"
                ".page { width: 100%; max-width: 800px; height: 1040px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid #e5e7eb; padding: 30px; box-sizing: border-box; }\n"
                "h1 { font-size: 20px; font-weight: 700; margin: 0 0 10px 0; border-bottom: 2px solid #e5e7eb; padding-bottom: 5px; }\n"
                ".section { margin-bottom: 15px; page-break-inside: avoid; }\n"
                "h2 { font-size: 14px; font-weight: 600; text-transform: uppercase; margin: 0 0 5px 0; color: #4b5563; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; }\n"
                "ul { padding-left: 20px; margin: 0; font-size: 12px; line-height: 1.5; }\n"
                "li { margin-bottom: 3px; }\n"
                ".footer { font-size: 10px; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 5px; }\n"
                "@media print { body { padding: 0; } .page { border: none; height: auto; page-break-after: always; } }"
            ),
            "html_template": (
                f"<div class='page'>\n"
                f"  <div>\n"
                f"    <h1>Veriscope Operational Pilot Report</h1>\n"
                f"    <div style='font-size:11px; margin-bottom:15px; color:#4b5563;'>\n"
                f"      <strong>Workspace:</strong> {workspace_name} | <strong>Pilot Window:</strong> {start_date.date()} to {end_date.date()}\n"
                f"    </div>\n"
                f"    \n"
                f"    <div class='section'>\n"
                f"      <h2>1. Executive Summary</h2>\n"
                f"      <ul>\n"
                f"        <li><strong>Pricing Tier:</strong> {profile.pricing_model}</li>\n"
                f"        <li><strong>Scope:</strong> {len(repo_names)} Enrolled Repositories</li>\n"
                f"        <li><strong>Status:</strong> {profile.pilot_status}</li>\n"
                f"      </ul>\n"
                f"    </div>\n"
                f"    \n"
                f"    <div class='section'>\n"
                f"      <h2>2. Regression Efficiency & Savings</h2>\n"
                f"      <ul>\n"
                f"        <li><strong>Average Full Regression Duration:</strong> {savings['average_full_suite_runtime']}</li>\n"
                f"        <li><strong>Average Veriscope Duration:</strong> {savings['average_veriscope_runtime']}</li>\n"
                f"        <li><strong>Net Reduction:</strong> {savings['estimated_runtime_reduction']}</li>\n"
                f"        <li><strong>Engineering Hours Saved:</strong> {savings['estimated_engineering_hours_saved_str']}</li>\n"
                f"      </ul>\n"
                f"    </div>\n"
                f"    \n"
                f"    <div class='section'>\n"
                f"      <h2>3. Fragility & Risk Intelligence</h2>\n"
                f"      <ul>\n"
                f"        <li><strong>Fragile Modules:</strong> {len(fragility_summary['most_fragile_modules'])} module(s) isolated</li>\n"
                f"        <li><strong>Co-Failure Risks:</strong> {len(fragility_summary['most_repeated_co_failure_patterns'])} risk patterns flagged</li>\n"
                f"        <li><strong>Rollback Risks:</strong> {len(fragility_summary['rollback_linked_fragility_patterns'])} patterns linked</li>\n"
                f"      </ul>\n"
                f"    </div>\n"
                f"    \n"
                f"    <div class='section'>\n"
                f"      <h2>4. Trust & Developer Adherence</h2>\n"
                f"      <ul>\n"
                f"        <li><strong>Total Runs:</strong> {total_runs} | <strong>Followed:</strong> {followed_count}</li>\n"
                f"        <li><strong>Adherence Rate:</strong> {round(adherence_rate * 100, 1)}%</li>\n"
                f"        <li><strong>Wilson Bounds (90% Confidence):</strong> [{round(lower_bound * 100, 1)}%, {round(upper_bound * 100, 1)}%]</li>\n"
                f"      </ul>\n"
                f"    </div>\n"
                f"    \n"
                f"    <div class='section'>\n"
                f"      <h2>5. Escaped Defect Safety</h2>\n"
                f"      <ul>\n"
                f"        <li><strong>Safety Status:</strong> {safety_analysis['safety_status']}</li>\n"
                f"        <li><strong>Assessment:</strong> {safety_analysis['safety_assessment']}</li>\n"
                f"      </ul>\n"
                f"    </div>\n"
                f"    \n"
                f"    <div class='section'>\n"
                f"      <h2>6. Recommended Next Step</h2>\n"
                f"      <ul>\n"
                f"        <li>{next_step}</li>\n"
                f"      </ul>\n"
                f"    </div>\n"
                f"  </div>\n"
                f"  <div class='footer'>\n"
                f"    Veriscope Forensic Audit Pipeline | Deterministic Report | Page 1 of 1\n"
                f"  </div>\n"
                f"</div>"
            )
        }

        # Structured JSON payload
        json_payload = {
            "pilot_summary": {
                "workspace_name": workspace_name,
                "pilot_name": profile.pilot_name,
                "pricing_model": profile.pricing_model,
                "monthly_price_usd": profile.monthly_price_usd,
                "pilot_status": profile.pilot_status,
                "enrolled_repositories": repo_names,
                "repo_limit": profile.repo_limit,
                "total_prs_analyzed": metrics["total_prs_analyzed"]
            },
            "regression_efficiency": savings,
            "fragility_intelligence": fragility_summary,
            "recommendation_trust_signals": {
                "total_runs": total_runs,
                "total_outcomes": total_outcomes,
                "followed_runs": followed_count,
                "overridden_runs": overridden_count,
                "ignored_runs": ignored_count,
                "adherence_rate": round(adherence_rate, 4),
                "trust_lower_bound": round(lower_bound, 4),
                "trust_upper_bound": round(upper_bound, 4)
            },
            "escaped_defect_safety": safety_analysis,
            "recommended_next_step": next_step,
            "confidence_warning": metrics["confidence_warning"] or safety_analysis["confidence_warning"]
        }

        return {
            "json_payload": json_payload,
            "markdown_content": md,
            "pdf_ready_structure": pdf_ready
        }
