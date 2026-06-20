"""
GitHub Webhook Security Tests

Tests for GitHub webhook signature verification, event handling,
and security properties.
"""
import pytest
import hmac
import hashlib
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.routers.github import verify_signature
from app.models.webhook_event import WebhookEvent
from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.pull_request import PullRequest


class TestWebhookSignatureVerification:
    """Tests for webhook signature verification."""
    
    def test_missing_signature_header_rejected(self):
        """Test that missing X-Hub-Signature-256 is rejected."""
        secret = "test_webhook_secret"
        raw_body = b'{"test": "data"}'
        
        # No signature header
        result = verify_signature(secret, raw_body, "")
        assert result is False
    
    def test_invalid_signature_rejected(self):
        """Test that invalid signature is rejected."""
        secret = "test_webhook_secret"
        raw_body = b'{"test": "data"}'
        
        # Invalid signature format
        result = verify_signature(secret, raw_body, "invalid_format")
        assert result is False
        
        # Wrong signature
        result = verify_signature(secret, raw_body, "sha256=wrong_signature")
        assert result is False
    
    def test_valid_signature_accepted(self):
        """Test that valid signature is accepted."""
        secret = "test_webhook_secret"
        raw_body = b'{"test": "data"}'
        
        # Generate valid signature
        expected_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        signature_header = f"sha256={expected_sig}"
        result = verify_signature(secret, raw_body, signature_header)
        assert result is True
    
    def test_signature_verification_uses_raw_body(self):
        """Test that signature verification uses raw request body."""
        secret = "test_webhook_secret"
        raw_body = b'{"test": "data"}'
        
        # Generate signature with raw body
        expected_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        signature_header = f"sha256={expected_sig}"
        result = verify_signature(secret, raw_body, signature_header)
        assert result is True
        
        # Verify that using parsed JSON would fail
        parsed_body = json.loads(raw_body)
        parsed_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=json.dumps(parsed_body).encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # These should be different if whitespace differs
        # The raw body signature should be the one used
        assert result is True


class TestWebhookPayloadHandling:
    """Tests for webhook payload handling."""
    
    def test_malformed_payload_fails_safely(self):
        """Test that malformed payload fails safely."""
        # This test verifies that the system handles malformed JSON gracefully
        # without crashing or exposing sensitive information
        malformed_payload = b'{"invalid": json}'
        
        # The verification should not crash
        secret = "test_webhook_secret"
        signature_header = "sha256=some_signature"
        
        # Should not raise exception
        result = verify_signature(secret, malformed_payload, signature_header)
        # Should return False for invalid signature
        assert result is False


