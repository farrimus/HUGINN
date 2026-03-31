import pytest
from src.token_manager import TokenManager


def test_token_manager_initializes_keys():
    """Token manager loads or creates RSA keys on init."""
    manager = TokenManager(key_dir="/tmp/test_keys")
    assert manager.private_key is not None
    assert manager.public_key is not None


def test_issue_token():
    """issue_token creates a valid JWT token with correct payload."""
    manager = TokenManager(key_dir="/tmp/test_keys_issue")
    agent_id = "test-agent-123"
    token = manager.issue_token(agent_id, scope="log-ingest", lifetime_hours=24)

    # Verify token is a string and not empty
    assert isinstance(token, str)
    assert len(token) > 0

    # Verify it's a valid JWT token (has 3 parts separated by dots)
    parts = token.split(".")
    assert len(parts) == 3


def test_validate_token_success():
    """validate_token returns payload for a valid token."""
    manager = TokenManager(key_dir="/tmp/test_keys_validate")
    agent_id = "test-agent-456"
    scope = "log-ingest"

    # Issue a token
    token = manager.issue_token(agent_id, scope=scope, lifetime_hours=24)

    # Validate the token
    payload = manager.validate_token(token)

    # Verify payload is correct
    assert payload is not None
    assert payload["sub"] == agent_id
    assert payload["scope"] == scope
    assert "iat" in payload
    assert "exp" in payload


def test_validate_token_invalid():
    """validate_token returns None for an invalid token."""
    manager = TokenManager(key_dir="/tmp/test_keys_invalid")

    # Try to validate a malformed token
    payload = manager.validate_token("invalid.token.here")
    assert payload is None

    # Try to validate an empty string
    payload = manager.validate_token("")
    assert payload is None
