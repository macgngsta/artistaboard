"""Symmetric encryption for secrets at rest (board Read/Write keys).

A Fernet key is derived from a passphrase (``settings.encryption_secret``) so any
configured string works as the key material; rotate by setting a dedicated
``APP_ENCRYPTION_KEY``. Decrypt only in-process when a send needs the key — never
return it over the API or write it to logs.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(plaintext: str, secret: str) -> str:
    return _fernet(secret).encrypt(plaintext.encode()).decode()


def decrypt(token: str, secret: str) -> str:
    return _fernet(secret).decrypt(token.encode()).decode()
