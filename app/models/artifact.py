import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.constants.evidence import EvidenceSource, EvidenceArtifactType, EvidenceHealthStatus

class RawArtifact(Base):
    """Preserves raw webhooks, JUnit XMLs, and coverage files for auditability."""
    __tablename__ = "raw_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Evidence Source & Type
    evidence_source = Column(String, nullable=False, default=EvidenceSource.MANUAL_UPLOAD.value, index=True)
    evidence_artifact_type = Column(String, nullable=False, default=EvidenceArtifactType.UNKNOWN.value, index=True)
    evidence_health_status = Column(String, nullable=False, default=EvidenceHealthStatus.HEALTHY.value, index=True)
    
    # Legacy artifact_type field (deprecated, use evidence_artifact_type instead)
    artifact_type = Column(String, nullable=False, index=True) # e.g. github_webhook, junit_xml, coverage_report, ingestion_response
    
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True)
    storage_path = Column(String, nullable=False) # S3/SaaS URI or path
    artifact_metadata = Column(JSONB, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="raw_artifacts")
