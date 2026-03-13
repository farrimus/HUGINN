# src/structure_auth.py
import os
import time
import base64
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import dataclass, field
import jwt as pyjwt
import datetime
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

log = logging.getLogger(__name__)

NONCE_TTL_SECONDS = 300  # 5 minutes


class NonceStore:
    """In-memory single-use nonce store with TTL. Thread-safe via dict ops (GIL)."""

    def __init__(self, ttl_seconds: int = NONCE_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: dict[str, float] = {}  # nonce -> expires_at

    def issue(self) -> str:
        """Generate a fresh nonce and store it. Returns hex string."""
        nonce = os.urandom(32).hex()
        self._store[nonce] = time.time() + self._ttl
        self._evict()
        return nonce

    def consume(self, nonce: str) -> bool:
        """Mark nonce as used. Returns True if valid and not yet consumed."""
        expires = self._store.pop(nonce, None)
        if expires is None:
            return False
        if time.time() > expires:
            return False
        return True

    def _evict(self):
        now = time.time()
        self._store = {k: v for k, v in self._store.items() if v > now}


# Global singleton
nonce_store = NonceStore()

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def issue_jwt(payload: dict) -> str:
    """Issue a signed JWT with 24h expiry."""
    data = {**payload, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS)}
    return pyjwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify JWT. Raises on expiry or tampering."""
    return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def verify_sui_personal_message(message_bytes: bytes, signature_b64: str, expected_address: str) -> bool:
    """
    Verify a Sui signPersonalMessage signature.

    Sui compact signature format: flag(1) || sig(64) || pubkey(32) = 97 bytes, base64-encoded.
    - flag 0x00 = ed25519 (only scheme supported here)

    Intent prefix for PersonalMessage: [3, 0, 0]
    BCS encoding of message: u32-LE length prefix + raw bytes
    Full signed message: intent_prefix + bcs(message_bytes)
    ed25519 signs the full message (RFC 8032 — library handles internal SHA-512).

    Address derivation: blake2b-256(flag_byte || pubkey_bytes) as 32-byte hex, prefixed "0x".

    NOTE: Verify this against real EVEVault signPersonalMessage output before relying on it.
    If the scheme fails, inspect the raw signature bytes from the wallet for the correct format.
    """
    try:
        sig_bytes = base64.b64decode(signature_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 signature: {e}")

    if len(sig_bytes) < 97:
        raise ValueError(f"Signature too short: {len(sig_bytes)} bytes, expected 97")

    flag = sig_bytes[0]
    if flag != 0x00:
        raise ValueError(f"Unsupported signature scheme flag: {flag:#04x} (only ed25519/0x00 supported)")

    sig = sig_bytes[1:65]
    pubkey_bytes = sig_bytes[65:97]

    # Intent prefix for PersonalMessage type in Sui
    intent = bytes([3, 0, 0])
    # BCS-encoded message: 4-byte LE length + raw bytes
    bcs_msg = len(message_bytes).to_bytes(4, 'little') + message_bytes
    full_msg = intent + bcs_msg

    # Verify ed25519 signature (raises InvalidSignature on failure)
    pubkey = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
    pubkey.verify(sig, full_msg)

    # Derive Sui address: blake2b-256(flag_byte || pubkey_bytes)
    h = hashlib.new('blake2b', digest_size=32)
    h.update(bytes([0x00]) + pubkey_bytes)
    derived_address = '0x' + h.hexdigest()

    if derived_address.lower() != expected_address.lower():
        raise InvalidSignature(f"Address mismatch: derived {derived_address} != claimed {expected_address}")

    return True


async def lookup_character(address: str) -> dict:
    """
    Look up a character by wallet address via the World API.
    Returns dict with 'id' and 'name' keys, or empty dict on failure.

    World API endpoint (Utopia): GET /v2/smartcharacters?address={address}
    or GET /v2/smartcharacters/{address} — verify exact path against Utopia docs.
    Falls back gracefully so auth still works if the World API is unavailable.
    """
    import httpx
    world_api_base = os.environ.get("WORLD_API_BASE_URL", "https://world-api-stillness.live.tech.evefrontier.com")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{world_api_base}/v2/smartcharacters", params={"address": address})
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("items", [])
                if items:
                    return {"id": items[0].get("id", 0), "name": items[0].get("name", "")}
    except Exception as e:
        log.warning("World API character lookup failed for %s: %s", address, e)
    return {}
