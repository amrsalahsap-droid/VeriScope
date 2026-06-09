"""
Regression Suite Models

Represents regression suites for PR-level and release-level testing.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Float, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class SuiteType:
    PR_REGRESSION = "PR_REGRESSION"
    RELEASE_REGRESSION = "RELEASE_REGRESSION"
    SMOKE = "SMOKE"
    FULL = "FULL"
    HOTFIX = "HOTFIX"


class SuiteStatus:
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class ScopeItemType:
    AUTOMATED_TEST = "AUTOMATED_TEST"
    MANUAL_TEST = "MANUAL_TEST"
    SUGGESTED_SCENARIO = "SUGGESTED_SCENARIO"
    COVERAGE_GAP = "COVERAGE_GAP"


class ScopeTier:
    MUST_RUN = "MUST_RUN"
    SHOULD_RUN = "SHOULD_RUN"
    OPTIONAL = "OPTIONAL"


class ScopePriority:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExecutionStatus:
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    MANUAL_PENDING = "MANUAL_PENDING"
    UNKNOWN = "UNKNOWN"


class OverrideType:
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    TIER_CHANGED = "TIER_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    MARKED_REQUIRED = "MARKED_REQUIRED"
    MARKED_OPTIONAL = "MARKED_OPTIONAL"
    EXCLUDED = "EXCLUDED"
    RESTORED = "RESTORED"


class RegressionSuite(Base):
    """Represents the generated/reviewed regression suite for a PR or Release."""
    __tablename__ = "regression_suites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Optional linking to release or PR
    release_id = Column(UUID(as_uuid=True), ForeignKey("releases.id", ondelete="SET NULL"), nullable=True, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Suite identity
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    suite_type = Column(
        ENUM(
            SuiteType.PR_REGRESSION, SuiteType.RELEASE_REGRESSION, SuiteType.SMOKE,
            SuiteType.FULL, SuiteType.HOTFIX,
            name="suite_type_enum",
            create_type=True
        ),
        nullable=False,
        default=SuiteType.PR_REGRESSION
    )
    status = Column(
        ENUM(
            SuiteStatus.DRAFT, SuiteStatus.REVIEWED, SuiteStatus.APPROVED,
            SuiteStatus.EXECUTED, SuiteStatus.BLOCKED, SuiteStatus.ARCHIVED,
            name="suite_status_enum",
            create_type=True
        ),
        nullable=False,
        default=SuiteStatus.DRAFT
    )
    
    # Quality metrics
    confidence_level = Column(String, nullable=True)  # HIGH, MODERATE, LOW
    scope_score = Column(Float, nullable=True)  # 0.0 to 1.0
    
    # Audit fields
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Constraints
    __table_args__ = (
        Index("ix_regression_suites_repo_status", "repository_id", "status"),
        Index("ix_regression_suites_release", "release_id"),
        Index("ix_regression_suites_pr", "pull_request_id"),
        Index("ix_regression_suites_rec_run", "recommendation_run_id"),
    )
    
    # Relationships
    repository = relationship("Repository")
    release = relationship("Release", back_populates="regression_suites")
    pull_request = relationship("PullRequest")
    recommendation_run = relationship("RecommendationRun")
    scope_items = relationship("RegressionScopeItem", back_populates="regression_suite", cascade="all, delete-orphan")
    overrides = relationship("ScopeOverride", back_populates="regression_suite", cascade="all, delete-orphan")


class RegressionScopeItem(Base):
    """Represents every selected test or scenario inside the suite."""
    __tablename__ = "regression_scope_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regression_suite_id = Column(UUID(as_uuid=True), ForeignKey("regression_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Links to test assets (one of these should be set)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    external_test_case_id = Column(UUID(as_uuid=True), ForeignKey("external_test_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    suggested_scenario_id = Column(UUID(as_uuid=True), ForeignKey("suggested_test_scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Links to business context
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="SET NULL"), nullable=True, index=True)
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True, index=True)
    acceptance_criterion_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Item classification
    item_type = Column(
        ENUM(
            ScopeItemType.AUTOMATED_TEST, ScopeItemType.MANUAL_TEST,
            ScopeItemType.SUGGESTED_SCENARIO, ScopeItemType.COVERAGE_GAP,
            name="scope_item_type_enum",
            create_type=True
        ),
        nullable=False
    )
    tier = Column(
        ENUM(
            ScopeTier.MUST_RUN, ScopeTier.SHOULD_RUN, ScopeTier.OPTIONAL,
            name="scope_tier_enum",
            create_type=True
        ),
        nullable=False,
        default=ScopeTier.SHOULD_RUN
    )
    priority = Column(
        ENUM(
            ScopePriority.CRITICAL, ScopePriority.HIGH, ScopePriority.MEDIUM, ScopePriority.LOW,
            name="scope_priority_enum",
            create_type=True
        ),
        nullable=False,
        default=ScopePriority.MEDIUM
    )
    
    # Selection rationale
    selection_reason = Column(Text, nullable=True)
    evidence_summary = Column(JSONB, nullable=True)
    
    # Execution tracking
    execution_status = Column(
        ENUM(
            ExecutionStatus.NOT_RUN, ExecutionStatus.PASSED, ExecutionStatus.FAILED,
            ExecutionStatus.SKIPPED, ExecutionStatus.BLOCKED, ExecutionStatus.MANUAL_PENDING,
            ExecutionStatus.UNKNOWN,
            name="execution_status_enum",
            create_type=True
        ),
        nullable=False,
        default=ExecutionStatus.NOT_RUN
    )
    coverage_status = Column(String, nullable=True)
    
    # Exclusion flag
    is_excluded = Column(Boolean, nullable=False, default=False)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        # Uniqueness guard to avoid duplicate same item in same suite
        # Ensure that within a suite, we don't have the same test_case_id, external_test_case_id, or suggested_scenario_id
        UniqueConstraint("regression_suite_id", "test_case_id", name="uq_scope_items_suite_test_case"),
        UniqueConstraint("regression_suite_id", "external_test_case_id", name="uq_scope_items_suite_external_test"),
        UniqueConstraint("regression_suite_id", "suggested_scenario_id", name="uq_scope_items_suite_suggested"),
        Index("ix_regression_scope_items_suite_tier", "regression_suite_id", "tier"),
        Index("ix_regression_scope_items_suite_type", "regression_suite_id", "item_type"),
        Index("ix_regression_scope_items_suite_execution", "regression_suite_id", "execution_status"),
        Index("ix_regression_scope_items_test_case", "test_case_id"),
        Index("ix_regression_scope_items_external_test", "external_test_case_id"),
        Index("ix_regression_scope_items_suggested", "suggested_scenario_id"),
        Index("ix_regression_scope_items_behavior", "behavior_id"),
        Index("ix_regression_scope_items_journey", "journey_id"),
    )
    
    # Relationships
    regression_suite = relationship("RegressionSuite", back_populates="scope_items")
    test_case = relationship("TestCase")
    external_test_case = relationship("ExternalTestCase")
    suggested_scenario = relationship("SuggestedTestScenario")
    behavior = relationship("Behavior")
    journey = relationship("Journey")
    acceptance_criterion = relationship("AcceptanceCriterion")
    overrides = relationship("ScopeOverride", back_populates="scope_item", cascade="all, delete-orphan")


class ScopeOverride(Base):
    """Captures QA Lead decisions on scope items."""
    __tablename__ = "scope_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regression_scope_item_id = Column(UUID(as_uuid=True), ForeignKey("regression_scope_items.id", ondelete="CASCADE"), nullable=False, index=True)
    regression_suite_id = Column(UUID(as_uuid=True), ForeignKey("regression_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Override details
    override_type = Column(
        ENUM(
            OverrideType.ADDED, OverrideType.REMOVED, OverrideType.TIER_CHANGED,
            OverrideType.PRIORITY_CHANGED, OverrideType.MARKED_REQUIRED, OverrideType.MARKED_OPTIONAL,
            OverrideType.EXCLUDED, OverrideType.RESTORED,
            name="override_type_enum",
            create_type=True
        ),
        nullable=False
    )
    original_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=False)  # Reason is required
    overridden_by = Column(String, nullable=True)
    overridden_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        Index("ix_scope_overrides_suite", "regression_suite_id"),
        Index("ix_scope_overrides_item", "regression_scope_item_id"),
        Index("ix_scope_overrides_type", "override_type"),
        Index("ix_scope_overrides_overridden_at", "overridden_at"),
    )
    
    # Relationships
    regression_suite = relationship("RegressionSuite", back_populates="overrides")
    scope_item = relationship("RegressionScopeItem", back_populates="overrides")
