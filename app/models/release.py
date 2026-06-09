"""
Release Model

Represents a software release, version, milestone, or hotfix.
Releases are optional for PR recommendations but required for release-level regression suites.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReleaseType:
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"
    HOTFIX = "HOTFIX"
    CUSTOM = "CUSTOM"


class ReleaseStatus:
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_SIGNOFF = "READY_FOR_SIGNOFF"
    RELEASED = "RELEASED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class Release(Base):
    """Represents a software release, version, milestone, or hotfix."""
    __tablename__ = "releases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Release identity
    version = Column(String, nullable=False, index=True)
    release_type = Column(
        ENUM(
            ReleaseType.MAJOR, ReleaseType.MINOR, ReleaseType.PATCH,
            ReleaseType.HOTFIX, ReleaseType.CUSTOM,
            name="release_type_enum",
            create_type=True
        ),
        nullable=False,
        default=ReleaseType.MINOR
    )
    status = Column(
        ENUM(
            ReleaseStatus.PLANNED, ReleaseStatus.IN_PROGRESS, ReleaseStatus.READY_FOR_SIGNOFF,
            ReleaseStatus.RELEASED, ReleaseStatus.ROLLED_BACK, ReleaseStatus.CANCELLED,
            name="release_status_enum",
            create_type=True
        ),
        nullable=False,
        default=ReleaseStatus.PLANNED
    )
    
    # Release timeline
    planned_date = Column(DateTime, nullable=True)
    actual_date = Column(DateTime, nullable=True)
    
    # Release documentation
    release_notes = Column(Text, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("repository_id", "version", name="uq_releases_repo_version"),
        Index("ix_releases_repo_status", "repository_id", "status"),
    )
    
    # Relationships
    repository = relationship("Repository")
    regression_suites = relationship("RegressionSuite", back_populates="release", cascade="all, delete-orphan")
