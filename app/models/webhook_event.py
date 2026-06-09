import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_delivery_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    action = Column(String, nullable=True, index=True)
    installation_id = Column(BigInteger, nullable=True, index=True)
    repository_id = Column(BigInteger, nullable=True, index=True)
    
    signature_valid = Column(Boolean, nullable=False, default=False)
    
    # Statuses: RECEIVED, PROCESSING, COMPLETED, FAILED, IGNORED_DUPLICATE
    processing_status = Column(String, nullable=False, default="RECEIVED", index=True)
    error_message = Column(String, nullable=True)
    
    # Link to RawArtifact carrying raw JSON
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)
    
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
