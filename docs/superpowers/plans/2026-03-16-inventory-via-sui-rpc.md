# Inventory and Player Structures via Sui RPC Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fabricated `blockchain_client.py` REST wrapper with real Sui RPC calls to read SSU inventory and player structure state directly from the chain.

**Architecture:** Inventory is stored as dynamic fields on the SSU object, readable via `suix_getDynamicFields` + `sui_getObject`. Type IDs are resolved to names via the existing `data/type_names_all.json`. Player structure state reuses the existing two-hop Sui RPC pattern already used in `poll_ssu_state`. `blockchain_client.py` is deleted entirely — it was built for a REST gateway that does not exist.

**Tech Stack:** Python 3.12, `nova_client._rpc` (Sui JSON-RPC), `data/type_names_all.json` (dict str→str), pytest, pytest-asyncio

---

## What Went Wrong (context for implementer)

`blockchain_client.py` was written assuming a "Blockchain Gateway REST API" at `blockchain-gateway-stillness.live.tech.evefrontier.com`. That host has never resolved from this VPS. No such REST gateway exists — all blockchain data in this project is accessed via Sui RPC (`fullnode.testnet.sui.io`) through `nova_client._rpc`. The file and all code that imports it is dead.

**Confirmed via live chain query (2026-03-16):**

Inventory is stored as `inventory::Inventory` dynamic fields on the SSU object:

```
suix_getDynamicFields("0x51b84c...") →
  [
    { objectType: "...inventory::Inventory", objectId: "0x0b8825..." },  ← empty
    { objectType: "...inventory::Inventory", objectId: "0xbb76b5..." },  ← has items
  ]

sui_getObject("0xbb76b5...") →
  value.fields.items.fields.contents = [
    { key: "78502",  value.fields: { type_id: "78502",  quantity: 1,  ... } },
    { key: "88561",  value.fields: { type_id: "88561",  quantity: 34, ... } },
  ]
```

Type IDs resolve via `data/type_names_all.json`:
- `78502` → `"Velocity CD82"`
- `88561` → `"Thermal Composites"`

Player structure state (fuel, status, assemblies) is already readable via the same two-hop Sui RPC used in `poll_ssu_state`. `system_name` is NOT available on-chain (location is a hashed game mechanic). The `get_player_structures_in_system` filter is therefore removed — all player structures are returned regardless of system.

---

## Files

| Action | File | Purpose |
|--------|------|---------|
| Create | `src/type_names.py` | Load `type_names_all.json`, expose `get_type_name(type_id)` |
| Modify | `src/ssu_poller.py` | Replace `poll_ssu_inventory` and `poll_player_structure` with Sui RPC versions; update `get_player_structures_in_system` |
| Delete | `src/blockchain_client.py` | Fabricated REST client — remove entirely |
| Create | `tests/test_type_names.py` | Tests for type name lookup |
| Modify | `tests/test_ssu_poller.py` | Add tests for new inventory and player structure poll functions |
| Delete | `tests/test_blockchain_client.py` | Tests for deleted module |

---

## Chunk 1: Type Name Lookup

### Task 1: `src/type_names.py`

**Files:**
- Create: `src/type_names.py`
- Create: `tests/test_type_names.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_type_names.py
from src.type_names import get_type_name

def test_known_type_id_returns_name():
    # 78502 and 88561 confirmed present in type_names_all.json
    assert get_type_name(78502) == "Velocity CD82"
    assert get_type_name(88561) == "Thermal Composites"

def test_string_type_id_also_works():
    assert get_type_name("78502") == "Velocity CD82"

def test_unknown_type_id_returns_unknown():
    assert get_type_name(0) == "Unknown"

def test_none_returns_unknown():
    assert get_type_name(None) == "Unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_type_names.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement `src/type_names.py`**

```python
# src/type_names.py
"""
Resolves EVE Frontier type IDs to human-readable names.
Loaded once from data/type_names_all.json at import time.
"""
import json
import os
import logging

log = logging.getLogger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "type_names_all.json")

def _load() -> dict:
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("type_names: could not load %s: %s", _DATA_PATH, e)
        return {}

_TYPE_NAMES: dict = _load()


def get_type_name(type_id) -> str:
    """Return human-readable name for a type_id (int or str). Returns 'Unknown' if not found."""
    if type_id is None:
        return "Unknown"
    return _TYPE_NAMES.get(str(type_id)) or "Unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_type_names.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier
