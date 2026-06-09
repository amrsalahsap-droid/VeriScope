"""
tests/property/test_recommendation_learning_engine_properties.py
===================================================================

Property-based tests for RecommendationLearningEngine using Hypothesis.
"""

import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st
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
from app.services.recommendation_learning_engine import (
    RecommendationLearningEngine,
    LearningEngineResult,
    _SOURCES,
    _CONFIDENCE_SATURATION,
    _SKIP_EXTENSIONS,
)

# --------------------------------------------------------------------------- #
# Database Setup
# --------------------------------------------------------------------------- #

engine_sqlite = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine_sqlite)
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine_sqlite)


# Helper to get session
def get_db():
    return SessionLocal()


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #

sources_strategy = st.sampled_from(list(_SOURCES.keys()))
n_strategy = st.integers(min_value=1, max_value=100)
n_confidence_strategy = st.integers(min_value=1, max_value=50)

# Paths strategy
extensions = st.sampled_from([
    ".py", ".ts", ".go", ".rs", ".java", ".cpp",
    ".md", ".yml", ".json", ".txt", ".toml", ".yaml"
])
filenames = st.text(alphabet=st.characters(codec="ascii", categories=["Lu", "Ll", "Nd"]), min_size=1, max_size=15)
paths_strategy = st.builds(
    lambda parts, ext: "/".join(parts) + ext,
    st.lists(filenames, min_size=1, max_size=5),
    extensions
)

test_names = st.text(alphabet=st.characters(codec="ascii", categories=["Lu", "Ll", "Nd", "Pd", "Pc"]), min_size=1, max_size=30)
test_list_strategy = st.lists(test_names, min_size=0, max_size=20, unique=True)


# --------------------------------------------------------------------------- #
# 1. Property 1: Strength Formula Correctness
# --------------------------------------------------------------------------- #

@given(source=sources_strategy, N=n_strategy)
@settings(max_examples=50, deadline=None)
def test_property_strength_formula_correctness(source, N):
    """Property 1: Assert strength == min(base + (N-1)*step, 1.0) after N observations."""
    db = get_db()
    engine = RecommendationLearningEngine(db)
    
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    pattern_key = f"file_change:app/prop1_{uuid.uuid4()}.py"
    test_id = f"test_{uuid.uuid4()}"
    
    result = LearningEngineResult()
    for _ in range(N):
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_id,
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
    assert row.usage_count == N
    
    cfg = _SOURCES[source]
    expected_strength = min(cfg["base"] + (N - 1) * cfg["step"], 1.0)
    assert float(row.strength) == pytest.approx(expected_strength)
    
    db.close()


# --------------------------------------------------------------------------- #
# 2. Property 2: Confidence Formula Correctness
# --------------------------------------------------------------------------- #

@given(source=sources_strategy, N=n_confidence_strategy)
@settings(max_examples=50, deadline=None)
def test_property_confidence_formula_correctness(source, N):
    """Property 2: Assert confidence == min(N / 10, 1.0) after N observations."""
    db = get_db()
    engine = RecommendationLearningEngine(db)
    
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    pattern_key = f"file_change:app/prop2_{uuid.uuid4()}.py"
    test_id = f"test_{uuid.uuid4()}"
    
    result = LearningEngineResult()
    for _ in range(N):
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_id,
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
    assert row.usage_count == N
    
    expected_confidence = min(N / _CONFIDENCE_SATURATION, 1.0)
    assert float(row.confidence) == pytest.approx(expected_confidence)
    
    db.close()


# --------------------------------------------------------------------------- #
# 3. Property 3: Strength and Confidence Monotonicity
# --------------------------------------------------------------------------- #

