"""
Tests for RiskIntelligenceEngine.

Covers:
- Risk level thresholds (LOW / MODERATE / HIGH / CRITICAL)
- Risk area collection
- Risk reason generation (max 4, priority-ordered, factual)
- Persistence via assess()
- assess_without_persist() returns correct dict
- Edge cases: empty ImpactProfile, TEST_CHANGE only
"""
import uuid
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# SQLite compat shims
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
import app.models  # noqa — ensures all models are registered on Base
from app.services.risk_intelligence_engine import RiskIntelligenceEngine
from app.models.risk_assessment import RiskAssessment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _profile(**overrides):
    """Build a minimal ImpactProfile dict, merging any overrides."""
    base = {
        "affected_domains": [],
        "affected_features": [],
        "change_types": [],
        "risk_categories": [],
        "recommended_testing_types": ["REGRESSION"],
        "impact_summary": "test",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Risk level threshold tests
# ---------------------------------------------------------------------------

class TestRiskLevel:
    def test_empty_profile_is_low(self):
        result = RiskIntelligenceEngine.assess_without_persist(_profile())
        assert result["risk_level"] == "LOW"

    def test_test_change_only_is_low(self):
        """TEST_CHANGE has weight=0, should not escalate risk."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(change_types=["TEST_CHANGE"])
        )
        assert result["risk_level"] == "LOW"

    def test_single_ui_change_is_low(self):
        """UI_CHANGE weight=1 → score=1 → LOW (threshold 0-2)."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(change_types=["UI_CHANGE"])
        )
        assert result["risk_level"] == "LOW"

    def test_two_medium_changes_is_moderate(self):
        """API_CHANGE(2) + VALIDATION_CHANGE(1) = 3 → MODERATE."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(change_types=["API_CHANGE", "VALIDATION_CHANGE"])
        )
        assert result["risk_level"] == "MODERATE"

    def test_auth_change_with_auth_category_is_high(self):
        """AUTH_CHANGE(3) + AUTH category(3) = 6 → HIGH."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE"],
                risk_categories=["AUTH"],
            )
        )
        assert result["risk_level"] == "HIGH"

    def test_full_password_pr_is_critical(self):
        """
        AUTH_CHANGE(3) + VALIDATION_CHANGE(1) + AUTH(3) + SECURITY(3) = 10 → CRITICAL.
        This mirrors the example from the spec: 'Password validation change'.
        """
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE", "VALIDATION_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "USER_REGISTRATION"],
                affected_features=["password", "reset-password"],
            )
        )
        assert result["risk_level"] == "CRITICAL"

    def test_payments_change_is_high(self):
        """API_CHANGE(2) + PAYMENTS(3) = 5 → MODERATE — PAYMENTS alone + API is 5."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["API_CHANGE"],
                risk_categories=["PAYMENTS"],
            )
        )
        # 2 + 3 = 5 → MODERATE
        assert result["risk_level"] == "MODERATE"

    def test_payments_plus_db_change_is_high(self):
        """API_CHANGE(2) + DATABASE_CHANGE(2) + PAYMENTS(3) = 7 → HIGH."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["API_CHANGE", "DATABASE_CHANGE"],
                risk_categories=["PAYMENTS"],
            )
        )
        assert result["risk_level"] == "HIGH"


# ---------------------------------------------------------------------------
# Risk area tests
# ---------------------------------------------------------------------------