git add src/type_names.py tests/test_type_names.py
git commit -m "feat: add type_names module — resolves type_id to name from type_names_all.json"
```

---

## Chunk 2: Inventory via Sui RPC

### Task 2: `poll_ssu_inventory` rewrite

**Files:**
- Modify: `src/ssu_poller.py:376-396` (replace `poll_ssu_inventory` and `_inventory_loop`)
- Modify: `tests/test_ssu_poller.py` (add inventory tests)

The new implementation:
1. Calls `suix_getDynamicFields(ssu_object_id)` to find `inventory::Inventory` dynamic field objects
2. For each, calls `sui_getObject(objectId)` to get the contents
3. Parses `value.fields.items.fields.contents` — each entry has `key` (type_id) and `value.fields.quantity`
4. Maps type_id → name via `get_type_name`
5. Stores `[{type_name, quantity}]` on profile

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_ssu_poller.py

# ---------------------------------------------------------------------------
# poll_ssu_inventory
# ---------------------------------------------------------------------------

def _dynamic_fields_response(inv_object_ids: list):
    """Simulate suix_getDynamicFields response with inventory dynamic fields."""
    return {
        "result": {
            "data": [
                {
                    "objectType": "0xpkg::inventory::Inventory",
                    "objectId": oid,
                }
                for oid in inv_object_ids
            ],
            "hasNextPage": False,
        }
    }


def _inventory_object_response(contents: list):
    """Simulate sui_getObject response for an Inventory dynamic field."""
    return {
        "result": {
            "data": {
                "content": {
                    "fields": {
                        "value": {
                            "fields": {
                                "items": {
                                    "fields": {
                                        "contents": [
                                            {
                                                "fields": {
                                                    "key": str(item["type_id"]),
                                                    "value": {
                                                        "fields": {
                                                            "type_id": str(item["type_id"]),
                                                            "quantity": item["quantity"],
                                                        }
                                                    },
                                                }
                                            }
                                            for item in contents
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_poll_ssu_inventory_populates_profile():
    """Items from Sui dynamic fields are stored on profile with resolved names."""
    inv_id = "0xINV0000000000000000000000000000000000000000000000000000000000000000"
    profile = _profile()
    saved = {}

    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(side_effect=[
        _dynamic_fields_response([inv_id]),
        _inventory_object_response([
            {"type_id": 88561, "quantity": 34},
        ]),
    ])

    orig_nova = poller_mod.nova_client
    orig_load = poller_mod.load_profile
    orig_save = poller_mod.save_profile
    poller_mod.nova_client = mock_nova
    poller_mod.load_profile = lambda sid, base_dir=None: profile
    poller_mod.save_profile = lambda p, base_dir=None: saved.update({"profile": p})
    try:
        await poller_mod.poll_ssu_inventory(STRUCT_ID, SSU_OBJ_ID)
    finally:
        poller_mod.nova_client = orig_nova
        poller_mod.load_profile = orig_load
        poller_mod.save_profile = orig_save

    assert "profile" in saved
    inv = saved["profile"].ssu_inventory
    assert len(inv) == 1
    assert inv[0]["type_name"] == "Thermal Composites"
    assert inv[0]["quantity"] == 34


@pytest.mark.asyncio
async def test_poll_ssu_inventory_skips_empty_inventories():
    """Dynamic fields with empty contents are ignored; profile not saved."""
    inv_id = "0xINV0000000000000000000000000000000000000000000000000000000000000000"
    profile = _profile()
    saved = {}

    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(side_effect=[
        _dynamic_fields_response([inv_id]),
        _inventory_object_response([]),   # empty
    ])

    orig_nova = poller_mod.nova_client
    orig_load = poller_mod.load_profile
    orig_save = poller_mod.save_profile
    poller_mod.nova_client = mock_nova
    poller_mod.load_profile = lambda sid, base_dir=None: profile
    poller_mod.save_profile = lambda p, base_dir=None: saved.update({"profile": p})
    try:
        await poller_mod.poll_ssu_inventory(STRUCT_ID, SSU_OBJ_ID)
    finally:
        poller_mod.nova_client = orig_nova
        poller_mod.load_profile = orig_load
        poller_mod.save_profile = orig_save

    assert "profile" not in saved


@pytest.mark.asyncio
async def test_poll_ssu_inventory_no_dynamic_fields_does_nothing():
    """If getDynamicFields returns empty list, nothing is stored."""
    profile = _profile()
    saved = {}

    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(return_value=_dynamic_fields_response([]))

    orig_nova = poller_mod.nova_client
    orig_load = poller_mod.load_profile
    orig_save = poller_mod.save_profile
    poller_mod.nova_client = mock_nova
    poller_mod.load_profile = lambda sid, base_dir=None: profile
    poller_mod.save_profile = lambda p, base_dir=None: saved.update({"profile": p})
    try:
        await poller_mod.poll_ssu_inventory(STRUCT_ID, SSU_OBJ_ID)
    finally:
        poller_mod.nova_client = orig_nova
        poller_mod.load_profile = orig_load
        poller_mod.save_profile = orig_save

    assert "profile" not in saved
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_ssu_poller.py -k "inventory" -v
```
Expected: 3 failures (current `poll_ssu_inventory` calls `blockchain_client`)

