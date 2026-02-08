"""Tests for encryption utilities."""

import pytest
from cryptography.fernet import Fernet

from app.utils.encryption import CredentialEncryption


@pytest.fixture
def encryption():
    """Create encryption instance with test key."""
    key = Fernet.generate_key().decode()
    return CredentialEncryption(key)


def test_encrypt_decrypt_credentials(encryption):
    """Test that credentials can be encrypted and decrypted."""
    credentials = {
        "api_key": "secret-api-key",
        "app_key": "secret-app-key",
        "nested": {"value": "nested-secret"},
    }
    
    # Encrypt
    encrypted = encryption.encrypt(credentials)
    assert encrypted != str(credentials)
    assert "secret" not in encrypted
    
    # Decrypt
    decrypted = encryption.decrypt(encrypted)
    assert decrypted == credentials


def test_encrypt_empty_credentials(encryption):
    """Test encrypting empty credentials."""
    credentials = {}
    
    encrypted = encryption.encrypt(credentials)
    decrypted = encryption.decrypt(encrypted)
    
    assert decrypted == credentials


def test_decrypt_invalid_data(encryption):
    """Test decrypting invalid data raises error."""
    with pytest.raises(ValueError, match="decrypt"):
        encryption.decrypt("invalid-encrypted-data")


def test_encryption_key_required():
    """Test that encryption key is required."""
    with pytest.raises(ValueError, match="key"):
        CredentialEncryption("")