class TestRiskAreas:
    def test_auth_areas_present(self):
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE"],
                risk_categories=["AUTH", "SECURITY"],
            )
        )
        areas = result["risk_areas"]
        assert "Authentication" in areas
        assert "Security" in areas

    def test_no_duplicate_areas(self):
        """AUTH_CHANGE adds Authentication/Security; AUTH category also adds Authentication — no dups."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE"],
                risk_categories=["AUTH", "SECURITY"],
            )
        )
        areas = result["risk_areas"]
        assert len(areas) == len(set(areas)), "Duplicate area found"

    def test_payments_area(self):
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(risk_categories=["PAYMENTS"])
        )
        assert "Billing / Payments" in result["risk_areas"]

    def test_user_registration_area(self):
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(risk_categories=["USER_REGISTRATION"])
        )
        assert "User Registration" in result["risk_areas"]

    def test_empty_profile_has_no_areas(self):
        result = RiskIntelligenceEngine.assess_without_persist(_profile())
        assert result["risk_areas"] == []


# ---------------------------------------------------------------------------
# Risk reason tests
# ---------------------------------------------------------------------------

class TestRiskReasons:
    def test_password_pr_reasons_match_spec(self):
        """
        Spec example: Password validation change
        The four highest-weight reasons should cover auth, security, and
        user registration.  VALIDATION_CHANGE (weight=1) is outweighed by
        AUTH(3)+SECURITY(3)+AUTH_CHANGE(3)+USER_REGISTRATION(2) which
        already fills the 4-slot cap.
        """
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE", "VALIDATION_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "USER_REGISTRATION"],
                affected_features=["password"],
            )
        )
        reasons = result["risk_reasons"]
        reason_text = " ".join(reasons).lower()
        # Auth and Security are the primary signals — must appear
        assert "authentication" in reason_text
        assert "security" in reason_text
        # At most 4 reasons
        assert len(reasons) <= 4

    def test_reasons_capped_at_four(self):
        """No matter how many signals, max 4 reasons."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE", "API_CHANGE", "DATABASE_CHANGE", "VALIDATION_CHANGE", "CONFIG_CHANGE"],
                risk_categories=["AUTH", "SECURITY", "PAYMENTS", "DATA_INTEGRITY", "PERMISSIONS", "USER_REGISTRATION"],
                affected_features=["password", "signup"],
            )
        )
        assert len(result["risk_reasons"]) <= 4

    def test_no_duplicate_reasons(self):
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE", "API_CHANGE"],
                risk_categories=["AUTH", "SECURITY"],
            )
        )
        reasons = result["risk_reasons"]
        assert len(reasons) == len(set(reasons)), "Duplicate reasons found"

    def test_high_weight_reasons_appear_first(self):
        """AUTH(3) and SECURITY(3) reasons should appear before CONFIG reason."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["CONFIG_CHANGE"],
                risk_categories=["AUTH", "SECURITY"],
            )
        )
        reasons = result["risk_reasons"]
        # AUTH/SECURITY reasons should be in the first 2 slots
        top_two = " ".join(reasons[:2]).lower()
        assert "authentication" in top_two or "security" in top_two

    def test_empty_profile_has_no_reasons(self):
        result = RiskIntelligenceEngine.assess_without_persist(_profile())
        assert result["risk_reasons"] == []

    def test_test_change_only_has_no_reasons(self):
        """TEST_CHANGE weight=0 produces no reasons (not a product risk signal)."""
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(change_types=["TEST_CHANGE"])
        )
        assert result["risk_reasons"] == []

    def test_password_feature_appends_credential_reason(self):
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE"],
                affected_features=["password"],
            )
        )
        combined = " ".join(result["risk_reasons"]).lower()
        assert "credential" in combined

    def test_signup_feature_appends_registration_reason(self):
        result = RiskIntelligenceEngine.assess_without_persist(
            _profile(
                change_types=["AUTH_CHANGE"],
                affected_features=["signup"],
            )
        )
        combined = " ".join(result["risk_reasons"]).lower()
        assert "registration" in combined


# ---------------------------------------------------------------------------
# Persistence test
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_assess_persists_to_db(self, db_session):
        repo_id = uuid.uuid4()
        pr_id = uuid.uuid4()
        profile = _profile(
            change_types=["AUTH_CHANGE", "VALIDATION_CHANGE"],
            risk_categories=["AUTH", "SECURITY"],
            affected_features=["password"],
        )

        assessment = RiskIntelligenceEngine.assess(
            db=db_session,
            impact_profile=profile,
            repository_id=repo_id,
            pull_request_id=pr_id,
        )

        assert assessment.id is not None
        assert assessment.risk_level in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert isinstance(assessment.risk_areas, list)
        assert isinstance(assessment.risk_reasons, list)
        assert len(assessment.risk_reasons) <= 4
        assert assessment.engine_version == "v1"

        # Verify it's actually in the DB
        fetched = db_session.query(RiskAssessment).filter_by(id=assessment.id).first()
        assert fetched is not None
        assert fetched.risk_level == assessment.risk_level

    def test_assess_without_pull_request_id(self, db_session):
        repo_id = uuid.uuid4()
        profile = _profile(change_types=["CONFIG_CHANGE"])

        assessment = RiskIntelligenceEngine.assess(
            db=db_session,
            impact_profile=profile,
            repository_id=repo_id,
            pull_request_id=None,
        )

        assert assessment.pull_request_id is None
        assert assessment.risk_level == "LOW"

    def test_impact_profile_stored_verbatim(self, db_session):
        repo_id = uuid.uuid4()
        profile = _profile(
            change_types=["DATABASE_CHANGE"],
            risk_categories=["DATA_INTEGRITY"],
            affected_domains=["billing"],
        )

        assessment = RiskIntelligenceEngine.assess(
            db=db_session,
            impact_profile=profile,
            repository_id=repo_id,
        )

        fetched = db_session.query(RiskAssessment).filter_by(id=assessment.id).first()
        # impact_profile is stored as-is for replay/audit purposes
        stored = fetched.impact_profile
        assert stored["change_types"] == ["DATABASE_CHANGE"]
        assert stored["risk_categories"] == ["DATA_INTEGRITY"]
