# log-agent/auth_flow.py
import requests
import time
from typing import Optional
from token_store import TokenStore


class AuthFlow:
    """Manages token acquisition and caching."""

    def __init__(self, server_url: str, agent_id: str, storage_dir: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.agent_id = agent_id
        self.token_store = TokenStore(storage_dir=storage_dir)
        self._cached_token = None
        self._token_expiry = 0

    def get_token(self) -> str:
        """Get a valid token, requesting from server if necessary."""
        # Check if cached token is still valid (with 60-second buffer)
        if self._cached_token and time.time() < (self._token_expiry - 60):
            return self._cached_token

        # Try to load from disk
        stored_token = self.token_store.get_token()
        if stored_token:
            # Assume stored token is still valid (server will reject if not)
            self._cached_token = stored_token
            # Estimate expiry as 24 hours from now (conservative)
            self._token_expiry = time.time() + 86400
            return stored_token

        # Request new token from server
        return self._request_token()

    def _request_token(self) -> str:
        """Request a new token from server."""
        url = f"{self.server_url}/auth/token"
        payload = {"agent_id": self.agent_id}

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 86400)

        # Save token
        self.token_store.save_token(token)

        # Update cache
        self._cached_token = token
        self._token_expiry = time.time() + expires_in

        return token

    def clear_token(self) -> None:
        """Clear cached and stored token."""
        self.token_store.clear_token()
        self._cached_token = None
        self._token_expiry = 0
