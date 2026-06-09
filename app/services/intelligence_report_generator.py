"""
app/services/intelligence_report_generator.py
=============================================
IntelligenceReportGenerator
===========================
Generates structured regression scoping intelligence reports serving as the
single source of truth for the recommendation page, GitHub PR comment, and
pilot customer report.
"""

import logging
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun, RecommendedTest
from app.models.pull_request import PullRequest

logger = logging.getLogger("veriscope.intelligence_report_generator")


class IntelligenceReportGenerator:
    """Service to generate unified Regression Scoping Intelligence Reports."""

    @classmethod
    def generate_report(cls, db: Session, run_id: UUID) -> Dict[str, Any]:
        """Gathers, maps, and structures recommendation run details into a report.

        Parameters
        ----------
        db: Session
            SQLAlchemy database session.
        run_id: UUID
            Unique identifier of the recommendation run.

        Returns
        -------
        Dict[str, Any]
            Structured single source of truth report dictionary.
        """
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            raise ValueError(f"RecommendationRun with ID {run_id} not found.")

        # 1. Fetch Pull Request title and repository information
        pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
        pr_title = pr.title if pr else None

        # 2. Extract Change Summary
        impact = run.impact_profile or {}
        impact_summary = impact.get("impact_summary")
        
        if pr_title and impact_summary:
            change_summary = f"{pr_title} — {impact_summary}"
        elif pr_title:
            change_summary = pr_title
        elif impact_summary:
            change_summary = impact_summary
        else:
            change_summary = run.recommendation_reasoning_summary or "Optimized regression scoping for this pull request."

        # 3. Affected Domains
        domains = impact.get("affected_domains") or []
        if not domains:
            # Fall back to capitalized domains mapped from reasoning summary if any
            domains = ["General"]
        else:
            domains = [d.title() for d in domains]

        # 4. Risk Areas
        risk_level = (run.risk_level or "MODERATE").title()
        risk_categories = impact.get("risk_categories") or []
        risk_categories = [rc.title() for rc in risk_categories]

        # 5. Recommended Testing Types
        testing_types = impact.get("recommended_testing_types") or []
        if not testing_types:
            # Fall back to base types from run mode
            testing_types = ["REGRESSION", "UNIT"]
        else:
            testing_types = [tt.upper() for tt in testing_types]

        # 6. Recommended Tests
        recommended_tests = (
            db.query(RecommendedTest)
            .filter(RecommendedTest.recommendation_run_id == run.id)
            .all()
        )

        must_run_tests = [t for t in recommended_tests if t.priority >= 0.80]
        should_run_tests = [t for t in recommended_tests if t.priority < 0.80]

        # 7. Evidence Sources
        evidence_mapping = {
            "DIRECT_COVERAGE": "Coverage",
            "TEST_COVERAGE_GRAPH": "Knowledge Graph",
            "HISTORICAL_FAILURE": "Historical Failures",
            "ARCHITECTURAL_IMPACT": "Architectural Impact",
            "DOMAIN_MATCH": "Domain Map",
            "MODULE_RISK": "Module Risk Profile",
            "MANUAL_OVERRIDE": "Manual Override History",
            "ESCAPED_DEFECT": "Escaped Defect Learning",
        }

        unique_signals = set()
        for t in recommended_tests:
            if t.source_signal:
                unique_signals.add(t.source_signal)

        evidence_sources = sorted(
            list(set(evidence_mapping.get(s, "Fallback Policy") for s in unique_signals))
        )
        if not evidence_sources:
            evidence_sources = ["Fallback Policy"]

        # 8. Confidence Explanation
        quality = (run.evidence_quality or "UNKNOWN").upper()
        if quality == "HIGH":
            confidence_explanation = "High confidence is assigned based on complete code coverage mapping and consistent historical test data."
        elif quality == "MODERATE":
            confidence_explanation = "Moderate confidence is assigned due to partial coverage information or widening rules."
        else:
            confidence_explanation = "Low confidence is assigned as targeted coverage evidence is sparse, triggering safety fallbacks."

        # Compile structured data
        report_data = {
            "run_id": str(run.id),
            "change_summary": change_summary,
            "affected_domains": sorted(domains),
            "risk_level": risk_level,
            "risk_categories": sorted(risk_categories),
            "recommended_testing_types": sorted(testing_types),
            "must_run_count": len(must_run_tests),
            "should_run_count": len(should_run_tests),
            "evidence_sources": evidence_sources,
            "confidence_explanation": confidence_explanation,
        }

        return report_data

    @classmethod
    def render_as_markdown(cls, report: Dict[str, Any]) -> str:
        """Renders the intelligence report into a premium, clean Markdown format."""
        domains_list = "\n".join(f"- {d}" for d in report["affected_domains"])
        testing_types_list = "\n".join(f"- {tt}" for tt in report["recommended_testing_types"])
        evidence_list = "\n".join(f"- {e}" for e in report["evidence_sources"])

        risk_cats = (
            f" ({', '.join(report['risk_categories'])})"
            if report["risk_categories"]
            else ""
        )

        md = (
            f"# Veriscope Scoping Intelligence Report\n\n"
            f"### Change Summary\n"
            f"{report['change_summary']}\n\n"
            f"### Affected Domains\n"
            f"{domains_list}\n\n"
            f"### Risk Areas\n"
            f"- **Risk Level**: {report['risk_level']}{risk_cats}\n\n"
            f"### Recommended Testing Types\n"
            f"{testing_types_list}\n\n"
            f"### Recommended Tests\n"
            f"- **Must Run**: {report['must_run_count']} test{'s' if report['must_run_count'] != 1 else ''}\n"
            f"- **Should Run**: {report['should_run_count']} test{'s' if report['should_run_count'] != 1 else ''}\n\n"
            f"### Evidence Sources\n"
            f"{evidence_list}\n\n"
            f"### Confidence Explanation\n"
            f"{report['confidence_explanation']}\n"
        )
        return md

    @classmethod
    def render_as_html(cls, report: Dict[str, Any]) -> str:
        """Renders the report into a highly polished, clean HTML container fragment."""
        domains_li = "".join(
            f"<li style='margin-bottom: 4px;'>{d}</li>" for d in report["affected_domains"]
        )
        testing_li = "".join(
            f"<li style='margin-bottom: 4px;'>{tt}</li>"
            for tt in report["recommended_testing_types"]
        )
        evidence_li = "".join(
            f"<li style='margin-bottom: 4px;'>{e}</li>" for e in report["evidence_sources"]
        )

        risk_color = (
            "#ef4444"
            if report["risk_level"].upper() == "HIGH"
            else "#f59e0b"
            if report["risk_level"].upper() == "MODERATE"
            else "#10b981"
        )
        risk_cats_str = (
            f" ({', '.join(report['risk_categories'])})"
            if report["risk_categories"]
            else ""
        )

        html = (
            f"<div class='veriscope-intelligence-report' style=\"font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; border-radius: 12px; background: #ffffff; border: 1px solid #e2e8f0; color: #334155; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);\">\n"
            f"    <h2 style=\"margin-top: 0; color: #0f172a; font-size: 20px; font-weight: 700; border-bottom: 2px solid #f1f5f9; padding-bottom: 12px; margin-bottom: 20px;\">Veriscope Scoping Intelligence Report</h2>\n"
            f"    \n"
            f"    <div style='margin-bottom: 18px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Change Summary</h4>\n"
            f"        <p style='margin: 0; font-size: 15px; color: #0f172a; line-height: 1.5;'>{report['change_summary']}</p>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 18px;'>\n"
            f"        <div>\n"
            f"            <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Affected Domains</h4>\n"
            f"            <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"                {domains_li}\n"
            f"            </ul>\n"
            f"        </div>\n"
            f"        <div>\n"
            f"            <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Risk Areas</h4>\n"
            f"            <div style='font-size: 14px; color: #334155;'>\n"
            f"                Risk Level: <span style='font-weight: 600; color: {risk_color};'>{report['risk_level']}</span>{risk_cats_str}\n"
            f"            </div>\n"
            f"        </div>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 18px;'>\n"
            f"        <div>\n"
            f"            <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Recommended Testing</h4>\n"
            f"            <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"                {testing_li}\n"
            f"            </ul>\n"
            f"        </div>\n"
            f"        <div>\n"
            f"            <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Recommended Tests</h4>\n"
            f"            <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"                <li>Must Run: <strong>{report['must_run_count']}</strong></li>\n"
            f"                <li>Should Run: <strong>{report['should_run_count']}</strong></li>\n"
            f"            </ul>\n"
            f"        </div>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='margin-bottom: 18px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Evidence Sources</h4>\n"
            f"        <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"            {evidence_li}\n"
            f"        </ul>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='border-top: 1px solid #f1f5f9; padding-top: 12px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>Confidence Explanation</h4>\n"
            f"        <p style='margin: 0; font-size: 13.5px; color: #475569; font-style: italic; line-height: 1.4;'>{report['confidence_explanation']}</p>\n"
            f"    </div>\n"
            f"</div>"
        )
        return html
