"""
RiskIntelligenceEngine
======================
Converts an ImpactProfile (produced by PRImpactAnalyzer) into a
deterministic, evidence-backed RiskAssessment.

Design principles
-----------------
- Zero speculative logic.  Every risk area and reason must trace directly
  to a change_type or risk_category present in the ImpactProfile.
- No fake percentages.  Risk level is an ordinal (LOW / MODERATE / HIGH /
  CRITICAL) derived from counted, weighted evidence signals.
- No alarmist language.  Reasons describe *what changed*, not worst-case
  outcomes.
- Deterministic.  Same ImpactProfile always produces the same assessment.

Risk Level Escalation Rules
----------------------------
Weight table (additive):
    AUTH_CHANGE               +3
    API_CHANGE                +2
    DATABASE_CHANGE           +2
    DEPENDENCY_CHANGE         +2
    VALIDATION_CHANGE         +1
    CONFIG_CHANGE             +1
    WORKFLOW_CHANGE           +1
    UI_CHANGE                 +1
    TEST_CHANGE               +0   (structural, not product risk)

    risk_category AUTH        +3
    risk_category SECURITY    +3
    risk_category PAYMENTS    +3
    risk_category DATA_INTEGRITY +2
    risk_category PERMISSIONS  +2
    risk_category USER_REGISTRATION +2
    risk_category NOTIFICATIONS +1
    risk_category WORKFLOW    +1

Thresholds:
    0–2   → LOW
    3–5   → MODERATE
    6–9   → HIGH
   10+    → CRITICAL
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.risk_assessment import RiskAssessment


# ---------------------------------------------------------------------------
# Internal scoring tables
# ---------------------------------------------------------------------------

_CHANGE_TYPE_WEIGHTS: Dict[str, int] = {
    "AUTH_CHANGE": 3,
    "API_CHANGE": 2,
    "DATABASE_CHANGE": 2,
    "DEPENDENCY_CHANGE": 2,
    "VALIDATION_CHANGE": 1,
    "CONFIG_CHANGE": 1,
    "WORKFLOW_CHANGE": 1,
    "UI_CHANGE": 1,
    "TEST_CHANGE": 0,
}

_RISK_CATEGORY_WEIGHTS: Dict[str, int] = {
    "AUTH": 3,
    "SECURITY": 3,
    "PAYMENTS": 3,
    "DATA_INTEGRITY": 2,
    "PERMISSIONS": 2,
    "USER_REGISTRATION": 2,
    "NOTIFICATIONS": 1,
    "WORKFLOW": 1,
}

# Maps a risk_category to a clear, factual reason sentence.
_RISK_CATEGORY_REASONS: Dict[str, str] = {
    "AUTH": "Authentication workflow modified",
    "SECURITY": "Security-sensitive code path changed",
    "PAYMENTS": "Payment or billing flow affected",
    "DATA_INTEGRITY": "Database write path or schema touched",
    "PERMISSIONS": "Access-control or permission logic changed",
    "USER_REGISTRATION": "User registration or onboarding path affected",
    "NOTIFICATIONS": "Notification or email delivery path touched",
    "WORKFLOW": "CI/CD or workflow pipeline configuration changed",
}

# Maps a change_type to a clear, factual reason sentence.
_CHANGE_TYPE_REASONS: Dict[str, str] = {
    "AUTH_CHANGE": "Authentication or session management logic changed",
    "API_CHANGE": "Public API surface modified",
    "DATABASE_CHANGE": "Database schema or model changed",
    "DEPENDENCY_CHANGE": "Third-party dependency updated",
    "VALIDATION_CHANGE": "Input validation or schema rules modified",
    "CONFIG_CHANGE": "Application configuration modified",
    "WORKFLOW_CHANGE": "CI/CD workflow definition changed",
    "UI_CHANGE": "Frontend or UI component modified",
    "TEST_CHANGE": "Test files modified",
}

# Maps change_types / risk_categories to canonical risk areas.
_CHANGE_TYPE_AREAS: Dict[str, List[str]] = {
    "AUTH_CHANGE": ["Authentication", "Security"],
    "API_CHANGE": ["API Layer"],
    "DATABASE_CHANGE": ["Data Layer", "Data Integrity"],
    "DEPENDENCY_CHANGE": ["Dependencies"],
    "VALIDATION_CHANGE": ["Validation", "Data Integrity"],
    "CONFIG_CHANGE": ["Configuration"],
    "WORKFLOW_CHANGE": ["CI/CD"],
    "UI_CHANGE": ["Frontend"],
    "TEST_CHANGE": ["Test Coverage"],
}

_RISK_CATEGORY_AREAS: Dict[str, str] = {
    "AUTH": "Authentication",
    "SECURITY": "Security",
    "PAYMENTS": "Billing / Payments",
    "DATA_INTEGRITY": "Data Integrity",
    "PERMISSIONS": "Permissions",
    "USER_REGISTRATION": "User Registration",
    "NOTIFICATIONS": "Notifications",
    "WORKFLOW": "Workflow",
}

_THRESHOLDS: List[Tuple[int, str]] = [
    (10, "CRITICAL"),
    (6, "HIGH"),
    (3, "MODERATE"),
    (0, "LOW"),
]


class RiskIntelligenceEngine:
    """
    Converts an ImpactProfile dict into a RiskAssessment and persists it.

    Usage
    -----
    ::

        impact_profile = PRImpactAnalyzer.analyze_pr_impact(...)
        assessment = RiskIntelligenceEngine.assess(
            db=db,
            impact_profile=impact_profile,
            repository_id=repo_id,
            pull_request_id=pr_id,   # optional
        )
        print(assessment.risk_level)   # "HIGH"
        print(assessment.risk_areas)   # ["Authentication", "Security", ...]
        print(assessment.risk_reasons) # ["Authentication workflow modified", ...]
    """

    ENGINE_VERSION = "v1"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def assess(
        cls,
        db: Session,
        impact_profile: Dict[str, Any],
        repository_id: uuid.UUID,
        pull_request_id: Optional[uuid.UUID] = None,
    ) -> RiskAssessment:
        """
        Generate and persist a RiskAssessment for the given ImpactProfile.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.
        impact_profile:
            Output dict from PRImpactAnalyzer.analyze_pr_impact().
        repository_id:
            UUID of the repository this PR belongs to.
        pull_request_id:
            Optional UUID of the PullRequest row. May be None when called
            outside a full recommendation run.

        Returns
        -------
        RiskAssessment
            The persisted SQLAlchemy model instance.
        """
        change_types = set(impact_profile.get("change_types", []))
        risk_categories = set(impact_profile.get("risk_categories", []))

        risk_level, score = cls._compute_risk_level(change_types, risk_categories)
        risk_areas = cls._collect_risk_areas(change_types, risk_categories)
        risk_reasons = cls._collect_risk_reasons(
            change_types, risk_categories, impact_profile
        )

        assessment = RiskAssessment(
            id=uuid.uuid4(),
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            impact_profile=impact_profile,
            risk_level=risk_level,
            risk_areas=risk_areas,
            risk_reasons=risk_reasons,
            engine_version=cls.ENGINE_VERSION,
            created_at=datetime.utcnow(),
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @classmethod
    def assess_without_persist(
        cls,
        impact_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute a RiskAssessment without touching the database.

        Useful for unit testing or embedding inside a larger transaction.

        Returns a plain dict with: risk_level, risk_areas, risk_reasons.
        """
        change_types = set(impact_profile.get("change_types", []))
        risk_categories = set(impact_profile.get("risk_categories", []))

        risk_level, _ = cls._compute_risk_level(change_types, risk_categories)
        risk_areas = cls._collect_risk_areas(change_types, risk_categories)
        risk_reasons = cls._collect_risk_reasons(
            change_types, risk_categories, impact_profile
        )

        return {
            "risk_level": risk_level,
            "risk_areas": risk_areas,
            "risk_reasons": risk_reasons,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _compute_risk_level(
        cls,
        change_types: set,
        risk_categories: set,
    ) -> Tuple[str, int]:
        """Sum weighted signals and map to a risk level."""
        score = 0

        for ct in change_types:
            score += _CHANGE_TYPE_WEIGHTS.get(ct, 0)

        for rc in risk_categories:
            score += _RISK_CATEGORY_WEIGHTS.get(rc, 0)

        for threshold, level in _THRESHOLDS:
            if score >= threshold:
                return level, score

        return "LOW", score

    @classmethod
    def _collect_risk_areas(
        cls,
        change_types: set,
        risk_categories: set,
    ) -> List[str]:
        """
        Collect deduplicated, ordered risk area labels.

        Priority: risk_category areas first (higher severity), then
        change_type areas.
        """
        seen: set = set()
        areas: List[str] = []

        # Risk-category areas first (higher signal weight)
        for rc in sorted(risk_categories):
            label = _RISK_CATEGORY_AREAS.get(rc)
            if label and label not in seen:
                areas.append(label)
                seen.add(label)

        # Change-type areas next
        for ct in sorted(change_types):
            for label in _CHANGE_TYPE_AREAS.get(ct, []):
                if label not in seen:
                    areas.append(label)
                    seen.add(label)

        return areas

    @classmethod
    def _collect_risk_reasons(
        cls,
        change_types: set,
        risk_categories: set,
        impact_profile: Dict[str, Any],
    ) -> List[str]:
        """
        Produce up to 4 concise, factual reason sentences.

        Priority ordering:
        1. High-weight risk categories (AUTH, SECURITY, PAYMENTS)
        2. Medium-weight risk categories (DATA_INTEGRITY, PERMISSIONS, USER_REGISTRATION)
        3. Low-weight risk categories (NOTIFICATIONS, WORKFLOW)
        4. High-weight change types
        5. Medium-weight change types
        6. Low-weight change types

        Each reason is a single sentence drawn from the static tables above —
        no AI wording, no confidence theater, no fake certainty.
        """
        # Build priority-ordered candidate reasons
        candidates: List[Tuple[int, str]] = []

        for rc in risk_categories:
            weight = _RISK_CATEGORY_WEIGHTS.get(rc, 0)
            reason = _RISK_CATEGORY_REASONS.get(rc)
            if reason:
                candidates.append((weight, reason))

        for ct in change_types:
            weight = _CHANGE_TYPE_WEIGHTS.get(ct, 0)
            reason = _CHANGE_TYPE_REASONS.get(ct)
            if reason and weight > 0:
                candidates.append((weight, reason))

        # Deduplicate, preserve stable order by (-weight, text)
        seen: set = set()
        ordered: List[str] = []
        for _, reason in sorted(candidates, key=lambda x: (-x[0], x[1])):
            if reason not in seen:
                ordered.append(reason)
                seen.add(reason)

        # Additional contextual reasons from the impact_profile
        if impact_profile.get("affected_features"):
            features = impact_profile["affected_features"]
            if "password" in features or "reset-password" in features:
                msg = "User-facing credential flow affected"
                if msg not in seen:
                    ordered.append(msg)
                    seen.add(msg)
            if "signup" in features or "sign-up" in features:
                msg = "New user registration path affected"
                if msg not in seen:
                    ordered.append(msg)
                    seen.add(msg)

        # Cap at 4 — engineers read all of them; beyond 4 is noise.
        return ordered[:4]
