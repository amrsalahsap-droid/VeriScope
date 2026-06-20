"""Manual Test Requirement Mapping Model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class ManualTestRequirementMapping(Base):
    """
    Represents a traceability link between an ExternalTestCase and an AcceptanceCriterion.
    
    Traceability links are workspace-scoped and repository-scoped.
    They provide metadata linking manual test cases to functional AC requirements.
    
    Unique Constraint: Only one active mapping per external_test_case_id + acceptance_criterion_id.
    """
    __tablename__ = "manual_test_requirement_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    external_test_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("external_test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    acceptance_criterion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("acceptance_criteria.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    mapping_source = Column(String, nullable=False, default="MANUAL")  # MANUAL, IMPORTED, GENERATED
    
    created_by_id = Column(String, nullable=True)
    created_by_name = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    external_test_case = relationship("ExternalTestCase")
    acceptance_criterion = relationship("AcceptanceCriterion")
    repository = relationship("Repository")

    __table_args__ = (
        Index(
            "uq_active_manual_test_ac_mapping",
            "external_test_case_id",
            "acceptance_criterion_id",
            unique=True,
            sqlite_where=text("is_active"),
            postgresql_where=text("is_active"),
        ),
    )

    def __repr__(self):
        return (
            f"<ManualTestRequirementMapping(id={self.id}, "
            f"external_test_case_id={self.external_test_case_id}, "
            f"acceptance_criterion_id={self.acceptance_criterion_id}, "
            f"is_active={self.is_active})>"
        )
