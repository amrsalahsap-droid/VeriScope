"""
Repository CI Token Model

Stores CI/CD pipeline tokens for repository authentication.
Tokens are stored as hashes only; raw tokens are never persisted.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
import hashlib
import secrets

from app.db.base import Base


class RepositoryCIToken(Base):
    """CI token for repository-level pipeline authentication."""
    
    __tablename__ = "repository_ci_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    scopes = Column(Text, nullable=False, default="pipeline:trigger,artifact:read")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token using SHA-256."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def verify_token(token: str, token_hash: str) -> bool:
        """Verify a token against its hash."""
        return RepositoryCIToken.hash_token(token) == token_hash
    
    def is_revoked(self) -> bool:
        """Check if token is revoked."""
        return self.revoked_at is not None or not self.is_active
    
    def is_valid(self) -> bool:
        """Check if token is valid (not revoked and active)."""
        return not self.is_revoked() and self.is_active
