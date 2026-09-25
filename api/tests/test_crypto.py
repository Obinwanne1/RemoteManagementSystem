"""Tests for utils/crypto.py (audits/security_audit.md Findings S1, C1)."""
from unittest.mock import patch
import pytest

from utils.crypto import encrypt_cred, decrypt_cred


class TestRoundTrip:
    def test_encrypts_and_decrypts_back_to_original(self, app):
        with app.app_context():
            secret = "super-secret-api-key-12345"
            ciphertext = encrypt_cred(secret)
            assert ciphertext != secret
            assert decrypt_cred(ciphertext) == secret

    def test_empty_value_passes_through_unencrypted(self, app):
        with app.app_context():
            assert encrypt_cred("") == ""
            assert decrypt_cred("") == ""


class TestFailsClosed:
    """Regression tests for Finding S1 — a prior version silently returned the
    plaintext on any encryption failure instead of raising."""

    def test_encrypt_raises_instead_of_returning_plaintext_on_failure(self, app):
        with app.app_context():
            with patch("utils.crypto._fernet", side_effect=RuntimeError("boom")):
                with pytest.raises(RuntimeError):
                    encrypt_cred("a-real-secret")

    def test_decrypt_raises_instead_of_returning_ciphertext_on_failure(self, app):
        with app.app_context():
            with patch("utils.crypto._fernet", side_effect=RuntimeError("boom")):
                with pytest.raises(RuntimeError):
                    decrypt_cred("some-ciphertext")

    def test_decrypt_raises_on_corrupted_ciphertext(self, app):
        with app.app_context():
            with pytest.raises(Exception):
                decrypt_cred("not-valid-fernet-ciphertext")
