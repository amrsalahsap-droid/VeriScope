"""
CI/CD Audit Visibility Tests

Tests for CI/CD audit trail visibility with sensitive field redaction.
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.ci_token_audit import CITokenAuditEvent
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
def mock_user():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User"
    )
    return user


class TestCICDAuditVisibility:
    """Tests for CI/CD audit trail visibility."""
    
    def test_audit_endpoint_returns_audit_events(self, db_session, repository, mock_user):
        """Test that audit endpoint returns audit events."""
        # Create an audit event
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_CREATED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Test token creation"
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        assert len(events) > 0
        assert events[0]["event_type"] == "TOKEN_CREATED"
    
    def test_audit_endpoint_filters_by_repository(self, db_session, repository, mock_user):
        """Test that audit endpoint filters by repository."""
        # Create audit event for this repository
        event1 = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_CREATED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Test token creation"
        )
        db_session.add(event1)
        
        # Create audit event for different repository
        event2 = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            event_type="TOKEN_CREATED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Test token creation"
        )
        db_session.add(event2)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        # Should only return events for this repository
        event_ids = [e["id"] for e in events]
        assert str(event1.id) in event_ids
        assert str(event2.id) not in event_ids
    
    def test_audit_endpoint_includes_event_details(self, db_session, repository, mock_user):
        """Test that audit endpoint includes event details."""
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_USED",
            actor_type="SYSTEM",
            actor_id="worker-1",
            reason="Artifact access"
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        assert events[0]["event_type"] == "TOKEN_USED"
        assert events[0]["actor_type"] == "SYSTEM"
        assert events[0]["actor_id"] == "worker-1"
        assert events[0]["reason"] == "Artifact access"
    
    def test_audit_endpoint_redacts_sensitive_fields(self, db_session, repository, mock_user):
        """Test that audit endpoint redacts sensitive fields."""
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_CREATED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Test token creation",
            metadata_json={
                "token": "secret-token-123",
                "token_hash": "abc123",
                "github_token": "ghp_secret",
                "webhook_secret": "wh_secret",
                "safe_field": "safe-value"
            }
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        metadata = events[0]["metadata_summary"]
        
        # Sensitive fields should be redacted
        assert metadata["token"] == "[REDACTED]"
        assert metadata["token_hash"] == "[REDACTED]"
        assert metadata["github_token"] == "[REDACTED]"
        assert metadata["webhook_secret"] == "[REDACTED]"
        
        # Safe field should not be redacted
        assert metadata["safe_field"] == "safe-value"
    
    def test_audit_endpoint_redacts_nested_sensitive_fields(self, db_session, repository, mock_user):
        """Test that audit endpoint redacts nested sensitive fields."""
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_CREATED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Test token creation",
            metadata_json={
                "nested": {
                    "token": "secret-token-123",
                    "safe_field": "safe-value"
                }
            }
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        metadata = events[0]["metadata_summary"]
        
        # Nested sensitive field should be redacted
        assert metadata["nested"]["token"] == "[REDACTED]"
        assert metadata["nested"]["safe_field"] == "safe-value"
    
    def test_audit_endpoint_limited_to_most_recent(self, db_session, repository, mock_user):
        """Test that audit endpoint is limited to most recent 100 events."""
        # Create more than 100 events
        for i in range(150):
            event = CITokenAuditEvent(
                id=uuid.uuid4(),
                repository_id=repository.id,
                event_type="TOKEN_USED",
                actor_type="SYSTEM",
                actor_id=f"worker-{i}",
                reason=f"Artifact access {i}"
            )
            db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        # Should be limited to 100
        assert len(events) <= 100
    
    def test_audit_endpoint_ordered_by_created_at_desc(self, db_session, repository, mock_user):
        """Test that audit endpoint is ordered by created_at descending."""
        # Create multiple events with different timestamps
        for i in range(5):
            event = CITokenAuditEvent(
                id=uuid.uuid4(),
                repository_id=repository.id,
                event_type="TOKEN_USED",
                actor_type="SYSTEM",
                actor_id=f"worker-{i}",
                reason=f"Artifact access {i}"
            )
            db_session.add(event)
            db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        # Verify ordering (most recent first)
        if len(events) > 1:
            for i in range(len(events) - 1):
                assert events[i]["created_at"] >= events[i + 1]["created_at"]
    
    def test_audit_endpoint_handles_null_metadata(self, db_session, repository, mock_user):
        """Test that audit endpoint handles null metadata."""
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_CREATED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Test token creation",
            metadata_json=None
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        assert events[0]["metadata_summary"] is None
    
    def test_audit_endpoint_includes_pipeline_operation_events(self, db_session, repository, mock_user):
        """Test that audit endpoint includes pipeline operation events."""
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="PIPELINE_JOB_RETRIED",
            actor_type="USER",
            actor_id=str(mock_user().id),
            reason="Operator retried job",
            metadata_json={"job_id": str(uuid.uuid4())}
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        assert events[0]["event_type"] == "PIPELINE_JOB_RETRIED"
    
    def test_audit_endpoint_includes_artifact_access_events(self, db_session, repository, mock_user):
        """Test that audit endpoint includes artifact access events."""
        event = CITokenAuditEvent(
            id=uuid.uuid4(),
            repository_id=repository.id,
            event_type="TOKEN_USED",
            actor_type="SYSTEM",
            actor_id="worker-1",
            reason="Artifact access",
            metadata_json={"artifact_id": str(uuid.uuid4())}
        )
        db_session.add(event)
        db_session.commit()
        
        from app.routers.cicd_observability import get_cicd_audit_events
        
        events = get_cicd_audit_events(repository.id, db_session, mock_user())
        
        assert events[0]["event_type"] == "TOKEN_USED"
