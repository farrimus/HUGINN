import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt


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

        # Load or generate keys
        self.private_key = self._load_or_generate_private_key()
        self.public_key = self.private_key.public_key()

    def _load_or_generate_private_key(self):
        """Load private key from file or generate a new one."""
        if self.private_key_path.exists():
            with open(self.private_key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
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
            # Save private key to file
            with open(self.private_key_path, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                )
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
        try:
            payload = jwt.decode(token, self.public_key, algorithms=["RS256"])
            return payload
        except jwt.InvalidTokenError:
            return None
