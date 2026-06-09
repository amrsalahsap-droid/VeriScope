import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class DomainMap(Base):
    """Persisted domain mapping automatically learned from folder structures, modules, and historical PRs."""
    __tablename__ = "domain_maps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String, nullable=False, index=True)
    files = Column(JSONB, nullable=False, default=list) # List of files in domain
    modules = Column(JSONB, nullable=False, default=list) # List of modules in domain
    owners = Column(JSONB, nullable=True) # Optional list of owners/engineers
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
