import pytest
from src.token_manager import TokenManager


def test_token_manager_initializes_keys():
    """Token manager loads or creates RSA keys on init."""
    manager = TokenManager(key_dir="/tmp/test_keys")
    assert manager.private_key is not None
    assert manager.public_key is not None
