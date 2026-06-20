"""Manual Test Execution Model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class ManualTestExecution(Base):
    """
    Represents an execution outcome of a manual test case.
    
    Tied to an ExternalTestCase and a Repository. Can optionally be associated
    with a PullRequest and a RecommendationRun.
    
    Is append-friendly: new executions deactivate prior active ones for the same context.
    """
    __tablename__ = "manual_test_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    external_test_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("external_test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    pull_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    recommendation_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    outcome = Column(String, nullable=False, index=True)  # PASSED, FAILED, SKIPPED, BLOCKED
    
    executed_by_id = Column(String, nullable=True)
    executed_by_name = Column(String, nullable=True)
    executed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    notes = Column(Text, nullable=True)
    evidence_url = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    
    # External system synchronization (Jira/Azure/TestRail integration compatibility)
    external_system = Column(String, nullable=True, index=True)
    external_run_id = Column(String, nullable=True, index=True)
    external_execution_id = Column(String, nullable=True)
    sync_status = Column(String, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    external_test_case = relationship("ExternalTestCase")
    repository = relationship("Repository")
    pull_request = relationship("PullRequest")
    recommendation_run = relationship("RecommendationRun")

    def __repr__(self):
        return (
            f"<ManualTestExecution(id={self.id}, external_test_case_id={self.external_test_case_id}, "
            f"outcome={self.outcome}, executed_at={self.executed_at})>"
        )
