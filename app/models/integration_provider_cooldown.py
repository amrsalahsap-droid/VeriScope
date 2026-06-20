"""
Integration Provider Cooldown Model

Tracks provider-level cooldowns to prevent hammering providers during rate limits or failures.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer
from app.db.base import Base


class IntegrationProviderCooldown(Base):
    """
    Provider-level cooldown to prevent hammering providers.
    
    When a provider hits a rate limit or experiences repeated failures,
    a cooldown is set to prevent further sync attempts until the cooldown expires.
    """
    __tablename__ = "integration_provider_cooldowns"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)  # TESTRAIL, XRAY, ZEPHYR
    cooldown_until = Column(DateTime, nullable=False, index=True)
    reason = Column(String, nullable=False)  # RATE_LIMITED, REPEATED_FAILURES, etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def is_active(self) -> bool:
        """Check if cooldown is currently active."""
        return datetime.utcnow() < self.cooldown_until
    
    def remaining_seconds(self) -> int:
        """Get remaining cooldown seconds."""
        if not self.is_active():
            return 0
        delta = self.cooldown_until - datetime.utcnow()
        return max(0, int(delta.total_seconds()))
