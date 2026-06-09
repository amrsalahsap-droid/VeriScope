import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun, RecommendedTest, RecommendationExplanation
from app.models.pull_request import PullRequest

from app.services.user_journey_impact_engine import UserJourneyImpactEngine
from app.services.evidence_gap_detector import EvidenceGapDetector
from app.services.missing_coverage_analyzer import MissingCoverageAnalyzer
from app.services.testing_scope_generator import TestingScopeGenerator
from app.services.recommendation_quality_evaluator import RecommendationQualityEvaluator

logger = logging.getLogger("veriscope.recommendation_report_generator")


class SimplePDFBuilder:
    """A lightweight, standard-compliant PDF binary stream builder written in pure Python."""

    def __init__(self):
        self.pages_content = []  # List of list of string commands

    def new_page(self) -> List[str]:
        page_stream = ["1 0 0 1 0 0 cm"]  # Reset coordinate transformation
        self.pages_content.append(page_stream)
        return page_stream

    def get_current_page(self) -> List[str]:
        if not self.pages_content:
            return self.new_page()
        return self.pages_content[-1]

    def draw_text(self, text: str, x: int, y: int, size: int = 10, bold: bool = False):
        page = self.get_current_page()
        font = "/F1" if bold else "/F2"
        # Escape special characters for PDF parentheses strings
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        page.append(f"BT\n{font} {size} Tf\n{x} {y} Td\n({escaped}) Tj\nET")

    def build(self) -> bytes:
        # Build catalog, pages, fonts, and page/content object list
        num_pages = len(self.pages_content)
        if num_pages == 0:
            self.new_page()
            num_pages = 1

        objects = []

        # Object Helper
        def add_obj(content: bytes) -> int:
            objects.append(content)
            return len(objects)

        # 1. Catalog (Obj 1)
        # 2. Pages node (Obj 2)
        # 3. Font F1 (Bold) (Obj 3)
        # 4. Font F2 (Regular) (Obj 4)
        # 5+2*i. Page object i (Obj 5 + 2*i)
        # 6+2*i. Content stream i (Obj 6 + 2*i)

        catalog_obj = b"<< /Type /Catalog /Pages 2 0 R >>"
        add_obj(catalog_obj)

        kids_refs = []
        for i in range(num_pages):
            kids_refs.append(f"{5 + 2 * i} 0 R")
        kids_str = " ".join(kids_refs)
        pages_obj = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>".encode("ascii")
        add_obj(pages_obj)

        font_bold = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"
        add_obj(font_bold)

        font_regular = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
        add_obj(font_regular)

        for i, page_stream in enumerate(self.pages_content):
            stream_content = "\n".join(page_stream).encode("utf-8")
            stream_obj = f"<< /Length {len(stream_content)} >>\nstream\n".encode("ascii") + stream_content + b"\nendstream"
            
            # Page object comes first (ID: 5 + 2*i), referencing content stream (ID: 6 + 2*i)
            page_obj = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {6 + 2 * i} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>".encode("utf-8")
            
            add_obj(page_obj)
            add_obj(stream_obj)

        # Compile PDF binary file and offsets
        offsets = []
        buf = b"%PDF-1.4\n"
        for idx, obj in enumerate(objects):
            offsets.append(len(buf))
            buf += f"{idx + 1} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

        xref_pos = len(buf)
        buf += b"xref\n"
        buf += f"0 {len(objects) + 1}\n".encode("ascii")
        buf += b"0000000000 65535 f \n"
        for offset in offsets:
            buf += f"{offset:010d} 00000 n \n".encode("ascii")

        buf += b"trailer\n"
        buf += f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
        buf += b"startxref\n"
        buf += f"{xref_pos}\n".encode("ascii")
        buf += b"%%EOF\n"

        return buf


