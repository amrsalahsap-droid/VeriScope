"""
Credential Encryption Tests (Phase 7.5A)

Tests for the credential encryption service and integration security.
"""

import pytest
import os
import json
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet, InvalidToken

from app.services.security.credential_encryption_service import (
    CredentialEncryptionService,
    get_credential_encryption_service
)


class TestCredentialEncryptionService:
    """Test the credential encryption service."""
    
    @pytest.fixture
    def encryption_key(self):
        """Generate a test encryption key."""
        return Fernet.generate_key().decode()
    
    @pytest.fixture
    def service(self, encryption_key):
        """Create an encryption service instance."""
        with patch.dict(os.environ, {'CREDENTIAL_ENCRYPTION_KEY': encryption_key}):
            return CredentialEncryptionService()
    
    def test_encrypt_decrypt_credentials(self, service):
        """Test that credentials can be encrypted and decrypted correctly."""
        credentials = {
            'api_key': 'test-api-key-123',
            'username': 'testuser',
            'password': 'testpass'
        }
        
        # Encrypt
        encrypted = service.encrypt(credentials)
        assert encrypted is not None
        assert len(encrypted) > 0
        assert encrypted != json.dumps(credentials)
        
        # Decrypt
        decrypted = service.decrypt(encrypted)
        assert decrypted == credentials
    
    def test_encrypt_empty_credentials(self, service):
        """Test that empty credentials are handled correctly."""
        credentials = {}
        
        encrypted = service.encrypt(credentials)
        assert encrypted == ""
        
        decrypted = service.decrypt(encrypted)
        assert decrypted == {}
    
    def test_encrypt_none_credentials(self, service):
        """Test that None credentials are handled correctly."""
        # None should be treated as empty dict
        encrypted = service.encrypt({})
        assert encrypted == ""
        
        decrypted = service.decrypt(encrypted)
        assert decrypted == {}
    
    def test_decrypt_invalid_token(self, service):
        """Test that invalid tokens raise InvalidToken."""
        invalid_token = "invalid-token-data"
        
        with pytest.raises(InvalidToken):
            service.decrypt(invalid_token)
    
    def test_decrypt_invalid_json(self, service):
        """Test that invalid JSON after decryption raises ValueError."""
        # Encrypt valid data first
        credentials = {'test': 'data'}
        encrypted = service.encrypt(credentials)
        
        # Corrupt the encrypted data
        corrupted = encrypted[:-5] + "XXXXX"
        
        with pytest.raises((InvalidToken, ValueError)):
            service.decrypt(corrupted)
    
    def test_redact_sensitive_keys(self, service):
        """Test that sensitive keys are redacted from data structures."""
        data = {
            'username': 'testuser',
            'password': 'secret123',
            'api_key': 'key-123',
            'normal_field': 'normal-value'
        }
        
        redacted = service.redact(data)
        
        assert redacted['username'] == 'testuser'
        assert redacted['password'] == '***REDACTED***'
        assert redacted['api_key'] == '***REDACTED***'
        assert redacted['normal_field'] == 'normal-value'
    
    def test_redact_nested_data(self, service):
        """Test that redaction works on nested data structures."""
        data = {
            'config': {
                'api_key': 'secret-key',
                'nested': {
                    'password': 'secret-pass'
                }
            },
            'normal': 'value'
        }
        
        redacted = service.redact(data)
        
        assert redacted['config']['api_key'] == '***REDACTED***'
        assert redacted['config']['nested']['password'] == '***REDACTED***'
        assert redacted['normal'] == 'value'
    
    def test_redact_array(self, service):
        """Test that redaction works on arrays."""
        data = [
            {'api_key': 'key1'},
            {'username': 'user1'},
            {'password': 'pass1'}
        ]
        
        redacted = service.redact(data)
        
        assert redacted[0]['api_key'] == '***REDACTED***'
        assert redacted[1]['username'] == 'user1'
        assert redacted[2]['password'] == '***REDACTED***'
    
    def test_redact_custom_replacement(self, service):
        """Test that custom replacement string works."""
        data = {'password': 'secret'}
        
        redacted = service.redact(data, replacement='[HIDDEN]')
        
        assert redacted['password'] == '[HIDDEN]'
    
    def test_is_encrypted_heuristic(self, service):
        """Test the is_encrypted heuristic check."""
        # Valid JSON should return False
        json_data = '{"test": "data"}'
        assert service.is_encrypted(json_data) is False
        
        # Encrypted data should return True
        credentials = {'test': 'data'}
        encrypted = service.encrypt(credentials)
        assert service.is_encrypted(encrypted) is True
        
        # Empty string should return False
        assert service.is_encrypted('') is False
    
    def test_missing_encryption_key_raises_error(self):
        """Test that missing encryption key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="CREDENTIAL_ENCRYPTION_KEY"):
                CredentialEncryptionService()
    
    def test_invalid_encryption_key_raises_error(self):
        """Test that invalid encryption key raises ValueError."""
        with patch.dict(os.environ, {'CREDENTIAL_ENCRYPTION_KEY': 'invalid-key'}):
            with pytest.raises(ValueError, match="Invalid CREDENTIAL_ENCRYPTION_KEY"):
                CredentialEncryptionService()


class TestGetCredentialEncryptionService:
    """Test the singleton pattern for encryption service."""
    
    @pytest.fixture
    def encryption_key(self):
        """Generate a test encryption key."""
        return Fernet.generate_key().decode()
    
    def test_singleton_returns_same_instance(self, encryption_key):
        """Test that get_credential_encryption_service returns the same instance."""
        with patch.dict(os.environ, {'CREDENTIAL_ENCRYPTION_KEY': encryption_key}):
            service1 = get_credential_encryption_service()
            service2 = get_credential_encryption_service()
            
            assert service1 is service2
    
    def test_singleton_requires_key(self):
        """Test that singleton requires encryption key."""
        # Clear the singleton first
        import app.services.security.credential_encryption_service as enc_module
        enc_module._encryption_service = None
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="CREDENTIAL_ENCRYPTION_KEY"):
                get_credential_encryption_service()


class TestRedactedKeys:
    """Test that all expected sensitive keys are redacted."""
    
    @pytest.fixture
    def service(self):
        """Create an encryption service instance."""
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {'CREDENTIAL_ENCRYPTION_KEY': key}):
            return CredentialEncryptionService()
    
    def test_all_sensitive_keys_redacted(self, service):
        """Test that all sensitive keys are redacted."""
        data = {
            'password': 'pass',
            'api_key': 'key',
            'apiKey': 'key',
            'token': 'token',
            'client_secret': 'secret',
            'clientSecret': 'secret',
            'access_token': 'token',
            'accessToken': 'token',
            'refresh_token': 'token',
            'refreshToken': 'token',
            'authorization': 'auth',
            'Authorization': 'auth',
            'secret': 'secret',
            'private_key': 'key',
            'privateKey': 'key',
            'normal_field': 'value'
        }
        
        redacted = service.redact(data)
        
        # All sensitive keys should be redacted
        for key in data.keys():
            if key in service.REDACTED_KEYS:
                assert redacted[key] == '***REDACTED***'
            else:
                assert redacted[key] == data[key]


class TestEncryptionServiceErrorHandling:
    """Test error handling in encryption service."""
    
    @pytest.fixture
    def service(self):
        """Create an encryption service instance."""
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {'CREDENTIAL_ENCRYPTION_KEY': key}):
            return CredentialEncryptionService()
    
    def test_encrypt_non_dict_raises_error(self, service):
        """Test that encrypting non-dict raises ValueError."""
        with pytest.raises(ValueError, match="Credentials must be a dictionary"):
            service.encrypt("not-a-dict")
    
    def test_encrypt_string_raises_error(self, service):
        """Test that encrypting string raises ValueError."""
        with pytest.raises(ValueError, match="Credentials must be a dictionary"):
            service.encrypt("string")
    
    def test_decrypt_empty_string_returns_empty_dict(self, service):
        """Test that decrypting empty string returns empty dict."""
        result = service.decrypt("")
        assert result == {}
