"""Shared credential encryption helpers.

Fernet key is derived from SHA-256("rmm-cred-encryption:" + SECRET_KEY) — the
fixed context prefix domain-separates this key from SECRET_KEY's other uses
(session/CSRF signing) so a single leaked value doesn't compromise both
properties, and so a future third use of SECRET_KEY can't collide with this
one (audits/security_audit.md Finding C1).

Used by any model that stores a third-party credential at rest (PSA
integrations, MDM integrations) — see also models/user.py::set_mfa_secret,
which reuses these functions for TOTP secrets (Finding S2).

Callers must handle exceptions explicitly — encrypt_cred()/decrypt_cred() do
NOT catch and silently fall back to returning the plaintext/ciphertext on
failure (a prior version did; audits/security_audit.md Finding S1 flagged
this as a silent plaintext-storage risk). Flask's app-wide Exception handler
(api/app.py) already converts any uncaught exception here into a generic
500 with server-side logging, matching this codebase's established
error-handling convention — no per-call-site try/except is needed.
"""
import base64
import hashlib
import os


def _fernet():
    from cryptography.fernet import Fernet
    key_material = hashlib.sha256(b"rmm-cred-encryption:" + os.getenv("SECRET_KEY", "").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_cred(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_cred(value: str) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode()).decode()
