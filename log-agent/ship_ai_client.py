# log-agent/ship_ai_client.py
import requests
from typing import Dict, Any, Optional
from auth_flow import AuthFlow


class ShipAIClient:
    """Client for communicating with the Ship AI server, with token-based auth."""

    def __init__(self, server_url: str, agent_id: str):
        self.server_url = server_url.rstrip("/")
        self.agent_id = agent_id
        self.auth_flow = AuthFlow(server_url, agent_id)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization token."""
        token = self.auth_flow.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def post_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post log data to server."""
        url = f"{self.server_url}/log/ingest"
        headers = self._get_headers()
        response = requests.post(url, json=log_data, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def post_route(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post route data to server."""
        url = f"{self.server_url}/route"
        headers = self._get_headers()
        response = requests.post(url, json=route_data, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_ship_profile(self) -> Dict[str, Any]:
        """Fetch ship profile from server."""
        url = f"{self.server_url}/ship-profile"
        headers = self._get_headers()
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def update_ship_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update ship profile on server."""
        url = f"{self.server_url}/ship-profile"
        headers = self._get_headers()
        response = requests.post(url, json=profile_data, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
