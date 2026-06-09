"""
Signed URL generator for lightweight feedback from GitHub PR comments.

Generates time-limited, signed URLs that can be used to capture feedback
without requiring full authentication.
"""

import hmac
import hashlib
import base64
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.config import settings


class SignedURLGenerator:
    """Generates and validates signed URLs for feedback collection."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the signed URL generator.
        
        Args:
            secret_key: Secret key for signing. If not provided, uses settings.
        """
        self.secret_key = secret_key or settings.SECRET_KEY
    
    def generate_feedback_url(
        self,
        recommendation_run_id: str,
        feedback_type: str,
        expires_in_hours: int = 24
    ) -> str:
        """
        Generate a signed feedback URL.
        
        Args:
            recommendation_run_id: The recommendation run ID
            feedback_type: Type of feedback (useful, not-useful, missing-tests)
            expires_in_hours: URL expiration time in hours
            
        Returns:
            Signed URL for feedback
        """
        # Create payload
        payload = {
            "recommendation_run_id": recommendation_run_id,
            "feedback_type": feedback_type,
            "expires_at": (datetime.utcnow() + timedelta(hours=expires_in_hours)).isoformat(),
            "timestamp": int(time.time())
        }
        
        # Sign the payload
        signature = self._sign_payload(payload)
        
        # Encode payload and signature
        encoded_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode()
        
        encoded_signature = base64.urlsafe_b64encode(signature).decode()
        
        # Construct URL
        base_url = settings.API_BASE_URL or "http://localhost:8000"
        return f"{base_url}/api/recommendations/{recommendation_run_id}/feedback/{feedback_type}?token={encoded_payload}&sig={encoded_signature}"
    
    def validate_signature(
        self,
        token: str,
        signature: str
    ) -> Optional[Dict]:
        """
        Validate a signed token.
        
        Args:
            token: Base64-encoded payload
            signature: Base64-encoded signature
            
        Returns:
            Payload if valid, None otherwise
        """
        try:
            # Decode payload and signature
            payload_json = base64.urlsafe_b64decode(token).decode()
            payload = json.loads(payload_json)
            signature_bytes = base64.urlsafe_b64decode(signature)
            
            # Verify signature
            expected_signature = self._sign_payload(payload)
            if not hmac.compare_digest(signature_bytes, expected_signature):
                return None
            
            # Check expiration
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.utcnow() > expires_at:
                return None
            
            return payload
        except Exception:
            return None
    
    def _sign_payload(self, payload: Dict) -> bytes:
        """
        Sign a payload using HMAC-SHA256.
        
        Args:
            payload: Payload to sign
            
        Returns:
            Signature bytes
        """
        payload_json = json.dumps(payload, sort_keys=True)
        return hmac.new(
            self.secret_key.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).digest()


# Singleton instance
signed_url_generator = SignedURLGenerator()
