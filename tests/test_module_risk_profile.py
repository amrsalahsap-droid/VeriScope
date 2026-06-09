"""
tests/test_module_risk_profile.py
==================================

Comprehensive unit and integration tests for ModuleRiskProfile tracking,
scoring, and prioritization.
"""

import uuid
from datetime import datetime
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.module_risk_profile import ModuleRiskProfile
from app.models.coverage import FileTestLink
from app.models.test_coverage_link import TestCoverageLink
from app.models.test_result import TestCase
from app.repositories.module_risk_profile import ModuleRiskProfileRepository
from app.services.module_risk_scoring_engine import (
    ModuleRiskScoringEngine,
    ModuleRiskInputs,
)
from app.services.recommendation_ranking_service import (
    RecommendationRankingService,
    RankingCandidateInput,
)


# --------------------------------------------------------------------------- #
#  SQLite DDL                                                                 #
# --------------------------------------------------------------------------- #

_CREATE_MRP_SQL = """
CREATE TABLE IF NOT EXISTS module_risk_profiles (
    id                         TEXT    NOT NULL PRIMARY KEY,
    repository_id              TEXT    NOT NULL,
    module_path                TEXT    NOT NULL,
    change_frequency           INTEGER NOT NULL DEFAULT 0,
    failure_frequency          INTEGER NOT NULL DEFAULT 0,
    escaped_defects            INTEGER NOT NULL DEFAULT 0,
    rollback_count             INTEGER NOT NULL DEFAULT 0,
    recommendations_presented  INTEGER NOT NULL DEFAULT 0,
    recommendations_accepted   INTEGER NOT NULL DEFAULT 0,
    risk_score                 REAL    NOT NULL DEFAULT 0.0,
    score_components           TEXT    NOT NULL DEFAULT '{}',
    scoring_formula_version    TEXT    NOT NULL DEFAULT 'module_risk.v1',
    last_scored_at             TEXT,
    created_at                 TEXT    NOT NULL,
    updated_at                 TEXT    NOT NULL,
    UNIQUE (repository_id, module_path)
);
"""

_CREATE_TCL_SQL = """
CREATE TABLE IF NOT EXISTS test_coverage_links (
    id             TEXT    NOT NULL PRIMARY KEY,
    workspace_id   TEXT    NOT NULL,
    repository_id  TEXT    NOT NULL,
    test_identifier TEXT   NOT NULL,
    file_path      TEXT    NOT NULL,
    link_strength  REAL,
    confidence     REAL,
    source         TEXT,
    run_count      INTEGER NOT NULL DEFAULT 0,
    success_count  INTEGER NOT NULL DEFAULT 0,
    failure_count  INTEGER NOT NULL DEFAULT 0,
    override_count INTEGER NOT NULL DEFAULT 0,
    defect_count   INTEGER NOT NULL DEFAULT 0,
    first_seen_at  TEXT,
    last_seen_at   TEXT,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    UNIQUE (repository_id, test_identifier, file_path)
);
"""

_CREATE_FTL_SQL = """
CREATE TABLE IF NOT EXISTS file_test_links (
    id                 TEXT    NOT NULL PRIMARY KEY,
    coverage_report_id TEXT    NOT NULL,
    file_path          TEXT    NOT NULL,
    test_case_id       TEXT    NOT NULL,
    mapping_type       TEXT    NOT NULL,
    confidence_score   TEXT    NOT NULL,
    created_at         TEXT    NOT NULL,
    UNIQUE (coverage_report_id, file_path, test_case_id)
);
"""

_CREATE_TC_SQL = """
CREATE TABLE IF NOT EXISTS test_cases (
    id                             TEXT    NOT NULL PRIMARY KEY,
    repository_id                  TEXT    NOT NULL,
    suite_name                     TEXT    NOT NULL,
    test_name                      TEXT    NOT NULL,
    stable_identity                TEXT    NOT NULL,
    raw_test_name                  TEXT    NOT NULL,
    normalized_test_name           TEXT    NOT NULL,
    normalized_identity_strategy   TEXT    NOT NULL,
    framework_name                 TEXT    NOT NULL,
    framework_version              TEXT    NOT NULL,
    identity_normalization_version TEXT    NOT NULL,
    canonical_identity_hash        TEXT    NOT NULL,
    previous_identity_hash         TEXT,
    identity_lineage_root_hash     TEXT    NOT NULL,
    identity_version               INTEGER NOT NULL,
    identity_resolution_strategy   TEXT    NOT NULL,
    created_at                     TEXT    NOT NULL
);
"""

