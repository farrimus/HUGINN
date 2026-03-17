import os
import sys
import json
from pathlib import Path
from typing import Optional
import base64


class TokenStore:
    """Secure token storage for log-agent."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            # Use Windows APPDATA on Windows, else ~/.ship_ai
            if sys.platform == "win32":
                storage_dir = os.path.join(os.environ.get("APPDATA", ""), "ShipAI")
            else:
                storage_dir = os.path.expanduser("~/.ship_ai")

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.token_file = self.storage_dir / "token.json"

    def save_token(self, token: str) -> None:
        """Save token securely to disk."""
        data = {
            "access_token": token,
            "encrypted": self._should_encrypt()
        }

        if self._should_encrypt():
            try:
                from dpapi_wrapper import encrypt_data
                encrypted_token = encrypt_data(token)
                data["access_token"] = encrypted_token
            except ImportError:
                # DPAPI not available, warn user
                print("WARNING: DPAPI not available. Token stored unencrypted.")
                data["encrypted"] = False

        with open(self.token_file, "w") as f:
            json.dump(data, f)

        # Restrict permissions (Unix-like only)
        if sys.platform != "win32":
            os.chmod(self.token_file, 0o600)

    def get_token(self) -> Optional[str]:
        """Retrieve token from disk."""
        if not self.token_file.exists():
            return None

        try:
            with open(self.token_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Token file corrupted")

        token = data.get("access_token")

        if data.get("encrypted"):
            try:
                from dpapi_wrapper import decrypt_data
                token = decrypt_data(token)
            except ImportError:
                raise ValueError("Token is encrypted but DPAPI not available")

        return token

    def clear_token(self) -> None:
        """Delete stored token."""
        if self.token_file.exists():
            self.token_file.unlink()

    def _should_encrypt(self) -> bool:
        """Check if encryption is available."""
        return sys.platform == "win32"
