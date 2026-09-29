from __future__ import annotations

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.config import get_settings


def _private_key() -> Ed25519PrivateKey:
    seed = hashlib.sha256(get_settings().signing_secret.encode("utf-8")).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def sign_bytes(payload: bytes) -> str:
    return _private_key().sign(payload).hex()


def verify_bytes(payload: bytes, signature_hex: str, public_key_hex: str | None = None) -> bool:
    try:
        public_bytes = bytes.fromhex(public_key_hex) if public_key_hex else public_key_bytes()
        signature = bytes.fromhex(signature_hex)
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def public_key_bytes() -> bytes:
    return _private_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_hex() -> str:
    return public_key_bytes().hex()


def signature_payload(payload: dict) -> bytes:
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def legacy_hmac_signature(payload: dict) -> str:
    """Kept for certificate verification of records created before Step 15."""
    import hashlib
    import hmac
    import json

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hmac.new(get_settings().signing_secret.encode("utf-8"), serialized, hashlib.sha256).hexdigest()
