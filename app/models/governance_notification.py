from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class NotificationStatus(str, enum.Enum):
    """Notification status."""
    UNREAD = "UNREAD"
    READ = "READ"
    DISMISSED = "DISMISSED"
    FAILED = "FAILED"


class NotificationSeverity(str, enum.Enum):
    """Notification severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotificationType(str, enum.Enum):
    """Notification types."""
    POLICY_DRIFT_DETECTED = "POLICY_DRIFT_DETECTED"
    HIGH_RISK_DRIFT_DETECTED = "HIGH_RISK_DRIFT_DETECTED"
    CRITICAL_RISK_DRIFT_DETECTED = "CRITICAL_RISK_DRIFT_DETECTED"
    EXCEPTION_REQUESTED = "EXCEPTION_REQUESTED"
    EXCEPTION_APPROVAL_PENDING = "EXCEPTION_APPROVAL_PENDING"
    EXCEPTION_APPROVED = "EXCEPTION_APPROVED"
    EXCEPTION_REJECTED = "EXCEPTION_REJECTED"
    EXCEPTION_REVOKED = "EXCEPTION_REVOKED"
    EXCEPTION_EXPIRING_SOON = "EXCEPTION_EXPIRING_SOON"
    EXCEPTION_EXPIRED = "EXCEPTION_EXPIRED"
    ROLE_EXPIRING_SOON = "ROLE_EXPIRING_SOON"
    ROLE_EXPIRED = "ROLE_EXPIRED"
    COMPLIANCE_SCORE_DROPPED = "COMPLIANCE_SCORE_DROPPED"
    GOVERNANCE_REVIEW_DUE = "GOVERNANCE_REVIEW_DUE"
    GOVERNANCE_REVIEW_CREATED = "GOVERNANCE_REVIEW_CREATED"
    BULK_OPERATION_COMPLETED = "BULK_OPERATION_COMPLETED"
    BULK_OPERATION_PARTIAL_FAILURE = "BULK_OPERATION_PARTIAL_FAILURE"
    EXECUTIVE_REPORT_READY = "EXECUTIVE_REPORT_READY"


class GovernanceNotification(Base):
    """Governance notification model."""
    __tablename__ = "governance_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True, index=True)
    recipient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    notification_type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    severity = Column(SQLEnum(NotificationSeverity), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    source_entity_type = Column(String(100), nullable=True, index=True)
    source_entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    status = Column(SQLEnum(NotificationStatus), nullable=False, default=NotificationStatus.UNREAD, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    
    delivery_metadata = Column(JSON, nullable=True)

    @property
    def organization_id(self):
        return self.workspace_id

    @organization_id.setter
    def organization_id(self, value):
        self.workspace_id = value

    def __repr__(self):
        return f"<GovernanceNotification(id={self.id}, type={self.notification_type}, recipient={self.recipient_user_id})>"
