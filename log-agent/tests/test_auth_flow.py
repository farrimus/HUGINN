import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from auth_flow import AuthFlow


def test_auth_flow_acquires_token():
    """AuthFlow requests token from server."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        auth_flow = AuthFlow(
            server_url="http://localhost:5000",
            agent_id="test-agent-001",
            storage_dir=tmpdir
        )

        with patch("auth_flow.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "access_token": "eyJhbGciOiJSUzI1NiIs...",
                "token_type": "Bearer",
                "expires_in": 86400
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            token = auth_flow.get_token()

            assert token == "eyJhbGciOiJSUzI1NiIs..."
            mock_post.assert_called_once()


def test_auth_flow_caches_token():
    """AuthFlow caches token and doesn't re-request until expiration."""
    import tempfile
    import time

    with tempfile.TemporaryDirectory() as tmpdir:
        auth_flow = AuthFlow(
            server_url="http://localhost:5000",
            agent_id="test-agent-001",
            storage_dir=tmpdir
        )

        with patch("auth_flow.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "access_token": "test_token_123",
                "token_type": "Bearer",
                "expires_in": 86400
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # First call should request from server
            token1 = auth_flow.get_token()
            assert token1 == "test_token_123"
            assert mock_post.call_count == 1

            # Second call should use cache (no server request)
            token2 = auth_flow.get_token()
            assert token2 == "test_token_123"
            assert mock_post.call_count == 1  # Still 1, not 2


def test_auth_flow_clears_token():
    """AuthFlow can clear cached and stored token."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        auth_flow = AuthFlow(
            server_url="http://localhost:5000",
            agent_id="test-agent-001",
            storage_dir=tmpdir
        )

        with patch("auth_flow.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "access_token": "test_token_123",
                "token_type": "Bearer",
                "expires_in": 86400
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            token = auth_flow.get_token()
            assert token == "test_token_123"

            # Clear token
            auth_flow.clear_token()

            # Next request should fetch from server again
            mock_post.reset_mock()
            token2 = auth_flow.get_token()
            assert mock_post.call_count == 1  # Fresh request


def test_auth_flow_server_error():
    """AuthFlow raises error if server returns error."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        auth_flow = AuthFlow(
            server_url="http://localhost:5000",
            agent_id="test-agent-001",
            storage_dir=tmpdir
        )

        with patch("auth_flow.requests.post") as mock_post:
            # Simulate HTTP error response
            mock_post.side_effect = Exception("Server error")

            with pytest.raises(Exception):
                auth_flow.get_token()
