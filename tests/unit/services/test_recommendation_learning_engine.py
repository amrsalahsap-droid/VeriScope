"""
tests/unit/services/test_recommendation_learning_engine.py
=============================================================

Unit and integration tests for the RecommendationLearningEngine service.
"""

import uuid
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Register custom SQLite type compilers for PostgreSQL-specific types
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
import app.models  # noqa
from app.models.pattern_learning import PatternLearning
from app.models.pull_request import PullRequestChangedFile
from app.models.recommendation import RecommendationOutcome
from app.services.recommendation_learning_engine import (
    RecommendationLearningEngine,
    LearningEngineResult,
    _SOURCES,
    _CONFIDENCE_SATURATION,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def sqlite_engine():
    """Sets up an in-memory SQLite database and registers all schemas."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(sqlite_engine):
    """Provides a transactional database session with autoflush enabled."""
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=connection)
    session = SessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def engine(db):
    """Provides an instance of RecommendationLearningEngine."""
    return RecommendationLearningEngine(db)


# --------------------------------------------------------------------------- #
# Helper factories
# --------------------------------------------------------------------------- #

def make_outcome(
    *,
    repository_id: uuid.UUID = None,
    pull_request_id: uuid.UUID = None,
    escaped_defect_detected: bool = False,
    rollback_occurred: bool = False,
    recommended: list[str] = None,
    executed: list[str] = None,
    manually_added: list[str] = None,
    manually_removed: list[str] = None,
) -> MagicMock:
    """Helper to construct a mock outcome that behaves correctly for attribute reads."""
    outcome = MagicMock()
    outcome.id = uuid.uuid4()
    outcome.repository_id = repository_id or uuid.uuid4()
    outcome.pull_request_id = pull_request_id
    outcome.escaped_defect_detected = escaped_defect_detected
    outcome.rollback_occurred = rollback_occurred
    outcome.recommended_tests = recommended or []
    outcome.executed_tests = executed or []
    outcome.manually_added_tests = manually_added or []
    outcome.manually_removed_tests = manually_removed or []
    return outcome


# --------------------------------------------------------------------------- #
# 1. Early Return & Signal Collection Tests
# --------------------------------------------------------------------------- #

def test_learn_null_pull_request_early_return(db, engine):
    """Test pull_request_id=None returns LearningEngineResult with no DB calls."""
    outcome = make_outcome(pull_request_id=None)
    
    # We pass a spy mock for DB to ensure absolutely no calls are made
    spy_db = MagicMock()
    engine_spy = RecommendationLearningEngine(spy_db)
    
    result = engine_spy.learn(outcome, workspace_id=uuid.uuid4())
    
    assert isinstance(result, LearningEngineResult)
    assert result.patterns_upserted == 0
    assert result.signals_processed == 0
    assert result.success is True
    spy_db.query.assert_not_called()


def test_signal_collection_escaped_defect(db, engine):
    """Test ESCAPED_DEFECT emits defect_escape:<file> and domain:<label> keys for missed tests."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    # Seed changed files
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        escaped_defect_detected=True,
        recommended=["test_login", "test_logout"],
        executed=["test_login"],  # test_logout is missed
    )
    
    signals = engine._collect_signals(outcome)
    
    # Missed test_logout should generate defect_escape and domain signals
    assert ("defect_escape:app/services/auth_service.py", "test_logout", "ESCAPED_DEFECT") in signals
    assert ("domain:authentication", "test_logout", "ESCAPED_DEFECT") in signals
    # No signal for executed test_login under ESCAPED_DEFECT path
    assert not any(s[1] == "test_login" and s[2] == "ESCAPED_DEFECT" for s in signals)


