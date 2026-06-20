"""
Test Asset Model

Classifies automated and manual tests with business-critical metadata.
TestAsset is metadata over existing tests/manual cases for selection, filtering, and future integrations.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class TestPriority:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TestType:
    UNIT = "UNIT"
    API = "API"
    INTEGRATION = "INTEGRATION"
    E2E = "E2E"
    UI = "UI"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    MANUAL = "MANUAL"
    SMOKE = "SMOKE"


class BusinessCriticality:
    MISSION_CRITICAL = "MISSION_CRITICAL"
    IMPORTANT = "IMPORTANT"
    SUPPORTING = "SUPPORTING"


class AutomationStatus:
    AUTOMATED = "AUTOMATED"
    MANUAL = "MANUAL"
    PARTIALLY_AUTOMATED = "PARTIALLY_AUTOMATED"
    UNKNOWN = "UNKNOWN"


class TestAsset(Base):
    """Classifies automated and manual tests with business-critical metadata."""
    __tablename__ = "test_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Links to test assets (one of these should be set)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True)
    external_test_case_id = Column(UUID(as_uuid=True), ForeignKey("external_test_cases.id", ondelete="SET NULL"), nullable=True)
    
    # Display identity
    stable_identity = Column(String, nullable=True)
    display_name = Column(String, nullable=False)
    
    # Classification
    priority = Column(
        ENUM(
            TestPriority.CRITICAL, TestPriority.HIGH, TestPriority.MEDIUM, TestPriority.LOW,
            name="test_priority_enum",
            create_type=True
        ),
        nullable=False,
        default=TestPriority.MEDIUM
    )
    test_type = Column(
        ENUM(
            TestType.UNIT, TestType.API, TestType.INTEGRATION, TestType.E2E,
            TestType.UI, TestType.SECURITY, TestType.PERFORMANCE, TestType.MANUAL, TestType.SMOKE,
            name="test_type_enum",
            create_type=True
        ),
        nullable=False,
        default=TestType.UNIT
    )
    business_criticality = Column(
        ENUM(
            BusinessCriticality.MISSION_CRITICAL, BusinessCriticality.IMPORTANT, BusinessCriticality.SUPPORTING,
            name="business_criticality_enum",
            create_type=True
        ),
        nullable=False,
        default=BusinessCriticality.SUPPORTING
    )
    automation_status = Column(
        ENUM(
            AutomationStatus.AUTOMATED, AutomationStatus.MANUAL,
            AutomationStatus.PARTIALLY_AUTOMATED, AutomationStatus.UNKNOWN,
            name="automation_status_enum",
            create_type=True
        ),
        nullable=False,
        default=AutomationStatus.UNKNOWN
    )
    
    # Business context mappings
    behavior_ids = Column(JSONB, nullable=True)  # List of behavior UUIDs
    journey_ids = Column(JSONB, nullable=True)  # List of journey UUIDs
    tags = Column(JSONB, nullable=True)  # Custom tags
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        Index("ix_test_assets_repo_priority", "repository_id", "priority"),
        Index("ix_test_assets_repo_type", "repository_id", "test_type"),
        Index("ix_test_assets_repo_automation", "repository_id", "automation_status"),
        Index("ix_test_assets_test_case", "test_case_id"),
        Index("ix_test_assets_external_test", "external_test_case_id"),
        Index("ix_test_assets_stable_identity", "stable_identity"),
    )
    
    # Relationships
    repository = relationship("Repository")
    test_case = relationship("TestCase")
    external_test_case = relationship("ExternalTestCase")