- [ ] **Step 3: Rewrite `poll_ssu_inventory` in `src/ssu_poller.py`**

Replace lines 376–396 (the `poll_ssu_inventory` function and `_inventory_loop`) with:

```python
async def poll_ssu_inventory(structure_id: str, ssu_object_id: str) -> None:
    """Fetch SSU inventory from Sui dynamic fields and store on profile.

    Three-step process:
      1. suix_getDynamicFields(ssu_object_id) → list of inventory::Inventory field objects
      2. sui_getObject(objectId) for each → parse items (type_id, quantity)
      3. Resolve type_id → name via type_names.get_type_name; store on profile
    """
    from src.type_names import get_type_name

    try:
        df_resp = await nova_client._rpc("suix_getDynamicFields", [ssu_object_id])
    except Exception as e:
        log.warning("poll_ssu_inventory: getDynamicFields failed for %s: %s", ssu_object_id, e)
        return

    inv_fields = [
        f for f in (df_resp.get("result", {}).get("data") or [])
        if "inventory" in f.get("objectType", "").lower()
    ]
    if not inv_fields:
        return

    all_items: list = []
    for field in inv_fields:
        obj_id = field.get("objectId")
        if not obj_id:
            continue
        try:
            obj = await nova_client._rpc("sui_getObject", [obj_id, {"showContent": True}])
        except Exception as e:
            log.warning("poll_ssu_inventory: getObject failed for %s: %s", obj_id, e)
            continue
        contents = (
            obj.get("result", {})
            .get("data", {})
            .get("content", {})
            .get("fields", {})
            .get("value", {})
            .get("fields", {})
            .get("items", {})
            .get("fields", {})
            .get("contents") or []
        )
        for entry in contents:
            ef = entry.get("fields", {})
            type_id = ef.get("key") or (ef.get("value", {}).get("fields") or {}).get("type_id")
            qty_raw = (ef.get("value", {}).get("fields") or {}).get("quantity")
            if type_id is None or qty_raw is None:
                continue
            try:
                qty = int(qty_raw)
            except (TypeError, ValueError):
                continue
            all_items.append({
                "type_name": get_type_name(type_id),
                "quantity": qty,
            })

    profile = load_profile(structure_id)
    if profile and all_items != profile.ssu_inventory:
        profile.ssu_inventory = all_items
        save_profile(profile)
        log.info("poll_ssu_inventory: updated %d items for %s", len(all_items), structure_id)


async def _inventory_loop(structure_id: str, ssu_object_id: str) -> None:
    """Poll SSU inventory every 5 minutes."""
    while True:
        await poll_ssu_inventory(structure_id, ssu_object_id)
        await asyncio.sleep(INVENTORY_POLL_INTERVAL)
```

- [ ] **Step 4: Run inventory tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_ssu_poller.py -k "inventory" -v
```
Expected: 3 passed

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_ssu_poller.py -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /opt/eve-frontier
git add src/ssu_poller.py tests/test_ssu_poller.py
git commit -m "feat: poll_ssu_inventory now uses Sui dynamic fields RPC, no gateway needed"
```

---

## Chunk 3: Player Structures via Sui RPC

### Task 3: `poll_player_structure` rewrite

**Files:**
- Modify: `src/ssu_poller.py:399-451` (replace `_parse_assembly_summary`, `poll_player_structure`, `_player_structure_loop`, `get_player_structures_in_system`)
- Modify: `tests/test_ssu_poller.py` (add player structure tests)

The new implementation polls each player-owned structure using the same two-hop Sui RPC as `poll_ssu_state`:
- Hop 1: `sui_getObject(assembly_id)` → status, energy_source_id
- Hop 2: `sui_getObject(energy_source_id)` → fuel quantity/capacity, connected_assembly_ids count

`_parse_assembly_summary` is deleted (it parsed a fabricated gateway response format).

`get_player_structures_in_system` is simplified — since `system_name` is not available on-chain (location is a hash, EVE Frontier game mechanic), the filter is removed and all player structures are returned.

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_ssu_poller.py

