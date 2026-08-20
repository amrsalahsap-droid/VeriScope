import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base

class TestImportQualityReport(Base):
    """Stores the forensic Import Quality Report generated after test result / JUnit XML ingestion."""
    __tablename__ = "test_import_quality_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id = Column(String, nullable=False, index=True) # UUID or TestRun ID string
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    
    metadata_quality_status = Column(String, nullable=False, default="PASS") # PASS | PARTIAL | FAIL
    mapping_confidence_impact = Column(String, nullable=False, default="NONE") # NONE | LOW | MEDIUM | HIGH
    
    report_json = Column(JSONB, nullable=False) # Complete structured report dictionary
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_import_report_repo_pr", "repository_id", "pull_request_id"),
        Index("idx_import_report_import_id", "import_id"),
    )
