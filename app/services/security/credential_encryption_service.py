"""
Credential Encryption Service

Provides encryption, decryption, and redaction for provider credentials.
Uses Fernet (AES) encryption with a key from environment variable.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings

logger = logging.getLogger("veriscope.credential_encryption")


class CredentialEncryptionService:
    """
    Service for encrypting, decrypting, and redacting provider credentials.
    
    Uses Fernet (AES-128 in CBC mode with PKCS7 padding) for encryption.
    The encryption key must be set in the CREDENTIAL_ENCRYPTION_KEY environment variable.
    """
    
    # Secret keys to redact from payloads
    REDACTED_KEYS = {
        'password', 'api_key', 'apiKey', 'token', 'client_secret', 'clientSecret',
        'access_token', 'accessToken', 'refresh_token', 'refreshToken',
        'authorization', 'Authorization', 'secret', 'private_key', 'privateKey'
    }
    
    def __init__(self):
        """Initialize the encryption service with the encryption key from environment."""
        self._key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        
        if not self._key:
            logger.error("CREDENTIAL_ENCRYPTION_KEY environment variable not set")
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY environment variable must be set. "
                "Generate a key with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        
        try:
            self._fernet = Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
            logger.info("Credential encryption service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Fernet with encryption key: {e}")
            raise ValueError(f"Invalid CREDENTIAL_ENCRYPTION_KEY: {e}")
    
    def encrypt(self, credentials: Dict[str, Any]) -> str:
        """
        Encrypt credential dictionary to a string.
        
        Args:
            credentials: Dictionary of credential fields (e.g., api_key, password)
            
        Returns:
            Encrypted string (base64-encoded)
            
        Raises:
            ValueError: If credentials is not a dictionary
        """
        if not isinstance(credentials, dict):
            raise ValueError("Credentials must be a dictionary")
        
        if not credentials:
            return ""
        
        try:
            # Convert to JSON string
            credentials_json = json.dumps(credentials)
            
            # Encrypt
            encrypted_bytes = self._fernet.encrypt(credentials_json.encode('utf-8'))
            
            # Return as string
            return encrypted_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encrypt credentials: {e}")
            raise RuntimeError(f"Credential encryption failed: {e}")
    
    def decrypt(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt encrypted credential string to a dictionary.
        
        Args:
            encrypted_data: Encrypted string from encrypt()
            
        Returns:
            Dictionary of credential fields
            
        Raises:
            InvalidToken: If decryption fails (wrong key or corrupted data)
        """
        if not encrypted_data:
            return {}
        
        try:
            # Decrypt
            decrypted_bytes = self._fernet.decrypt(encrypted_data.encode('utf-8'))
            
            # Parse JSON
            credentials = json.loads(decrypted_bytes.decode('utf-8'))
            
            if not isinstance(credentials, dict):
                raise ValueError("Decrypted data is not a dictionary")
            
            return credentials
            
        except InvalidToken as e:
            logger.error(f"Failed to decrypt credentials: invalid token (wrong key or corrupted data)")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decrypt credentials: invalid JSON")
            raise ValueError(f"Decrypted data is not valid JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            raise RuntimeError(f"Credential decryption failed: {e}")
    
    def redact(self, data: Any, replacement: str = "***REDACTED***") -> Any:
        """
        Redact sensitive credential keys from a data structure.
        
        Recursively processes dictionaries and lists, replacing values for keys
        that match sensitive credential names.
        
        Args:
            data: Data structure to redact (dict, list, or other)
            replacement: String to replace sensitive values with
            
        Returns:
            Redacted copy of the data structure
        """
        if isinstance(data, dict):
            redacted = {}
            for key, value in data.items():
                if key in self.REDACTED_KEYS:
                    redacted[key] = replacement
                elif isinstance(value, (dict, list)):
                    redacted[key] = self.redact(value, replacement)
                else:
                    redacted[key] = value
            return redacted
        elif isinstance(data, list):
            return [self.redact(item, replacement) for item in data]
        else:
            return data
    
    def is_encrypted(self, data: str) -> bool:
        """
        Check if a string appears to be encrypted data.
        
        This is a heuristic check - it doesn't guarantee the data is valid,
        but can help distinguish between plaintext JSON and encrypted blobs.
        
        Args:
            data: String to check
            
        Returns:
            True if the string appears to be encrypted, False otherwise
        """
        if not data:
            return False
        
        # Encrypted data is base64-encoded and typically longer than plaintext
        # Also, it won't be valid JSON
        try:
            json.loads(data)
            return False  # Valid JSON, likely plaintext
        except json.JSONDecodeError:
            # Not valid JSON, could be encrypted
            # Encrypted Fernet data is typically 44+ characters (base64)
            return len(data) >= 44


# Singleton instance
_encryption_service: Optional[CredentialEncryptionService] = None


def get_credential_encryption_service() -> CredentialEncryptionService:
    """
    Get the singleton credential encryption service instance.
    
    Returns:
        CredentialEncryptionService instance
        
    Raises:
        ValueError: If CREDENTIAL_ENCRYPTION_KEY is not set
    """
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = CredentialEncryptionService()
    
    return _encryption_service
