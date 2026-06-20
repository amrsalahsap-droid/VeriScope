import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, BigInteger, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Workspace scoping — every repo belongs to exactly one workspace
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # GitHub identity
    github_repo_id = Column(BigInteger, nullable=False)
    installation_id = Column(BigInteger, nullable=True, index=True)  # GitHub App installation that manages this repo
    owner = Column(String, nullable=True)
    name = Column(String, nullable=False)
    full_name = Column(String, nullable=False, index=True)
    default_branch = Column(String, nullable=True, default="main")

    # Visibility: PUBLIC / PRIVATE / INTERNAL / UNKNOWN
    visibility = Column(String, nullable=False, default="UNKNOWN")

    # Lifecycle
    is_active = Column(Boolean, nullable=False, default=False)
    selected_for_analysis = Column(Boolean, nullable=False, default=False)
    source = Column(String, nullable=False, default="GITHUB_APP")
    connection_status = Column(String, nullable=False, default="CONNECTED")

    # Framework and metadata
    framework_hints = Column(JSONB, nullable=True) # ["nextjs", "react", etc.]

    # CI/CD quality gate behavior
    ci_fail_on_partial = Column(Boolean, nullable=False, default=False)

    # Sync health
    last_synced_at = Column(DateTime, nullable=True)
    last_webhook_at = Column(DateTime, nullable=True)
    latest_pr_synced_at = Column(DateTime, nullable=True)  # Last time PRs were synced from GitHub
    latest_sync_status = Column(String, nullable=False, default="UNKNOWN")  # SUCCESS / FAILED / PENDING / UNKNOWN
    sync_error = Column(Text, nullable=True)

    # Legacy / retained for compatibility
    missing_from_github_since = Column(DateTime, nullable=True)
    last_seen_in_github_at = Column(DateTime, nullable=True)
    deactivation_reason = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def workspace_path(self) -> str:
        """Fallback property for local checkout path compatibility."""
        return ""

    @property
    def organization_id(self):
        return self.workspace_id

    @organization_id.setter
    def organization_id(self, value):
        self.workspace_id = value

    # Constraints
    __table_args__ = (
        UniqueConstraint("workspace_id", "github_repo_id", name="uq_repository_workspace_github"),
    )

    # Relationships
    acceptance_criteria = relationship("AcceptanceCriterion", back_populates="repository", cascade="all, delete-orphan")

    # Relationships
    workspace = relationship("Workspace", back_populates="repositories")
    recommendation_runs = relationship("RecommendationRun", back_populates="repository", cascade="all, delete-orphan")
    raw_artifacts = relationship("RawArtifact", back_populates="repository", cascade="all, delete-orphan")
    ingestion_jobs = relationship("IngestionJob", back_populates="repository", cascade="all, delete-orphan")
    file_dependencies = relationship("FileDependency", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    test_runs = relationship("TestRun", back_populates="repository", cascade="all, delete-orphan")
    coverage_reports = relationship("CoverageReport", back_populates="repository", cascade="all, delete-orphan")
    test_coverage_links = relationship("TestCoverageLink", back_populates="repository", cascade="all, delete-orphan")
    project_context_indices = relationship("ProjectContextIndex", back_populates="repository", cascade="all, delete-orphan")
    external_test_case_references = relationship("ExternalTestCaseReference", back_populates="repository", cascade="all, delete-orphan")
    integration_connections = relationship("IntegrationConnection", back_populates="repository", cascade="all, delete-orphan")
    external_work_items = relationship("ExternalWorkItem", back_populates="repository", cascade="all, delete-orphan")
    external_test_cases = relationship("ExternalTestCase", back_populates="repository", cascade="all, delete-orphan")
    behaviors = relationship("Behavior", back_populates="repository", cascade="all, delete-orphan")
    journeys = relationship("Journey", back_populates="repository", cascade="all, delete-orphan")
    semantic_entries = relationship("RepositorySemanticEntry", back_populates="repository", cascade="all, delete-orphan")
    architecture_nodes = relationship("ArchitectureNode", back_populates="repository", cascade="all, delete-orphan")
    architecture_edges = relationship("ArchitectureEdge", back_populates="repository", cascade="all, delete-orphan")
    releases = relationship("Release", back_populates="repository", cascade="all, delete-orphan")
    regression_suites = relationship("RegressionSuite", back_populates="repository", cascade="all, delete-orphan")
    pipeline_runs = relationship("PipelineRun", back_populates="repository", cascade="all, delete-orphan")
    # test_assets = relationship("TestAsset", back_populates="repository", cascade="all, delete-orphan")  # Table not yet migrated




