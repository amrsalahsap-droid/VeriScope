import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class FileDependency(Base):
    """Dependency tree records mapped to a specific commit_sha."""
    __tablename__ = "file_dependencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String, nullable=False, index=True)
    depends_on_file_path = Column(String, nullable=False, index=True)
    dependency_type = Column(String, nullable=False, default="import")
    commit_sha = Column(String, nullable=False, index=True) # Historical mapping anchor
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="file_dependencies")

    @property
    def source_file(self) -> str:
        return self.file_path

    @source_file.setter
    def source_file(self, value: str):
        self.file_path = value

    @property
    def target_file(self) -> str:
        return self.depends_on_file_path

    @target_file.setter
    def target_file(self, value: str):
        self.depends_on_file_path = value