def test_signal_collection_manual_override(db, engine):
    """Test MANUAL_OVERRIDE emits manual_add:<file>, file_change:<file>, and domain:<label> keys."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    # Seed changed files
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        manually_added=["test_custom_verification"],
    )
    
    signals = engine._collect_signals(outcome)
    
    assert ("manual_add:app/services/auth_service.py", "test_custom_verification", "MANUAL_OVERRIDE") in signals
    assert ("file_change:app/services/auth_service.py", "test_custom_verification", "MANUAL_OVERRIDE") in signals
    assert ("domain:authentication", "test_custom_verification", "MANUAL_OVERRIDE") in signals


def test_signal_collection_followed(db, engine):
    """Test FOLLOWED signals: recommended ∩ executed emits file_change:<file> and domain:<label>."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        recommended=["test_login", "test_other"],
        executed=["test_login"],
    )
    
    signals = engine._collect_signals(outcome)
    
    assert ("file_change:app/services/auth_service.py", "test_login", "FOLLOWED") in signals
    assert ("domain:authentication", "test_login", "FOLLOWED") in signals
    # test_other was not executed, so it's not followed
    assert not any(s[1] == "test_other" and s[2] == "FOLLOWED" for s in signals)


def test_signal_collection_heuristic(db, engine):
    """Test HEURISTIC signals: recommended - executed - added emits file_change:<file> keys only."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        recommended=["test_login", "test_heuristic"],
        executed=["test_login"],  # test_heuristic is skipped
    )
    
    signals = engine._collect_signals(outcome)
    
    # Skipped recommended test produces file_change HEURISTIC signal
    assert ("file_change:app/services/auth_service.py", "test_heuristic", "HEURISTIC") in signals
    # HEURISTIC signals should not contain domain keys
    assert not any(s[0].startswith("domain:") and s[2] == "HEURISTIC" for s in signals)


def test_extension_skip_list(db, engine):
    """Test extension skip-list: .yml, .md, .json files produce no pattern keys."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="README.md",
        status="modified"
    ))
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="config.json",
        status="modified"
    ))
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",  # valid file
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        recommended=["test_login"],
        executed=["test_login"],
    )
    
    signals = engine._collect_signals(outcome)
    
    # We should have signals for auth_service.py but NOT for README.md or config.json
    assert any("auth_service.py" in s[0] for s in signals)
    assert not any("README.md" in s[0] for s in signals)
    assert not any("config.json" in s[0] for s in signals)


def test_signal_deduplication(db, engine):
    """Test deduplication: same triple not emitted twice even if multiple signal paths trigger it."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    # Add identical files
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        manually_added=["test_login"],
        recommended=["test_login"],
        executed=["test_login"],
    )
    
    signals = engine._collect_signals(outcome)
    
    # Verify uniqueness of each signal in the output list
    seen = set()
    for s in signals:
        assert s not in seen
        seen.add(s)


# --------------------------------------------------------------------------- #
# 2. Upsert Mathematics Tests
# --------------------------------------------------------------------------- #

def test_upsert_first_observation(db, engine):
    """Test first observation: usage_count=1, strength=base, confidence=0.1."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    result = LearningEngineResult()
    
    for source in _SOURCES.keys():
        pattern_key = f"file_change:app/{source.lower()}.py"
        test_identifier = f"test_{source.lower()}"
        
        success = engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_identifier,
            source=source,
            outcome_id=outcome_id,
            now=now,
            result=result,
        )
        assert success is True
        
        row = db.query(PatternLearning).filter(
            PatternLearning.repository_id == repo_id,
            PatternLearning.pattern_key == pattern_key,
            PatternLearning.source == source
        ).first()
        
        assert row is not None
        assert row.usage_count == 1
        assert float(row.strength) == pytest.approx(_SOURCES[source]["base"])
        assert float(row.confidence) == pytest.approx(1 / _CONFIDENCE_SATURATION)


