import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Float,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class PatternMemory(Base):
    """Stores learned associations between changed file patterns and recommended tests.

    Attributes
    ----------
    id:
        UUID primary key.
    workspace_id:
        Workspace this pattern memory belongs to. Enforces tenant isolation.
    repository_id:
        Repository this pattern memory belongs to.
    pattern_key:
        Normalised signal pattern key.
    changed_file_pattern:
        Normalized path pattern of the changed file.
    recommended_test:
        Stable test identifier (TestCase.stable_identity), nullable.
    test_identifier:
        Stable test identifier (TestCase.stable_identity), nullable.
    confidence:
        Confidence score in range [0, 1].
    usage_count:
        Number of outcomes where this relationship was reinforced.
    success_count:
        Number of successful executions.
    defect_count:
        Number of associated defect occurrences.
    last_seen_at:
        Last timestamp this pattern was observed.
    """

    __tablename__ = "pattern_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pattern_key = Column(String, nullable=False, index=True)
    changed_file_pattern = Column(String, nullable=False, index=True)
    recommended_test = Column(String, nullable=True, index=True)
    test_identifier = Column(String, nullable=True, index=True)

    confidence = Column(Float, nullable=False, default=0.0)
    usage_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    defect_count = Column(Integer, nullable=False, default=0)

    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    repository = relationship("Repository")
    workspace = relationship("Workspace")

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "pattern_key",
            "test_identifier",
            name="uq_pattern_memory_repo_pattern_test",
        ),
        Index("ix_pattern_memory_repo_key", "repository_id", "pattern_key"),
        Index("ix_pattern_memory_repo_identifier", "repository_id", "test_identifier"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="chk_pattern_memory_confidence"),
    )

    def __repr__(self) -> str:
        return (
            f"<PatternMemory id={self.id} "
            f"pattern_key={self.pattern_key!r} "
            f"test_identifier={self.test_identifier!r} "
            f"confidence={self.confidence:.3f} "
            f"usage={self.usage_count}>"
        )
