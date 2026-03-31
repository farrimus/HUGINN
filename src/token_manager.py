import os
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt

log = logging.getLogger(__name__)


class TokenManager:
    """Manages RSA key generation, loading, and JWT token operations."""

    def __init__(self, key_dir: str):
        """
        Initialize TokenManager, loading existing keys or generating new ones.

        Args:
            key_dir: Directory to store/load RSA keys
        """
        self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)

        self.private_key_path = self.key_dir / "private_key.pem"
        self.public_key_path = self.key_dir / "public_key.pem"

        # Load config from token_config.json
        try:
            with open("config/token_config.json", "r") as f:
                config = json.load(f)
                self.lifetime_hours = config.get("token_lifetime_hours", 24)
                self.algorithm = config.get("token_algorithm", "RS256")
        except FileNotFoundError:
            # Use defaults if config file not found
            self.lifetime_hours = 24
            self.algorithm = "RS256"

        # Get encryption password from environment or derive from key directory
        self._encryption_password = self._get_encryption_password()

        # Load or generate keys
        self.private_key = self._load_or_generate_private_key()
        self.public_key = self.private_key.public_key()

    def _get_encryption_password(self) -> bytes:
        """
        Get encryption password for private key.

        First checks TOKEN_KEY_PASSWORD environment variable.
        If not set, derives a password from the key directory path.

        Returns:
            bytes: Password for key encryption (always 32 bytes)
        """
        env_password = os.environ.get("TOKEN_KEY_PASSWORD")
        if env_password:
            # Ensure it's 32 bytes (SHA-256 digest size)
            return hashlib.sha256(env_password.encode()).digest()
        else:
            # Fallback: derive from key directory path
            return hashlib.sha256(str(self.key_dir).encode()).digest()

    def _load_or_generate_private_key(self):
        """Load private key from file or generate a new one."""
        if self.private_key_path.exists():
            with open(self.private_key_path, "rb") as f:
                key_data = f.read()

            # Try to load with password first, then without (backward compatibility)
            try:
                private_key = serialization.load_pem_private_key(
                    key_data,
                    password=self._encryption_password,
                    backend=default_backend()
                )
            except TypeError:
                # Key is not encrypted, try without password
                private_key = serialization.load_pem_private_key(
                    key_data,
                    password=None,
                    backend=default_backend()
                )
            return private_key
        else:
            # Generate new RSA key pair (2048-bit for balance of security and performance)
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            # Save private key to file with encryption
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(self._encryption_password)
            )
            with open(self.private_key_path, "wb") as f:
                f.write(private_pem)
            # Restrict file permissions to owner only (read/write)
            os.chmod(self.private_key_path, 0o600)
            return private_key

    def issue_token(self, agent_id: str, scope: str = "log-ingest", lifetime_hours: int = 24) -> str:
        """Issue a new JWT token for an agent."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": agent_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=lifetime_hours)).timestamp()),
            "scope": scope,
        }
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token

    def validate_token(self, token: str) -> Optional[Dict]:
        """Validate a JWT token and return payload if valid."""
        log.debug("Validating token: %s...", token[:50])
        try:
            payload = jwt.decode(token, self.public_key, algorithms=["RS256"])
            log.debug("Token valid, payload: %s", payload)
            return payload
        except jwt.InvalidTokenError as e:
            log.error("Token validation failed: %s (token: %s)", str(e), token[:50])
            return None
