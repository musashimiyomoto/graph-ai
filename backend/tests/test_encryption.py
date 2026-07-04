"""Encryption utility and settings tests."""

import pytest
from pydantic import ValidationError

from settings.auth import AuthSettings
from settings.encryption import EncryptionSettings
from utils.encryption import decrypt, encrypt


def test_encrypt_roundtrip() -> None:
    """Encryption produces a different token that decrypts back."""
    plaintext = "sk-secret-value"
    token = encrypt(plaintext)
    if token == plaintext:
        pytest.fail("Encrypted token must differ from the plaintext")
    if decrypt(token) != plaintext:
        pytest.fail("Decrypt must recover the original plaintext")


def test_default_key_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default encryption key is rejected when ENVIRONMENT=production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValidationError, match="ENCRYPTION_SECRET_KEY"):
        EncryptionSettings()


def test_default_key_rejected_in_unknown_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Secure default: any non local/test environment rejects the default key."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(ValidationError, match="ENCRYPTION_SECRET_KEY"):
        EncryptionSettings()


def test_default_key_allowed_in_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default key is tolerated when ENVIRONMENT=test."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    EncryptionSettings()


def test_default_auth_secret_rejected_outside_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default JWT secret is rejected outside local/test."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Force the default secret (the repo .env otherwise supplies a real one).
    monkeypatch.setenv("AUTH_SECRET_KEY", "secret")
    with pytest.raises(ValidationError, match="AUTH_SECRET_KEY"):
        AuthSettings()
