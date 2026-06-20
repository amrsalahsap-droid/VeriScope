"""
Integration Connection Model

Stores connections to external systems (Jira, Azure DevOps, TestRail, Xray, Zephyr, etc.)
in a provider-agnostic way to support multiple external systems without hardcoding one vendor.

Credentials are encrypted using Fernet (AES) encryption with a key from CREDENTIAL_ENCRYPTION_KEY environment variable.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, Index
from app.db.base import Base


class IntegrationConnection(Base):
    """
    Connection to an external system (Jira, Azure DevOps, TestRail, Xray, Zephyr, etc.).
    
    This model provides a provider-agnostic foundation for storing external system
    connections. Each connection is workspace-scoped and can optionally be bound to
    a specific repository for repository-level integrations.
    
    Provider types:
    - JIRA: Atlassian Jira for work items and test management
    - AZURE_DEVOPS: Microsoft Azure DevOps for work items and test management
    - TESTRAIL: TestRail for test case management
    - XRAY: Xray for Jira test management
    - ZEPHYR: Zephyr for Jira test management
    - MANUAL_CSV: Manual CSV import for test cases
    
    Status values:
    - CONNECTED: Connection is active and validated
    - DISCONNECTED: Connection exists but is not active
    - ERROR: Connection failed validation or sync
    - NEEDS_REAUTH: Credentials expired or need refresh
    
    Security:
    - Credentials are encrypted using Fernet (AES) encryption
    - Encryption key from CREDENTIAL_ENCRYPTION_KEY environment variable
    - Never log plaintext credentials
    - Credentials stored in encrypted_credentials JSONB field (encrypted string)
    - credentials_encrypted_at tracks when credentials were last encrypted
    - credentials_version tracks encryption format version for migrations
    """
    __tablename__ = "integration_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Workspace scoping - every connection belongs to exactly one workspace
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Optional repository binding for repository-level integrations
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    # Provider identification
    provider = Column(
        String,
        nullable=False,
        index=True
    )  # JIRA, AZURE_DEVOPS, TESTRAIL, XRAY, ZEPHYR, MANUAL_CSV
    
    display_name = Column(
        String,
        nullable=False
    )  # User-friendly name (e.g., "Company Jira", "TestRail QA")
    
    # Connection status
    status = Column(
        String,
        nullable=False,
        default="DISCONNECTED",
        index=True
    )  # CONNECTED, DISCONNECTED, ERROR, NEEDS_REAUTH
    
    # Connection configuration
    base_url = Column(
        String,
        nullable=True
    )  # Base URL for the external system (e.g., "https://company.atlassian.net")
    
    # Encrypted credentials (encrypted string, not JSONB)
    # Stores Fernet-encrypted credential dictionary as a string
    # Use CredentialEncryptionService to encrypt/decrypt
    encrypted_credentials = Column(
        Text,
        nullable=True
    )
    
    # Credential encryption tracking
    credentials_encrypted_at = Column(
        DateTime,
        nullable=True
    )  # Timestamp when credentials were last encrypted
    
    credentials_version = Column(
        Integer,
        nullable=False,
        default=1
    )  # Encryption format version (for migrations)
    
    # Provider-specific metadata (JSONB)
    # Structure: {"external_project_id": "PROJ-123", "default_test_suite_id": 456, ...}
    provider_metadata = Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Sync tracking
    last_sync_at = Column(
        DateTime,
        nullable=True
    )
    last_sync_status = Column(
        String,
        nullable=True
    )  # SUCCESS, FAILED, PARTIAL
    last_sync_error = Column(
        Text,
        nullable=True
    )
    
    # Lifecycle
    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Constraints
    __table_args__ = (
        # Unique constraint: workspace_id + provider + display_name
        # Allows multiple connections per provider with different display names
        UniqueConstraint(
            'workspace_id',
            'provider',
            'display_name',
            name='uq_workspace_provider_display_name'
        ),
        # Index for filtering by workspace and status
        Index('ix_integration_connections_workspace_status', 'workspace_id', 'status'),
        # Index for filtering by repository
        Index('ix_integration_connections_repository', 'repository_id'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="integration_connections")
    repository = relationship("Repository", back_populates="integration_connections")
    external_work_items = relationship("ExternalWorkItem", back_populates="integration_connection", cascade="all, delete-orphan")
    external_test_cases = relationship("ExternalTestCase", back_populates="integration_connection", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<IntegrationConnection(id={self.id}, provider={self.provider}, "
            f"display_name={self.display_name}, status={self.status})>"
        )