_CREATE_TR_SQL = """
CREATE TABLE IF NOT EXISTS test_results (
    id             TEXT    NOT NULL PRIMARY KEY,
    test_run_id    TEXT    NOT NULL,
    test_case_id   TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    duration       REAL    NOT NULL,
    failure_message TEXT,
    stack_trace    TEXT,
    stack_trace_redaction_status TEXT,
    encryption_status TEXT,
    created_at     TEXT    NOT NULL
);
"""

_DROP_MRP_SQL = "DROP TABLE IF EXISTS module_risk_profiles;"
_DROP_TCL_SQL = "DROP TABLE IF EXISTS test_coverage_links;"
_DROP_FTL_SQL = "DROP TABLE IF EXISTS file_test_links;"
_DROP_TC_SQL = "DROP TABLE IF EXISTS test_cases;"
_DROP_TR_SQL = "DROP TABLE IF EXISTS test_results;"


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with eng.connect() as conn:
        conn.execute(text(_CREATE_MRP_SQL))
        conn.execute(text(_CREATE_TCL_SQL))
        conn.execute(text(_CREATE_FTL_SQL))
        conn.execute(text(_CREATE_TC_SQL))
        conn.execute(text(_CREATE_TR_SQL))
        conn.commit()
    yield eng
    with eng.connect() as conn:
        conn.execute(text(_DROP_MRP_SQL))
        conn.execute(text(_DROP_TCL_SQL))
        conn.execute(text(_DROP_FTL_SQL))
        conn.execute(text(_DROP_TC_SQL))
        conn.execute(text(_DROP_TR_SQL))
        conn.commit()



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


@pytest.fixture()
def repo(db):
    return ModuleRiskProfileRepository(db)


# --------------------------------------------------------------------------- #
#  Tests                                                                       #
# --------------------------------------------------------------------------- #

class TestModuleRiskProfileUnit:
    """Pure unit tests for scoring calculations."""

    def test_pure_scoring_calculation(self):
        inputs = ModuleRiskInputs(
            change_frequency=10,
            failure_frequency=5,
            escaped_defects=2,
            rollback_count=1,
            recommendations_presented=8,
            recommendations_accepted=5,
        )
        result = ModuleRiskScoringEngine.calculate_from_inputs(inputs)

        # Rationale/Weights check:
        # W_ESCAPED_DEFECT = 10 * 2 = 20
        # W_ROLLBACK       = 8  * 1 = 8
        # W_FAILURE_FREQ   = 3  * 5 = 15
        # W_CHANGE_FREQ    = 1  * 10 = 10
        # low_accuracy_penalty = Presented - Accepted = 8 - 5 = 3
        # W_LOW_ACCURACY   = 2  * 3 = 6
        # Expected total risk_score = 20 + 8 + 15 + 10 + 6 = 59.0
        assert result.risk_score == 59.0
        assert result.escaped_defect_contrib == 20.0
        assert result.rollback_contrib == 8.0
        assert result.failure_freq_contrib == 15.0
        assert result.change_freq_contrib == 10.0
        assert result.low_accuracy_penalty == 3
        assert result.low_accuracy_contrib == 6.0


class TestModuleRiskProfileRepositoryIntegration:
    """Integration tests verifying repository behavior in database."""

    def test_get_or_create_and_increments(self, db, repo):
        repository_id = uuid.uuid4()
        module_path = "src/auth/login.py"

        # Record a change
        profile = repo.record_change(repository_id, module_path)
        db.commit()

        assert profile.module_path == "src/auth/login.py"
        assert profile.change_frequency == 1
        assert profile.risk_score == 1.0  # W_CHANGE_FREQ = 1 * 1

        # Record a failure
        profile = repo.record_failure(repository_id, module_path)
        db.commit()

        assert profile.failure_frequency == 1
        # risk_score: 1.0 (change) + 3.0 (failure) = 4.0
        assert profile.risk_score == 4.0

        # Record escaped defect
        profile = repo.record_escaped_defect(repository_id, module_path)
        db.commit()

        assert profile.escaped_defects == 1
        # risk_score: 4.0 + 10.0 = 14.0
        assert profile.risk_score == 14.0

        # Record rollback
        profile = repo.record_rollback(repository_id, module_path)
        db.commit()

        assert profile.rollback_count == 1
        # risk_score: 14.0 + 8.0 = 22.0
        assert profile.risk_score == 22.0

        # Record recommendation outcome (presented but ignored)
        profile = repo.record_recommendation_outcome(repository_id, module_path, was_accepted=False)
        db.commit()

        assert profile.recommendations_presented == 1
        assert profile.recommendations_accepted == 0
        # risk_score: 22.0 + 2.0 (low accuracy penalty) = 24.0
        assert profile.risk_score == 24.0


