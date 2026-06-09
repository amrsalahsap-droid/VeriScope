"""
External Test Scenario Mapping Model

Stores mappings between external test cases (TestRail, Xray, Zephyr, CSV)
and Veriscope Behavior Scenarios and Scenario Intents.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, Index
from app.db.base import Base


class ExternalTestScenarioMapping(Base):
    """
    Mapping between external test cases and Veriscope behavior scenarios.
    
    This model stores the results of mapping external test cases (manual/managed)
    to discovered behavior scenarios and scenario intents in Veriscope.
    
    Key distinction:
    - External test cases are manual/managed test assets, not executed tests
    - They can cover scenarios but are not executed
    - This mapping is separate from automated test coverage mapping
    
    Rules:
    - Confidence must be explainable via matched terms
    - Track matched terms for explainability
    - Store reason for mapping decision
    - Do not duplicate existing automated test mapping
    """
    __tablename__ = "external_test_scenario_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # External test case reference
    external_test_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("external_test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Behavior mapping (nullable if no match found)
    behavior_id = Column(
        UUID(as_uuid=True),
        ForeignKey("behaviors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Behavior scenario mapping (nullable if no match found)
    behavior_scenario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("behavior_scenarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Scenario intent key mapping (nullable if no match found)
    scenario_intent_key = Column(
        String,
        nullable=True,
        index=True
    )
    
    # Mapping confidence
    confidence = Column(
        Float,
        nullable=False
    )  # 0.0 to 1.0
    
    # Matched terms for explainability
    matched_terms = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of terms that contributed to the match
    
    # Reason for mapping decision
    reason = Column(
        Text,
        nullable=True
    )  # Human-readable explanation of why this mapping was made
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Constraints
    __table_args__ = (
        # Unique constraint: external_test_case_id
        # Each test case can have at most one mapping (we update if better match found)
        UniqueConstraint(
            'external_test_case_id',
            name='uq_external_test_scenario_mapping'
        ),
        # Index for filtering by behavior
        Index('ix_external_test_scenario_mappings_behavior', 'behavior_id'),
        # Index for filtering by behavior_scenario
        Index('ix_external_test_scenario_mappings_scenario', 'behavior_scenario_id'),
        # Index for filtering by scenario_intent_key
        Index('ix_external_test_scenario_mappings_intent_key', 'scenario_intent_key'),
        # Index for filtering by confidence
        Index('ix_external_test_scenario_mappings_confidence', 'confidence'),
    )
    
    # Relationships
    external_test_case = relationship("ExternalTestCase", back_populates="scenario_mappings")
    behavior = relationship("Behavior", back_populates="external_test_scenario_mappings")
    behavior_scenario = relationship("BehaviorScenario", back_populates="external_test_mappings")
    
    def __repr__(self):
        return (
            f"<ExternalTestScenarioMapping(id={self.id}, external_test_case_id={self.external_test_case_id}, "
            f"behavior_scenario_id={self.behavior_scenario_id}, confidence={self.confidence})>"
        )
