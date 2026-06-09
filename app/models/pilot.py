import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, event, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class PilotReport(Base):
    """
    Represents an aggregated pilot report for a repository over a given time window.
    """
    __tablename__ = "pilot_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    total_runs = Column(Integer, nullable=False, default=0)
    followed_runs = Column(Integer, nullable=False, default=0)
    overridden_runs = Column(Integer, nullable=False, default=0)
    ignored_runs = Column(Integer, nullable=False, default=0)
    
    # Conservative savings in seconds
    ci_runtime_saved_seconds = Column(Float, nullable=False, default=0.0)
    ci_runtime_total_seconds = Column(Float, nullable=False, default=0.0)
    
    escaped_defects_count = Column(Integer, nullable=False, default=0)
    rollbacks_count = Column(Integer, nullable=False, default=0)
    
    # Trust Indicators
    trust_adherence_rate = Column(Float, nullable=False, default=0.0)
    trust_lower_bound = Column(Float, nullable=False, default=0.0) # Wilson lower bound
    trust_upper_bound = Column(Float, nullable=False, default=0.0) # Wilson upper bound
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    repository = relationship("Repository")
    snapshot = relationship("PilotSnapshot", back_populates="report", uselist=False, cascade="all, delete-orphan")


class PilotSnapshot(Base):
    """
    Immutable, replayable snapshot of a PilotReport's computed statistics.
    Ensures that once a pilot report is finalized, its details can never mutate or be tampered with.
    """
    __tablename__ = "pilot_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pilot_report_id = Column(UUID(as_uuid=True), ForeignKey("pilot_reports.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    snapshot_hash = Column(String, nullable=False, unique=True, index=True)
    payload = Column(JSONB, nullable=False)
    
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    snapshot_version = Column(Integer, nullable=False, default=1)
    
    # Relationships
    report = relationship("PilotReport", back_populates="snapshot")


@event.listens_for(PilotSnapshot, "before_update")
def prevent_pilot_snapshot_mutation(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: PilotSnapshot is immutable and cannot be mutated.")


@event.listens_for(PilotSnapshot, "before_delete")
def prevent_pilot_snapshot_deletion(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: PilotSnapshot is immutable and cannot be deleted.")


class PilotWorkspaceProfile(Base):
    """
    Represents the pilot packaging profile for a workspace, defining pricing,
    status, and duration of the operational evaluation pilot.
    """
    __tablename__ = "pilot_workspace_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pilot_name = Column(String, nullable=False)
    pilot_status = Column(String, nullable=False)
    pilot_start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    pilot_end_date = Column(DateTime, nullable=True)
    pricing_model = Column(String, nullable=False)
    monthly_price_usd = Column(Float, nullable=True)
    repo_limit = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "pilot_status IN ('ACTIVE', 'COMPLETED', 'CONVERTED', 'EXPIRED')",
            name="chk_pilot_status"
        ),
        CheckConstraint(
            "pricing_model IN ('FREE', 'FIXED_MONTHLY', 'INTERNAL_DESIGN_PARTNER')",
            name="chk_pricing_model"
        ),
    )

    # Relationships
    workspace = relationship("Workspace")
    enrollments = relationship("PilotRepositoryEnrollment", back_populates="pilot_profile", cascade="all, delete-orphan")
    report_snapshots = relationship("PilotReportSnapshot", back_populates="pilot_profile", cascade="all, delete-orphan")


class PilotRepositoryEnrollment(Base):
    """
    Represents the enrollment status of repositories under a specific organization's pilot.
    """
    __tablename__ = "pilot_repository_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pilot_profile_id = Column(UUID(as_uuid=True), ForeignKey("pilot_workspace_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_status = Column(String, nullable=False)
    enrolled_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    removed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "enrollment_status IN ('ACTIVE', 'REMOVED')",
            name="chk_enrollment_status"
        ),
        UniqueConstraint("pilot_profile_id", "repository_id", name="uq_pilot_profile_repository"),
    )

    # Relationships
    pilot_profile = relationship("PilotWorkspaceProfile", back_populates="enrollments")
    repository = relationship("Repository")


class PilotReportSnapshot(Base):
    """
    Represents append-only, immutable historical report snapshots for a pilot.
    """
    __tablename__ = "pilot_report_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pilot_profile_id = Column(UUID(as_uuid=True), ForeignKey("pilot_workspace_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    report_snapshot_hash = Column(String, nullable=False, unique=True, index=True)
    report_version = Column(Integer, nullable=False, default=1)
    reporting_window_start = Column(DateTime, nullable=False)
    reporting_window_end = Column(DateTime, nullable=False)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    report_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    pilot_profile = relationship("PilotWorkspaceProfile", back_populates="report_snapshots")


@event.listens_for(PilotReportSnapshot, "before_update")
def prevent_pilot_report_snapshot_mutation(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: PilotReportSnapshot is immutable and cannot be mutated.")


@event.listens_for(PilotReportSnapshot, "before_delete")
def prevent_pilot_report_snapshot_deletion(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError("Forensic Immutability Violation: PilotReportSnapshot is immutable and cannot be deleted.")
