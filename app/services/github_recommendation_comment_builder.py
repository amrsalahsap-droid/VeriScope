import math
from typing import Dict, Any, Optional

class GitHubRecommendationCommentBuilder:
    """Builds highly structured, concise, and actionable GitHub PR comments based on recommendation reports."""

    @staticmethod
    def calculate_wilson_interval(successes: int, total: int, confidence_level: float = 0.95) -> tuple:
        """Calculate the Wilson Score Interval bounds for a given success count and total trials."""
        if total <= 0:
            return 0.0, 0.0

        p_hat = successes / total
        
        # Determine z-score based on confidence level
        if confidence_level == 0.95:
            z = 1.95996
        else:
            z = 1.64485  # default/fallback to 90%

        z2 = z ** 2
        denominator = 1 + z2 / total
        center = (p_hat + z2 / (2 * total)) / denominator
        spread = z * math.sqrt((p_hat * (1 - p_hat) / total) + z2 / (4 * total ** 2)) / denominator

        lower_bound = max(0.0, center - spread)
        upper_bound = min(1.0, center + spread)

        return lower_bound, upper_bound

    @classmethod
    def build_comment(cls, report: Dict[str, Any], run: Optional[Any] = None) -> str:
        """Constructs a clean, actionable, and structured GitHub PR comment with 6 required sections."""
        # 1. Extract and Format Summary Section
        change_summary = report.get("change_summary", "Optimized regression scoping recommendation.")
        if not change_summary.endswith("."):
            change_summary += "."

        changed_files_count = len(report.get("changed_files", []))
        affected_domains = report.get("affected_domains", [])
        affected_domains_count = len(affected_domains)
        affected_domains_str = ", ".join(f"`{d}`" for d in affected_domains) if affected_domains else "None"

        # Runtimes retrieval with fallback
        if run:
            estimated_runtime = run.estimated_runtime_seconds
            full_suite_runtime = run.full_suite_runtime_seconds or (estimated_runtime * 10)
        else:
            estimated_runtime = 0.0
            full_suite_runtime = 0.0

        summary_section = (
            f"### 📋 Summary\n"
            f"- **Change Summary**: {change_summary}\n"
            f"- **Scope**: touched `{changed_files_count}` file(s) across `{affected_domains_count}` domain(s) ({affected_domains_str}).\n"
            f"- **Estimated Runtime**: `{estimated_runtime:.1f}s` (Full suite: `{full_suite_runtime:.1f}s`).\n"
        )

        # 2. Extract and Format Risk Section
        risk_level = report.get("risk_level", "MODERATE").upper()
        risk_badge = "🔴" if risk_level == "HIGH" else "🟡" if risk_level == "MODERATE" else "🟢"
        risk_categories = report.get("risk_categories", [])
        risk_categories_str = ", ".join(f"`{rc}`" for rc in risk_categories) if risk_categories else "None"

        risk_section = (
            f"### ⚠️ Risk\n"
            f"- **Risk Level**: {risk_badge} **{risk_level}**.\n"
            f"- **Risk Categories**: {risk_categories_str}.\n"
        )

        # 3. Extract and Format Testing Scope Section
        scope = report.get("testing_scope", {})
        must_list = scope.get("must_test", [])
        should_list = scope.get("should_test", [])
        optional_list = scope.get("optional", [])

        must_str = ", ".join(f"`{item['category']}: {item['item']}`" for item in must_list) if must_list else "None"
        should_str = ", ".join(f"`{item['category']}: {item['item']}`" for item in should_list) if should_list else "None"
        optional_str = ", ".join(f"`{item['category']}: {item['item']}`" for item in optional_list) if optional_list else "None"

        if not must_str.endswith("."):
            must_str += "."
        if not should_str.endswith("."):
            should_str += "."
        if not optional_str.endswith("."):
            optional_str += "."

        testing_scope_section = (
            f"### 🎯 Testing Scope\n"
            f"- **Must Test**: {must_str}\n"
            f"- **Should Test**: {should_str}\n"
            f"- **Optional**: {optional_str}\n"
        )

        # 4. Extract and Format Recommended Tests Section
        rec_tests_data = report.get("recommended_tests", {})
        must_run = rec_tests_data.get("must_run", [])
        should_run = rec_tests_data.get("should_run", [])
        all_recs = must_run + should_run
        total_count = rec_tests_data.get("total_count", len(all_recs))

        tests_lines = []
        if not all_recs:
            tests_lines.append("No tests recommended.")
        else:
            tests_lines.append("| Test Name | Priority | Source Signal | Reason |")
            tests_lines.append("|---|---|---|---|")
            for t in all_recs:
                reason = t.get("reason", "").strip()
                if reason and not reason.endswith("."):
                    reason += "."
                tests_lines.append(
                    f"| `{t.get('display_name') or t.get('stable_identity')}` | "
                    f"{round(t.get('priority', 0.0), 2)} | "
                    f"`{t.get('source_signal', 'UNKNOWN')}` | "
                    f"{reason} |"
                )

        tests_table = "\n".join(tests_lines)
        recommended_tests_section = (
            f"### 🧪 Recommended Tests ({total_count})\n"
            f"{tests_table}\n"
        )

        # 5. Extract and Format Missing Coverage Section
        missing_coverage = report.get("missing_coverage", [])
        if not missing_coverage:
            missing_coverage_str = "- No critical coverage gaps detected in modified directories.\n"
        else:
            missing_lines = []
            for m in missing_coverage:
                reason = m.get("reason", "").strip()
                if reason and not reason.endswith("."):
                    reason += "."
                missing_lines.append(
                    f"- **{m.get('domain')}** (Feature: `{m.get('feature')}`): {reason}"
                )
            missing_coverage_str = "\n".join(missing_lines) + "\n"

        missing_coverage_section = (
            f"### 🛑 Missing Coverage\n"
            f"{missing_coverage_str}"
        )

        # 6. Extract and Format Evidence Quality Section
        cb = report.get("confidence_breakdown", {})
        score = cb.get("score", 0)
        tier = cb.get("tier", "POOR")
        breakdown = cb.get("breakdown", {})

        coverage_contrib = breakdown.get("coverage_contribution", 0.0)
        graph_contrib = breakdown.get("graph_contribution", 0.0)
        domain_contrib = breakdown.get("domain_contribution", 0.0)
        fallback_ratio = breakdown.get("fallback_ratio", 0.0)
        completeness = breakdown.get("evidence_completeness", 0.0)

        # Wilson interval estimation for evidence completeness
        successes = int(round(completeness * total_count)) if total_count > 0 else 0
        lower, upper = cls.calculate_wilson_interval(successes, total_count, confidence_level=0.95)

        # Retrieve evidence quality string from run
        evidence_quality = run.evidence_quality if run else "UNKNOWN"

        evidence_quality_section = (
            f"### 📊 Evidence Quality\n"
            f"- **Overall Quality Score**: `{score}/100` (Tier: **{tier}**).\n"
            f"- **Coverage Confidence**: `{evidence_quality}`.\n"
            f"- **Evidence Breakdown**:\n"
            f"  - Direct Coverage Contribution: `{coverage_contrib * 100:.1f}%`.\n"
            f"  - Knowledge Graph Contribution: `{graph_contrib * 100:.1f}%`.\n"
            f"  - Domain Matching: `{domain_contrib * 100:.1f}%`.\n"
            f"  - Fallback Ratio (History): `{fallback_ratio * 100:.1f}%`.\n"
            f"  - Evidence Completeness: `{completeness * 100:.1f}%`.\n"
            f"- **Statistical Trust Bounds (95% Wilson Score)**: [`{lower * 100:.1f}%`, `{upper * 100:.1f}%`].\n"
        )

        # Construct ultimate markdown body
        comment_body = (
            f"## 🔍 Veriscope Scoping Intelligence Report\n\n"
            f"{summary_section}\n"
            f"{risk_section}\n"
            f"{testing_scope_section}\n"
            f"{recommended_tests_section}\n"
            f"{missing_coverage_section}\n"
            f"{evidence_quality_section}\n"
            f"---\n"
            f"<!-- veriscope-pr-comment -->"
        )

        return comment_body
