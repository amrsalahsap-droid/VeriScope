"""
app/services/intelligence_dashboard.py
=======================================
IntelligenceDashboardService
============================
Aggregates all eight Intelligence Dashboard widgets in a single service call,
composing from RecommendationAnalyticsService and direct model queries.
No new database tables are introduced — all data comes from existing models.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun
from app.models.repository import Repository
from app.services.analytics import RecommendationAnalyticsService

logger = logging.getLogger("veriscope.intelligence_dashboard")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RISK_ORDER: Dict[str, int] = {"HIGH": 3, "MODERATE": 2, "LOW": 1}


def max_risk(risk_a: str, risk_b: str) -> str:
    """Return the higher of two risk level strings (HIGH > MODERATE > LOW)."""
    if _RISK_ORDER.get(risk_a, 0) >= _RISK_ORDER.get(risk_b, 0):
        return risk_a
    return risk_b


def format_duration(total_seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Rules:
    - 0 or negative  → "0s"
    - hours > 0      → "{h}h {m}m"  (minutes omitted when 0: "{h}h")
    - only minutes   → "{m}m {s}s"  (seconds omitted when 0: "{m}m")
    - only seconds   → "{s}s"
    """
    if total_seconds <= 0:
        return "0s"

    total_int = int(total_seconds)
    hours = total_int // 3600
    minutes = (total_int % 3600) // 60
    seconds = total_int % 60

    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    if minutes > 0:
        if seconds > 0:
            return f"{minutes}m {seconds}s"
        return f"{minutes}m"
    return f"{seconds}s"


