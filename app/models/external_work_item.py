"""
External Work Item Model

Stores user stories, tasks, bugs, and requirements from external systems
(Jira, Azure DevOps, etc.) for linking to PRs and recommendations.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, Index
from app.db.base import Base


class ExternalWorkItem(Base):
    """
    External work item from systems like Jira, Azure DevOps, etc.
    
    This model stores work items (stories, tasks, bugs, requirements) imported
    from external work item management systems. These can be linked to PRs
    and recommendations to provide business context.
    
    Work item types:
    - STORY: User story or feature request
    - BUG: Bug report or defect
    - TASK: Task or sub-task
    - REQUIREMENT: Requirement specification
    - EPIC: Epic or large feature
    - UNKNOWN: Unknown or unclassified type
    
    Sync behavior:
    - Unique constraint on provider + integration_connection_id + external_id
    - Raw payload preserved for replay/debug
    - Acceptance criteria normalized when possible
    - Non-empty fields not overwritten with empty sync values
    """
    __tablename__ = "external_work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Workspace scoping
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Optional repository binding for repository-specific work items
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    # Integration connection that sourced this work item
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
    )  # JIRA, AZURE_DEVOPS, etc.
    
    # External identifiers
    external_id = Column(
        String,
        nullable=False,
        index=True
    )  # External system's unique ID (e.g., Jira issue ID)
    
    external_key = Column(
        String,
        nullable=False,
        index=True
    )  # External system's key (e.g., "PROJ-123")
    
    # Work item content
    title = Column(
        String,
        nullable=False
    )
    
    description = Column(
        Text,
        nullable=True
    )
    
    # Work item classification
    work_item_type = Column(
        String,
        nullable=False,
        default="UNKNOWN",
        index=True
    )  # STORY, BUG, TASK, REQUIREMENT, EPIC, UNKNOWN
    
    status = Column(
        String,
        nullable=False,
        index=True
    )  # External system's status (e.g., "Open", "In Progress", "Done")
    
    priority = Column(
        String,
        nullable=True,
        index=True
    )  # External system's priority (e.g., "High", "Medium", "Low")
    
    # Structured data
    labels = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of labels/tags from external system
    
    acceptance_criteria = Column(
        JSONB,
        nullable=True,
        default=list
    )  # Normalized acceptance criteria from external system
    
    # External reference
    url = Column(
        String,
        nullable=True
    )  # URL to view work item in external system
    
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
        # Ensures we don't duplicate work items from the same integration
        UniqueConstraint(
            'provider',
            'integration_connection_id',
            'external_id',
            name='uq_provider_connection_external_id'
        ),
        # Index for filtering by workspace and work item type
        Index('ix_external_work_items_workspace_type', 'workspace_id', 'work_item_type'),
        # Index for filtering by repository
        Index('ix_external_work_items_repository', 'repository_id'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="external_work_items")
    repository = relationship("Repository", back_populates="external_work_items")
    integration_connection = relationship("IntegrationConnection", back_populates="external_work_items")
    pull_request_links = relationship("PullRequestWorkItemLink", back_populates="external_work_item")
    behavior_mappings = relationship("WorkItemBehaviorMapping", back_populates="external_work_item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<ExternalWorkItem(id={self.id}, provider={self.provider}, "
            f"external_key={self.external_key}, work_item_type={self.work_item_type})>"
        )
