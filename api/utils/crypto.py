"""Shared credential encryption helpers.

Fernet key is derived from SHA-256(SECRET_KEY). Used by any model that stores
a third-party credential at rest (PSA integrations, MDM integrations).
"""
import base64
import hashlib
import os


def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(os.getenv("SECRET_KEY", "").encode()).digest())
    return Fernet(key)


def encrypt_cred(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().encrypt(value.encode()).decode()
    except Exception:
        return value


def decrypt_cred(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception:
        return value