# ---------------------------------------------------------------------------
# poll_player_structure
# ---------------------------------------------------------------------------

PLAYER_ASM_ID = "0xPLAYER00000000000000000000000000000000000000000000000000000000000"
PLAYER_NODE_ID = "0xPLAYERNODE000000000000000000000000000000000000000000000000000000"


@pytest.mark.asyncio
async def test_poll_player_structure_populates_cache():
    """Player structure fuel and status are cached after successful poll."""
    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(side_effect=[
        _ssu_response(energy_source_id=PLAYER_NODE_ID, status_variant="ONLINE"),
        _node_response(quantity=800, max_capacity=1000, connected_count=2),
    ])

    orig_nova = poller_mod.nova_client
    orig_cache = dict(poller_mod._player_structure_cache)
    poller_mod.nova_client = mock_nova
    poller_mod._player_structure_cache.clear()
    try:
        await poller_mod.poll_player_structure(PLAYER_ASM_ID)
        assert PLAYER_ASM_ID in poller_mod._player_structure_cache
        cached = poller_mod._player_structure_cache[PLAYER_ASM_ID]
        assert cached["status"] == "ONLINE"
        assert cached["fuel_pct"] == 80.0
    finally:
        poller_mod.nova_client = orig_nova
        poller_mod._player_structure_cache.clear()
        poller_mod._player_structure_cache.update(orig_cache)


@pytest.mark.asyncio
async def test_poll_player_structure_rpc_failure_does_not_raise():
    """RPC error is swallowed; no exception propagates."""
    mock_nova = MagicMock()
    mock_nova._rpc = AsyncMock(side_effect=RuntimeError("RPC down"))
    orig_nova = poller_mod.nova_client
    poller_mod.nova_client = mock_nova
    try:
        await poller_mod.poll_player_structure(PLAYER_ASM_ID)  # must not raise
    finally:
        poller_mod.nova_client = orig_nova


def test_get_player_structures_returns_all():
    """get_player_structures_in_system returns all cached structures (no system filter)."""
    orig = dict(poller_mod._player_structure_cache)
    poller_mod._player_structure_cache.clear()
    poller_mod._player_structure_cache["0xA"] = {"type_name": "SSU", "status": "ONLINE", "fuel_pct": 50.0}
    poller_mod._player_structure_cache["0xB"] = {"type_name": "SSU", "status": "OFFLINE", "fuel_pct": 5.0}
    try:
        result = poller_mod.get_player_structures_in_system("ANY-SYSTEM")
        assert len(result) == 2
    finally:
        poller_mod._player_structure_cache.clear()
        poller_mod._player_structure_cache.update(orig)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_ssu_poller.py -k "player_structure" -v
```
Expected: failures (old implementation uses blockchain_client)

- [ ] **Step 3: Rewrite `poll_player_structure` and related functions in `src/ssu_poller.py`**

Delete the following functions entirely:
- `_parse_assembly_summary` (lines ~399–424)
- `poll_player_structure` (lines ~427–437)

Replace with:

```python
async def poll_player_structure(assembly_id: str) -> None:
    """Poll a single player-owned structure via two-hop Sui RPC.

    Same pattern as poll_ssu_state:
      Hop 1: sui_getObject(assembly_id) → status, energy_source_id
      Hop 2: sui_getObject(energy_source_id) → fuel quantity/capacity

    system_name is NOT available on-chain (location is a hashed game mechanic).
    Results stored in _player_structure_cache keyed by assembly_id.
    """
    try:
        resp = await nova_client._rpc("sui_getObject", [
            assembly_id, {"showContent": True, "showType": True}
        ])
    except Exception as e:
        log.warning("poll_player_structure: hop 1 RPC failed for %s: %s", assembly_id, e)
        return

    data = resp.get("result", {}).get("data", {})
    fields = data.get("content", {}).get("fields", {})
    if not fields:
        return

    # Status
    status_val = fields.get("status", {})
    status_str = "UNKNOWN"
    if isinstance(status_val, dict):
        inner = status_val.get("fields", {}).get("status")
        if isinstance(inner, dict):
            status_str = inner.get("variant") or inner.get("name") or "UNKNOWN"

    # Type name from Sui Move type string
    type_str = data.get("type", "")
    type_name = _assembly_type_label(type_str)

    # Hop 2: fuel
    fuel_pct = None
    energy_source_id = fields.get("energy_source_id")
    if isinstance(energy_source_id, dict):
        energy_source_id = (
            energy_source_id.get("fields", {}).get("id")
            or energy_source_id.get("id")
            or energy_source_id.get("Some")
        )
    if energy_source_id:
        try:
            node_resp = await nova_client._rpc("sui_getObject", [
                energy_source_id, {"showContent": True}
            ])
            node_fields = (
                node_resp.get("result", {})
                .get("data", {})
                .get("content", {})
                .get("fields", {})
            )
            fuel = node_fields.get("fuel", {})
            if isinstance(fuel, dict):
                fuel = fuel.get("fields", fuel)
            qty = fuel.get("quantity")
            cap = fuel.get("max_capacity")
            if qty is not None and cap is not None and int(cap) > 0:
                fuel_pct = round(int(qty) * 100 / int(cap), 1)
        except Exception as e:
            log.warning("poll_player_structure: hop 2 RPC failed for %s: %s", assembly_id, e)

    _player_structure_cache[assembly_id] = {
        "assembly_id": assembly_id,
        "type_name": type_name,
        "status": status_str.upper(),
        "fuel_pct": fuel_pct,
    }
    log.debug("poll_player_structure: cached %s status=%s fuel=%s", assembly_id[:12], status_str, fuel_pct)
