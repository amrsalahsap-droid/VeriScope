"""Simple test to verify release decision models and service work."""

import pytest
from app.db.session import SessionLocal
from app.models.release_decision import ReleaseDecision
from app.models.release_decision_history import ReleaseDecisionHistory
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.recommendation import RecommendationRun
from app.services.release_decision_service import ReleaseDecisionService


def test_models_import():
    """Verify models can be imported."""
    assert ReleaseDecision is not None
    assert ReleaseDecisionHistory is not None


def test_service_import():
    """Verify service can be imported."""
    assert ReleaseDecisionService is not None


def test_service_get_snapshot_hash():
    """Verify snapshot hash generation works."""
    db = SessionLocal()
    try:
        # Get an existing recommendation run instead of creating one
        run = db.query(RecommendationRun).first()
        if run:
            # Get snapshot hash
            snapshot_hash = ReleaseDecisionService.get_snapshot_hash(run)
            assert snapshot_hash is not None
            assert isinstance(snapshot_hash, str)
        else:
            # Skip test if no runs exist
            pytest.skip("No recommendation runs found in database")
    finally:
        db.close()


def test_decision_status_enum():
    """Verify decision status enum values."""
    from app.models.release_decision import DecisionStatus
    # DecisionStatus is a SQLAlchemy ENUM, check it has the right name
    assert DecisionStatus.name == 'decision_status'


def test_history_event_type_enum():
    """Verify history event type enum values."""
    from app.models.release_decision_history import HistoryEventType
    # HistoryEventType is a SQLAlchemy ENUM, check it has the right name
    assert HistoryEventType.name == 'history_event_type'
