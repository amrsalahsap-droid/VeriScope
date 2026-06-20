"""
Webhook Diagnostics Tests

Tests for webhook delivery diagnostics endpoint.
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent
from app.models.repository import Repository
from app.api.models.user import User


@pytest.fixture
def db_session():
    """Create a transaction-isolated database session for testing."""
    from app.db.session import engine
    from sqlalchemy.orm import sessionmaker
    
    connection = engine.connect()
    transaction = connection.begin()
    
    TestSessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    db = TestSessionLocal()
    
    nested = connection.begin_nested()
    
    @event.listens_for(db, "after_transaction_end")
    def restart_savepoint(session, transaction_):
        nonlocal nested
        if nested.is_active:
            return
        nested = connection.begin_nested()
    
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def repository(db_session):
    repo = Repository(
        id=uuid.uuid4(),
        name="test-repo",
        owner="test-owner",
        provider="github",
        external_id="12345"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    yield repo


@pytest.fixture
def webhook_event(db_session):
    event = WebhookEvent(
        id=uuid.uuid4(),
        github_delivery_id="delivery-123",
        event_type="pull_request",
        action="opened",
        signature_valid=True,
        processing_status="COMPLETED",
        received_at=datetime.utcnow(),
        processed_at=datetime.utcnow()
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    yield event


@pytest.fixture
def failed_webhook_event(db_session):
    event = WebhookEvent(
        id=uuid.uuid4(),
        github_delivery_id="delivery-456",
        event_type="pull_request",
        action="synchronize",
        signature_valid=False,
        processing_status="FAILED",
        error_message="Invalid signature",
        received_at=datetime.utcnow()
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    yield event


@pytest.fixture
def mock_user():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User"
    )
    return user


class TestWebhookDiagnostics:
    """Tests for webhook delivery diagnostics."""
    
    def test_webhook_events_endpoint_returns_events(self, db_session, repository, webhook_event, mock_user):
        """Test that webhook events endpoint returns events."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        assert len(events) > 0
        assert events[0]["github_delivery_id"] == "delivery-123"
        assert events[0]["event_type"] == "pull_request"
    
    def test_webhook_events_includes_signature_status(self, db_session, repository, webhook_event, mock_user):
        """Test that webhook events include signature status."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        assert events[0]["signature_valid"] == True
    
    def test_webhook_events_includes_processing_status(self, db_session, repository, webhook_event, mock_user):
        """Test that webhook events include processing status."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        assert events[0]["processing_status"] == "COMPLETED"
    
    def test_webhook_events_includes_error_message_for_failed_events(self, db_session, repository, failed_webhook_event, mock_user):
        """Test that webhook events include error message for failed events."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        # Find the failed event
        failed_event = next((e for e in events if e["github_delivery_id"] == "delivery-456"), None)
        assert failed_event is not None
        assert failed_event["error_message"] == "Invalid signature"
        assert failed_event["signature_valid"] == False
        assert failed_event["processing_status"] == "FAILED"
    
    def test_webhook_events_includes_timing_information(self, db_session, repository, webhook_event, mock_user):
        """Test that webhook events include timing information."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        assert events[0]["received_at"] is not None
        assert events[0]["processed_at"] is not None
    
    def test_webhook_events_does_not_expose_raw_payload(self, db_session, repository, webhook_event, mock_user):
        """Test that webhook events do not expose raw payload."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        # Should not include raw payload fields
        assert "raw_payload" not in events[0]
        assert "payload" not in events[0]
        assert "body" not in events[0]
    
    def test_webhook_events_limited_to_most_recent(self, db_session, repository, mock_user):
        """Test that webhook events are limited to most recent 100."""
        from app.routers.cicd_observability import get_webhook_events
        
        # Create more than 100 events
        for i in range(150):
            event = WebhookEvent(
                id=uuid.uuid4(),
                github_delivery_id=f"delivery-{i}",
                event_type="push",
                signature_valid=True,
                processing_status="COMPLETED",
                received_at=datetime.utcnow()
            )
            db_session.add(event)
        db_session.commit()
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        # Should be limited to 100
        assert len(events) <= 100
    
    def test_webhook_events_ordered_by_received_at_desc(self, db_session, repository, webhook_event, failed_webhook_event, mock_user):
        """Test that webhook events are ordered by received_at descending."""
        from app.routers.cicd_observability import get_webhook_events
        
        events = get_webhook_events(repository.id, db_session, mock_user())
        
        # Verify ordering (most recent first)
        if len(events) > 1:
            for i in range(len(events) - 1):
                assert events[i]["received_at"] >= events[i + 1]["received_at"]
