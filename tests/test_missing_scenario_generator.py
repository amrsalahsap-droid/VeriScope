import uuid
from typing import Any
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

# SQLite compilation helper for PostgreSQL JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

from app.db.base import Base
from app.models.test_result import TestCase
from app.services.missing_scenario_generator import MissingScenarioGenerator
from app.services.domain_sme_analyzer import DomainSMEAnalyzer

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)

@pytest.fixture()
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()

def test_missing_scenario_generator_with_sme_snapshot(db):
    """Verify that MissingScenarioGenerator consumes ProjectUnderstandingSnapshot and produces high-fidelity suggested scenarios."""
    repository_id = uuid.uuid4()
    
    # 1. Seed actual test case to verify related_existing_tests logic (no invented tests)
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repository_id,
        suite_name="tests.security",
        test_name="test_reset_password_strength",
        stable_identity="tests.security::test_reset_password_strength",
        canonical_identity_hash="hash_tc_sme_sec",
        identity_lineage_root_hash="hash_tc_sme_sec"
    )
    db.add(tc)
    db.commit()

    # 2. Mock ProjectUnderstandingSnapshot and DomainVocabulary
    snapshot = {
        "affected_journeys": [
            {"journey": "Password Recovery Flow", "confidence": "HIGH", "source_files": ["src/app/reset-password/page.tsx"]}
        ],
        "affected_domains": ["password reset"],
        "touched_layers": ["UI Layer", "API Layer"],
        "missing_scenarios": []
    }
    
    domain_vocab = {
        "test_term_map": {
            "password reset": ["tests.security::test_reset_password_strength"]
        }
    }

    potential_missing = [
        {
            "domain": "Authentication",
            "feature": "Password Reset",
            "reason": "Exact automated coverage is missing or weak for changed password reset files."
        }
    ]

    changed_files = ["src/app/reset-password/page.tsx"]

    # Generate Scenarios
    scenarios = MissingScenarioGenerator.generate_missing_scenarios(
        potential_missing_coverage=potential_missing,
        recommended_scope={},
        impacted_areas=["Authentication"],
        project_understanding_snapshot=snapshot,
        domain_vocab=domain_vocab,
        changed_files=changed_files,
        db=db,
        repository_id=repository_id
    )

    assert len(scenarios) == 1
    s = scenarios[0]

    # Verify all rich SME snapshot fields exist and are populated
    assert s["title"] == "Validate password reset expired token rejection"
    assert s["affected_journey"] == "Password Recovery Flow"
    assert s["impacted_layer"] == "API"
    assert s["risk_category"] == "Security"
    assert s["suggested_automation_layer"] == "API / Security"
    
    # Verify exact preconditions, steps, expected result
    assert "registered user exists" in s["preconditions"]
    assert "password reset token is expired" in s["preconditions"]
    assert len(s["steps"]) == 3
    assert s["expected_result"] == "API rejects token and password remains unchanged."

    # Verify concrete test data
    assert s["test_data"]["expired_token"] == "expired-reset-token-999"
    assert s["test_data"]["valid_new_password"] == "StrongPass123!"

    # Verify related files & actual non-invented existing tests
    assert s["related_changed_files"] == changed_files
    assert s["related_existing_tests"] == ["tests.security::test_reset_password_strength"]

def test_missing_scenario_generator_fallback_without_snapshot(db):
    """Verify that MissingScenarioGenerator falls back gracefully to high-fidelity predefined mappings when snapshot is absent."""
    repository_id = uuid.uuid4()
    
    potential_missing = [
        {
            "domain": "Authentication",
            "feature": "Signup",
            "reason": "Exact automated coverage is missing or weak for changed signup files."
        }
    ]

    scenarios = MissingScenarioGenerator.generate_missing_scenarios(
        potential_missing_coverage=potential_missing,
        recommended_scope={},
        impacted_areas=["Authentication"],
        project_understanding_snapshot=None,
        domain_vocab=None,
        changed_files=["src/app/signup/sign-up-form.tsx"],
        db=db,
        repository_id=repository_id
    )

    assert len(scenarios) == 1
    s = scenarios[0]

    # Verify fallbacks are still fully populated with high-fidelity template values
    assert s["title"] == "Validate user signup flow password complexity rules"
    assert s["affected_journey"] == "User Registration Flow"
    assert s["impacted_layer"] == "UI"
    assert s["risk_category"] == "Security"
    assert s["suggested_automation_layer"] == "Security / UI"
    assert s["test_data"]["weak_password"] == "123456"
    
    # No tests exist in DB or vocab, so related_existing_tests must be empty (NO invented tests)
    assert s["related_existing_tests"] == []