def test_upsert_second_observation(db, engine):
    """Test second observation: strength = min(base + step, 1.0), confidence = min(2/10, 1.0)."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result = LearningEngineResult()
    
    for source in _SOURCES.keys():
        pattern_key = f"file_change:app/{source.lower()}.py"
        test_identifier = f"test_{source.lower()}"
        
        # Call 1 (first observation)
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_identifier,
            source=source,
            outcome_id=outcome_id,
            now=now,
            result=result,
        )
        
        # Call 2 (second observation)
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_identifier,
            source=source,
            outcome_id=outcome_id,
            now=now,
            result=result,
        )
        
        row = db.query(PatternLearning).filter(
            PatternLearning.repository_id == repo_id,
            PatternLearning.pattern_key == pattern_key,
            PatternLearning.source == source
        ).first()
        
        assert row is not None
        assert row.usage_count == 2
        
        expected_strength = min(_SOURCES[source]["base"] + _SOURCES[source]["step"], 1.0)
        assert float(row.strength) == pytest.approx(expected_strength)
        assert float(row.confidence) == pytest.approx(2 / _CONFIDENCE_SATURATION)


def test_upsert_n_observations(db, engine):
    """Test N-th observation: strength = min(base + (N-1)*step, 1.0) for N in {1, 2, 5, 10, 20}."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result = LearningEngineResult()
    
    source = "HEURISTIC"
    cfg = _SOURCES[source]
    pattern_key = "file_change:app/heuristic_n.py"
    test_identifier = "test_heuristic_n"
    
    for i in range(1, 21):
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_identifier,
            source=source,
            outcome_id=outcome_id,
            now=now,
            result=result,
        )
        
        if i in {1, 2, 5, 10, 20}:
            row = db.query(PatternLearning).filter(
                PatternLearning.repository_id == repo_id,
                PatternLearning.pattern_key == pattern_key,
                PatternLearning.source == source
            ).first()
            
            assert row is not None
            assert row.usage_count == i
            expected_strength = min(cfg["base"] + (i - 1) * cfg["step"], 1.0)
            expected_confidence = min(i / _CONFIDENCE_SATURATION, 1.0)
            
            assert float(row.strength) == pytest.approx(expected_strength)
            assert float(row.confidence) == pytest.approx(expected_confidence)


def test_strength_cap_manual_override(db, engine):
    """Test strength cap: for MANUAL_OVERRIDE at N=10, min(0.60 + 9*0.10, 1.0) = 1.0."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result = LearningEngineResult()
    
    source = "MANUAL_OVERRIDE"
    pattern_key = "file_change:app/override_cap.py"
    test_identifier = "test_override_cap"
    
    for _ in range(10):
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_identifier,
            source=source,
            outcome_id=outcome_id,
            now=now,
            result=result,
        )
        
    row = db.query(PatternLearning).filter(
        PatternLearning.repository_id == repo_id,
        PatternLearning.pattern_key == pattern_key,
        PatternLearning.source == source
    ).first()
    
    assert row is not None
    assert row.usage_count == 10
    assert float(row.strength) == pytest.approx(1.0)
    assert float(row.confidence) == pytest.approx(1.0)


def test_monotonicity_guard(db, engine):
    """Test max() monotonicity guard: if existing strength/confidence is higher than computed, preserve it."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result = LearningEngineResult()
    
    source = "HEURISTIC"
    pattern_key = "file_change:app/mono.py"
    test_identifier = "test_mono"
    
    # 1. Create a row
    engine._upsert(
        repository_id=repo_id,
        pattern_key=pattern_key,
        test_identifier=test_identifier,
        source=source,
        outcome_id=outcome_id,
        now=now,
        result=result,
    )
    
    row = db.query(PatternLearning).filter(
        PatternLearning.repository_id == repo_id,
        PatternLearning.pattern_key == pattern_key,
        PatternLearning.source == source
    ).first()
    
    assert row is not None
    
    # Manually hack strength and confidence to high values
    row.strength = 0.95
    row.confidence = 0.99
    db.flush()  # Flush changes to the SQL session instead of committing/refreshing
    
    # 2. Call upsert again. Computed values will be lower:
    # usage = 2, strength = min(0.20 + 1 * 0.02, 1.0) = 0.22, confidence = 0.20
    engine._upsert(
        repository_id=repo_id,
        pattern_key=pattern_key,
        test_identifier=test_identifier,
        source=source,
        outcome_id=outcome_id,
        now=now,
        result=result,
    )
    
    # Read properties directly from the session-attached row
    assert row.usage_count == 2
    # Hand-hacked high values must be preserved per monotonicity guard
    assert float(row.strength) == pytest.approx(0.95)
    assert float(row.confidence) == pytest.approx(0.99)


