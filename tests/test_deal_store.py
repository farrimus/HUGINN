import pytest
import time
import os
from src.deal_store import DealStore, DealRecord


@pytest.fixture
def store(tmp_path):
    return DealStore(base_dir=str(tmp_path))


def test_issue_creates_record(store):
    store.issue("0xabc", "keep-7a", "item")
    rec = store.get("0xabc", "keep-7a")
    assert rec is not None
    assert rec.payment_method == "item"
    assert rec.messages_remaining == 20
    assert rec.expires_at > time.time()


def test_consume_message_decrements(store):
    store.issue("0xabc", "keep-7a", "sui")
    assert store.consume_message("0xabc", "keep-7a") is True
    rec = store.get("0xabc", "keep-7a")
    assert rec.messages_remaining == 19


def test_consume_exhausted_returns_false(store):
    store.issue("0xabc", "keep-7a", "info", messages=1)
    assert store.consume_message("0xabc", "keep-7a") is True
    assert store.consume_message("0xabc", "keep-7a") is False


def test_consume_expired_returns_false(store):
    store.issue("0xabc", "keep-7a", "item", duration_hours=0)
    rec = store.get("0xabc", "keep-7a")
    rec.expires_at = time.time() - 1
    store._save(rec)
    assert store.consume_message("0xabc", "keep-7a") is False


def test_get_missing_returns_none(store):
    assert store.get("0xnobody", "keep-7a") is None


def test_issue_overwrites_existing(store):
    store.issue("0xabc", "keep-7a", "item")
    store.issue("0xabc", "keep-7a", "sui", messages=5)
    rec = store.get("0xabc", "keep-7a")
    assert rec.messages_remaining == 5
    assert rec.payment_method == "sui"


def test_path_sanitizes_address(store, tmp_path):
    """Addresses with special chars don't escape the directory."""
    store.issue("0x../../../etc/passwd", "keep-7a", "info")
    for f in os.listdir(tmp_path):
        assert "/" not in f
        assert ".." not in f


def test_consume_with_no_deal_returns_false(store):
    assert store.consume_message("0xghost", "keep-7a") is False
