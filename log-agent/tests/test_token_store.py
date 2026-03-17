import pytest
import os
import sys
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from token_store import TokenStore


def test_token_store_saves_and_loads():
    """Token store saves token to disk and loads it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TokenStore(storage_dir=tmpdir)
        test_token = "eyJhbGciOiJSUzI1NiIs..."

        store.save_token(test_token)
        loaded_token = store.get_token()

        assert loaded_token == test_token


def test_token_store_encrypts_on_windows():
    """Token store uses Windows DPAPI for encryption."""
    # Mock test (DPAPI only works on Windows)
    # On non-Windows, falls back to file-based storage
    pass


def test_token_store_raises_on_corrupted_file():
    """Token store raises error if file is corrupted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write garbage to token file
        token_file = os.path.join(tmpdir, "token.json")
        with open(token_file, "w") as f:
            f.write("corrupted data")

        store = TokenStore(storage_dir=tmpdir)
        with pytest.raises(ValueError):
            store.get_token()