class TestRecommendationRankingFragilityPrioritization:
    """Verification of historically fragile modules prioritization in recommendation ranking."""

    def test_ranking_prioritizes_fragile_modules(self, db):
        repository_id = uuid.uuid4()
        tc_id_1 = uuid.uuid4()
        tc_id_2 = uuid.uuid4()

        # Seed TestCases
        tc1 = TestCase(
            id=tc_id_1,
            repository_id=repository_id,
            suite_name="suite_a",
            test_name="test_a",
            stable_identity="suite_a::test_a",
            raw_test_name="test_a",
            normalized_test_name="test_a",
            normalized_identity_strategy="EXACT",
            framework_name="pytest",
            framework_version="1.0",
            identity_normalization_version="1.0",
            canonical_identity_hash="hash1",
            identity_lineage_root_hash="hash1",
            identity_version=1,
            identity_resolution_strategy="EXACT",
            created_at=datetime.utcnow()
        )
        tc2 = TestCase(
            id=tc_id_2,
            repository_id=repository_id,
            suite_name="suite_b",
            test_name="test_b",
            stable_identity="suite_b::test_b",
            raw_test_name="test_b",
            normalized_test_name="test_b",
            normalized_identity_strategy="EXACT",
            framework_name="pytest",
            framework_version="1.0",
            identity_normalization_version="1.0",
            canonical_identity_hash="hash2",
            identity_lineage_root_hash="hash2",
            identity_version=1,
            identity_resolution_strategy="EXACT",
            created_at=datetime.utcnow()
        )
        db.add(tc1)
        db.add(tc2)

        # Seed FileTestLink coverage links
        link1 = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=uuid.uuid4(),
            file_path="src/auth/login.py",
            test_case_id=tc_id_1,
            mapping_type="DIRECT",
            confidence_score="HIGH",
            created_at=datetime.utcnow()
        )
        link2 = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=uuid.uuid4(),
            file_path="src/utils/helper.py",
            test_case_id=tc_id_2,
            mapping_type="DIRECT",
            confidence_score="HIGH",
            created_at=datetime.utcnow()
        )
        db.add(link1)
        db.add(link2)

        # Seed ModuleRiskProfile for fragile module src/auth/login.py
        mrp = ModuleRiskProfile(
            id=uuid.uuid4(),
            repository_id=repository_id,
            module_path="src/auth/login.py",
            risk_score=50.0,
            score_components={},
            scoring_formula_version="module_risk.v1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(mrp)
        db.commit()

        # Build candidate inputs
        candidates = [
            RankingCandidateInput(
                test_case_id=tc_id_1,
                reasons=["Test covers auth logic"],
                base_priority_score=0.9,
                evidence_sources=["DIRECT_COVERAGE"],
                mapping_confidence="HIGH",
                flaky_status=None,
                historical_failure_score=None
            ),
            RankingCandidateInput(
                test_case_id=tc_id_2,
                reasons=["Test covers utility logic"],
                base_priority_score=0.9,
                evidence_sources=["DIRECT_COVERAGE"],
                mapping_confidence="HIGH",
                flaky_status=None,
                historical_failure_score=None
            )
        ]

        # Call the ranking service
        bundle = RecommendationRankingService.rank_candidates(
            db=db,
            repository_id=repository_id,
            candidate_tests=candidates,
            mode="NORMAL"
        )

        ranked = bundle.ranked_candidates
        assert len(ranked) == 2

        # Verify test_a (covering fragile login.py) is prioritized over test_b
        # Priority score = risk_value / execution_cost.
        # Since execution_cost defaults to 5.0 for both:
        # test_a should have boosted risk_value because it covers historically fragile login.py
        # test_b should have unboosted risk_value
        test_a_ranked = next(r for r in ranked if r.test_case_id == tc_id_1)
        test_b_ranked = next(r for r in ranked if r.test_case_id == tc_id_2)

        assert test_a_ranked.priority_score > test_b_ranked.priority_score
        assert any("Historically fragile module" in reason for reason in test_a_ranked.reasons)
