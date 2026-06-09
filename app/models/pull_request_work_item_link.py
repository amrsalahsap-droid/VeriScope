"""
Pull Request Work Item Link Model

Links pull requests to external work items (Jira, Azure DevOps, etc.)
based on detected keys in PR title, body, branch name, commit messages, or manual linking.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, Index
from app.db.base import Base


class PullRequestWorkItemLink(Base):
    """
    Link between a pull request and an external work item.
    
    This model stores links between PRs and external work items detected
    from PR title, body, branch name, commit messages, or manual linking.
    
    Link sources:
    - PR_TITLE: Work item key detected in PR title
    - PR_BODY: Work item key detected in PR description
    - BRANCH_NAME: Work item key detected in branch name
    - COMMIT_MESSAGE: Work item key detected in commit messages
    - MANUAL: Manually linked by user
    
    Confidence:
    - Higher confidence for PR_TITLE and BRANCH_NAME
    - Lower confidence for PR_BODY and COMMIT_MESSAGE
    - Maximum confidence for MANUAL
    """
    __tablename__ = "pull_request_work_item_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Pull request reference
    pull_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # External work item reference (nullable for unresolved keys)
    external_work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("external_work_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Unresolved key (if external_work_item_id is null)
    unresolved_key = Column(
        String,
        nullable=True,
        index=True
    )  # e.g., "ABC-123" if not yet matched to ExternalWorkItem
    
    # Detection source
    link_source = Column(
        String,
        nullable=False,
        index=True
    )  # PR_TITLE, PR_BODY, BRANCH_NAME, COMMIT_MESSAGE, MANUAL
    
    # Confidence score (0.0 to 1.0)
    confidence = Column(
        Float,
        nullable=False,
        default=0.5
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Constraints
    __table_args__ = (
        # Unique constraint: pull_request_id + external_work_item_id
        # Prevents duplicate links to the same work item
        UniqueConstraint(
            'pull_request_id',
            'external_work_item_id',
            name='uq_pr_work_item'
        ),
        # Index for filtering by pull request
        Index('ix_pr_work_item_links_pr', 'pull_request_id'),
        # Index for filtering by external work item
        Index('ix_pr_work_item_links_work_item', 'external_work_item_id'),
        # Index for filtering by unresolved keys
        Index('ix_pr_work_item_links_unresolved', 'unresolved_key'),
    )
    
    # Relationships
    pull_request = relationship("PullRequest", back_populates="work_item_links")
    external_work_item = relationship("ExternalWorkItem", back_populates="pull_request_links")
    
    def __repr__(self):
        return (
            f"<PullRequestWorkItemLink(id={self.id}, pull_request_id={self.pull_request_id}, "
            f"external_work_item_id={self.external_work_item_id}, link_source={self.link_source})>"
        )
