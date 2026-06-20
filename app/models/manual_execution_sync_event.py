"""
Manual Execution Sync Event Model

Stores audit trail and durable queue for manual test execution synchronization to external providers.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class ManualExecutionSyncEvent(Base):
    """
    Audit trail and durable queue for manual test execution synchronization to external providers.
    
    This model stores the history of sync attempts for manual test executions
    to external test management systems (TestRail, Xray, Zephyr, etc.).
    
    Purpose:
    - Forensic troubleshooting
    - Provider diagnostics
    - Retry support
    - Audit compliance
    - Durable queue for crash recovery
    
    Status values:
    - PENDING: Waiting to be processed
    - IN_PROGRESS: Currently being processed by a worker
    - SYNCED: Successfully synchronized
    - FAILED: Failed (will be retried)
    - RETRY_PENDING: Scheduled for retry
    - DEAD_LETTER: Max attempts reached, will not retry
    """
    __tablename__ = "manual_execution_sync_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference to the manual test execution
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("manual_test_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Provider information
    provider = Column(
        String,
        nullable=False,
        index=True
    )  # TESTRAIL, XRAY, ZEPHYR, etc.
    
    # Sync status
    status = Column(
        String,
        nullable=False,
        index=True
    )  # PENDING, IN_PROGRESS, SYNCED, FAILED, RETRY_PENDING, DEAD_LETTER
    
    # Request/Response payloads for debugging
    request_payload = Column(
        JSONB,
        nullable=True
    )  # Payload sent to provider
    
    response_payload = Column(
        JSONB,
        nullable=True
    )  # Response from provider
    
    # Error information
    error_message = Column(
        Text,
        nullable=True
    )  # Error message if sync failed
    
    # Queue management fields
    attempt_count = Column(
        Integer,
        nullable=False,
        default=0
    )  # Number of sync attempts
    
    max_attempts = Column(
        Integer,
        nullable=False,
        default=3
    )  # Maximum retry attempts
    
    next_attempt_at = Column(
        DateTime,
        nullable=True,
        index=True
    )  # When to retry (for RETRY_PENDING)
    
    locked_at = Column(
        DateTime,
        nullable=True
    )  # When the job was locked by a worker
    
    locked_by = Column(
        String,
        nullable=True
    )  # Worker identifier that locked the job
    
    completed_at = Column(
        DateTime,
        nullable=True
    )  # When the job completed (SYNCED, DEAD_LETTER)
    
    last_error = Column(
        Text,
        nullable=True
    )  # Last error message (for retry context)
    
    # External references
    external_run_id = Column(
        String,
        nullable=True,
        index=True
    )  # Test run ID in provider
    
    external_execution_id = Column(
        String,
        nullable=True,
        index=True
    )  # Execution/result ID in provider
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    # Relationships
    execution = relationship("ManualTestExecution", backref="sync_events")
    
    def __repr__(self):
        return (
            f"<ManualExecutionSyncEvent(id={self.id}, execution_id={self.execution_id}, "
            f"provider={self.provider}, status={self.status})>"
        )
