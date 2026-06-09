"""
External Test Case Reference Model.

This model stores metadata imported from external test management systems
(TestRail, Xray, Zephyr, Jira, etc.) to provide business context for tests.

Important: This is metadata only. JUnit/CI evidence remains the source of
execution truth. External references enrich test cases with business context
like priority, tags, and business criticality.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class ExternalTestCaseReference(Base):
    """
    Reference to a test case in an external test management system.
    
    This model stores metadata imported from external TMS providers to enrich
    Veriscope's understanding of test cases with business context.
    
    Key points:
    - Repository-scoped: Each reference belongs to a specific repository
    - Provider-agnostic: Supports multiple TMS providers via the provider field
    - Metadata-only: Does not replace JUnit execution evidence
    - Enrichment purpose: Adds business context (priority, tags, criticality)
    """
    __tablename__ = "external_test_case_references"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Repository scoping
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Provider information
    provider = Column(String, nullable=False, index=True)  # TESTRAIL, XRAY, ZEPHYR, JIRA, MANUAL
    
    # External identifiers
    external_project_id = Column(String, nullable=False, index=True)
    external_test_case_id = Column(String, nullable=False, index=True)
    
    # Test case metadata
    title = Column(String, nullable=False)
    tags = Column(JSON, nullable=True)  # List of tags as JSON array
    priority = Column(String, nullable=True)  # Priority level (e.g., "High", "Medium", "Low")
    business_criticality = Column(String, nullable=True)  # Business criticality (e.g., "Critical", "Important", "Standard")
    
    # Timestamps
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    repository = relationship("Repository", back_populates="external_test_case_references")
    
    def __repr__(self):
        return (
            f"<ExternalTestCaseReference(id={self.id}, provider={self.provider}, "
            f"external_test_case_id={self.external_test_case_id}, title={self.title})>"
        )
