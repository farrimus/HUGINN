import pytest
import time
import os
from unittest.mock import patch

from src.structure_auth import NonceStore

def test_issue_nonce_returns_string():
    store = NonceStore()
    nonce = store.issue()
    assert isinstance(nonce, str)
    assert len(nonce) == 64  # 32 hex bytes

def test_consume_valid_nonce_returns_true():
    store = NonceStore()
    nonce = store.issue()
    assert store.consume(nonce) is True

def test_consume_same_nonce_twice_returns_false():
    store = NonceStore()
    nonce = store.issue()
    store.consume(nonce)
    assert store.consume(nonce) is False

def test_consume_unknown_nonce_returns_false():
    store = NonceStore()
    assert store.consume("deadbeef" * 8) is False

def test_expired_nonce_returns_false():
    from unittest.mock import patch
    store = NonceStore(ttl_seconds=10)
    nonce = store.issue()
    # Advance time by 20s via mock — avoids fragile sleep on a loaded VPS
    with patch("src.structure_auth.time") as mock_time:
        mock_time.time.return_value = time.time() + 20
        assert store.consume(nonce) is False


from src.structure_auth import verify_sui_personal_message

def test_verify_returns_true_for_valid_signature():
    """
    This test uses a pre-computed test vector.
    To generate: run the EVEVault wallet in Utopia, call signPersonalMessage("test-nonce"),
    capture address + signature, paste below.
    Replace with real values when first testing against EVEVault.
    """
    # Placeholder — will be replaced with real test vector from EVEVault
    pytest.skip("Needs real EVEVault test vector — see comment above")

def test_verify_raises_for_tampered_message():
    pytest.skip("Needs real EVEVault test vector")

def test_verify_raises_for_wrong_address():
    pytest.skip("Needs real EVEVault test vector")

def test_verify_rejects_unsupported_scheme_flag():
    from cryptography.exceptions import InvalidSignature
    from src.structure_auth import verify_sui_personal_message
    import base64
    # Build a fake signature with flag=0xFF (unsupported)
    fake_sig = base64.b64encode(bytes([0xFF]) + bytes(96)).decode()
    with pytest.raises(ValueError, match="Unsupported"):
        verify_sui_personal_message(b"hello", fake_sig, "0x" + "00" * 32)


from src.structure_auth import issue_jwt, decode_jwt

def test_issue_and_decode_jwt_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing-only")
    import importlib, src.structure_auth as sa
    importlib.reload(sa)  # reload so JWT_SECRET picks up monkeypatched env
    payload = {"character_id": 12345, "character_name": "Markus", "address": "0xabc", "tier": "OWNER", "structure_id": "keep-7a"}
    token = sa.issue_jwt(payload)
    assert isinstance(token, str)
    decoded = sa.decode_jwt(token)
    assert decoded["character_id"] == 12345
    assert decoded["tier"] == "OWNER"

def test_decode_expired_jwt_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing-only")
    import importlib, src.structure_auth as sa, jwt as pyjwt, datetime
    importlib.reload(sa)
    expired = pyjwt.encode(
        {"sub": "test", "exp": datetime.datetime.utcnow() - datetime.timedelta(seconds=1)},
        "test-secret-key-for-testing-only", algorithm="HS256"
    )
    with pytest.raises(Exception):
        sa.decode_jwt(expired)

def test_decode_tampered_jwt_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing-only")
    import importlib, src.structure_auth as sa
    importlib.reload(sa)
    payload = {"character_id": 1, "tier": "OWNER", "structure_id": "keep-7a"}
    token = sa.issue_jwt(payload)
    tampered = token[:-4] + "XXXX"
    with pytest.raises(Exception):
        sa.decode_jwt(tampered)