def _empty_dashboard(workspace_id: UUID, repository_id: Optional[UUID], lookback_days: int) -> Dict[str, Any]:
    """Return a fully-populated empty dashboard response (HTTP 200, all zeros/empty lists)."""
    return {
        "top_risk_domains": [],
        "most_fragile_modules": [],
        "most_valuable_tests": [],
        "most_added_tests": [],
        "recommendation_accuracy": {
            "score": 100,
            "score_raw": 1.0,
            "rationale": "No data yet",
            "total_recommendations": 0,
            "override_rate": 0.0,
        },
        "escaped_defects": {
            "rate": 0.0,
            "count": 0,
            "rollback_rate": 0.0,
            "rollback_count": 0,
            "total_outcomes": 0,
        },
        "runtime_saved": {
            "total_seconds": 0,
            "formatted": "0s",
            "run_count": 0,
        },
        "coverage_health": [
            {"quality": "HIGH", "count": 0, "percentage": 0.0},
            {"quality": "MODERATE", "count": 0, "percentage": 0.0},
            {"quality": "LOW", "count": 0, "percentage": 0.0},
            {"quality": "UNKNOWN", "count": 0, "percentage": 0.0},
        ],
        "repository_id": str(repository_id) if repository_id else None,
        "workspace_id": str(workspace_id),
        "lookback_days": lookback_days,
        "generated_at": datetime.utcnow().isoformat(),
        "total_runs_analyzed": 0,
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class IntelligenceDashboardService:
    """Aggregates all dashboard data in a single service call."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._analytics = RecommendationAnalyticsService(db)

    def aggregate_dashboard(
        self,
        workspace_id: UUID,
        repository_id: Optional[UUID] = None,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Return the full dashboard payload for a workspace (optionally filtered
        to a single repository). Aggregates across all workspace repos when
        repository_id is None.

        Returns HTTP 200 with empty/zero values when no data exists.
        Raises HTTP 403 when repository_id does not belong to workspace_id.
        """
        # ------------------------------------------------------------------
        # 1. Resolve repository scope
        # ------------------------------------------------------------------
        if repository_id is not None:
            repo = (
                self.db.query(Repository)
                .filter(Repository.id == repository_id)
                .first()
            )
            if repo is None or repo.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=403,
                    detail="Repository does not belong to this workspace.",
                )
            repo_ids: List[UUID] = [repository_id]
        else:
            repo_ids = [
                r.id
                for r in self.db.query(Repository.id)
                .filter(Repository.workspace_id == workspace_id)
                .all()
            ]

        if not repo_ids:
            return _empty_dashboard(workspace_id, repository_id, lookback_days)

        cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        # ------------------------------------------------------------------
        # 2. Fetch recent runs
        # ------------------------------------------------------------------
        runs: List[RecommendationRun] = (
            self.db.query(RecommendationRun)
            .filter(
                RecommendationRun.repository_id.in_(repo_ids),
                RecommendationRun.created_at >= cutoff,
            )
            .order_by(RecommendationRun.created_at.desc())
            .all()
        )

        if not runs:
            return _empty_dashboard(workspace_id, repository_id, lookback_days)

        # ------------------------------------------------------------------
        # 3. Delegate to analytics service (use first/provided repo for now)
        # ------------------------------------------------------------------
        primary_repo_id = repository_id if repository_id is not None else repo_ids[0]
        outcome_analytics = self._analytics.get_outcome_analytics(primary_repo_id)
        learning_diagnostics = self._analytics.get_learning_diagnostics(primary_repo_id)

        # ------------------------------------------------------------------
        # 4. Top Risk Domains — aggregate + rank atomically
        # ------------------------------------------------------------------
        domain_counts: Dict[str, int] = {}
        domain_risk: Dict[str, str] = {}

        for run in runs:
            impact = run.impact_profile or {}
            affected = impact.get("affected_domains") or []
            run_risk = (impact.get("risk_level") or "LOW").upper()
            for domain in affected:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                current_risk = domain_risk.get(domain, "LOW")
                domain_risk[domain] = max_risk(current_risk, run_risk)

        top_risk_domains = sorted(
            [
                {
                    "domain": d,
                    "risk_level": domain_risk[d],
                    "occurrence_count": domain_counts[d],
                }
                for d in domain_counts
            ],
            key=lambda x: (_RISK_ORDER.get(x["risk_level"], 0) * -1, -x["occurrence_count"]),
        )[:5]

        # ------------------------------------------------------------------
        # 5. Most Fragile Modules
        # ------------------------------------------------------------------
        by_taxonomy: Dict[str, Any] = (
            learning_diagnostics.get("failure_signals", {}).get("by_taxonomy", {})
        )
        conservative_recs: List[Dict[str, Any]] = learning_diagnostics.get(
            "conservative_learning_recommendations", []
        )
        rec_map: Dict[str, str] = {
            item["test_case_id"]: item["reason"] for item in conservative_recs
        }

        fragile_modules = []
        for taxonomy, stats in by_taxonomy.items():
            count = stats.get("count", 0)
            if count == 0:
                continue
            escaped = stats.get("escaped_defects", 0)
            rollbacks = stats.get("rollbacks", 0)
            raw_score = (escaped + rollbacks) / count
            fragility_score = max(0.0, min(1.0, raw_score))
            fragile_modules.append(
                {
                    "file_path": taxonomy,
                    "fragility_score": fragility_score,
                    "failure_count": escaped + rollbacks,
                    "recommendation": rec_map.get(
                        taxonomy, "Monitor for recurring failures"
                    ),
                }
            )

        fragile_modules.sort(key=lambda x: x["fragility_score"], reverse=True)
        most_fragile_modules = fragile_modules[:5]

        # ------------------------------------------------------------------
        # 6. Most Valuable Tests (priority_score >= 0.80, deduplicate by max)
        # ------------------------------------------------------------------
        test_scores: Dict[str, float] = {}
        test_run_counts: Dict[str, int] = {}

        for run in runs:
            for test in run.tests:
                if test.priority_score >= 0.80:
                    prev = test_scores.get(test.test_case_id, 0.0)
                    test_scores[test.test_case_id] = max(prev, test.priority_score)
                    test_run_counts[test.test_case_id] = (
                        test_run_counts.get(test.test_case_id, 0) + 1
                    )

        most_valuable_tests = sorted(
            [
                {
                    "stable_identity": tid,
                    "display_name": tid.split("::")[-1] if "::" in tid else tid,
                    "priority_score": score,
                    "run_count": test_run_counts[tid],
                }
                for tid, score in test_scores.items()
            ],
            key=lambda x: x["priority_score"],
            reverse=True,
        )[:10]

        # ------------------------------------------------------------------
        # 7. Most Added Tests (from learning diagnostics)
        # ------------------------------------------------------------------
        raw_added: List[Dict[str, Any]] = (
            learning_diagnostics.get("override_insights", {})
            .get("top_manually_added_tests", [])
        )
        most_added_tests = [
            {
                "test_case_id": item["test_case_id"],
                "manual_addition_count": item["count"],
                "display_name": (
                    item["test_case_id"].split("::")[-1]
                    if "::" in item["test_case_id"]
                    else item["test_case_id"]
                ),
            }
            for item in raw_added[:10]
        ]

        # ------------------------------------------------------------------
        # 8. Recommendation Accuracy
        # ------------------------------------------------------------------
        total_recommendations = outcome_analytics.get("total_recommendations", 0)
        if total_recommendations == 0:
            recommendation_accuracy = {
                "score": 100,
                "score_raw": 1.0,
                "rationale": "No data yet",
                "total_recommendations": 0,
                "override_rate": 0.0,
            }
        else:
            raw_score = outcome_analytics.get("trust_calibration_score", 1.0)
            recommendation_accuracy = {
                "score": round(raw_score * 100, 1),
                "score_raw": raw_score,
                "rationale": outcome_analytics.get("calibration_rationale", ""),
                "total_recommendations": total_recommendations,
                "override_rate": outcome_analytics.get("override_rate", 0.0),
            }

        # ------------------------------------------------------------------
        # 9. Escaped Defects
        # ------------------------------------------------------------------
        if total_recommendations == 0:
            escaped_defects = {
                "rate": 0.0,
                "count": 0,
                "rollback_rate": 0.0,
                "rollback_count": 0,
                "total_outcomes": 0,
            }
        else:
            escaped_rate = outcome_analytics.get("escaped_defect_rate", 0.0)
            rollback_rate = outcome_analytics.get("rollback_rate", 0.0)
            escaped_defects = {
                "rate": escaped_rate,
                "count": round(escaped_rate * total_recommendations),
                "rollback_rate": rollback_rate,
                "rollback_count": round(rollback_rate * total_recommendations),
                "total_outcomes": total_recommendations,
            }

        # ------------------------------------------------------------------
        # 10. Runtime Saved
        # ------------------------------------------------------------------
        total_seconds = sum(
            run.estimated_runtime_seconds
            for run in runs
            if run.estimated_runtime_seconds is not None
            and run.estimated_runtime_seconds > 0
        )
        runtime_saved = {
            "total_seconds": total_seconds,
            "formatted": format_duration(total_seconds),
            "run_count": len(runs),
        }

        # ------------------------------------------------------------------
        # 11. Coverage Health
        # ------------------------------------------------------------------
        quality_counts: Dict[str, int] = {
            "HIGH": 0,
            "MODERATE": 0,
            "LOW": 0,
            "UNKNOWN": 0,
        }
        for run in runs:
            q = (run.evidence_quality or "UNKNOWN").upper()
            if q not in quality_counts:
                q = "UNKNOWN"
            quality_counts[q] += 1

        total_runs = len(runs)
        coverage_health = [
            {
                "quality": q,
                "count": c,
                "percentage": round(c / max(total_runs, 1) * 100, 1),
            }
            for q, c in quality_counts.items()
        ]

        # ------------------------------------------------------------------
        # Return assembled response
        # ------------------------------------------------------------------
        return {
            "top_risk_domains": top_risk_domains,
            "most_fragile_modules": most_fragile_modules,
            "most_valuable_tests": most_valuable_tests,
            "most_added_tests": most_added_tests,
            "recommendation_accuracy": recommendation_accuracy,
            "escaped_defects": escaped_defects,
            "runtime_saved": runtime_saved,
            "coverage_health": coverage_health,
            "repository_id": str(repository_id) if repository_id else None,
            "workspace_id": str(workspace_id),
            "lookback_days": lookback_days,
            "generated_at": datetime.utcnow().isoformat(),
            "total_runs_analyzed": total_runs,
        }