@given(source=sources_strategy, N=st.integers(min_value=2, max_value=20))
@settings(max_examples=40, deadline=None)
def test_property_monotonicity(source, N):
    """Property 3: Assert strength and confidence grow monotonically over multiple subsequent observations."""
    db = get_db()
    engine = RecommendationLearningEngine(db)
    
    repo_id = uuid.uuid4()
    outcome_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    pattern_key = f"file_change:app/prop3_{uuid.uuid4()}.py"
    test_id = f"test_{uuid.uuid4()}"
    result = LearningEngineResult()
    
    prev_strength = -1.0
    prev_confidence = -1.0
    
    for _ in range(N):
        engine._upsert(
            repository_id=repo_id,
            pattern_key=pattern_key,
            test_identifier=test_id,
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
        
        curr_strength = float(row.strength)
        curr_confidence = float(row.confidence)
        
        assert curr_strength >= prev_strength
        assert curr_confidence >= prev_confidence
        
        prev_strength = curr_strength
        prev_confidence = curr_confidence
        
    db.close()


# --------------------------------------------------------------------------- #
# 4. Property 4: Signal Deduplication
# --------------------------------------------------------------------------- #

@given(
    recommended=test_list_strategy,
    executed=test_list_strategy,
    manually_added=test_list_strategy,
    paths=st.lists(paths_strategy, min_size=0, max_size=10, unique=True),
    escaped_defect=st.booleans(),
    rollback=st.booleans()
)
@settings(max_examples=40, deadline=None)
def test_property_signal_deduplication(recommended, executed, manually_added, paths, escaped_defect, rollback):
    """Property 4: Assert _collect_signals() never produces duplicate signals."""
    db = get_db()
    engine = RecommendationLearningEngine(db)
    
    pr_id = uuid.uuid4()
    
    # Mock outcome
    outcome = MagicMock()
    outcome.id = uuid.uuid4()
    outcome.repository_id = uuid.uuid4()
    outcome.pull_request_id = pr_id
    outcome.escaped_defect_detected = escaped_defect
    outcome.rollback_occurred = rollback
    outcome.recommended_tests = recommended
    outcome.executed_tests = executed
    outcome.manually_added_tests = manually_added
    outcome.manually_removed_tests = []
    
    # We patch _changed_files to return the generated paths
    with patch.object(engine, "_changed_files", return_value=paths):
        signals = engine._collect_signals(outcome)
        
        # Verify deduplication
        assert len(signals) == len(set(signals))
        
    db.close()


# --------------------------------------------------------------------------- #
# 5. Property 5: Extension Skip-List Filtering
# --------------------------------------------------------------------------- #

@given(
    recommended=test_list_strategy,
    executed=test_list_strategy,
    paths=st.lists(paths_strategy, min_size=1, max_size=20, unique=True)
)
@settings(max_examples=40, deadline=None)
def test_property_skip_list_filtering(recommended, executed, paths):
    """Property 5: Assert that no signal is produced for files ending in skip-list extensions."""
    db = get_db()
    engine = RecommendationLearningEngine(db)
    
    outcome = MagicMock()
    outcome.id = uuid.uuid4()
    outcome.repository_id = uuid.uuid4()
    outcome.pull_request_id = uuid.uuid4()
    outcome.escaped_defect_detected = True
    outcome.rollback_occurred = False
    outcome.recommended_tests = recommended
    outcome.executed_tests = executed
    outcome.manually_added_tests = []
    outcome.manually_removed_tests = []
    
    with patch.object(engine, "_changed_files", return_value=paths):
        signals = engine._collect_signals(outcome)
        
        for pattern_key, _, _ in signals:
            # Skip keys that are domains, check only file pattern keys
            if ":" in pattern_key and not pattern_key.startswith("domain:"):
                # Extract file path from pattern_key (e.g. 'file_change:app/README.md')
                _, path = pattern_key.split(":", 1)
                
                # Assert extension is NOT in skip-list
                has_skip_ext = any(path.endswith(ext) for ext in _SKIP_EXTENSIONS)
                assert not has_skip_ext, f"Pattern key {pattern_key} contains skip-list extension!"
                
    db.close()


# --------------------------------------------------------------------------- #
# 6. Property 8: Domain Inference Determinism
# --------------------------------------------------------------------------- #

@given(path=paths_strategy)
@settings(max_examples=100, deadline=None)
def test_property_domain_inference_determinism(path):
    """Property 8: Assert that domain inference is idempotent and completely deterministic."""
    d1 = RecommendationLearningEngine._infer_domain(path)
    d2 = RecommendationLearningEngine._infer_domain(path)
    assert d1 == d2
    
    # Assert result is always a string and is never empty
    assert isinstance(d1, str)
    assert len(d1) > 0


# --------------------------------------------------------------------------- #
# 7. Property 9: learn() Never Raises
# --------------------------------------------------------------------------- #

@given(
    pull_request_id=st.none() | st.uuids(),
    escaped_defect=st.booleans(),
    rollback=st.booleans(),
    recommended=st.lists(st.text(), min_size=0, max_size=10),
    executed=st.lists(st.text(), min_size=0, max_size=10),
    manually_added=st.lists(st.text(), min_size=0, max_size=10),
    manually_removed=st.lists(st.text(), min_size=0, max_size=10),
    db_fails=st.booleans()
)
@settings(max_examples=40, deadline=None)
def test_property_learn_never_raises(pull_request_id, escaped_defect, rollback, recommended, executed, manually_added, manually_removed, db_fails):
    """Property 9: Assert that learn() never raises, regardless of input shape or DB errors."""
    db = get_db()
    engine = RecommendationLearningEngine(db)
    
    outcome = MagicMock()
    outcome.id = uuid.uuid4()
    outcome.repository_id = uuid.uuid4()
    outcome.pull_request_id = pull_request_id
    outcome.escaped_defect_detected = escaped_defect
    outcome.rollback_occurred = rollback
    outcome.recommended_tests = recommended
    outcome.executed_tests = executed
    outcome.manually_added_tests = manually_added
    outcome.manually_removed_tests = manually_removed
    
    # If db_fails is True, we mock the db.query or db.commit to raise an exception
    if db_fails:
        db.query = MagicMock(side_effect=RuntimeError("Mock DB Query Failure"))
        db.commit = MagicMock(side_effect=RuntimeError("Mock DB Commit Failure"))
        
    try:
        result = engine.learn(outcome, workspace_id=uuid.uuid4())
        assert isinstance(result, LearningEngineResult)
    except Exception as exc:
        pytest.fail(f"RecommendationLearningEngine.learn raised an exception: {exc}")
    finally:
        db.close()
