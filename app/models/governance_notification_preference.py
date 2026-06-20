from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from app.db.base import Base
from app.models.governance_notification import NotificationType, NotificationSeverity


class GovernanceNotificationPreference(Base):
    """Governance notification preference model."""
    __tablename__ = "governance_notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    notification_type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    
    enabled = Column(Boolean, nullable=False, default=True)
    minimum_severity = Column(SQLEnum(NotificationSeverity), nullable=False, default=NotificationSeverity.INFO)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def organization_id(self):
        return self.workspace_id

    @organization_id.setter
    def organization_id(self, value):
        self.workspace_id = value

    def __repr__(self):
        return f"<GovernanceNotificationPreference(user_id={self.user_id}, type={self.notification_type}, enabled={self.enabled})>"
