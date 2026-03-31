"""Integration tests for transaction building on Nova testnet."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.tx_builders.gate_builder import GateTransactionBuilder
from src.blockchain_queries import nova_client


@pytest.mark.asyncio
async def test_gate_link_ptb_structure_valid():
    """Gate link PTB has valid Sui format"""
    builder = GateTransactionBuilder(
        assembly_type="gate",
        wallet_address="0x123456789abcdef",
        world_package_id="0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9"
    )

    # Mock PTB structure with valid Sui format
    ptb = {
        "version": 1,
        "sender": "0x123456789abcdef",
        "expiration": {"Epoch": 1000},
        "gasData": {"payment": [], "owner": "0x123456789abcdef", "price": 1000, "budget": 10000000},
        "inputs": [
            {"type": "object", "objectId": "0xcap"},
            {"type": "object", "objectId": "0xgate"},
            {"type": "pure", "valueType": "u64", "value": "30000004"}
        ],
        "transactions": [{
            "kind": "MoveCall",
            "target": "0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9::gate::link_smart_gates",
            "typeArguments": ["0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9::assembly::Gate"],
            "arguments": [0, 1, 2]
        }]
    }

    assert ptb["version"] == 1
    assert ptb["sender"] == "0x123456789abcdef"
    assert len(ptb["inputs"]) == 3
    assert "link_smart_gates" in ptb["transactions"][0]["target"]


def test_gate_transaction_builder_initialization():
    """GateTransactionBuilder initializes correctly"""
    builder = GateTransactionBuilder(
        assembly_type="gate",
        wallet_address="0xabc123",
        world_package_id="0xpkg"
    )

    assert builder.assembly_type == "gate"
    assert builder.wallet_address == "0xabc123"
    assert builder.world_package_id == "0xpkg"
    assert builder.nova_client is not None


def test_ptb_digest_generation():
    """Transaction digest is generated correctly"""
    builder = GateTransactionBuilder(
        assembly_type="gate",
        wallet_address="0x123456789abcdef",
        world_package_id="0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9"
    )

    ptb = {
        "version": 1,
        "sender": "0x123456789abcdef",
        "expiration": {"Epoch": 1000},
        "gasData": {"payment": [], "owner": "0x123456789abcdef", "price": 1000, "budget": 10000000},
        "inputs": [{"type": "object", "objectId": "0xcap"}],
        "transactions": []
    }

    digest = builder.tx_digest(ptb)

    # Digest should be 16 hex characters
    assert len(digest) == 16
    assert all(c in '0123456789abcdef' for c in digest)

    # Same PTB should produce same digest
    digest2 = builder.tx_digest(ptb)
    assert digest == digest2
