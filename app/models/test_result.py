import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean, Index, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.constants.evidence import EvidenceSource, EvidenceArtifactType, EvidenceHealthStatus

class TestCase(Base):
    """Represents a stable test case identity tracked per repository to preserve lineage and flakiness records."""
    __tablename__ = "test_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    suite_name = Column(String, nullable=False)
    test_name = Column(String, nullable=False)
    stable_identity = Column(String, nullable=False) # e.g. "suite_name::test_name"
    
    # Parameterization & Framework-Aware Future-Proofing
    raw_test_name = Column(String, nullable=True) # Full parameterized name e.g. test_login[user1]
    normalized_test_name = Column(String, nullable=True) # Normalized name e.g. test_login
    normalized_identity_strategy = Column(String, nullable=True, default="RAW") # RAW, PARAMETER_STRIPPED, FRAMEWORK_NORMALIZED, CUSTOM
    framework_name = Column(String, nullable=True) # e.g. pytest, junit5, jest, mocha
    framework_version = Column(String, nullable=True)
    identity_normalization_version = Column(Integer, nullable=True, default=1)
    
    # Lineage and Evolution Tracking
    canonical_identity_hash = Column(String, nullable=False, index=True) # SHA-256 in hex of stable_identity
    previous_identity_hash = Column(String, nullable=True, index=True)
    identity_lineage_root_hash = Column(String, nullable=False, index=True) # Anchors historical rename groups
    identity_version = Column(Integer, nullable=False, default=1)
    identity_resolution_strategy = Column(String, nullable=False, default="EXACT") # EXACT, RENAMED, HEURISTIC, MANUAL_OVERRIDE
    
    # Input 4 — Test inventory metadata
    test_type = Column(String, nullable=True) # unit / integration / e2e / api / manual / smoke / regression / unknown
    automation_status = Column(String, nullable=False, default="UNKNOWN") # automated / manual / unknown
    source = Column(String, nullable=False, default="unknown") # repo_scan / junit_import / test_management_import / manual_import / postman_collection / playwright / jest / pytest / unknown
    source_metadata_json = Column(JSONB, nullable=True)
    file_path = Column(String, nullable=True) # test file path or external source path
    dedupe_key = Column(String, nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_seen_commit_sha = Column(String, nullable=True, index=True)
    inventory_snapshot_sha = Column(String, nullable=True, index=True)
    module_or_area = Column(String, nullable=True)
    owner = Column(String, nullable=True)
    tags = Column(JSONB, nullable=True)
    confidence = Column(Float, nullable=True)
    
    # Separate Taxonomy Columns
    test_nature = Column(String, nullable=True)
    primary_test_category = Column(String, nullable=True)
    suite_purpose = Column(String, nullable=True)
    risk_tags = Column(JSONB, nullable=True)
    execution_layer = Column(String, nullable=True)
    import_source = Column(String, nullable=True)
    execution_method = Column(String, nullable=True)
    framework = Column(String, nullable=True)
    external_ac_ref = Column(String, nullable=True)
    
    # Semantic Classification Columns
    product_area = Column(String, nullable=True)
    business_flow = Column(String, nullable=True)
    behavior_key = Column(String, nullable=True)
    scenario_intent = Column(String, nullable=True)
    scenario_type = Column(String, nullable=True)
    validation_target = Column(String, nullable=True)
    risk_dimensions = Column(JSON, nullable=True)
    regression_role = Column(String, nullable=True)
    must_run_condition = Column(String, nullable=True)
    semantic_classification_json = Column(JSON, nullable=True)
    classification_source = Column(String, nullable=True)
    classification_confidence = Column(Float, nullable=True)
    classification_review_status = Column(String, nullable=True)
    classified_at = Column(DateTime, nullable=True)
    classified_by = Column(String, nullable=True)
    semantic_classifier_version = Column(String, nullable=True)
    behavior_mapping_status = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    results = relationship("TestResult", back_populates="test_case")
    repository = relationship("Repository")

    __table_args__ = (
        UniqueConstraint("repository_id", "canonical_identity_hash", name="uq_test_cases_repo_canonical_hash"),
        Index("ix_test_cases_repo_stable_identity", "repository_id", "stable_identity"),
        Index("ix_test_cases_repo_active", "repository_id", "is_active"),
        Index("ix_test_cases_repo_source", "repository_id", "source"),
        Index("ix_test_cases_repo_type", "repository_id", "test_type"),
    )

class TestRun(Base):
    """Represents an atomic collection of test results ingested from a single XML run upload."""
    __tablename__ = "test_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_sha = Column(String, nullable=True, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)
    
    # Evidence Source & Type
    evidence_source = Column(String, nullable=False, default=EvidenceSource.MANUAL_UPLOAD.value, index=True)
    evidence_artifact_type = Column(String, nullable=False, default=EvidenceArtifactType.JUNIT_XML.value, index=True)
    
    # Traceability & Lineage Links
    parent_test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    ingestion_reason = Column(String, nullable=False, default="ORIGINAL_UPLOAD") # ORIGINAL_UPLOAD, RETRY_UPLOAD, REPROCESS_NORMALIZATION, RECONCILIATION_REBUILD
    
    # Global Correlation Propagation
    correlation_id = Column(String, nullable=True, index=True) # Current request trace ID
    source_correlation_id = Column(String, nullable=True, index=True) # Upstream originator trace ID
    request_origin = Column(String, nullable=True) # e.g. github_actions, gitlab_ci, manual
    
    # Traceability, Replay, and Verification Statuses
    file_hash = Column(String, nullable=False, index=True) # SHA-256 of raw XML payload
    normalized_execution_fingerprint = Column(String, nullable=False, index=True) # Identifies duplicate runs safely
    parser_version = Column(String, nullable=False, default="junit_parser.v1")
    parser_support_status = Column(String, nullable=True, default="ACTIVE") # ACTIVE, DEPRECATED, UNSUPPORTED, REPLAY_ONLY
    normalization_schema_version = Column(String, nullable=False, default="junit_result.v1")
    
    # Replay Verification & Auditing
    replay_verification_status = Column(String, nullable=True, default="NOT_VERIFIED") # VERIFIED, DRIFT_DETECTED, NOT_VERIFIED, FAILED
    replay_verified_at = Column(DateTime, nullable=True)
    replay_audit_count = Column(Integer, nullable=True, default=0)
    last_replay_audit_at = Column(DateTime, nullable=True)
    replay_drift_detected = Column(Boolean, nullable=False, default=False)
    
    # Retention Management & Locking
    retention_class = Column(String, nullable=True) # e.g. KEEP_FOREVER, ARCHIVE, SUPERSEDED
    archival_status = Column(String, nullable=True) # e.g. ACTIVE, COMPACTED, PURGED
    retention_locked = Column(Boolean, nullable=False, default=False)
    retention_lock_reason = Column(String, nullable=True) # e.g. RECOMMENDATION_REFERENCED, INCIDENT_REFERENCED, AUDIT_REFERENCED, ROLLBACK_REFERENCED
    
    # Recommendation Replay & Accountability snapshots
    recommendation_eligibility_snapshot = Column(JSONB, nullable=True)
    recommendation_replay_eligible = Column(Boolean, nullable=False, default=True)
    
    # Ingestion Health & Consistency Status
    status = Column(String, nullable=False) # SUCCESS, FAILURE, PARTIAL_SUCCESS
    evidence_health_status = Column(String, nullable=False, default="HEALTHY") # HEALTHY, DEGRADED, INSUFFICIENT
    consistency_status = Column(String, nullable=False, default="UNKNOWN") # CONSISTENT, PARTIALLY_INCONSISTENT, BROKEN, UNKNOWN
    consistency_severity = Column(String, nullable=False, default="NONE") # CRITICAL, IMPORTANT, SUPPORTING, NONE
    
    # Metadata summaries
    total_tests = Column(Integer, nullable=False, default=0)
    passed_tests = Column(Integer, nullable=False, default=0)
    failed_tests = Column(Integer, nullable=False, default=0)
    skipped_tests = Column(Integer, nullable=False, default=0)
    duration = Column(Float, nullable=False, default=0.0)
    
    # Ingestion Backpressure & Throttling Diagnostics
    queue_wait_duration_ms = Column(Integer, nullable=True)
    ingestion_retry_count = Column(Integer, nullable=True, default=0)
    ingestion_backpressure_applied = Column(Boolean, nullable=False, default=False)
    
    # Granular telemetry logs & bounded diagnostics
    ingestion_diagnostics = Column(JSONB, nullable=False, default=dict)
    consistency_diagnostics = Column(JSONB, nullable=False, default=dict)
    diagnostics_truncated = Column(Boolean, nullable=False, default=False)
    
    # Sequence ordering fields
    execution_sequence_number = Column(Integer, nullable=True)
    execution_window_id = Column(UUID(as_uuid=True), nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="test_runs")
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")
    parent = relationship("TestRun", remote_side=[id])

    __table_args__ = (
        UniqueConstraint("repository_id", "normalized_execution_fingerprint", name="uq_test_runs_repo_execution_fingerprint"),
    )

class TestResult(Base):
    """Represents the execution outcome of a specific TestCase inside a TestRun."""
    __tablename__ = "test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(String, nullable=False) # passed, failed, skipped, error
    duration = Column(Float, nullable=False, default=0.0)
    
    failure_message = Column(String, nullable=True)
    stack_trace = Column(String, nullable=True)
    
    # Stack Trace Compliance Hardening & Encryption Readiness
    stack_trace_redaction_status = Column(String, nullable=True, default="NOT_REDACTED") # NOT_REDACTED, REDACTED, PARTIALLY_REDACTED, UNKNOWN
    redaction_version = Column(String, nullable=True)
    contains_pii = Column(Boolean, nullable=True)
    contains_secrets = Column(Boolean, nullable=True)
    compliance_classification = Column(String, nullable=True) # e.g. internal, sensitive, restricted
    encryption_status = Column(String, nullable=True, default="PLAINTEXT") # PLAINTEXT, ENCRYPTED, REDACTED, UNKNOWN
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    test_run = relationship("TestRun", back_populates="results")
    test_case = relationship("TestCase", back_populates="results")

from sqlalchemy import event, inspect

@event.listens_for(TestRun, "before_update")
def prevent_test_run_mutation(mapper, connection, target):
    state = inspect(target)
    forbidden_attributes = [
        "file_hash", "normalized_execution_fingerprint", "status", "repository_id",
        "total_tests", "passed_tests", "failed_tests", "skipped_tests"
    ]
    for attr in forbidden_attributes:
        hist = state.attrs[attr].history
        if hist.has_changes():
            raise RuntimeError(f"Forensic Immutability Violation: Attribute '{attr}' of TestRun is immutable after commit.")

@event.listens_for(TestResult, "before_update")
def prevent_test_result_mutation(mapper, connection, target):
    state = inspect(target)
    forbidden_attributes = ["test_run_id", "test_case_id", "status", "duration"]
    for attr in forbidden_attributes:
        hist = state.attrs[attr].history
        if hist.has_changes():
            raise RuntimeError(f"Forensic Immutability Violation: Attribute '{attr}' of TestResult is immutable after commit.")
