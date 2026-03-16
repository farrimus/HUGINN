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


def _profile(fuel_pct=100.0, services_online=0, shield_pct=85.0, connected_assembly_ids=None,
             connected_assemblies=None):
    return StructureProfile(
        structure_id=STRUCT_ID,
        owner_address="0xOWNER",
        fuel_pct=fuel_pct,
        services_online=services_online,
        shield_pct=shield_pct,
        connected_assembly_ids=connected_assembly_ids or [],
        connected_assemblies=connected_assemblies or [],
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
    # Pre-populate connected_assembly_ids to match what the RPC will return
    expected_ids = [f"0xASSEM{i:04d}" for i in range(2)]
    profile = _profile(fuel_pct=40.0, services_online=2, connected_assembly_ids=expected_ids)
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


# ---------------------------------------------------------------------------
# Phase 1: connected_assembly_ids stored on profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connected_assembly_ids_stored_on_profile():
    """connected_assembly_ids are written to the profile after a successful hop 2."""
    profile = _profile(fuel_pct=100.0, services_online=0)
    with _PollHarness(
        [_ssu_response(), _node_response(quantity=400, max_capacity=1000, connected_count=2)],
        profile,
    ) as h:
        await poller_mod.poll_ssu_state(STRUCT_ID, SSU_OBJ_ID)

    assert "profile" in h.saved
    ids = h.saved["profile"].connected_assembly_ids
    assert len(ids) == 2
    assert all(isinstance(i, str) for i in ids)


# ---------------------------------------------------------------------------
# Phase 1: poll_connected_assemblies
# ---------------------------------------------------------------------------

def _assembly_obj_response(type_str: str, status_variant: str = "ONLINE"):
    return {
        "result": {
            "data": {
                "type": type_str,
                "content": {
                    "fields": {
                        "status": {
                            "fields": {
                                "status": {"variant": status_variant}
                            }
                        }
                    }
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_poll_connected_assemblies_updates_profile():
    """type_name and status extracted and stored on profile.connected_assemblies."""
    asm_id = "0xGATE0000000000000000000000000000000000000000000000000000000000000"
    profile = _profile()
    saved = {}

    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(return_value=_assembly_obj_response(
        "0xpkg::smart_gate::SmartGate", "ONLINE"
    ))
    orig_nova = poller_mod.nova_client
    orig_load = poller_mod.load_profile
    orig_save = poller_mod.save_profile
    poller_mod.nova_client = mock_nova
    poller_mod.load_profile = lambda sid, base_dir=None: profile
    poller_mod.save_profile = lambda p, base_dir=None: saved.update({"profile": p})
    try:
        await poller_mod.poll_connected_assemblies(STRUCT_ID, [asm_id])
    finally:
        poller_mod.nova_client = orig_nova
        poller_mod.load_profile = orig_load
        poller_mod.save_profile = orig_save

    assert "profile" in saved
    assemblies = saved["profile"].connected_assemblies
    assert len(assemblies) == 1
    # Real on-chain struct name is "Gate" → mapped to "Smart Gate"
    assert assemblies[0]["type_name"] == "Smart Gate"
    assert assemblies[0]["status"] == "ONLINE"


@pytest.mark.asyncio
async def test_poll_connected_assemblies_swallows_per_assembly_errors():
    """One failing RPC does not abort the whole call; other assemblies still resolve."""
    good_id = "0xGOOD000000000000000000000000000000000000000000000000000000000000"
    bad_id  = "0xBAD0000000000000000000000000000000000000000000000000000000000000"
    profile = _profile()
    saved = {}

    async def rpc_side(method, params):
        obj_id = params[0]
        if obj_id == bad_id:
            raise RuntimeError("simulated RPC failure")
        return _assembly_obj_response("0xpkg::smart_turret::SmartTurret", "ONLINE")

    mock_nova = MagicMock()
    mock_nova._rpc = rpc_side
    orig_nova = poller_mod.nova_client
    orig_load = poller_mod.load_profile
    orig_save = poller_mod.save_profile
    poller_mod.nova_client = mock_nova
    poller_mod.load_profile = lambda sid, base_dir=None: profile
    poller_mod.save_profile = lambda p, base_dir=None: saved.update({"profile": p})
    try:
        await poller_mod.poll_connected_assemblies(STRUCT_ID, [bad_id, good_id])
    finally:
        poller_mod.nova_client = orig_nova
        poller_mod.load_profile = orig_load
        poller_mod.save_profile = orig_save

    assert "profile" in saved
    assemblies = saved["profile"].connected_assemblies
    # Only the good one resolved
    assert len(assemblies) == 1
    assert assemblies[0]["type_name"] == "Smart Turret"


@pytest.mark.asyncio
async def test_poll_connected_assemblies_real_struct_names():
    """Real on-chain struct names (Gate, Turret, StorageUnit) map to human labels."""
    cases = [
        ("0xpkg::gate::Gate", "Smart Gate"),
        ("0xpkg::turret::Turret", "Smart Turret"),
        ("0xpkg::storage_unit::StorageUnit", "SSU"),
    ]
    for type_str, expected_label in cases:
        assert poller_mod._assembly_type_label(type_str) == expected_label, \
            f"Expected {expected_label!r} for type {type_str!r}"


@pytest.mark.asyncio
async def test_poll_connected_assemblies_empty_list_does_nothing():
    """Empty assembly_ids list must make no RPC calls."""
    rpc_called = {}

    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(side_effect=lambda *a: rpc_called.update({"called": True}))
    orig_nova = poller_mod.nova_client
    poller_mod.nova_client = mock_nova
    try:
        await poller_mod.poll_connected_assemblies(STRUCT_ID, [])
    finally:
        poller_mod.nova_client = orig_nova

    assert "called" not in rpc_called, "No RPC calls should be made for empty assembly list"
