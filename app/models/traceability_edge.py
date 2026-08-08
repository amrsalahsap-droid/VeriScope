import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import sqlalchemy as sa

class TraceabilityEdge(Base):
    __tablename__ = "traceability_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    source_node_type = Column(String, nullable=False, index=True)
    source_node_id = Column(String, nullable=False, index=True)
    target_node_type = Column(String, nullable=False, index=True)
    target_node_id = Column(String, nullable=False, index=True)
    
    edge_type = Column(String, nullable=False, index=True)
    edge_source = Column(String, nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    
    evidence_json = Column(sa.JSON, nullable=True)
    metadata_json = Column(sa.JSON, nullable=True)
    
    review_status = Column(String, nullable=False, default="system_suggested", index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    created_by = Column(String, nullable=True)
    confirmed_by = Column(String, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "source_node_type",
            "source_node_id",
            "target_node_type",
            "target_node_id",
            "edge_type",
            "edge_source",
            name="uq_traceability_edges_unique_active"
        ),
    )
