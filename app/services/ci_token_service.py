"""
CI Token Service

Manages CI/CD pipeline tokens for repository authentication.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.ci_token import RepositoryCIToken
from app.models.repository import Repository
from app.models.ci_token_audit import ActorType
from app.schemas.ci_token import CITokenCreate, CITokenResponse
from app.services.ci_token_audit_service import CITokenAuditService


class CITokenService:
    """Service for managing CI tokens."""
    
    def create_token(
        self, 
        db: Session, 
        repository_id: UUID, 
        token_in: CITokenCreate,
        created_by: Optional[UUID] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenResponse:
        """Create a new CI token. Returns raw token only once."""
        # Verify repository exists
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError("Repository not found")
        
        # Generate token and hash
        raw_token = RepositoryCIToken.generate_token()
        token_hash = RepositoryCIToken.hash_token(raw_token)
        
        # Create token record
        db_token = RepositoryCIToken(
            repository_id=repository_id,
            name=token_in.name,
            token_hash=token_hash,
            scopes=token_in.scopes,
            created_by=created_by,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        
        # Log audit event
        CITokenAuditService.log_token_created(
            db=db,
            repository_id=str(repository_id),
            token_id=str(db_token.id),
            actor_type=ActorType.USER if created_by else ActorType.SYSTEM,
            source_ip=source_ip,
            user_agent=user_agent
        )
        
        # Return response with raw token (shown only once)
        return CITokenResponse(
            id=db_token.id,
            repository_id=db_token.repository_id,
            name=db_token.name,
            scopes=db_token.scopes,
            created_at=db_token.created_at,
            last_used_at=db_token.last_used_at,
            is_active=db_token.is_active,
            raw_token=raw_token
        )
    
    def list_tokens(self, db: Session, repository_id: UUID) -> List[CITokenResponse]:
        """List all CI tokens for a repository (without raw tokens)."""
        tokens = db.query(RepositoryCIToken).filter(
            RepositoryCIToken.repository_id == repository_id
        ).all()
        
        return [
            CITokenResponse(
                id=token.id,
                repository_id=token.repository_id,
                name=token.name,
                scopes=token.scopes,
                created_at=token.created_at,
                last_used_at=token.last_used_at,
                is_active=token.is_active,
                raw_token=None  # Never include raw token in list
            )
            for token in tokens
        ]
    
    def revoke_token(
        self, 
        db: Session, 
        repository_id: UUID, 
        token_id: UUID,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Revoke a CI token."""
        token = db.query(RepositoryCIToken).filter(
            RepositoryCIToken.id == token_id,
            RepositoryCIToken.repository_id == repository_id
        ).first()
        
        if not token:
            raise ValueError("Token not found")
        
        token.revoked_at = datetime.utcnow()
        token.is_active = False
        db.commit()
        
        # Log audit event
        CITokenAuditService.log_token_revoked(
            db=db,
            repository_id=str(repository_id),
            token_id=str(token_id),
            actor_type=ActorType.USER,
            source_ip=source_ip,
            user_agent=user_agent
        )
        
        return True
    
    def verify_token(
        self, 
        db: Session, 
        token: str,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[RepositoryCIToken]:
        """Verify a CI token and return the token record if valid."""
        token_hash = RepositoryCIToken.hash_token(token)
        
        db_token = db.query(RepositoryCIToken).filter(
            RepositoryCIToken.token_hash == token_hash
        ).first()
        
        if not db_token:
            # Log rejection for invalid token - skip audit logging since we don't know the repository
            # Audit logging requires a valid repository_id which we don't have for invalid tokens
            return None
        
        if not db_token.is_valid():
            # Log rejection for invalid/expired/revoked token
            reason = "Token revoked" if db_token.revoked_at else "Token expired"
            CITokenAuditService.log_token_rejected(
                db=db,
                repository_id=str(db_token.repository_id),
                reason=reason,
                token_id=str(db_token.id),
                source_ip=source_ip,
                user_agent=user_agent
            )
            return None
        
        # Update last used timestamp
        db_token.last_used_at = datetime.utcnow()
        db.commit()
        
        # Log successful token usage
        CITokenAuditService.log_token_used(
            db=db,
            repository_id=str(db_token.repository_id),
            token_id=str(db_token.id),
            source_ip=source_ip,
            user_agent=user_agent
        )
        
        return db_token
    
    def get_token_by_id(self, db: Session, repository_id: UUID, token_id: UUID) -> Optional[CITokenResponse]:
        """Get a token by ID (without raw token)."""
        token = db.query(RepositoryCIToken).filter(
            RepositoryCIToken.id == token_id,
            RepositoryCIToken.repository_id == repository_id
        ).first()
        
        if not token:
            return None
        
        return CITokenResponse(
            id=token.id,
            repository_id=token.repository_id,
            name=token.name,
            scopes=token.scopes,
            created_at=token.created_at,
            last_used_at=token.last_used_at,
            is_active=token.is_active,
            raw_token=None
        )
