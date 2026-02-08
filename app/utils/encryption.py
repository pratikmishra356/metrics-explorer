"""Encryption utilities for securing provider credentials."""

import base64
import json
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CredentialEncryption:
    """Handles encryption and decryption of provider credentials."""

    def __init__(self, key: str | None = None):
        """Initialize with encryption key."""
        settings = get_settings()
        encryption_key = key or settings.encryption_key
        
        if not encryption_key:
            raise ValueError(
                "Encryption key not configured. Set ENCRYPTION_KEY environment variable."
            )
        
        # Ensure the key is properly formatted for Fernet
        try:
            self._fernet = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(
                f"Invalid encryption key format. Generate a new key with: "
                f"python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from e

    def encrypt(self, credentials: Dict[str, Any]) -> str:
        """
        Encrypt credentials dictionary to a base64 string.
        
        Args:
            credentials: Dictionary containing provider credentials
            
        Returns:
            Base64 encoded encrypted string
        """
        # Serialize credentials to JSON
        json_bytes = json.dumps(credentials).encode("utf-8")
        
        # Encrypt with Fernet
        encrypted_bytes = self._fernet.encrypt(json_bytes)
        
        # Return as base64 string for database storage
        return base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")

    def decrypt(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt credentials from base64 string.
        
        Args:
            encrypted_data: Base64 encoded encrypted string
            
        Returns:
            Decrypted credentials dictionary
            
        Raises:
            ValueError: If decryption fails
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode("utf-8"))
            
            # Decrypt with Fernet
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            
            # Parse JSON
            return json.loads(decrypted_bytes.decode("utf-8"))
        except InvalidToken:
            raise ValueError("Failed to decrypt credentials - invalid key or corrupted data")
        except json.JSONDecodeError:
            raise ValueError("Failed to parse decrypted credentials as JSON")


# Singleton instance
_encryption_instance: CredentialEncryption | None = None


def get_encryption() -> CredentialEncryption:
    """Get singleton encryption instance."""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = CredentialEncryption()
    return _encryption_instance


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """Convenience function to encrypt credentials."""
    return get_encryption().encrypt(credentials)


def decrypt_credentials(encrypted_data: str) -> Dict[str, Any]:
    """Convenience function to decrypt credentials."""
    return get_encryption().decrypt(encrypted_data)
