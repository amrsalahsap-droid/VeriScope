"""
External Test Case Model

Stores manual/managed test cases from TestRail, Xray, Zephyr, or CSV import.
These represent planned/managed test assets, not executed JUnit results.

Note: This is different from ExternalTestCaseReference which is a lightweight
metadata reference. ExternalTestCase stores detailed test case structure.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, Index
from app.db.base import Base


class ExternalTestCase(Base):
    """
    External test case from test management systems (TestRail, Xray, Zephyr, CSV).
    
    This model stores detailed test case information from external test management
    systems. These are planned/managed test assets, NOT executed JUnit results.
    They enrich recommendation scope without pretending they ran.
    
    Automation status:
    - MANUAL: Manual test case requiring human execution
    - AUTOMATED: Fully automated test case
    - PARTIALLY_AUTOMATED: Semi-automated test case
    - UNKNOWN: Automation status unknown
    
    Important distinction:
    - ExternalTestCase: Planned test assets with steps, preconditions, expected results
    - TestCase: Executed JUnit test results with pass/fail status
    - ExternalTestCaseReference: Lightweight metadata reference only
    
    Mapping:
    - behavior_id: Links to Behavior if test maps to a discovered behavior
    - journey_id: Links to Journey if test maps to a user journey
    - scenario_intent_key: Links to scenario intent for coverage tracking
    """
    __tablename__ = "external_test_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Workspace scoping
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Optional repository binding for repository-specific test cases
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    # Integration connection that sourced this test case
    integration_connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Provider identification
    provider = Column(
        String,
        nullable=False,
        index=True
    )  # TESTRAIL, XRAY, ZEPHYR, MANUAL_CSV
    
    # External identifiers
    external_id = Column(
        String,
        nullable=False,
        index=True
    )  # External system's unique ID
    
    external_key = Column(
        String,
        nullable=True,
        index=True
    )  # External system's key (e.g., "C123", "TEST-456")
    
    # Test case content
    title = Column(
        String,
        nullable=False
    )
    
    description = Column(
        Text,
        nullable=True
    )
    
    # Test case structure
    preconditions = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of preconditions (JSONB array)
    
    steps = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of test steps (JSONB array with step, expected_result)
    
    expected_result = Column(
        Text,
        nullable=True
    )  # Overall expected result
    
    # Classification
    priority = Column(
        String,
        nullable=True,
        index=True
    )  # Priority level (e.g., "Critical", "High", "Medium", "Low")
    
    test_type = Column(
        String,
        nullable=True,
        index=True
    )  # Test type (e.g., "Functional", "UI", "API", "Performance")
    
    automation_status = Column(
        String,
        nullable=False,
        default="UNKNOWN",
        index=True
    )  # MANUAL, AUTOMATED, PARTIALLY_AUTOMATED, UNKNOWN
    
    # Structured data
    tags = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of tags/labels from external system
    
    linked_work_item_keys = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of linked work item keys (e.g., ["PROJ-123", "PROJ-456"])
    
    # Veriscope mapping
    behavior_id = Column(
        UUID(as_uuid=True),
        ForeignKey("behaviors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # Links to Behavior if mapped
    
    journey_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journeys.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # Links to Journey if mapped
    
    scenario_intent_key = Column(
        String,
        nullable=True,
        index=True
    )  # Links to scenario intent for coverage tracking
    
    # External reference
    url = Column(
        String,
        nullable=True
    )  # URL to view test case in external system
    
    # Raw payload for replay/debug
    raw_payload = Column(
        JSONB,
        nullable=True
    )  # Complete raw payload from external system API
    
    # Sync tracking
    last_synced_at = Column(
        DateTime,
        nullable=True
    )
    
    # Lifecycle
    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Constraints
    __table_args__ = (
        # Unique constraint: provider + integration_connection_id + external_id
        # Ensures we don't duplicate test cases from the same integration
        UniqueConstraint(
            'provider',
            'integration_connection_id',
            'external_id',
            name='uq_external_test_cases_provider_connection_id'
        ),
        # Index for filtering by workspace and automation status
        Index('ix_external_test_cases_workspace_automation', 'workspace_id', 'automation_status'),
        # Index for filtering by repository
        Index('ix_external_test_cases_repository', 'repository_id'),
        # Index for filtering by behavior mapping
        Index('ix_external_test_cases_behavior', 'behavior_id'),
        # Index for filtering by journey mapping
        Index('ix_external_test_cases_journey', 'journey_id'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="external_test_cases")
    repository = relationship("Repository", back_populates="external_test_cases")
    integration_connection = relationship("IntegrationConnection", back_populates="external_test_cases")
    behavior = relationship("Behavior", back_populates="external_test_cases")
    journey = relationship("Journey", back_populates="external_test_cases")
    scenario_mappings = relationship("ExternalTestScenarioMapping", back_populates="external_test_case", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<ExternalTestCase(id={self.id}, provider={self.provider}, "
            f"external_key={self.external_key}, automation_status={self.automation_status})>"
        )
