"""Tests for transaction builders."""
import pytest
from src.tx_builders.base import map_move_error, MOVE_ERROR_MAP


def test_map_move_error_recognizes_not_owner():
    """ENotOwner maps to readable message"""
    error = "MoveAbort(ENotOwner, 0) in module gate"
    result = map_move_error(error)
    assert "do not own" in result.lower()


def test_map_move_error_recognizes_already_linked():
    """EAlreadyLinked maps to readable message"""
    error = "MoveAbort(EAlreadyLinked, 0)"
    result = map_move_error(error)
    assert "already linked" in result.lower()


def test_map_move_error_fallback():
    """Unknown codes return generic message"""
    error = "MoveAbort(EUnknown, 0)"
    result = map_move_error(error)
    assert "Move error" in result


def test_move_error_map_has_common_codes():
    """Standard errors are in the map"""
    assert "ENotOwner" in MOVE_ERROR_MAP
    assert "EAlreadyLinked" in MOVE_ERROR_MAP
    assert "EInvalidTargetSystem" in MOVE_ERROR_MAP


from src.tx_builders.gate_builder import build_link_gate_ptb, build_unlink_gate_ptb

def test_link_gate_ptb_structure():
    """Gate link PTB has correct structure"""
    ptb_struct = build_link_gate_ptb("0xcap", "0xgate", 30000004)

    assert len(ptb_struct["inputs"]) == 3
    assert ptb_struct["inputs"][0]["objectId"] == "0xcap"
    assert ptb_struct["inputs"][1]["objectId"] == "0xgate"
    assert ptb_struct["inputs"][2]["value"] == "30000004"
    assert "link_smart_gates" in ptb_struct["commands"][0]["target"]

def test_unlink_gate_ptb_structure():
    """Gate unlink PTB has correct structure"""
    ptb_struct = build_unlink_gate_ptb("0xcap", "0xgate")

    assert len(ptb_struct["inputs"]) == 2
    assert "unlink_smart_gate" in ptb_struct["commands"][0]["target"]
    assert ptb_struct["commands"][0]["arguments"] == [0, 1]