```

Also update `get_player_structures_in_system` — remove the system filter:

```python
def get_player_structures_in_system(system_name: str) -> list:
    """Return all cached player structure summaries.

    system_name parameter retained for API compatibility but not used for filtering —
    location is a hashed game mechanic and system_name is not available on-chain.
    """
    return list(_player_structure_cache.values())
```

- [ ] **Step 4: Run player structure tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_ssu_poller.py -k "player_structure" -v
```
Expected: all pass

- [ ] **Step 5: Run full ssu_poller test suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_ssu_poller.py -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /opt/eve-frontier
git add src/ssu_poller.py tests/test_ssu_poller.py
git commit -m "feat: poll_player_structure now uses two-hop Sui RPC; remove system_name filter"
```

---

## Chunk 4: Remove blockchain_client

### Task 4: Delete fabricated module and its tests

**Files:**
- Delete: `src/blockchain_client.py`
- Delete: `tests/test_blockchain_client.py`

- [ ] **Step 1: Verify nothing else imports blockchain_client**

```bash
grep -rn "blockchain_client\|BlockchainClient" /opt/eve-frontier/src/ /opt/eve-frontier/main.py /opt/eve-frontier/tests/
```
Expected: zero results in `src/` and `main.py` after Task 3 (only the files we're about to delete)

- [ ] **Step 2: Delete the files**

```bash
cd /opt/eve-frontier
rm src/blockchain_client.py tests/test_blockchain_client.py
```

- [ ] **Step 3: Run full test suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```
Expected: all pass, no import errors

- [ ] **Step 4: Commit**

```bash
cd /opt/eve-frontier
git add -u
git commit -m "chore: remove blockchain_client.py — was built for a non-existent REST gateway"
```

---

## Chunk 5: Docs and .env cleanup

### Task 5: Update documentation and config

**Files:**
- Modify: `docs/ref/ops.md` (remove BLOCKCHAIN_GW_URL from config section, update known gaps)
- Modify: `docs/ref/structure-ai.md` (update inventory polling description, remove gateway references)
- Modify: `.env.example` (remove BLOCKCHAIN_GW_URL)

- [ ] **Step 1: Update `docs/ref/ops.md`**

Remove `BLOCKCHAIN_GW_URL` from the Server `.env` config block. Update the Known Gaps table:
- Change `blockchain_client._parse_inventory` row from "Blocked on DNS fix" to "Resolved — inventory now read via Sui dynamic fields RPC"
- Change "Blockchain gateway DNS" row to "Resolved — no gateway; all chain data via Sui RPC (`fullnode.testnet.sui.io`)"
- Add note that `system_name` for player structures is not available on-chain (location hash is a game mechanic)

- [ ] **Step 2: Update `docs/ref/structure-ai.md`**

Replace all references to "blockchain gateway" in the polling description with Sui RPC approach. Update the "Live Chain Field Paths" section to document the inventory dynamic field path.

- [ ] **Step 3: Update `.env.example`**

Remove `BLOCKCHAIN_GW_URL` line. Add comment noting that all chain data goes through `NOVA_RPC_URL`.

- [ ] **Step 4: Verify .env has no BLOCKCHAIN_GW_URL**

```bash
grep "BLOCKCHAIN_GW" /opt/eve-frontier/.env
```
Expected: no output

- [ ] **Step 5: Run full test suite one final time**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /opt/eve-frontier
git add docs/ref/ops.md docs/ref/structure-ai.md .env.example
git commit -m "docs: remove blockchain gateway references; document Sui RPC inventory path"
```