class RecommendationReportGenerator:
    """Orchestrates structured regression scoping report generation and export formats."""

    @classmethod
    def generate_report(cls, db: Session, run_id: uuid.UUID) -> Dict[str, Any]:
        """Gathers, resolves, and maps all 9 distinct scoping sections to return the single source of truth report."""
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            raise ValueError(f"RecommendationRun with ID {run_id} not found.")

        pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
        pr_title = pr.title if pr else None

        # 1. What Changed & Executive Bullets
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

        # Changed files list recovery
        changed_files = []
        if run.input_snapshot and run.input_snapshot.changed_files:
            raw = run.input_snapshot.changed_files
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        changed_files.append(item)
                    elif isinstance(item, dict):
                        fp = item.get("file_path") or item.get("filename")
                        if fp:
                            changed_files.append(fp)
        if not changed_files and pr:
            changed_files = [f.file_path for f in (pr.changed_files or [])]

        # 2. Impacted Domains
        domains = impact.get("affected_domains") or []
        domains = [d.title() for d in domains] if domains else ["General"]

        # 3. Affected User Journeys
        affected_journeys = UserJourneyImpactEngine.detect_journeys(db, run, changed_files)

        # 4. Risk Areas
        risk_level = (run.risk_level or "MODERATE").upper()
        risk_categories = impact.get("risk_categories") or []
        risk_categories = [rc.title() for rc in risk_categories]

        # 5. Testing Scope
        testing_scope = TestingScopeGenerator.generate_scope(db, run, changed_files)

        # 6. Recommended Tests
        recommended_tests = (
            db.query(RecommendedTest)
            .filter(RecommendedTest.recommendation_run_id == run.id)
            .all()
        )
        must_run_tests = [t for t in recommended_tests if t.priority >= 0.80]
        should_run_tests = [t for t in recommended_tests if t.priority < 0.80]

        # 7. Missing Coverage
        missing_coverage = MissingCoverageAnalyzer.analyze_missing_coverage(db, run, changed_files)

        # 8. Evidence Gaps
        explanations = db.query(RecommendationExplanation).filter(
            RecommendationExplanation.recommendation_run_id == run.id
        ).all()
        evidence_gaps = EvidenceGapDetector.detect_gaps(db, run, explanations)

        # 9. Confidence Breakdown
        confidence_breakdown = RecommendationQualityEvaluator.evaluate_quality(recommended_tests)

        testing_types = impact.get("recommended_testing_types") or []
        testing_types = [tt.upper() for tt in testing_types] if testing_types else ["REGRESSION", "UNIT"]

        report_data = {
            "run_id": str(run.id),
            "change_summary": change_summary,
            "changed_files": changed_files,
            "affected_domains": sorted(domains),
            "affected_journeys": affected_journeys,
            "risk_level": risk_level,
            "risk_categories": sorted(risk_categories),
            "testing_scope": testing_scope,
            "recommended_testing_types": sorted(testing_types),
            "recommended_tests": {
                "must_run": [
                    {
                        "stable_identity": t.test_identifier,
                        "display_name": t.test_name,
                        "priority": t.priority,
                        "reason": t.reason,
                        "source_signal": t.source_signal
                    } for t in must_run_tests
                ],
                "should_run": [
                    {
                        "stable_identity": t.test_identifier,
                        "display_name": t.test_name,
                        "priority": t.priority,
                        "reason": t.reason,
                        "source_signal": t.source_signal
                    } for t in should_run_tests
                ],
                "total_count": len(recommended_tests)
            },
            "missing_coverage": missing_coverage,
            "evidence_gaps": evidence_gaps,
            "confidence_breakdown": confidence_breakdown,
            "created_at": run.created_at.isoformat() + "Z" if run.created_at else None,
        }
        return report_data

    @classmethod
    def render_as_ui(cls, report: Dict[str, Any]) -> Dict[str, Any]:
        """Returns structured JSON report format along with a highly polished, styled HTML fragment."""
        risk_color = (
            "#ef4444"
            if report["risk_level"] == "HIGH"
            else "#f59e0b"
            if report["risk_level"] == "MODERATE"
            else "#10b981"
        )
        
        # User journeys HTML list
        journeys_li = ""
        for j in report["affected_journeys"]:
            sev_color = "#ef4444" if j["severity"] == "HIGH" else "#f59e0b" if j["severity"] == "MODERATE" else "#10b981"
            journeys_li += (
                f"<li style='margin-bottom: 8px; line-height: 1.4;'>"
                f"<strong>{j['journey']}</strong> — <span style='font-size: 11px; font-weight:600; padding: 2px 6px; border-radius: 4px; color:#ffffff; background-color:{sev_color};'>{j['severity']}</span><br/>"
                f"<span style='font-size: 13px; color:#475569;'>{j['reason']}</span>"
                f"</li>"
            )

        # Missing coverage HTML list
        missing_li = ""
        for m in report["missing_coverage"]:
            missing_li += (
                f"<li style='margin-bottom: 8px; line-height: 1.4;'>"
                f"<strong>{m['domain']} ({m['feature']})</strong>: "
                f"<span style='font-size: 13px; color:#475569;'>{m['reason']}</span>"
                f"</li>"
            )
        if not missing_li:
            missing_li = "<li>No critical coverage gaps detected in modified directories.</li>"

        # Evidence gaps HTML list
        gaps_li = ""
        for g in report["evidence_gaps"]:
            gap_color = "#ef4444" if g["severity"] == "HIGH" else "#f59e0b" if g["severity"] == "WARNING" else "#3b82f6"
            gaps_li += (
                f"<li style='margin-bottom: 12px; line-height: 1.4;'>"
                f"<strong style='color:{gap_color};'>[{g['severity']}] {g['message']}</strong><br/>"
                f"<span style='font-size: 13px; color:#475569;'>{g['impact']}</span>"
                f"</li>"
            )
        if not gaps_li:
            gaps_li = "<li>All evidence lineages are healthy and intact.</li>"

        # Confidence Breakdown details
        cb = report["confidence_breakdown"]
        cb_html = (
            f"<div style='background-color:#f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px; font-size: 13.5px; color:#334155;'>"
            f"  <strong>Quality Score</strong>: <span style='font-size:16px; font-weight:700; color:#0f172a;'>{cb['score']}/100</span> "
            f"  (<span style='font-weight:600;'>{cb['tier']}</span>)<br/>"
            f"  <div style='margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size:12.5px;'>"
            f"    <div>Direct Coverage: {round(cb['breakdown']['coverage_contribution']*100, 1)}%</div>"
            f"    <div>Knowledge Graph: {round(cb['breakdown']['graph_contribution']*100, 1)}%</div>"
            f"    <div>Domain Rules: {round(cb['breakdown']['domain_contribution']*100, 1)}%</div>"
            f"    <div>Fallback Ratio: {round(cb['breakdown']['fallback_ratio']*100, 1)}%</div>"
            f"  </div>"
            f"</div>"
        )

        html = (
            f"<div class='veriscope-recommendation-report' style=\"font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 28px; border-radius: 16px; background: #ffffff; border: 1px solid #e2e8f0; color: #334155; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);\">\n"
            f"    <h2 style=\"margin-top: 0; color: #0f172a; font-size: 22px; font-weight: 800; border-bottom: 2px solid #f1f5f9; padding-bottom: 14px; margin-bottom: 24px;\">Regression Scoping Report</h2>\n"
            f"    \n"
            f"    <div style='margin-bottom: 20px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 6px 0; letter-spacing: 0.05em;'>What Changed</h4>\n"
            f"        <p style='margin: 0; font-size: 16px; color: #0f172a; font-weight: 600; line-height: 1.5;'>{report['change_summary']}</p>\n"
            f"        <p style='margin: 4px 0 0 0; font-size: 13.5px; color: #64748b;'>PR modified {len(report['changed_files'])} file(s)</p>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;'>\n"
            f"        <div>\n"
            f"            <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Impacted Domains</h4>\n"
            f"            <ul style='margin: 0; padding-left: 20px; font-size: 14.5px; color: #334155;'>\n"
            f"                " + "".join(f"<li style='margin-bottom:4px;'>{d}</li>" for d in report["affected_domains"]) + "\n"
            f"            </ul>\n"
            f"        </div>\n"
            f"        <div>\n"
            f"            <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Risk Areas</h4>\n"
            f"            <div style='font-size: 14.5px; color: #334155; margin-bottom:4px;'>\n"
            f"                Risk Level: <span style='font-weight: 700; color: {risk_color};'>{report['risk_level']}</span>\n"
            f"            </div>\n"
            f"            " + (f"<div style='font-size:13px; color:#475569;'>Categories: {', '.join(report['risk_categories'])}</div>" if report["risk_categories"] else "") + "\n"
            f"        </div>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='margin-bottom: 20px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Affected Journeys</h4>\n"
            f"        <ul style='margin: 0; padding-left: 20px; font-size: 14.5px; color: #334155;'>\n"
            f"            {journeys_li}\n"
            f"        </ul>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='margin-bottom: 20px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Testing Scope</h4>\n"
            f"        <div style='font-size: 13.5px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;'>\n"
            f"          <div>\n"
            f"            <strong style='color:#ef4444;'>Must Test:</strong>\n"
            f"            <ul style='padding-left:16px; margin: 4px 0 0 0;'>\n"
            f"              " + "".join(f"<li>{s['category']}: {s['item']}</li>" for s in report["testing_scope"]["must_test"]) + "\n"
            f"            </ul>\n"
            f"          </div>\n"
            f"          <div>\n"
            f"            <strong style='color:#f59e0b;'>Should Test:</strong>\n"
            f"            <ul style='padding-left:16px; margin: 4px 0 0 0;'>\n"
            f"              " + "".join(f"<li>{s['category']}: {s['item']}</li>" for s in report["testing_scope"]["should_test"]) + "\n"
            f"            </ul>\n"
            f"          </div>\n"
            f"          <div>\n"
            f"            <strong style='color:#64748b;'>Optional:</strong>\n"
            f"            <ul style='padding-left:16px; margin: 4px 0 0 0;'>\n"
            f"              " + "".join(f"<li>{s['category']}: {s['item']}</li>" for s in report["testing_scope"]["optional"]) + "\n"
            f"            </ul>\n"
            f"          </div>\n"
            f"        </div>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='margin-bottom: 20px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Recommended Tests ({report['recommended_tests']['total_count']})</h4>\n"
            f"        <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"            " + "".join(f"<li style='margin-bottom:6px;'><strong>{t['display_name']}</strong> <span style='font-size:11px; color:#475569;'>({t['source_signal']})</span> — <em>{t['reason']}</em></li>" for t in (report["recommended_tests"]["must_run"] + report["recommended_tests"]["should_run"])) + "\n"
            f"        </ul>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='margin-bottom: 20px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Missing Coverage Gaps</h4>\n"
            f"        <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"            {missing_li}\n"
            f"        </ul>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='margin-bottom: 20px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Evidence Gaps</h4>\n"
            f"        <ul style='margin: 0; padding-left: 20px; font-size: 14px; color: #334155;'>\n"
            f"            {gaps_li}\n"
            f"        </ul>\n"
            f"    </div>\n"
            f"    \n"
            f"    <div style='border-top: 1px solid #f1f5f9; padding-top: 16px;'>\n"
            f"        <h4 style='font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 8px 0; letter-spacing: 0.05em;'>Confidence Breakdown</h4>\n"
            f"        {cb_html}\n"
            f"    </div>\n"
            f"</div>"
        )

        return {
            "report": report,
            "html": html
        }

    @classmethod
    def render_as_github_comment(cls, report: Dict[str, Any]) -> str:
        """Renders report payload into premium GitHub Markdown comments."""
        # Affected journeys format
        journeys_str = "\n".join(
            f"- **{j['journey']}** (Severity: `{j['severity']}`): {j['reason']}"
            for j in report["affected_journeys"]
        )

        # Testing Scope format
        scope = report["testing_scope"]
        must_str = ", ".join(f"`{s['category']}: {s['item']}`" for s in scope["must_test"])
        should_str = ", ".join(f"`{s['category']}: {s['item']}`" for s in scope["should_test"])
        opt_str = ", ".join(f"`{s['category']}: {s['item']}`" for s in scope["optional"])

        # Recommended Tests format
        tests_lines = []
        all_recs = report["recommended_tests"]["must_run"] + report["recommended_tests"]["should_run"]
        if not all_recs:
            tests_lines.append("| No tests recommended. |")
        else:
            tests_lines.append("| Test Name | Priority | Source Signal | Reason |")
            tests_lines.append("|---|---|---|---|")
            for t in all_recs:
                tests_lines.append(f"| `{t['display_name']}` | {round(t['priority'], 2)} | `{t['source_signal']}` | {t['reason']} |")
        tests_table = "\n".join(tests_lines)

        # Missing coverage format
        missing_str = "\n".join(
            f"- **{m['domain']}** (Feature: `{m['feature']}`): {m['reason']}"
            for m in report["missing_coverage"]
        )
        if not missing_str:
            missing_str = "- No missing coverage detected."

        # Evidence gaps format
        gaps_str = "\n".join(
            f"- **[{g['severity']}] {g['message']}**\n  *Impact*: {g['impact']}"
            for g in report["evidence_gaps"]
        )
        if not gaps_str:
            gaps_str = "- All evidence linkages are active and healthy."

        # Confidence Breakdown format
        cb = report["confidence_breakdown"]
        cb_str = (
            f"- **Overall Quality Score**: `{cb['score']}/100` (Tier: **{cb['tier']}**)\n"
            f"- **Coverage Contribution**: {round(cb['breakdown']['coverage_contribution']*100, 1)}%\n"
            f"- **Knowledge Graph Contribution**: {round(cb['breakdown']['graph_contribution']*100, 1)}%\n"
            f"- **Domain Contribution**: {round(cb['breakdown']['domain_contribution']*100, 1)}%\n"
            f"- **Fallback Ratio**: {round(cb['breakdown']['fallback_ratio']*100, 1)}%"
        )

        md = (
            f"## 🔍 Veriscope Scoping Intelligence Report\n\n"
            f"### 📋 What Changed\n"
            f"**Change Summary**: {report['change_summary']}\n"
            f"- PR touched `{len(report['changed_files'])}` file(s) across: {', '.join(report['affected_domains'])}.\n\n"
            f"### 🏢 Impacted Domains\n"
            f"{chr(10).join(f'- {d}' for d in report['affected_domains'])}\n\n"
            f"### 🚀 Affected User Journeys\n"
            f"{journeys_str}\n\n"
            f"### ⚠️ Risk Areas\n"
            f"- **Risk Level**: `{report['risk_level']}`\n"
            f"- **Categories**: {', '.join(report['risk_categories']) if report['risk_categories'] else 'None'}\n\n"
            f"### 🎯 Testing Scope Recommendations\n"
            f"- **Must Test**: {must_str}\n"
            f"- **Should Test**: {should_str}\n"
            f"- **Optional**: {opt_str}\n\n"
            f"### 🧪 Recommended Tests ({report['recommended_tests']['total_count']})\n"
            f"{tests_table}\n\n"
            f"### 🛑 Potential Missing Coverage Gaps\n"
            f"{missing_str}\n\n"
            f"### 🧩 Evidence Integrity Gaps\n"
            f"{gaps_str}\n\n"
            f"### 📊 Confidence & Quality Breakdown\n"
            f"{cb_str}\n"
        )
        return md

    @classmethod
    def render_as_pdf(cls, report: Dict[str, Any]) -> bytes:
        """Compiles the report dynamically into a clean A4 PDF byte stream in pure Python."""
        builder = SimplePDFBuilder()
        
        # We start on page 1
        page = builder.new_page()
        y = 800

        # Title
        builder.draw_text("VERISCOPE SCOPING INTELLIGENCE REPORT", 50, y, size=14, bold=True)
        y -= 25

        # Subtitle
        builder.draw_text(f"Run ID: {report['run_id']} | Generated at: {datetime.utcnow().date().isoformat()}", 50, y, size=8, bold=False)
        y -= 25

        def check_y(needed: int) -> List[str]:
            nonlocal y
            if y - needed < 50:
                builder.new_page()
                y = 800
            return builder.get_current_page()

        def draw_section_header(title: str):
            nonlocal y
            check_y(30)
            builder.draw_text(title, 50, y, size=11, bold=True)
            y -= 15

        def wrap_text(text: str, max_chars: int = 85) -> List[str]:
            words = text.split(" ")
            lines = []
            curr = []
            curr_len = 0
            for w in words:
                if curr_len + len(w) + 1 > max_chars:
                    lines.append(" ".join(curr))
                    curr = [w]
                    curr_len = len(w)
                else:
                    curr.append(w)
                    curr_len += len(w) + 1
            if curr:
                lines.append(" ".join(curr))
            return lines

        # Section 1: What Changed
        draw_section_header("1. WHAT CHANGED")
        summary_lines = wrap_text(report["change_summary"], max_chars=85)
        for line in summary_lines:
            check_y(15)
            builder.draw_text(line, 60, y, size=9, bold=False)
            y -= 12
        y -= 5

        # Section 2: Impacted Domains
        draw_section_header("2. IMPACTED DOMAINS")
        for d in report["affected_domains"]:
            check_y(15)
            builder.draw_text(f"- {d}", 60, y, size=9, bold=False)
            y -= 12
        y -= 5

        # Section 3: Affected Journeys
        draw_section_header("3. AFFECTED USER JOURNEYS")
        for j in report["affected_journeys"]:
            check_y(30)
            builder.draw_text(f"- {j['journey']} ({j['severity']})", 60, y, size=9, bold=True)
            y -= 11
            j_lines = wrap_text(j["reason"], max_chars=80)
            for line in j_lines:
                check_y(15)
                builder.draw_text(line, 70, y, size=8.5, bold=False)
                y -= 10
            y -= 4
        y -= 5

        # Section 4: Risk Areas
        draw_section_header("4. RISK AREAS")
        check_y(15)
        builder.draw_text(f"- Risk Level: {report['risk_level']}", 60, y, size=9, bold=True)
        y -= 12
        if report["risk_categories"]:
            check_y(15)
            builder.draw_text(f"- Categories: {', '.join(report['risk_categories'])}", 60, y, size=9, bold=False)
            y -= 12
        y -= 5

        # Section 5: Testing Scope
        draw_section_header("5. TESTING SCOPE")
        scope = report["testing_scope"]
        check_y(15)
        builder.draw_text("Must Test:", 60, y, size=9, bold=True)
        y -= 11
        for item in scope["must_test"]:
            check_y(15)
            builder.draw_text(f"  * {item['category']}: {item['item']}", 65, y, size=8.5, bold=False)
            y -= 10
        y -= 4

        check_y(15)
        builder.draw_text("Should Test:", 60, y, size=9, bold=True)
        y -= 11
        for item in scope["should_test"]:
            check_y(15)
            builder.draw_text(f"  * {item['category']}: {item['item']}", 65, y, size=8.5, bold=False)
            y -= 10
        y -= 4

        # Section 6: Recommended Tests
        draw_section_header("6. RECOMMENDED TESTS")
        all_recs = report["recommended_tests"]["must_run"] + report["recommended_tests"]["should_run"]
        if not all_recs:
            check_y(15)
            builder.draw_text("- No tests recommended.", 60, y, size=9, bold=False)
            y -= 12
        else:
            for t in all_recs:
                check_y(25)
                builder.draw_text(f"* {t['display_name']} (Priority: {round(t['priority'], 2)})", 60, y, size=9, bold=True)
                y -= 10
                t_lines = wrap_text(f"Signal: {t['source_signal']} | Reason: {t['reason']}", max_chars=80)
                for line in t_lines:
                    check_y(15)
                    builder.draw_text(line, 70, y, size=8, bold=False)
                    y -= 9
                y -= 3
        y -= 5

        # Section 7: Missing Coverage
        draw_section_header("7. POTENTIAL MISSING COVERAGE")
        if not report["missing_coverage"]:
            check_y(15)
            builder.draw_text("- No missing coverage identified.", 60, y, size=9, bold=False)
            y -= 12
        else:
            for m in report["missing_coverage"]:
                check_y(25)
                builder.draw_text(f"* {m['domain']} - {m['feature']}", 60, y, size=9, bold=True)
                y -= 10
                m_lines = wrap_text(m["reason"], max_chars=80)
                for line in m_lines:
                    check_y(15)
                    builder.draw_text(line, 70, y, size=8, bold=False)
                    y -= 9
                y -= 3
        y -= 5

        # Section 8: Evidence Gaps
        draw_section_header("8. EVIDENCE INTEGRITY GAPS")
        if not report["evidence_gaps"]:
            check_y(15)
            builder.draw_text("- All evidence streams are active and healthy.", 60, y, size=9, bold=False)
            y -= 12
        else:
            for g in report["evidence_gaps"]:
                check_y(25)
                builder.draw_text(f"* [{g['severity']}] {g['message']}", 60, y, size=9, bold=True)
                y -= 10
                g_lines = wrap_text(f"Impact: {g['impact']}", max_chars=80)
                for line in g_lines:
                    check_y(15)
                    builder.draw_text(line, 70, y, size=8, bold=False)
                    y -= 9
                y -= 3
        y -= 5

        # Section 9: Confidence Breakdown
        draw_section_header("9. CONFIDENCE & QUALITY BREAKDOWN")
        cb = report["confidence_breakdown"]
        check_y(15)
        builder.draw_text(f"Overall Quality Score: {cb['score']}/100 (Tier: {cb['tier']})", 60, y, size=9, bold=True)
        y -= 12
        check_y(15)
        builder.draw_text(f"Coverage: {round(cb['breakdown']['coverage_contribution']*100, 1)}% | Graph: {round(cb['breakdown']['graph_contribution']*100, 1)}%", 60, y, size=8.5, bold=False)
        y -= 11
        check_y(15)
        builder.draw_text(f"Domain Match: {round(cb['breakdown']['domain_contribution']*100, 1)}% | Fallback Ratio: {round(cb['breakdown']['fallback_ratio']*100, 1)}%", 60, y, size=8.5, bold=False)
        y -= 11

        return builder.build()
