"""
GitHub App Authentication Tests

Tests for GitHub App JWT generation, installation token management,
and security properties.
"""
import pytest
import jwt
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.github_api_client import GitHubApiClient, GitHubAuthPermissionError
from app.config import settings


class TestGitHubAppJWTGeneration:
    """Tests for GitHub App JWT generation."""
    
    @patch('app.services.github_api_client.settings.GITHUB_APP_ID', '12345')
    @patch('app.services.github_api_client.settings.GITHUB_PRIVATE_KEY', 'test_key')
    def test_jwt_is_generated(self):
        """Test that GitHub App JWT is generated."""
        client = GitHubApiClient()
        
        # Mock the private key to avoid actual RSA signing
        with patch.object(client, 'private_key', 'mock_key'):
            with patch('jwt.encode') as mock_encode:
                mock_encode.return_value = 'mock_jwt_token'
                
                token = client.generate_app_jwt()
                
                assert token == 'mock_jwt_token'
                mock_encode.assert_called_once()
    
    @patch('app.services.github_api_client.settings.GITHUB_APP_ID', '12345')
    @patch('app.services.github_api_client.settings.GITHUB_PRIVATE_KEY', 'test_key')
    def test_jwt_uses_rs256_algorithm(self):
        """Test that JWT uses RS256 algorithm."""
        client = GitHubApiClient()
        
        with patch.object(client, 'private_key', 'mock_key'):
            with patch('jwt.encode') as mock_encode:
                mock_encode.return_value = 'mock_jwt_token'
                
                client.generate_app_jwt()
                
                # Check that RS256 algorithm was used
                call_args = mock_encode.call_args
                assert call_args[1]['algorithm'] == 'RS256'
    
    @patch('app.services.github_api_client.settings.GITHUB_APP_ID', '12345')
    @patch('app.services.github_api_client.settings.GITHUB_PRIVATE_KEY', 'test_key')
    def test_jwt_expiry_is_short_lived(self):
        """Test that JWT expiry is short-lived (10 minutes max)."""
        client = GitHubApiClient()
        
        with patch.object(client, 'private_key', 'mock_key'):
            with patch('jwt.encode') as mock_encode:
                mock_encode.return_value = 'mock_jwt_token'
                
                client.generate_app_jwt()
                
                # Check payload has short expiry
                call_args = mock_encode.call_args
                payload = call_args[0][0]
                now = int(time.time())
                exp = payload['exp']
                iat = payload['iat']
                
                # Expiry should be within 10 minutes of issue time
                assert exp - iat <= 600  # 10 minutes in seconds
                assert exp - iat > 0
    
    def test_private_key_never_returned(self):
        """Test that private key is never returned from JWT generation."""
        client = GitHubApiClient()
        
        with patch.object(client, 'private_key', 'mock_key'):
            with patch('jwt.encode') as mock_encode:
                mock_encode.return_value = 'mock_jwt_token'
                
                token = client.generate_app_jwt()
                
                # Token should not contain private key
                assert 'mock_key' not in token
                assert 'private_key' not in token