def test_unknown_source_guard(db, engine):
    """Test unknown source: records error in result, returns False, no DB write."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result = LearningEngineResult()
    
    success = engine._upsert(
        repository_id=repo_id,
        pattern_key="file_change:app/unknown.py",
        test_identifier="test_unknown",
        source="UNKNOWN_SOURCE_VALUE",
        outcome_id=outcome_id,
        now=now,
        result=result,
    )
    
    assert success is False
    assert len(result.errors) == 1
    assert "UNKNOWN_SOURCE_VALUE" in result.errors[0]
    
    row = db.query(PatternLearning).filter(
        PatternLearning.repository_id == repo_id,
        PatternLearning.pattern_key == "file_change:app/unknown.py"
    ).first()
    assert row is None


# --------------------------------------------------------------------------- #
# 3. Error Handling and Transactions
# --------------------------------------------------------------------------- #

def test_learn_collection_failure(db, engine):
    """Test signal collection failure: signals_processed=0, patterns_upserted=0, success=False."""
    outcome = make_outcome(pull_request_id=uuid.uuid4())
    
    with patch.object(engine, "_collect_signals", side_effect=RuntimeError("Collect error")):
        result = engine.learn(outcome, workspace_id=uuid.uuid4())
        
        assert result.signals_processed == 0
        assert result.patterns_upserted == 0
        assert result.success is False
        assert len(result.errors) == 1
        assert "Collect error" in result.errors[0]


def test_learn_individual_upsert_failure(db, engine):
    """Test individual upsert failure: signals_processed incremented, loop continues, error recorded."""
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    db.add(PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/auth_service.py",
        status="modified"
    ))
    db.commit()
    
    outcome = make_outcome(
        repository_id=repo_id,
        pull_request_id=pr_id,
        recommended=["test_login", "test_logout"],
        executed=["test_login"],
    )
    
    # We should have multiple signals. We mock _upsert to fail on "test_login" but succeed on "test_logout".
    original_upsert = engine._upsert
    
    def mock_upsert(*args, **kwargs):
        if kwargs.get("test_identifier") == "test_login":
            raise RuntimeError("Upsert error")
        return original_upsert(*args, **kwargs)
        
    with patch.object(engine, "_upsert", side_effect=mock_upsert):
        result = engine.learn(outcome, workspace_id=uuid.uuid4())
        
        # Verify both signals were processed, and only one failed
        assert result.signals_processed > 0
        assert result.patterns_upserted > 0
        assert result.success is False
        # Multiple keys are produced for test_login (file_change:..., domain:...)
        assert len(result.errors) >= 1


def test_learn_commit_failure(db, engine):
    """Test commit failure: db.rollback() called, error recorded, result returned."""
    outcome = make_outcome(pull_request_id=uuid.uuid4())
    
    with patch.object(engine, "_collect_signals", return_value=[("file_change:app/auth.py", "test_login", "FOLLOWED")]):
        with patch.object(db, "commit", side_effect=RuntimeError("Commit error")):
            with patch.object(db, "rollback") as mock_rollback:
                result = engine.learn(outcome, workspace_id=uuid.uuid4())
                
                assert result.success is False
                assert len(result.errors) == 1
                assert "Commit error" in result.errors[0]
                mock_rollback.assert_called_once()


# --------------------------------------------------------------------------- #
# 4. Domain Inference Tests
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "path,expected_domain",
    [
        ("app/auth/login.py", "authentication"),
        ("billing/invoices/subscription.ts", "billing"),
        ("app/security/acl_policy.py", "security"),
        ("api/v1/router/handler.py", "api"),
        ("db/migrations/001_initial.sql", "data_model"),
        ("src/utils/shared_helpers.go", "utilities"),
        ("config/settings/env.yaml", "configuration"),
    ]
)
def test_domain_inference_keyword_groups(path, expected_domain):
    """Test that each keyword group maps to the correct label."""
    assert RecommendationLearningEngine._infer_domain(path) == expected_domain


def test_domain_inference_first_match_wins():
    """Test first-match-wins: a path containing both 'auth' and 'billing' keywords resolves to the first keyword group (authentication)."""
    # "auth" appears in auth_keywords (first), "billing" appears in billing_keywords (second)
    path = "app/auth/billing_checkout.py"
    assert RecommendationLearningEngine._infer_domain(path) == "authentication"


def test_domain_inference_parent_directory_fallback():
    """Test parent-directory fallback: 'services/my_module/file.py' -> 'my module'."""
    path = "services/my_module/file.py"
    assert RecommendationLearningEngine._infer_domain(path) == "my module"


def test_domain_inference_general_fallback():
    """Test 'general' fallback: 'file.py' (single component) -> 'general'."""
    path = "file.py"
    assert RecommendationLearningEngine._infer_domain(path) == "general"


# --------------------------------------------------------------------------- #
# 5. Query Helper Tests
# --------------------------------------------------------------------------- #

def test_get_learned_tests_empty_pattern_keys(db, engine):
    """Test get_learned_tests() with empty pattern_keys: returns [] without calling db.query()."""
    spy_db = MagicMock()
    engine_spy = RecommendationLearningEngine(spy_db)
    
    result = engine_spy.get_learned_tests(uuid.uuid4(), [])
    assert result == []
    spy_db.query.assert_not_called()


def test_get_learned_tests_shape_and_rounding(db, engine):
    """Test get_learned_tests() result dict shape and rounding to 4 decimal places."""
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    # Upsert a record
    engine._upsert(
        repository_id=repo_id,
        pattern_key="file_change:app/auth.py",
        test_identifier="test_login",
        source="FOLLOWED",
        outcome_id=outcome_id,
        now=now,
        result=LearningEngineResult(),
    )
    
    # Query it back
    tests = engine.get_learned_tests(
        repository_id=repo_id,
        pattern_keys=["file_change:app/auth.py"],
        min_strength=0.1,
        min_confidence=0.0
    )
    
    assert len(tests) == 1
    t = tests[0]
    
    # Assert dict shape
    assert "test_identifier" in t
    assert "pattern_key" in t
    assert "source" in t
    assert "strength" in t
    assert "confidence" in t
    assert "usage_count" in t
    
    assert t["test_identifier"] == "test_login"
    assert t["pattern_key"] == "file_change:app/auth.py"
    assert t["source"] == "FOLLOWED"
    
    # Assert rounding to 4 dp (holds true for both floats and decimals)
    assert isinstance(t["strength"], (float, Decimal))
    assert isinstance(t["confidence"], (float, Decimal))
    assert float(t["strength"]) == pytest.approx(0.4, abs=1e-4)
    assert float(t["confidence"]) == pytest.approx(0.1, abs=1e-4)


# --------------------------------------------------------------------------- #
# 6. LearningEngineResult Success Property Tests
# --------------------------------------------------------------------------- #

def test_result_success_property():
    """Test success property: True when errors is empty, False otherwise."""
    r1 = LearningEngineResult(errors=[])
    assert r1.success is True
    
    r2 = LearningEngineResult(errors=["An error"])
    assert r2.success is False
