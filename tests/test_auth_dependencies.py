"""
Authentication Dependency Tests

Tests to verify JWT token validation and workspace scoping logic.
"""
import pytest
import uuid
from datetime import datetime, timezone
import jwt
from fastapi import HTTPException

from app.config import settings


def create_jwt_token(user_id: uuid.UUID, workspace_id: uuid.UUID, expired: bool = False) -> str:
    """Create a test JWT token."""
    if expired:
        exp = int(datetime.now(timezone.utc).timestamp()) - 3600
        iat = int(datetime.now(timezone.utc).timestamp()) - 7200
    else:
        exp = int(datetime.now(timezone.utc).timestamp()) + 3600
        iat = int(datetime.now(timezone.utc).timestamp())
    
    payload = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "email": "test@example.com",
        "name": "Test User",
        "auth_provider": "github",
        "provider_user_id": "github_123456",
        "exp": exp,
        "iat": iat
    }
    return jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")


def decode_jwt_token(token: str) -> dict:
    """Decode and validate a JWT token, returning the payload."""
    try:
        payload = jwt.decode(
            token,
            settings.STATE_SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token."
        )


class TestJWTTokenValidation:
    """Test JWT token validation."""
    
    def test_valid_token_decodes_correctly(self):
        """Test that a valid token decodes correctly."""
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        
        token = create_jwt_token(user_id, workspace_id)
        
        # Verify token decodes correctly
        payload = decode_jwt_token(token)
        assert payload["workspace_id"] == str(workspace_id)
        assert payload["sub"] == str(user_id)
        assert payload["email"] == "test@example.com"
    
    def test_expired_token_raises_exception(self):
        """Test that an expired token raises HTTPException."""
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        
        # Create expired token
        expired_token = create_jwt_token(user_id, workspace_id, expired=True)
        
        # Try to use expired token
        try:
            decode_jwt_token(expired_token)
            assert False, "Expired token should raise exception"
        except HTTPException as e:
            assert e.status_code == 401
            assert "expired" in str(e.detail).lower()
    
    def test_invalid_token_raises_exception(self):
        """Test that an invalid token raises HTTPException."""
        # Create a completely invalid token
        invalid_token = "invalid.token.here"
        
        # Try to use invalid token
        try:
            decode_jwt_token(invalid_token)
            assert False, "Invalid token should raise exception"
        except HTTPException as e:
            assert e.status_code == 401
    
    def test_token_without_workspace_id_still_decodes(self):
        """Test that a token without workspace_id still decodes but won't have the field."""
        user_id = uuid.uuid4()
        
        # Create token without workspace_id
        payload = {
            "sub": str(user_id),
            "email": "test@example.com",
            "name": "Test User",
            "auth_provider": "github",
            "provider_user_id": "github_123456",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "iat": int(datetime.now(timezone.utc).timestamp())
        }
        token = jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")
        
        # Decode token
        decoded = decode_jwt_token(token)
        
        # Verify workspace_id is not present
        assert "workspace_id" not in decoded
    
    def test_token_with_wrong_secret_raises_exception(self):
        """Test that a token signed with wrong secret raises HTTPException."""
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        
        # Create token with wrong secret
        payload = {
            "sub": str(user_id),
            "workspace_id": str(workspace_id),
            "email": "test@example.com",
            "name": "Test User",
            "auth_provider": "github",
            "provider_user_id": "github_123456",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "iat": int(datetime.now(timezone.utc).timestamp())
        }
        token = jwt.encode(payload, "wrong_secret", algorithm="HS256")
        
        # Try to use token with wrong secret
        try:
            decode_jwt_token(token)
            assert False, "Token with wrong secret should raise exception"
        except HTTPException as e:
            assert e.status_code == 401


class TestWorkspaceScopingLogic:
    """Test workspace scoping logic."""
    
    def test_different_workspace_ids_are_isolated(self):
        """Test that different workspace IDs are properly isolated."""
        workspace1_id = uuid.uuid4()
        workspace2_id = uuid.uuid4()
        
        # Create tokens for different workspaces
        token1 = create_jwt_token(uuid.uuid4(), workspace1_id)
        token2 = create_jwt_token(uuid.uuid4(), workspace2_id)
        
        # Verify each token returns its own workspace_id
        payload1 = decode_jwt_token(token1)
        payload2 = decode_jwt_token(token2)
        
        assert payload1["workspace_id"] == str(workspace1_id)
        assert payload2["workspace_id"] == str(workspace2_id)
        assert payload1["workspace_id"] != payload2["workspace_id"]
    
    def test_same_workspace_id_consistent_across_tokens(self):
        """Test that the same workspace ID is consistent across different tokens."""
        workspace_id = uuid.uuid4()
        
        # Create multiple tokens for the same workspace
        token1 = create_jwt_token(uuid.uuid4(), workspace_id)
        token2 = create_jwt_token(uuid.uuid4(), workspace_id)
        
        # Verify both tokens return the same workspace_id
        payload1 = decode_jwt_token(token1)
        payload2 = decode_jwt_token(token2)
        
        assert payload1["workspace_id"] == str(workspace_id)
        assert payload2["workspace_id"] == str(workspace_id)
        assert payload1["workspace_id"] == payload2["workspace_id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
