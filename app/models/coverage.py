import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.constants.evidence import EvidenceSource, EvidenceArtifactType, EvidenceHealthStatus
class CoverageReport(Base):
    """Represents a validated coverage report run, storing metadata and overall statistics."""
    __tablename__ = "coverage_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_sha = Column(String, nullable=True, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)

    # Final Contract Evidence Fields
    format = Column(String, nullable=False, index=True)  # "LCOV", "COBERTURA"
    source = Column(String, nullable=False, index=True)  # "MANUAL_UPLOAD", "GITHUB_ACTIONS", "CI_ARTIFACT"
    branch = Column(String, nullable=True, index=True)
    
    files_total = Column(Integer, nullable=False, default=0)
    covered_lines_total = Column(Integer, nullable=False, default=0)
    uncovered_lines_total = Column(Integer, nullable=False, default=0)
    total_lines = Column(Integer, nullable=False, default=0)
    
    line_coverage_ratio = Column(Float, nullable=True)
    branch_coverage_ratio = Column(Float, nullable=True)
    
    coverage_confidence = Column(String, nullable=False, index=True)  # "LOW", "MODERATE", "HIGH"
    evidence_health_status = Column(String, nullable=False, index=True)  # "HEALTHY", "DEGRADED", "INVALID", "UNSUPPORTED"
    
    parser_version = Column(String, nullable=False, default="1.0.0")
    normalization_schema_version = Column(String, nullable=False, default="1.0.0")

    # Legacy Evidence Source & Type (for backwards compatibility)
    evidence_source = Column(String, nullable=False, default=EvidenceSource.MANUAL_UPLOAD.value, index=True)
    evidence_artifact_type = Column(String, nullable=False, default=EvidenceArtifactType.LCOV.value, index=True)

    # Telemetry and Traceability (Legacy/backward compatibility)
    correlation_id = Column(String, nullable=True, index=True)
    file_hash = Column(String, nullable=False, index=True) # SHA-256 hash of payload

    # Aggregated coverage stats (Legacy/backward compatibility)
    overall_coverage_pct = Column(Float, nullable=False, default=0.0) # covered_lines / total_lines
    covered_lines_count = Column(Integer, nullable=False, default=0)
    uncovered_lines_count = Column(Integer, nullable=False, default=0)

    # Coverage Confidence Scoring (Legacy/backward compatibility)
    confidence_score = Column(String, nullable=False) # HIGH, MODERATE, LOW
    confidence_logic = Column(String, nullable=True) # Explanation of the score assessment

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="coverage_reports")
    workspace = relationship("Workspace")
    pull_request = relationship("PullRequest")
    raw_artifact = relationship("RawArtifact")
    file_entries = relationship("CoverageFileEntry", back_populates="coverage_report", cascade="all, delete-orphan")
    test_links = relationship("FileTestLink", back_populates="coverage_report", cascade="all, delete-orphan")


class CoverageFileEntry(Base):
    """Granular coverage information mapped per source file in a CoverageReport."""
    __tablename__ = "coverage_file_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coverage_report_id = Column(UUID(as_uuid=True), ForeignKey("coverage_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    file_path = Column(String, nullable=False, index=True) # Normalized source file path

    # Line-level statement tracking
    covered_lines = Column(JSONB, nullable=False, default=list) # Array of covered line numbers
    uncovered_lines = Column(JSONB, nullable=False, default=list) # Array of uncovered line numbers

    # Metrics (New contract)
    total_lines = Column(Integer, nullable=False, default=0)
    line_coverage_ratio = Column(Float, nullable=True)
    branch_coverage_ratio = Column(Float, nullable=True)
    functions_covered = Column(Integer, nullable=True)
    functions_total = Column(Integer, nullable=True)

    # Metrics (Legacy/backward compatibility)
    total_lines_count = Column(Integer, nullable=False, default=0)
    covered_lines_count = Column(Integer, nullable=False, default=0)
    uncovered_lines_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    coverage_report = relationship("CoverageReport", back_populates="file_entries")
    repository = relationship("Repository")

    __table_args__ = (
        UniqueConstraint("coverage_report_id", "file_path", name="uq_coverage_file_entries_report_path"),
    )


class FileTestLink(Base):
    """Maps a source file to specific test cases covering it, allowing direct trace lookup."""
    __tablename__ = "file_test_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coverage_report_id = Column(UUID(as_uuid=True), ForeignKey("coverage_reports.id", ondelete="CASCADE"), nullable=False, index=True)

    file_path = Column(String, nullable=False, index=True) # Normalized source file path
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)

    # Resolution Metadata
    mapping_type = Column(String, nullable=False) # DIRECT, HEURISTIC_NAMING, HEURISTIC_PATH
    confidence_score = Column(String, nullable=False) # HIGH, MODERATE, LOW (based on heuristic strength)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    coverage_report = relationship("CoverageReport", back_populates="test_links")
    test_case = relationship("TestCase")

    __table_args__ = (
        UniqueConstraint("coverage_report_id", "file_path", "test_case_id", name="uq_file_test_links_report_file_test"),
    )
