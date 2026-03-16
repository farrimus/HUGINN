# tests/test_ssu_poller.py
"""
Tests for the two-hop poll_ssu_state implementation.

poll_ssu_state(structure_id, ssu_object_id):
  Hop 1 — sui_getObject(ssu_object_id) → StorageUnit fields (status, energy_source_id)
  Hop 2 — sui_getObject(energy_source_id) → NetworkNode fields (fuel, connected_assembly_ids)

Verifies:
  - fuel_pct computed correctly from quantity / max_capacity
  - services_online set from len(connected_assembly_ids)
  - shield_pct NOT modified by polling
  - profile saved when values change, not saved when unchanged
  - hop 2 skipped gracefully when energy_source_id is absent
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

import src.ssu_poller as poller_mod
from src.structure_profile import StructureProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SSU_OBJ_ID  = "0xSSU0000000000000000000000000000000000000000000000000000000000000"
NODE_OBJ_ID = "0xNODE000000000000000000000000000000000000000000000000000000000000"
STRUCT_ID   = "ssu-test-1"


def _ssu_response(energy_source_id=NODE_OBJ_ID, status_variant="ONLINE"):
    """Realistic sui_getObject response for a StorageUnit."""
    energy_field = {"fields": {"id": energy_source_id}} if energy_source_id else None
    return {
        "result": {
            "data": {
                "content": {
                    "fields": {
                        "status": {
                            "fields": {
                                "status": {"variant": status_variant}
                            }
                        },
                        "energy_source_id": energy_field,
                    }
                }
            }
        }
    }


def _node_response(quantity=500, max_capacity=1000, connected_count=3):
    """Realistic sui_getObject response for a NetworkNode."""
    connected = [f"0xASSEM{i:04d}" for i in range(connected_count)]
    return {
        "result": {
            "data": {
                "content": {
                    "fields": {
                        "fuel": {
                            "fields": {
                                "quantity": str(quantity),
                                "max_capacity": str(max_capacity),
                            }
                        },
                        "connected_assembly_ids": connected,
                    }
                }
            }
        }
    }


def _profile(fuel_pct=100.0, services_online=0, shield_pct=85.0):
    return StructureProfile(
        structure_id=STRUCT_ID,
        owner_address="0xOWNER",
        fuel_pct=fuel_pct,
        services_online=services_online,
        shield_pct=shield_pct,
    )


class _PollHarness:
    """Context manager that patches nova_client, load_profile, save_profile on the module."""

    def __init__(self, rpc_side_effects, profile):
        self._rpc_sides = rpc_side_effects
        self._profile = profile
        self.saved = {}
        self._orig = {}

    def __enter__(self):
        mock_nova = MagicMock()
        mock_nova._rpc = AsyncMock(side_effect=self._rpc_sides)

        profile = self._profile
        saved = self.saved

        def fake_load(structure_id, base_dir=None):
            return profile

        def fake_save(p, base_dir=None):
            saved["profile"] = p

        for attr, val in [("nova_client", mock_nova),
                          ("load_profile", fake_load),
                          ("save_profile", fake_save)]:
            self._orig[attr] = getattr(poller_mod, attr, None)
            setattr(poller_mod, attr, val)
        return self

    def __exit__(self, *args):
        for attr, orig in self._orig.items():
            if orig is not None:
                setattr(poller_mod, attr, orig)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fuel_pct_computed_correctly():
    """fuel_pct = round(quantity * 100 / max_capacity, 1) = 25.0 for 250/1000."""
    profile = _profile(fuel_pct=100.0, services_online=0)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=250, max_capacity=1000, connected_count=2)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    assert "profile" in h.saved
    assert h.saved["profile"].fuel_pct == 25.0


@pytest.mark.asyncio
async def test_services_online_set_from_connected_assembly_ids():
    """services_online = len(connected_assembly_ids)."""
    profile = _profile(fuel_pct=100.0, services_online=0)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=800, max_capacity=1000, connected_count=5)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    assert h.saved["profile"].services_online == 5


@pytest.mark.asyncio
async def test_shield_pct_not_modified_by_polling():
    """shield_pct on the profile must not be touched by poll_ssu_state."""
    profile = _profile(fuel_pct=100.0, services_online=0, shield_pct=72.5)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=600, max_capacity=1000, connected_count=1)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    # shield_pct must be unchanged whether or not save happened
    result_profile = h.saved.get("profile", profile)
    assert result_profile.shield_pct == 72.5


@pytest.mark.asyncio
async def test_profile_saved_when_values_change():
    """save_profile is called when fuel_pct or services_online changes."""
    profile = _profile(fuel_pct=100.0, services_online=0)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=400, max_capacity=1000, connected_count=2)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    assert "profile" in h.saved, "save_profile must be called when values change"
    assert h.saved["profile"].fuel_pct == 40.0
    assert h.saved["profile"].services_online == 2


@pytest.mark.asyncio
async def test_profile_not_saved_when_values_unchanged():
    """save_profile is NOT called when polled values already match the profile."""
    # Profile already matches what the RPC will return
    profile = _profile(fuel_pct=40.0, services_online=2)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=400, max_capacity=1000, connected_count=2)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    assert "profile" not in h.saved, "save_profile must NOT be called when nothing changed"


@pytest.mark.asyncio
async def test_no_energy_source_id_skips_hop2():
    """When energy_source_id is None, hop 2 is skipped and no error is raised."""
    rpc_call_count = 0

    async def counting_rpc(method, params):
        nonlocal rpc_call_count
        rpc_call_count += 1
        return _ssu_response(energy_source_id=None)

    profile = _profile(fuel_pct=55.0, services_online=1)
    mock_nova = MagicMock()
    mock_nova._rpc = counting_rpc
    saved = {}

    orig = {attr: getattr(poller_mod, attr, None)
            for attr in ("nova_client", "load_profile", "save_profile")}
    try:
        poller_mod.nova_client = mock_nova
        poller_mod.load_profile = lambda sid, base_dir=None: profile
        poller_mod.save_profile = lambda p, base_dir=None: saved.update({"profile": p})
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)
    finally:
        for attr, val in orig.items():
            if val is not None:
                setattr(poller_mod, attr, val)

    assert rpc_call_count == 1, "Only hop 1 should fire when energy_source_id is None"
    assert "profile" not in saved, "Nothing changed so profile must not be saved"


@pytest.mark.asyncio
async def test_missing_fields_returns_early_no_load_profile():
    """If StorageUnit response has no fields, returns without calling load_profile."""
    load_called = {}
    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(return_value={"result": {"data": {"content": {}}}})

    orig = {attr: getattr(poller_mod, attr, None)
            for attr in ("nova_client", "load_profile")}
    try:
        poller_mod.nova_client = mock_nova
        poller_mod.load_profile = lambda sid, base_dir=None: load_called.update({"called": True}) or None
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)
    finally:
        for attr, val in orig.items():
            if val is not None:
                setattr(poller_mod, attr, val)

    assert "called" not in load_called, "load_profile should not be called when fields are empty"


@pytest.mark.asyncio
async def test_fuel_pct_zero_max_capacity_not_stored():
    """Division-by-zero guard: if max_capacity == 0, fuel_pct stays at its current value."""
    profile = _profile(fuel_pct=77.0, services_online=0)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=100, max_capacity=0, connected_count=0)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    result = h.saved.get("profile", profile)
    assert result.fuel_pct == 77.0, "fuel_pct must not be updated when max_capacity is 0"


@pytest.mark.asyncio
async def test_fuel_pct_rounding_to_one_decimal():
    """fuel_pct is rounded to 1 decimal place (1/3 * 100 = 33.3)."""
    profile = _profile(fuel_pct=100.0, services_online=0)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=1, max_capacity=3, connected_count=0)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    assert h.saved["profile"].fuel_pct == 33.3
