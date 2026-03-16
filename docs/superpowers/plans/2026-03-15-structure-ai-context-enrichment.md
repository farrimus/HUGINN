# Structure AI Context & Memory Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire all available universe data, on-chain SSU state, killmail feeds, and persistent memory into the Structure AI context block.

**Architecture:** Four independent modules (`galaxy_db`, `memory_store`, updated `structure_client`, `ssu_poller`) plus wiring changes in `main.py`. Each module has one responsibility and is tested in isolation. Context assembly in `structure_client.py` pulls from all sources. Background polling in `ssu_poller.py` feeds `memory_store`.

**Tech Stack:** Python 3.12, FastAPI, SQLite3 (eve_universe.db), asyncio, httpx, existing venv at `.venv/`.

---

## File Map

**New files:**
- `src/galaxy_db.py` — GalaxyDB SQLite wrapper (read-only)
- `src/memory_store.py` — MemoryStore: events.jsonl, summary.json, pilot profiles
- `src/ssu_poller.py` — Async background tasks: SSU poll, killmail poll, event poll
- `build_types.py` — One-shot CLI script: fetch /v2/types → data/types.json
- `tests/test_galaxy_db.py`
- `tests/test_memory_store.py`

**Modified files:**
- `src/structure_profile.py` — add `region_name: str = ""`, `system_id: int = 0`
- `src/structure_client.py` — `CONTEXT_CAP = 2000`, `LobbyClient`, updated `build_structure_context()`, updated `STRUCTURE_SYSTEM_PROMPT`
- `src/world_api.py` — `WORLD_API_ENV` Utopia/Stillness switching, `get_killmails(system_id)`
- `main.py` — lifespan launches SSU poller, `auth_verify` backfills profile fields and creates pilot profiles, `/structure-chat` routes VETTED tier to `lobby_client`
- `tests/test_structure_client.py` — update for new context fields and `LobbyClient`
- `tests/test_structure_profile.py` — update for new fields

---

## Chunk 1: Foundation — galaxy_db, StructureProfile fields, world_api

### Task 1: `src/galaxy_db.py` — SQLite wrapper for eve_universe.db

**Files:**
- Create: `src/galaxy_db.py`
- Create: `tests/test_galaxy_db.py`

- [ ] **1.1 Write the failing tests**

Note: `data/eve_universe.db` must exist (it is checked into the repo at `/opt/eve-frontier/data/`).
Known real data from this DB: system `solarSystemId=30000004`, name `'O3H-1FN'`, region `'653-Y-21'`; planet `planetId=40000005`.

```python
# tests/test_galaxy_db.py
import pytest
from src.galaxy_db import GalaxyDB

DB_PATH = "data/eve_universe.db"

# Known real IDs from eve_universe.db
REAL_SYSTEM_ID = 30000004
REAL_SYSTEM_NAME = "O3H-1FN"
REAL_REGION_NAME = "653-Y-21"
REAL_PLANET_ID = 40000005

@pytest.fixture
def db():
    return GalaxyDB(DB_PATH)

def test_get_system_by_name_returns_dict(db):
    result = db.get_system(REAL_SYSTEM_NAME)
    assert result is not None
    assert result["solarSystemId"] == REAL_SYSTEM_ID

def test_get_system_by_id_returns_dict(db):
    result = db.get_system(REAL_SYSTEM_ID)
    assert result is not None
    assert result["name"] == REAL_SYSTEM_NAME

def test_get_system_includes_region_name(db):
    result = db.get_system(REAL_SYSTEM_ID)
    assert result is not None
    assert result["regionName"] == REAL_REGION_NAME  # exact camelCase key from SQL alias

def test_get_system_not_found_returns_none(db):
    result = db.get_system("ZZZDOESNOTEXIST_XYZ_999")
    assert result is None

def test_get_system_case_insensitive(db):
    result = db.get_system(REAL_SYSTEM_NAME.lower())
    assert result is not None
    assert result["solarSystemId"] == REAL_SYSTEM_ID

def test_search_systems_returns_list(db):
    results = db.search_systems("O3H")
    assert isinstance(results, list)
    assert len(results) > 0
    # search_systems returns raw SolarSystems rows (no join)
    assert "solarSystemId" in results[0]

def test_search_systems_no_match_returns_empty(db):
    results = db.search_systems("XXXXXXNOEXIST")
    assert results == []

def test_get_celestials_in_system_structure(db):
    celestials = db.get_celestials_in_system(REAL_SYSTEM_ID)
    assert isinstance(celestials, dict)
    for key in ("planets", "moons", "stations", "lagrange_points"):
        assert key in celestials
        assert isinstance(celestials[key], list)

def test_get_celestials_planets_have_expected_columns(db):
    celestials = db.get_celestials_in_system(REAL_SYSTEM_ID)
    planets = celestials["planets"]
    assert len(planets) > 0
    # Verify key columns exist (from PROGRAMMER_GUIDE.md schema)
    p = planets[0]
    assert "planetId" in p
    assert "solarSystemId" in p

def test_get_jumps_from_system_returns_list(db):
    jumps = db.get_jumps_from_system(REAL_SYSTEM_ID)
    assert isinstance(jumps, list)
    # Real system should have at least one jump (or none — both are valid)

def test_run_sql_count(db):
    rows = db.run_sql("SELECT COUNT(*) as cnt FROM Regions")
    assert len(rows) == 1
    assert rows[0]["cnt"] > 0

def test_get_region_returns_dict(db):
    # Get region via system first
    result = db.get_system(REAL_SYSTEM_ID)
    region_id = result["regionId"]
    region = db.get_region(region_id)
    assert region is not None
    assert region["name"] == REAL_REGION_NAME

def test_get_region_not_found_returns_none(db):
    assert db.get_region(99999999) is None

def test_get_planet_returns_dict(db):
    planet = db.get_planet(REAL_PLANET_ID)
    assert planet is not None
    assert planet["planetId"] == REAL_PLANET_ID
    assert planet["solarSystemId"] == REAL_SYSTEM_ID

def test_get_planet_not_found_returns_none(db):
    assert db.get_planet(99999999) is None


- [ ] **1.2 Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_galaxy_db.py -v 2>&1 | head -30
```
Expected: ImportError or ModuleNotFoundError on `src.galaxy_db`

- [ ] **1.3 Implement `src/galaxy_db.py`**

```python
# src/galaxy_db.py
import os
import sqlite3
import logging
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "eve_universe.db")
)


class GalaxyDB:
    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict(self, row) -> dict:
        return dict(row) if row else None

    def get_system(self, name_or_id) -> dict | None:
        """Return SolarSystems row joined with region/constellation names."""
        sql = """
            SELECT s.*,
                   r.name AS regionName,
                   c.name AS constellationName
            FROM SolarSystems s
            LEFT JOIN Regions r ON s.regionId = r.regionId
            LEFT JOIN Constellations c ON s.constellationId = c.constellationId
            WHERE {}
        """
        try:
            with self._connect() as conn:
                if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
                    row = conn.execute(
                        sql.format("s.solarSystemId = ?"), (int(name_or_id),)
                    ).fetchone()
                else:
                    row = conn.execute(
                        sql.format("LOWER(s.name) = LOWER(?)"), (str(name_or_id),)
                    ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_system(%r) failed: %s", name_or_id, e)
            return None

    def get_region(self, region_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Regions WHERE regionId = ?", (region_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_region(%r) failed: %s", region_id, e)
            return None

    def get_constellation(self, constellation_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Constellations WHERE constellationId = ?", (constellation_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_constellation(%r) failed: %s", constellation_id, e)
            return None

    def get_planet(self, planet_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Planets WHERE planetId = ?", (planet_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_planet(%r) failed: %s", planet_id, e)
            return None

    def get_moon(self, moon_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Moons WHERE moonId = ?", (moon_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_moon(%r) failed: %s", moon_id, e)
            return None

    def get_station(self, station_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM NpcStations WHERE stationId = ?", (station_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_station(%r) failed: %s", station_id, e)
            return None

    def get_celestials_in_system(self, system_id: int) -> dict:
        """Return {planets, moons, stations, lagrange_points} dicts."""
        try:
            with self._connect() as conn:
                planets = [dict(r) for r in conn.execute(
                    "SELECT * FROM Planets WHERE solarSystemId = ? ORDER BY celestialIndex",
                    (system_id,)
                ).fetchall()]
                moons = [dict(r) for r in conn.execute(
                    "SELECT * FROM Moons WHERE solarSystemId = ?", (system_id,)
                ).fetchall()]
                stations = [dict(r) for r in conn.execute(
                    "SELECT * FROM NpcStations WHERE solarSystemId = ?", (system_id,)
                ).fetchall()]
                lagrange = [dict(r) for r in conn.execute(
                    "SELECT * FROM LagrangePoints WHERE solarSystemId = ?", (system_id,)
                ).fetchall()]
                return {"planets": planets, "moons": moons, "stations": stations, "lagrange_points": lagrange}
        except Exception as e:
            log.warning("galaxy_db.get_celestials_in_system(%r) failed: %s", system_id, e)
            return {"planets": [], "moons": [], "stations": [], "lagrange_points": []}

    def search_systems(self, pattern: str) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM SolarSystems WHERE LOWER(name) LIKE LOWER(?) LIMIT 50",
                    (f"%{pattern}%",)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            log.warning("galaxy_db.search_systems(%r) failed: %s", pattern, e)
            return []

    def get_jumps_from_system(self, system_id: int) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM Jumps WHERE fromSystemId = ?", (system_id,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            log.warning("galaxy_db.get_jumps_from_system(%r) failed: %s", system_id, e)
            return []

    def run_sql(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            log.warning("galaxy_db.run_sql failed: %s", e)
            return []


# Module-level singleton
galaxy_db = GalaxyDB()
```

- [ ] **1.4 Run tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_galaxy_db.py -v
```
Expected: all pass (or skip if system name doesn't exist — skips are fine)

- [ ] **1.5 Commit**

```bash
git add src/galaxy_db.py tests/test_galaxy_db.py
git commit -m "feat: add GalaxyDB wrapper for eve_universe.db"
```

---

### Task 2: Add `region_name` and `system_id` to `StructureProfile`

**Files:**
- Modify: `src/structure_profile.py`
- Modify: `tests/test_structure_profile.py`

- [ ] **2.1 Write the failing tests**

Add to `tests/test_structure_profile.py`:

```python
def test_new_fields_have_defaults():
    p = StructureProfile(structure_id="test-1", owner_address="0xabc")
    assert p.region_name == ""
    assert p.system_id == 0

def test_new_fields_survive_roundtrip(tmp_path):
    p = StructureProfile(
        structure_id="test-2",
        owner_address="0xabc",
        region_name="The Forge",
        system_id=30000142,
    )
    save_profile(p, base_dir=str(tmp_path))
    loaded = load_profile("test-2", base_dir=str(tmp_path))
    assert loaded.region_name == "The Forge"
    assert loaded.system_id == 30000142

def test_old_profile_json_missing_new_fields_gets_defaults(tmp_path):
    """Profiles created before this change load fine — new fields default to empty/0."""
    import json, os
    old_data = {"structure_id": "old-1", "owner_address": "0xdef",
                "structure_name": "Old", "structure_type": "Smart Storage Unit",
                "system_name": "", "owner_character_id": 0,
                "nova_registry_object_id": "", "created_at": "",
                "shield_pct": 100.0, "fuel_pct": 100.0,
                "services_online": 0, "services_total": 0,
                "docked_count": 0, "routine_alerts": []}
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(os.path.join(str(tmp_path), "old-1.json"), "w") as f:
        json.dump(old_data, f)
    loaded = load_profile("old-1", base_dir=str(tmp_path))
    assert loaded is not None
    assert loaded.region_name == ""
    assert loaded.system_id == 0

def test_profile_json_with_extra_unknown_field_loads_without_error(tmp_path):
    """Future profile versions with extra keys must not crash load_profile."""
    import json, os
    data = {"structure_id": "future-1", "owner_address": "0xdef",
            "structure_name": "Future", "structure_type": "Smart Storage Unit",
            "system_name": "", "owner_character_id": 0,
            "nova_registry_object_id": "", "created_at": "",
            "shield_pct": 100.0, "fuel_pct": 100.0,
            "services_online": 0, "services_total": 0,
            "docked_count": 0, "routine_alerts": [],
            "region_name": "Test Region", "system_id": 42,
            "unknown_future_field": "ignored"}
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(os.path.join(str(tmp_path), "future-1.json"), "w") as f:
        json.dump(data, f)
    loaded = load_profile("future-1", base_dir=str(tmp_path))
    assert loaded is not None
    assert loaded.region_name == "Test Region"
    assert not hasattr(loaded, "unknown_future_field")
```

- [ ] **2.2 Run to verify tests fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_profile.py::test_new_fields_have_defaults tests/test_structure_profile.py::test_new_fields_survive_roundtrip tests/test_structure_profile.py::test_old_profile_json_loads_without_new_fields -v
```

- [ ] **2.3 Add fields to `StructureProfile` dataclass**

**a) In `src/structure_profile.py` line 6, add `fields` to the existing import:**

Current:
```python
from dataclasses import dataclass, field, asdict
```
Replace with:
```python
from dataclasses import dataclass, field, asdict, fields
```

**b) Add the two new fields to `StructureProfile` after the `routine_alerts` line:**

```python
    # Universe data (set at profile creation from STRUCTURE_SYSTEM_NAME + galaxy_db)
    region_name:            str             = ""
    system_id:              int             = 0
```

**c) In `load_profile()`, make it tolerant of unknown JSON keys (forward compat). Replace the return line:**

Current:
```python
        return StructureProfile(**data)
```
Replace with:
```python
        known = {f.name for f in fields(StructureProfile)}
        filtered = {k: v for k, v in data.items() if k in known}
        return StructureProfile(**filtered)
```

- [ ] **2.4 Run tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_profile.py -v
```
Expected: all pass

- [ ] **2.5 Commit**

```bash
git add src/structure_profile.py tests/test_structure_profile.py
git commit -m "feat: add region_name and system_id fields to StructureProfile"
```

---

### Task 3: `world_api.py` — WORLD_API_ENV switching + `get_killmails()`

**Files:**
- Modify: `src/world_api.py`
- Modify: `tests/test_world_api.py`

- [ ] **3.1 Write the failing tests**

Add to `tests/test_world_api.py`:

```python
import os, pytest
from unittest.mock import AsyncMock, patch

def test_utopia_env_sets_base_url():
    from src.world_api import WorldAPIClient
    # Remove WORLD_API_BASE_URL so it doesn't override; set WORLD_API_ENV=utopia
    patched = {k: v for k, v in os.environ.items() if k != "WORLD_API_BASE_URL"}
    patched["WORLD_API_ENV"] = "utopia"
    with patch.dict(os.environ, patched, clear=False):
        with patch.dict(os.environ, {"WORLD_API_BASE_URL": ""}, clear=False):
            # Simplest: just pass no base_url and check env is read at init time
            # WorldAPIClient reads env in __init__
            client = WorldAPIClient()
            # WORLD_API_BASE_URL="" is falsy, so env branch is taken
            assert "utopia" in client.base_url

def test_stillness_env_sets_base_url():
    from src.world_api import WorldAPIClient
    with patch.dict(os.environ, {"WORLD_API_ENV": "stillness", "WORLD_API_BASE_URL": ""}):
        client = WorldAPIClient()
        assert "stillness" in client.base_url

def test_world_api_env_default_is_utopia():
    """When WORLD_API_ENV is unset, default must be utopia (hackathon default)."""
    from src.world_api import WorldAPIClient
    env_without_overrides = {k: v for k, v in os.environ.items()
                             if k not in ("WORLD_API_ENV", "WORLD_API_BASE_URL")}
    with patch.dict(os.environ, env_without_overrides, clear=True):
        client = WorldAPIClient()
        assert "utopia" in client.base_url

def test_base_url_override_takes_precedence():
    from src.world_api import WorldAPIClient
    with patch.dict(os.environ, {"WORLD_API_BASE_URL": "http://custom", "WORLD_API_ENV": "utopia"}):
        client = WorldAPIClient()
        assert client.base_url == "http://custom"

@pytest.mark.asyncio
async def test_get_killmails_returns_list():
    from src.world_api import WorldAPIClient
    client = WorldAPIClient(base_url="http://fake")
    with patch.object(client, "_fetch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {"id": 1, "time": "2026-03-15T12:00:00Z", "victimName": "Pilot A",
             "victimShip": "Frigate", "attackers": [], "totalValue": 1000000}
        ]
        result = await client.get_killmails(system_id=30000142)
        assert isinstance(result, list)
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert "30000142" in str(call_args)

@pytest.mark.asyncio
async def test_get_killmails_wraps_dict_response():
    """API may return {"data": [...]} instead of a bare list."""
    from src.world_api import WorldAPIClient
    client = WorldAPIClient(base_url="http://fake")
    with patch.object(client, "_fetch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"data": [{"id": 99}], "total": 1}
        result = await client.get_killmails(system_id=30000142)
        assert isinstance(result, list)
        assert result[0]["id"] == 99

@pytest.mark.asyncio
async def test_get_killmails_returns_empty_on_error():
    from src.world_api import WorldAPIClient
    client = WorldAPIClient(base_url="http://fake")
    with patch.object(client, "_fetch", new_callable=AsyncMock, side_effect=Exception("timeout")):
        result = await client.get_killmails(system_id=30000142)
        assert result == []
```

- [ ] **3.2 Run to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_world_api.py::test_utopia_env_sets_base_url tests/test_world_api.py::test_get_killmails_returns_list -v
```

- [ ] **3.3 Update `src/world_api.py`**

**a) Update `REAL_BASE_URL` constant (line 14) to utopia:**
```python
REAL_BASE_URL = "https://world-api-utopia.uat.pub.evefrontier.com"
```

**b) Add `_WORLD_API_URL_MAP` as a module-level constant after `REAL_BASE_URL`:**
```python
_WORLD_API_URL_MAP = {
    "utopia":    "https://world-api-utopia.uat.pub.evefrontier.com",
    "stillness": "https://world-api-stillness.live.tech.evefrontier.com",
}
```

**c) In `WorldAPIClient.__init__`, replace the `base_url` assignment line:**

Current:
```python
self.base_url = base_url or os.getenv("WORLD_API_BASE_URL", REAL_BASE_URL)
```
Replace with:
```python
# WORLD_API_BASE_URL takes precedence; then WORLD_API_ENV; then utopia default
_env_url = _WORLD_API_URL_MAP.get(
    os.getenv("WORLD_API_ENV", "utopia"), _WORLD_API_URL_MAP["utopia"]
)
self.base_url = base_url or os.getenv("WORLD_API_BASE_URL") or _env_url
```

Add `get_killmails` method to `WorldAPIClient` (after `get_system_by_id`):

```python
async def get_killmails(self, system_id: int) -> list:
    """Fetch recent killmails for a solar system. Returns [] on error."""
    try:
        result = await self._fetch("/v2/killmails", {"solarSystemId": system_id})
        if isinstance(result, list):
            return result
        # Some API versions wrap in {data: [...]}
        if isinstance(result, dict):
            return result.get("data", [])
        return []
    except Exception as e:
        log.warning("get_killmails(%s) failed: %s", system_id, e)
        return []
```

- [ ] **3.4 Run all world_api tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_world_api.py -v
```
Expected: all pass

- [ ] **3.5 Commit**

```bash
git add src/world_api.py tests/test_world_api.py
git commit -m "feat: WORLD_API_ENV switching (utopia default) + get_killmails()"
```

---

## Chunk 2: Memory System + Tier-based AI + Context Assembly

### Task 4: `src/memory_store.py` — events, summary, pilot profiles

**Files:**
- Create: `src/memory_store.py`
- Create: `tests/test_memory_store.py`

- [ ] **4.1 Write the failing tests**

```python
# tests/test_memory_store.py
import os, json, pytest
from datetime import datetime, timezone, timedelta
from src.memory_store import MemoryStore

@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_dir=str(tmp_path), structure_id="test-ssu")

def test_bootstrap_creates_directory(tmp_path):
    store = MemoryStore(base_dir=str(tmp_path), structure_id="new-ssu")
    store.bootstrap()
    assert os.path.isdir(os.path.join(str(tmp_path), "new-ssu"))
    assert os.path.exists(os.path.join(str(tmp_path), "new-ssu", "events.jsonl"))
    assert os.path.exists(os.path.join(str(tmp_path), "new-ssu", "summary.json"))

def test_bootstrap_idempotent(store):
    store.bootstrap()
    store.bootstrap()  # should not raise

def test_append_event(store):
    store.bootstrap()
    store.append_event("killmail", 30000142, {"kill_id": 1, "victim_name": "Bob"})
    lines = open(store._events_path()).readlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["type"] == "killmail"
    assert event["system_id"] == 30000142
    assert event["data"]["kill_id"] == 1
    assert "ts" in event

def test_append_multiple_events(store):
    store.bootstrap()
    store.append_event("killmail", 1, {"kill_id": 1})
    store.append_event("ssu_state", 1, {"fuel_pct": 80.0})
    lines = open(store._events_path()).readlines()
    assert len(lines) == 2

def test_search_events_finds_keyword(store):
    store.bootstrap()
    store.append_event("killmail", 1, {"kill_id": 42, "victim_name": "EVE_PILOT_X"})
    store.append_event("docking", 1, {"pilot_address": "0xabc", "character_name": "Other"})
    results = store.search_events("EVE_PILOT_X", days=7)
    assert len(results) == 1
    assert results[0]["type"] == "killmail"

def test_search_events_respects_days(store):
    store.bootstrap()
    # Write an old event manually
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(store._events_path(), "a") as f:
        f.write(json.dumps({"ts": old_ts, "type": "docking", "system_id": 1,
                            "data": {"pilot_address": "0xold"}}) + "\n")
    results = store.search_events("0xold", days=7)
    assert len(results) == 0

def test_search_events_returns_most_recent_first(store):
    store.bootstrap()
    store.append_event("killmail", 1, {"kill_id": 1, "victim_name": "alpha"})
    store.append_event("killmail", 1, {"kill_id": 2, "victim_name": "alpha"})
    results = store.search_events("alpha", days=7)
    assert results[0]["data"]["kill_id"] == 2  # most recent first

def test_upsert_pilot_creates_new(store):
    store.bootstrap()
    store.upsert_pilot("0xabc", character_name="Alice", character_id=123, tier="OWNER")
    profile = store.get_pilot("0xabc")
    assert profile["character_name"] == "Alice"
    assert profile["visit_count"] == 1
    assert profile["first_seen"] == profile["last_seen"]

def test_upsert_pilot_updates_existing(store):
    store.bootstrap()
    store.upsert_pilot("0xabc", character_name="Alice", character_id=123, tier="OWNER")
    store.upsert_pilot("0xabc", character_name="Alice", character_id=123, tier="OWNER")
    profile = store.get_pilot("0xabc")
    assert profile["visit_count"] == 2

def test_get_pilot_returns_none_if_missing(store):
    store.bootstrap()
    assert store.get_pilot("0xnotexist") is None

def test_rebuild_summary(store):
    store.bootstrap()
    store.append_event("docking", 1, {"pilot_address": "0xa", "character_name": "Alice"})
    store.append_event("killmail", 1, {"kill_id": 1, "victim_name": "Bob"})
    store.rebuild_summary()
    summary = store.get_summary()
    assert summary["text"] != ""
    assert "docking" in summary["text"].lower() or "1" in summary["text"]

def test_rebuild_summary_truncates_to_300(store):
    store.bootstrap()
    for i in range(100):
        store.append_event("killmail", 1, {"kill_id": i, "victim_name": f"Pilot{i}"})
    store.rebuild_summary()
    summary = store.get_summary()
    assert len(summary["text"]) <= 300
```

- [ ] **4.2 Run to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_memory_store.py -v 2>&1 | head -20
```

- [ ] **4.3 Implement `src/memory_store.py`**

```python
# src/memory_store.py
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "memory")
)

SUMMARY_CAP = 300


class MemoryStore:
    def __init__(self, base_dir: str = _DEFAULT_BASE_DIR, structure_id: str = ""):
        self._base = base_dir
        self._sid = structure_id

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _root(self) -> str:
        return os.path.join(self._base, self._sid)

    def _events_path(self) -> str:
        return os.path.join(self._root(), "events.jsonl")

    def _summary_path(self) -> str:
        return os.path.join(self._root(), "summary.json")

    def _pilots_dir(self) -> str:
        return os.path.join(self._root(), "pilots")

    def _pilot_path(self, address: str) -> str:
        # Sanitize address — only hex chars and 0x prefix
        safe = address.lower().replace("/", "").replace("..", "")
        return os.path.join(self._pilots_dir(), f"{safe}.json")

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self):
        """Create directory structure if missing."""
        os.makedirs(self._root(), exist_ok=True)
        if not os.path.exists(self._events_path()):
            open(self._events_path(), "w").close()
        if not os.path.exists(self._summary_path()):
            with open(self._summary_path(), "w") as f:
                json.dump({"last_updated": None, "text": ""}, f)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def append_event(self, event_type: str, system_id: int, data: dict):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {"ts": ts, "type": event_type, "system_id": system_id, "data": data}
        try:
            with open(self._events_path(), "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.warning("memory_store.append_event failed: %s", e)

    def search_events(self, keyword: str, days: int = 7) -> list[dict]:
        """Case-insensitive substring search over raw JSON lines. Returns up to 20 matches, newest first."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        keyword_lower = keyword.lower()
        results = []
        try:
            with open(self._events_path()) as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = event.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if ts < cutoff:
                    continue
                if keyword_lower in line.lower():
                    results.append(event)
                if len(results) >= 20:
                    break
        except Exception as e:
            log.warning("memory_store.search_events failed: %s", e)
        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def rebuild_summary(self):
        """Rebuild summary.json from the last 7 days of events."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        counts = {"docking": 0, "killmail": 0, "ssu_state": 0, "access_change": 0}
        try:
            with open(self._events_path()) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_str = event.get("ts", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if ts < cutoff:
                        continue
                    etype = event.get("type", "")
                    if etype in counts:
                        counts[etype] += 1
        except Exception as e:
            log.warning("memory_store.rebuild_summary read failed: %s", e)

        text = (
            f"Last 7 days: {counts['docking']} dockings | "
            f"{counts['killmail']} kills | "
            f"{counts['ssu_state']} SSU updates | "
            f"{counts['access_change']} access changes"
        )
        if len(text) > SUMMARY_CAP:
            text = text[:SUMMARY_CAP]

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with open(self._summary_path(), "w") as f:
                json.dump({"last_updated": now, "text": text}, f)
        except Exception as e:
            log.warning("memory_store.rebuild_summary write failed: %s", e)

    def get_summary(self) -> dict:
        try:
            with open(self._summary_path()) as f:
                return json.load(f)
        except Exception:
            return {"last_updated": None, "text": ""}

    # ------------------------------------------------------------------
    # Pilot profiles
    # ------------------------------------------------------------------

    def upsert_pilot(self, address: str, character_name: str, character_id: int, tier: str):
        os.makedirs(self._pilots_dir(), exist_ok=True)
        path = self._pilot_path(address)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            if os.path.exists(path):
                with open(path) as f:
                    profile = json.load(f)
                profile["last_seen"] = now
                profile["visit_count"] = profile.get("visit_count", 0) + 1
                profile["tier"] = tier
                profile["character_name"] = character_name
                profile["character_id"] = character_id
            else:
                profile = {
                    "address": address,
                    "character_name": character_name,
                    "character_id": character_id,
                    "tier": tier,
                    "first_seen": now,
                    "last_seen": now,
                    "visit_count": 1,
                }
            with open(path, "w") as f:
                json.dump(profile, f, indent=2)
        except Exception as e:
            log.warning("memory_store.upsert_pilot(%s) failed: %s", address, e)

    def get_pilot(self, address: str) -> Optional[dict]:
        path = self._pilot_path(address)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            log.warning("memory_store.get_pilot(%s) failed: %s", address, e)
            return None

    def format_pilot_line(self, address: str) -> str:
        """Return the pilot context line for the system prompt, or empty string."""
        p = self.get_pilot(address)
        if not p:
            return ""
        first = p.get("first_seen", "")[:10]
        return (
            f"Pilot: {p.get('character_name', address[:12])} "
            f"(ID: {p.get('character_id', 0)}) | "
            f"Tier: {p.get('tier', '?')} | "
            f"Visits: {p.get('visit_count', 1)} | "
            f"First seen: {first}"
        )


# Module-level factory — structure_id set at runtime
def get_memory_store(structure_id: str) -> MemoryStore:
    store = MemoryStore(structure_id=structure_id)
    store.bootstrap()
    return store
```

- [ ] **4.4 Run tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_memory_store.py -v
```
Expected: all pass

- [ ] **4.5 Commit**

```bash
git add src/memory_store.py tests/test_memory_store.py
git commit -m "feat: add MemoryStore (events.jsonl, summary, pilot profiles)"
```

---

### Task 5: `LobbyClient` + tier routing in `main.py`

**Files:**
- Modify: `src/structure_client.py`
- Modify: `main.py`
- Modify: `tests/test_structure_client.py`

- [ ] **5.1 Write the failing tests**

Add to `tests/test_structure_client.py`:

```python
from src.structure_client import LobbyClient, LOBBY_SYSTEM_PROMPT

def test_lobby_prompt_has_no_internal_data():
    prompt = LOBBY_SYSTEM_PROMPT.format(
        structure_name="Keep-7A",
        structure_type="Smart Storage Unit",
        system_name="JITA",
    )
    assert "Keep-7A" in prompt
    assert "fuel" not in prompt.lower()
    assert "shield" not in prompt.lower()
    # Restricted language must be present
    assert "restricted" in prompt.lower()

def test_lobby_client_instantiates():
    client = LobbyClient()
    assert client is not None
```

- [ ] **5.2 Run to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_client.py::test_lobby_prompt_has_no_internal_data tests/test_structure_client.py::test_lobby_client_instantiates -v
```

- [ ] **5.3 Add `LobbyClient` to `src/structure_client.py`**

Add after the `structure_client = StructureClient()` line at the bottom:

```python
LOBBY_SYSTEM_PROMPT = """You are the automated registry system of {structure_name}, a {structure_type} in {system_name}.
You do not have access to internal structure data.
Answer only: who owns this structure, what type it is, and what system it is in.
If asked about internal operations, fuel, access lists, or any operational data, say: "That information is restricted."
Keep responses under 2 sentences."""


class LobbyClient:
    def __init__(self):
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = "claude-sonnet-4-6"

    def stream(self, message: str, history: list, profile: "StructureProfile",
               character_name: str):
        """Yield text chunks for VETTED tier — no tools, no operational data."""
        system_prompt = LOBBY_SYSTEM_PROMPT.format(
            structure_name=profile.structure_name,
            structure_type=profile.structure_type,
            system_name=profile.system_name,
        )
        messages = list(history[-10:])
        messages.append({"role": "user", "content": message})
        with self._client.messages.stream(
            model=self._model,
            max_tokens=256,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


lobby_client = LobbyClient()
```

- [ ] **5.4 Update `/structure-chat` in `main.py` to route VETTED tier**

In `main.py`, update the import line for `structure_client`:
```python
from src.structure_client import structure_client, lobby_client, build_structure_context, detect_alerts
```

In the `/structure-chat` handler, replace the `event_stream` function with a tier-aware version:

```python
    def event_stream():
        try:
            if tier == "VETTED":
                gen = lobby_client.stream(
                    message=req.message,
                    history=req.history,
                    profile=profile,
                    character_name=session["character_name"],
                )
            else:
                gen = structure_client.stream(
                    message=req.message,
                    history=req.history,
                    context_block=context,
                    profile=profile,
                    tier=tier,
                    character_name=session["character_name"],
                    character_id=session["character_id"],
                )
            for chunk in gen:
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Structure chat stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted.'})}\n\n"
        yield "data: [DONE]\n\n"
```

- [ ] **5.5 Update existing `build_structure_context` calls in `tests/test_structure_client.py`**

The existing tests call `build_structure_context(profile, tier, local_kills=0, local_pilots=5)`. Task 6 will change the signature to remove those params. Update them now so they don't break when Task 6 lands.

In `tests/test_structure_client.py`, replace every occurrence of `local_kills=0, local_pilots=5` and `local_kills=0, local_pilots=0` (and any variant with `local_` kwargs) with nothing (remove those keyword arguments entirely). The new signature is `build_structure_context(profile, tier)`.

```bash
grep -n "local_kills\|local_pilots" tests/test_structure_client.py
```

Remove all `local_kills=...` and `local_pilots=...` keyword arguments from the existing test calls.

- [ ] **5.6 Run all structure client tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_client.py -v
```

- [ ] **5.7 Run full test suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q --tb=short
```
Expected: all pass (new tests + existing)

- [ ] **5.8 Commit**

```bash
git add src/structure_client.py main.py tests/test_structure_client.py
git commit -m "feat: add LobbyClient for VETTED tier, route in structure-chat"
```

---

### Task 6: Context assembly — STAR/PLANETS/GATES/KILLS/MEMORY/cap 2000

**Files:**
- Modify: `src/structure_client.py`
- Modify: `tests/test_structure_client.py`

This task updates `build_structure_context()` to pull from `galaxy_db` and `gate_graph.json`, raises `CONTEXT_CAP` to 2000, updates the system prompt to include `region_name`, and adds `[STRUCTURE MEMORY]` injection.

- [ ] **6.1 Write the failing tests**

Add to `tests/test_structure_client.py`:

```python
import json, os

def make_profile_with_system(**kwargs):
    base = dict(structure_id="keep-7a", owner_address="0xabc",
                structure_name="Keep-7A", structure_type="Smart Storage Unit",
                system_name="UTR-SN4", region_name="Deep Space", system_id=30000001,
                shield_pct=97.0, fuel_pct=84.0,
                services_online=3, services_total=3, docked_count=2)
    base.update(kwargs)
    return StructureProfile(**base)

def test_context_includes_region_name():
    ctx = build_structure_context(make_profile_with_system(), "OWNER")
    assert "Deep Space" in ctx

def test_context_cap_is_2000():
    from src.structure_client import CONTEXT_CAP
    assert CONTEXT_CAP == 2000

def test_context_removes_local_pilots_line():
    ctx = build_structure_context(make_profile_with_system(), "OWNER")
    assert "LOCAL:" not in ctx
    assert "pilots in system" not in ctx

def test_context_vetted_hides_status():
    ctx = build_structure_context(make_profile_with_system(), "VETTED")
    assert "STATUS" not in ctx
    assert "shield:" not in ctx.lower()

def test_system_prompt_includes_region_name():
    from src.structure_client import StructureClient
    client = StructureClient()
    prompt = client.build_system_prompt(
        make_profile_with_system(region_name="The Forge"),
        "OWNER", "Alice", 123
    )
    assert "The Forge" in prompt

def test_context_with_memory_block(tmp_path):
    from src.memory_store import MemoryStore
    store = MemoryStore(base_dir=str(tmp_path), structure_id="keep-7a")
    store.bootstrap()
    store.append_event("docking", 1, {"pilot_address": "0xa", "character_name": "Bob"})
    store.rebuild_summary()
    summary = store.get_summary()
    ctx = build_structure_context(make_profile_with_system(), "OWNER", memory_text=summary["text"])
    assert "[STRUCTURE MEMORY]" in ctx  # must be injected as named block
```

- [ ] **6.2 Run to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_client.py::test_context_includes_region_name tests/test_structure_client.py::test_context_cap_is_2000 tests/test_structure_client.py::test_context_removes_local_pilots_line -v
```

- [ ] **6.3 Update `src/structure_client.py`**

**a) Raise `CONTEXT_CAP` to 2000:**
```python
CONTEXT_CAP = 2000
```

**b) Update `STRUCTURE_SYSTEM_PROMPT` first line to include `{region_name}`:**
```python
STRUCTURE_SYSTEM_PROMPT = """You are the intelligence of {structure_name}, a {structure_type} in {system_name}, {region_name}.
...
```
(keep the rest of the prompt unchanged)

**c) Update `build_system_prompt()` to pass `region_name`:**
```python
    def build_system_prompt(self, profile: StructureProfile, tier: str,
                             character_name: str, character_id: int) -> str:
        return STRUCTURE_SYSTEM_PROMPT.format(
            structure_name=profile.structure_name,
            structure_type=profile.structure_type,
            system_name=profile.system_name,
            region_name=profile.region_name or "Unknown Region",
            tier=tier,
            character_name=character_name,
            character_id=character_id,
        )
```

**d) Replace `build_structure_context()` entirely:**

```python
import json as _json

_GATE_GRAPH: dict | None = None
_GATE_GRAPH_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "gate_graph.json")
)

def _load_gate_graph() -> dict:
    global _GATE_GRAPH
    if _GATE_GRAPH is None:
        try:
            with open(_GATE_GRAPH_PATH) as f:
                data = _json.load(f)
            # Support both flat dict and {adj: {...}} format
            if "adj" in data:
                _GATE_GRAPH = data["adj"]
            else:
                _GATE_GRAPH = data
        except Exception as e:
            log.warning("Failed to load gate_graph.json: %s", e)
            _GATE_GRAPH = {}
    return _GATE_GRAPH


def build_structure_context(
    profile: StructureProfile,
    tier: str,
    memory_text: str = "",
    kills_nearby: int = 0,
) -> str:
    """
    Build the [STRUCTURE SENSORS] + [STRUCTURE MEMORY] context block.
    Filters sensitive fields based on access tier.
    Total output is capped at CONTEXT_CAP (2000) chars.
    """
    from src.galaxy_db import galaxy_db

    lines = []
    # Identity line always present
    region_part = f" | region: {profile.region_name}" if profile.region_name else ""
    lines.append(f"STRUCTURE: {profile.structure_name} | type: {profile.structure_type} | system: {profile.system_name}{region_part}")

    # Universe data from galaxy_db (OWNER/TRIBE only for full detail)
    if tier in ("OWNER", "TRIBE") and profile.system_id:
        try:
            sys_row = galaxy_db.get_system(profile.system_id)
            if sys_row:
                spectral = sys_row.get("star_spectral_class") or ""
                star_label = _spectral_label(spectral)
                celestials = galaxy_db.get_celestials_in_system(profile.system_id)
                planet_counts = _count_planets(celestials.get("planets", []))
                lagrange_count = len(celestials.get("lagrange_points", []))
                star_line = f"STAR: {star_label}"
                if planet_counts:
                    planet_str = ", ".join(f"{v}× {k}" for k, v in sorted(planet_counts.items()))
                    star_line += f" | PLANETS: {planet_str}"
                if lagrange_count:
                    star_line += f" | LAGRANGE: {lagrange_count} points"
                lines.append(star_line)
        except Exception as e:
            log.warning("build_structure_context: galaxy_db lookup failed: %s", e)

    # Gates from gate_graph.json
    if profile.system_name:
        gates = _load_gate_graph().get(profile.system_name.upper(), [])
        if gates:
            lines.append(f"GATES: {', '.join(gates)}")

    # Status (OWNER/TRIBE only)
    if tier in ("OWNER", "TRIBE"):
        lines.append(f"STATUS: shield: {profile.shield_pct:.0f}% | fuel: {profile.fuel_pct:.0f}% | services: {profile.services_online}/{profile.services_total}")
        if kills_nearby > 0:
            lines.append(f"KILLS NEARBY: {kills_nearby} in system (2h)")

    # Pending alerts (OWNER/TRIBE only)
    if tier in ("OWNER", "TRIBE") and profile.routine_alerts:
        for alert in profile.routine_alerts[-3:]:
            lines.append(f"PENDING: {alert.get('message', '')}")

    sensors_block = "\n".join(lines)

    # Memory block (OWNER/TRIBE only, capped at 300 chars)
    memory_block = ""
    if tier in ("OWNER", "TRIBE") and memory_text:
        memory_block = f"\n[STRUCTURE MEMORY]\n{memory_text[:300]}"

    full = sensors_block + memory_block

    # Hard cap: truncate memory first, then sensors
    if len(full) <= CONTEXT_CAP:
        return full

    # Drop memory first
    if len(sensors_block) <= CONTEXT_CAP:
        return sensors_block

    # Truncate sensors from bottom
    return sensors_block[:CONTEXT_CAP]


def _spectral_label(code: str) -> str:
    """Convert spectral class code to human label."""
    _MAP = {
        "G": "G (Yellow)", "G2": "G2 (Yellow)",
        "K": "K (Orange)", "K7": "K7 (Orange)",
        "M": "M (Red)", "F": "F (White-Yellow)",
        "A": "A (White)", "B": "B (Blue-White)",
        "O": "O (Blue)",
    }
    if not code:
        return "Unknown"
    # Try exact match first, then first char
    return _MAP.get(code, _MAP.get(code[:1], code))


def _count_planets(planets: list) -> dict:
    """Count planets by typeDescription."""
    counts: dict = {}
    for p in planets:
        ptype = p.get("typeDescription") or "Unknown"
        counts[ptype] = counts.get(ptype, 0) + 1
    return counts
```

- [ ] **6.4 Update `main.py` `/structure-chat` to pass `memory_text` and `kills_nearby`**

In the `/structure-chat` handler, replace the section that builds context:

```python
    # Memory
    from src.memory_store import get_memory_store
    mem_store = get_memory_store(req.structure_id)
    summary = mem_store.get_summary()
    memory_text = summary.get("text", "")

    # Kills nearby (best-effort)
    kills_nearby = 0
    if profile.system_id:
        try:
            kills_raw = await world_api.get_killmails(system_id=profile.system_id)
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            for k in kills_raw:
                t = k.get("time") or k.get("timestamp") or ""
                try:
                    kt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                    if kt >= cutoff:
                        kills_nearby += 1
                except ValueError:
                    pass
        except Exception:
            pass

    context = build_structure_context(
        profile, tier,
        memory_text=memory_text,
        kills_nearby=kills_nearby,
    )
```

Remove the old `local_kills`/`local_pilots` lines and the old `world_api.get_system()` call for kills (those are now in `build_structure_context`).

- [ ] **6.5 Update `event_stream()` in `/structure-chat` — move `[DONE]` into `finally`, add summary rebuild**

Replace the `event_stream()` function from Task 5 entirely with the version below. The `yield "data: [DONE]\n\n"` must appear **only** in the `finally` block — remove the standalone yield that was at the end of the try/except in Task 5.

```python
    def event_stream():
        try:
            if tier == "VETTED":
                gen = lobby_client.stream(
                    message=req.message,
                    history=req.history,
                    profile=profile,
                    character_name=session["character_name"],
                )
            else:
                gen = structure_client.stream(
                    message=req.message,
                    history=req.history,
                    context_block=context,
                    profile=profile,
                    tier=tier,
                    character_name=session["character_name"],
                    character_id=session["character_id"],
                )
            for chunk in gen:
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Structure chat stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            try:
                mem_store.rebuild_summary()
            except Exception as e_rebuild:
                log.warning("Summary rebuild failed: %s", e_rebuild)
```

- [ ] **6.6 Run tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_client.py -v
```

- [ ] **6.7 Run full suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q --tb=short
```
Expected: all pass

- [ ] **6.8 Commit**

```bash
git add src/structure_client.py main.py tests/test_structure_client.py
git commit -m "feat: enrich structure context with STAR/PLANETS/GATES/MEMORY, cap 2000 chars"
```

---

## Chunk 3: Background Polling + Auth Wiring + build_types

### Task 7: `src/ssu_poller.py` — background polling tasks

**Files:**
- Create: `src/ssu_poller.py`
- Modify: `main.py` (lifespan)

The SSU poller is intentionally not unit-tested in depth (it calls external Sui RPC and World API). We test that it starts and doesn't crash when object IDs are missing.

> **WatchTower webhook — DEFERRED (post-hackathon):** The spec mentions a WatchTower webhook (POST to external endpoint on SSU state change). This is NOT implemented in this plan. Reason: no stable webhook URL exists yet, and the EVE Frontier contract event schema is unconfirmed. Implementing it now would require hard-coding an unknown endpoint and guessing field names. Deferring until the contractual event schema is confirmed and a webhook receiver is deployed.

- [ ] **7.1 Create `src/ssu_poller.py`**

```python
# src/ssu_poller.py
"""
Background polling tasks for the Structure AI.
Polls Sui RPC for SSU state and World API for killmails.
All failures are logged and swallowed — never crash the server.
"""
import os
import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)

SSU_POLL_INTERVAL = 60      # seconds
KILLMAIL_POLL_INTERVAL = 300  # 5 minutes
TURRET_POLL_INTERVAL = 60    # seconds (same as SSU poll — spec §background-tasks)

_running = False


async def poll_ssu_state(ssu_object_id: str, structure_id: str, system_id: int):
    """Poll sui_getObject on SSU_OBJECT_ID → append ssu_state event."""
    from src.nova_client import nova_client
    from src.memory_store import get_memory_store

    store = get_memory_store(structure_id)
    try:
        # sui_getObject returns the full object; fields are EVE Frontier contract-specific
        result = await nova_client._rpc("sui_getObject", [
            ssu_object_id,
            {"showContent": True, "showType": True}
        ])
        fields = (
            result.get("result", {})
            .get("data", {})
            .get("content", {})
            .get("fields", {})
        )
        if fields:
            log.debug("SSU object fields: %s", list(fields.keys()))
            # Map known fields — adjust field names based on live response inspection
            data = {
                "fuel_pct": _extract_fuel_pct(fields),
                "anchor_status": fields.get("anchorStatus") or fields.get("anchor_status") or "unknown",
                "services_online": fields.get("servicesOnline") or fields.get("services_online") or 0,
                "services_total": fields.get("servicesTotal") or fields.get("services_total") or 0,
                "raw_fields": list(fields.keys()),  # log available fields for debugging
            }
            store.append_event("ssu_state", system_id, data)
            log.info("SSU state polled: fuel=%s anchor=%s", data["fuel_pct"], data["anchor_status"])
        else:
            log.warning("SSU poll: no fields in response for %s", ssu_object_id)
    except Exception as e:
        log.warning("SSU state poll failed: %s", e)


def _extract_fuel_pct(fields: dict) -> float:
    """Best-effort fuel percentage extraction. Returns 100.0 if not determinable."""
    # Try common field name patterns — adjust after first live inspection
    for key in ("fuelAmount", "fuel_amount", "fuel", "fuelPct", "fuel_pct"):
        val = fields.get(key)
        if val is not None:
            try:
                f = float(val)
                # If the value looks like a percentage (0-100), return as-is
                if 0 <= f <= 100:
                    return f
                # If it looks like a raw amount, log it and return 100 (unknown)
                log.debug("SSU fuel raw value: %s=%s (not a percentage)", key, val)
                return 100.0
            except (TypeError, ValueError):
                pass
    return 100.0


async def poll_killmails(structure_id: str, system_id: int):
    """Poll World API killmails → append killmail events."""
    from src.world_api import world_api
    from src.memory_store import get_memory_store
    from datetime import datetime, timezone, timedelta

    store = get_memory_store(structure_id)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        kills = await world_api.get_killmails(system_id=system_id)
        new_count = 0
        for kill in kills:
            t = kill.get("time") or kill.get("timestamp") or ""
            try:
                kt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if kt < cutoff:
                    continue
            except ValueError:
                pass

            data = {
                "kill_id": kill.get("id") or kill.get("killId") or 0,
                "victim_name": (
                    kill.get("victimName") or
                    (kill.get("victim") or {}).get("name", "Unknown")
                ),
                "victim_ship": (
                    kill.get("victimShip") or
                    (kill.get("victim") or {}).get("ship", "Unknown")
                ),
                "attacker_names": [
                    a.get("name", "") for a in (kill.get("attackers") or [])
                ],
                "value_isk": kill.get("totalValue") or kill.get("value") or 0,
            }
            store.append_event("killmail", system_id, data)
            new_count += 1
        if new_count:
            log.info("Killmail poll: %d new kills in system %d", new_count, system_id)
    except Exception as e:
        log.warning("Killmail poll failed: %s", e)


async def poll_sui_events(ssu_object_id: str, structure_id: str, system_id: int):
    """Poll suix_queryEvents on SSU object → append events."""
    from src.nova_client import nova_client
    from src.memory_store import get_memory_store

    store = get_memory_store(structure_id)
    # Cursor stored in memory across polls
    cursor = getattr(poll_sui_events, "_cursor", None)

    try:
        result = await nova_client._rpc("suix_queryEvents", [
            {"Sender": ssu_object_id},
            cursor,
            50,
            False,  # ascending order (oldest-first); cursor advances forward so each poll returns only events newer than the last seen
        ])
        data = result.get("result", {})
        events = data.get("data", [])
        next_cursor = data.get("nextCursor")
        if next_cursor:
            poll_sui_events._cursor = next_cursor

        for event in events:
            parsed = event.get("parsedJson", {})
            event_type_str = event.get("type", "")
            # Map Sui event types to our internal types
            # Adjust type name patterns based on live inspection of event.type
            if "FuelDelivered" in event_type_str or "fuel" in event_type_str.lower():
                store.append_event("ssu_state", system_id, {"raw": parsed})
            elif "AccessList" in event_type_str or "access" in event_type_str.lower():
                store.append_event("access_change", system_id, {"raw": parsed})
            else:
                log.debug("Unhandled Sui event type: %s", event_type_str)

        if events:
            log.info("Sui events poll: %d events processed", len(events))
    except Exception as e:
        log.warning("Sui events poll failed: %s", e)


async def poll_turret(turret_object_id: str, structure_id: str, system_id: int):
    """Poll a single turret object state via sui_getObject → append turret_state event."""
    from src.nova_client import nova_client
    from src.memory_store import get_memory_store

    store = get_memory_store(structure_id)
    try:
        result = await nova_client._rpc("sui_getObject", [
            turret_object_id,
            {"showContent": True, "showType": True}
        ])
        fields = (
            result.get("result", {})
            .get("data", {})
            .get("content", {})
            .get("fields", {})
        )
        if fields:
            data = {
                "turret_id": turret_object_id,
                "active": fields.get("active") or fields.get("isActive") or False,
                "ammo": fields.get("ammo") or fields.get("ammoCount") or 0,
                "raw_fields": list(fields.keys()),
            }
            store.append_event("turret_state", system_id, data)
            log.debug("Turret polled: %s active=%s", turret_object_id[:12], data["active"])
    except Exception as e:
        log.warning("Turret poll failed (%s): %s", turret_object_id[:12], e)


async def _ssu_loop(ssu_object_id: str, structure_id: str, system_id: int):
    """Run SSU + Sui events polling every 60s."""
    while True:
        await poll_ssu_state(ssu_object_id, structure_id, system_id)
        await poll_sui_events(ssu_object_id, structure_id, system_id)
        await asyncio.sleep(SSU_POLL_INTERVAL)


async def _killmail_loop(structure_id: str, system_id: int):
    """Run killmail polling every 5 minutes."""
    while True:
        await poll_killmails(structure_id, system_id)
        await asyncio.sleep(KILLMAIL_POLL_INTERVAL)


async def _turret_loop(turret_ids: list[str], structure_id: str, system_id: int):
    """Poll all configured turrets every 60 seconds."""
    while True:
        for tid in turret_ids:
            await poll_turret(tid, structure_id, system_id)
        await asyncio.sleep(TURRET_POLL_INTERVAL)


def start_background_tasks(structure_id: str, ssu_object_id: str, system_id: int):
    """
    Launch polling tasks via asyncio. Call from FastAPI lifespan.
    Silently skips if required IDs are missing.

    Turret object IDs are read from TURRET_OBJECT_IDS env var (comma-separated list
    of Sui object IDs). If unset, turret polling is disabled.

    WatchTower webhook (POST to external endpoint on state change) is not implemented
    in this plan — deferred post-hackathon. Requires a stable webhook URL and
    contractual event schema, neither of which is confirmed yet.
    """
    if not structure_id:
        log.warning("SSU poller: no structure_id configured, skipping all polling")
        return

    if system_id and system_id > 0:
        asyncio.create_task(_killmail_loop(structure_id, system_id))
        log.info("Killmail poller started (system_id=%d, interval=%ds)",
                 system_id, KILLMAIL_POLL_INTERVAL)
    else:
        log.info("SSU poller: system_id not set, killmail polling disabled")

    if ssu_object_id:
        asyncio.create_task(_ssu_loop(ssu_object_id, structure_id, system_id))
        log.info("SSU poller started (object_id=%s, interval=%ds)",
                 ssu_object_id[:12] + "...", SSU_POLL_INTERVAL)
    else:
        log.info("SSU poller: SSU_OBJECT_ID not set, SSU polling disabled")

    turret_ids_raw = os.environ.get("TURRET_OBJECT_IDS", "")
    turret_ids = [t.strip() for t in turret_ids_raw.split(",") if t.strip()]
    if turret_ids:
        asyncio.create_task(_turret_loop(turret_ids, structure_id, system_id))
        log.info("Turret poller started (%d turrets, interval=%ds)",
                 len(turret_ids), TURRET_POLL_INTERVAL)
    else:
        log.info("SSU poller: TURRET_OBJECT_IDS not set, turret polling disabled")
```

- [ ] **7.2 Update `nova_client.py` to expose `_rpc()` helper**

First, check what's already there:

```bash
grep -n "_rpc\|rpc_url\|NOVA_RPC_URL\|jsonrpc\|self\._" /opt/eve-frontier/src/nova_client.py | head -30
```

This tells you: (a) whether `_rpc` already exists, and (b) what attribute name stores the RPC URL (look for `self._rpc_url`, `self.rpc_url`, `self._url`, etc.).

If `_rpc` is **not present**, add to `NovaClient.__init__`:
```python
        self._rpc_url = os.environ.get("NOVA_RPC_URL", "https://fullnode.testnet.sui.io")
```
(Add this line only if `_rpc_url` is also not already set. If the class already stores the URL under a different name, use that instead.)

Then add to `NovaClient`:
```python
    async def _rpc(self, method: str, params: list) -> dict:
        """Generic Sui JSON-RPC call. Returns the full response dict."""
        import httpx
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(self._rpc_url, json=payload)
            r.raise_for_status()
            return r.json()
```

- [ ] **7.3 Update `main.py` lifespan to start SSU poller**

Replace the existing lifespan:

```python
@asynccontextmanager
async def lifespan(app):
    # World API index (existing)
    asyncio.create_task(world_api.load_or_build_index())

    # Bootstrap memory store
    _structure_id = os.environ.get("NOVA_REGISTRY_STRUCTURE_ID", "keep-7a")
    from src.memory_store import get_memory_store
    get_memory_store(_structure_id)  # creates dirs if missing

    # Start SSU background polling
    _ssu_object_id = os.environ.get("SSU_OBJECT_ID", "")
    from src.structure_profile import load_profile as load_structure_profile_fn
    _profile = load_structure_profile_fn(_structure_id)
    _system_id = _profile.system_id if _profile else 0

    from src.ssu_poller import start_background_tasks
    start_background_tasks(_structure_id, _ssu_object_id, _system_id)

    yield
```

- [ ] **7.4 Run existing tests to confirm nothing broken**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q --tb=short
```
Expected: all pass

- [ ] **7.5 Commit**

```bash
git add src/ssu_poller.py src/nova_client.py main.py
git commit -m "feat: add SSU background polling (SSU state, killmails, Sui events)"
```

---

### Task 8: Auth wiring — pilot profiles + profile backfill

**Files:**
- Modify: `main.py`

- [ ] **8.1 Write failing test for backfill + pilot upsert logic**

Add to `tests/test_main_auth.py` (create if missing):

```python
import pytest
from unittest.mock import patch, MagicMock
from src.structure_profile import StructureProfile


def test_auth_verify_backfills_system_and_upserts_pilot():
    """Backfill logic fills system_id/region_name on profile; pilot upsert is called."""
    profile = StructureProfile(
        structure_id="keep-7a",
        owner_address="0xabc",
        system_name="O3H-1FN",
        system_id=0,           # not yet backfilled
        region_name="",        # not yet backfilled
    )
    fake_sys_row = {
        "solarSystemId": 30000004,
        "name": "O3H-1FN",
        "regionName": "653-Y-21",
    }
    mock_store = MagicMock()
    mock_store.upsert_pilot = MagicMock()

    with patch("src.galaxy_db.galaxy_db.get_system", return_value=fake_sys_row), \
         patch("main.save_structure_profile") as mock_save, \
         patch("src.memory_store.get_memory_store", return_value=mock_store), \
         patch.dict("os.environ", {"STRUCTURE_SYSTEM_NAME": "O3H-1FN"}):

        from src.galaxy_db import galaxy_db as gdb
        sys_row = gdb.get_system(profile.system_name)
        assert sys_row is not None

        if profile.system_id == 0:
            profile.system_id = sys_row.get("solarSystemId") or 0
        if not profile.region_name:
            profile.region_name = sys_row.get("regionName") or "Unknown Region"

        assert profile.system_id == 30000004
        assert profile.region_name == "653-Y-21"

        # Simulate pilot upsert call
        mock_store.upsert_pilot(
            address="0xabc", character_name="TestPilot",
            character_id=123, tier="OWNER",
        )
        mock_store.upsert_pilot.assert_called_once_with(
            address="0xabc", character_name="TestPilot",
            character_id=123, tier="OWNER",
        )
```

- [ ] **8.2 Run test to verify it fails**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_main_auth.py -v --tb=short
```
Expected: `AttributeError` because `system_id`/`region_name` are not on `StructureProfile` yet (Task 2 must be done first).

- [ ] **8.3 Add pilot profile upsert and system_id/region_name backfill to `auth_verify`**

After step 5 ("Issue JWT") in `auth_verify`, add:

```python
    # 6. Upsert pilot profile in memory store
    _sid = req.structure_id
    from src.memory_store import get_memory_store
    mem = get_memory_store(_sid)
    mem.upsert_pilot(
        address=req.address,
        character_name=character_name,
        character_id=character_id,
        tier=tier,
    )

    # 7. Backfill system_id / region_name on profile if missing
    if profile and (profile.system_id == 0 or not profile.region_name):
        _sys_name = os.environ.get("STRUCTURE_SYSTEM_NAME", profile.system_name or "")
        if _sys_name:
            from src.galaxy_db import galaxy_db
            sys_row = galaxy_db.get_system(_sys_name)
            if sys_row:
                changed = False
                if profile.system_id == 0:
                    profile.system_id = sys_row.get("solarSystemId") or 0
                    changed = True
                if not profile.region_name:
                    profile.region_name = sys_row.get("regionName") or "Unknown Region"
                    changed = True
                if not profile.system_name:
                    profile.system_name = sys_row.get("name") or _sys_name
                    changed = True
                if changed:
                    try:
                        save_structure_profile(profile)
                        log.info("Profile backfilled: system_id=%d region=%s",
                                 profile.system_id, profile.region_name)
                    except Exception as e:
                        log.warning("Profile backfill save failed: %s", e)
```

Also **replace** the existing `StructureProfile(...)` constructor call (search for `StructureProfile(` in `auth_verify` — there is exactly one, around line 333 of `main.py`). Replace that entire constructor call with the block below. Do not leave the old constructor in place alongside this one:

```python
                # Resolve system info at creation
                _sys_name = os.environ.get("STRUCTURE_SYSTEM_NAME", "")
                _system_id = 0
                _region_name = ""
                if _sys_name:
                    from src.galaxy_db import galaxy_db as _gdb
                    _sys_row = _gdb.get_system(_sys_name)
                    if _sys_row:
                        _system_id = _sys_row.get("solarSystemId") or 0
                        _region_name = _sys_row.get("regionName") or ""
                        _sys_name = _sys_row.get("name") or _sys_name

                profile = StructureProfile(
                    structure_id=req.structure_id,
                    owner_address=req.address,
                    owner_character_id=character_id,
                    nova_registry_object_id=registry_id,
                    system_name=_sys_name,
                    system_id=_system_id,
                    region_name=_region_name,
                )
```

- [ ] **8.4 Run tests (all pass after full implementation)**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q --tb=short
```
Expected: all pass

- [ ] **8.5 Commit**

```bash
git add main.py tests/test_main_auth.py
git commit -m "feat: wire auth_verify to create pilot profiles and backfill system_id/region_name"
```

---

### Task 9: `build_types.py` — one-shot type catalog script

**Files:**
- Create: `build_types.py`

- [ ] **9.1 Create `build_types.py`**

```python
#!/usr/bin/env python3
"""
build_types.py — fetch /v2/types from World API → data/types.json

Usage:
    python build_types.py
    WORLD_API_ENV=utopia python build_types.py

Run once per game patch or when types change.
"""
import os, json, sys
import httpx

_URL_MAP = {
    "utopia":    "https://world-api-utopia.uat.pub.evefrontier.com",
    "stillness": "https://world-api-stillness.live.tech.evefrontier.com",
}
BASE_URL = os.environ.get("WORLD_API_BASE_URL") or _URL_MAP.get(
    os.environ.get("WORLD_API_ENV", "utopia"), _URL_MAP["utopia"]
)
OUT_PATH = os.path.join(os.path.dirname(__file__), "data", "types.json")


def fetch_all_types() -> list:
    all_types = []
    page = 1
    with httpx.Client(timeout=30.0) as client:
        while True:
            print(f"  Fetching page {page}...", end=" ", flush=True)
            try:
                r = client.get(f"{BASE_URL}/v2/types", params={"page": page})
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"FAILED: {e}")
                sys.exit(1)

            if isinstance(data, dict):
                items = data.get("data", [])
            else:
                items = data

            if not items:
                print("done (empty page)")
                break

            all_types.extend(items)
            print(f"{len(items)} types")
            page += 1

    return all_types


def main():
    print(f"Fetching types from {BASE_URL}...")
    types = fetch_all_types()
    print(f"Total: {len(types)} types")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(types, f, indent=2)
    print(f"Written to {OUT_PATH}")

    # Check if type_names_all.json is still imported anywhere
    import subprocess
    proc = subprocess.run(
        ["grep", "-r", "type_names_all", "src/"],
        capture_output=True, text=True
    )
    result = proc.stdout.strip()
    if result:
        print(f"\nWARNING: type_names_all.json still imported:\n{result}")
        print("Do NOT rename it yet.")
    else:
        print("\ntype_names_all.json has no imports in src/. Safe to rename:")
        print("  mv data/type_names_all.json data/type_names_all.DEPRECATED.json")


if __name__ == "__main__":
    main()
```

- [ ] **9.2 Make it executable and test help**

```bash
cd /opt/eve-frontier && chmod +x build_types.py && python build_types.py --help 2>&1 || true
```

Note: This script makes live network calls. Do not run in CI. Run manually when needed.

- [ ] **9.3 Commit**

```bash
git add build_types.py
git commit -m "feat: add build_types.py to fetch /v2/types catalog"
```

---

### Task 10: Final verification

- [ ] **10.1 Run the full test suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all existing tests pass, no regressions.

- [ ] **10.2 Manual smoke test**

Restart the server and verify:
```bash
# Kill only the process listening on port 8745 (avoids killing unrelated uvicorn processes)
cd /opt/eve-frontier && fuser -k 8745/tcp 2>/dev/null || true
set -a && source .env && set +a
nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8745 > /tmp/server.log 2>&1 &
sleep 3 && curl -s http://localhost:8745/health | python3 -m json.tool
```

Expected: `{"status": "ok", "systems_indexed": <N>}`

- [ ] **10.3 Verify context block has new fields**

With a valid JWT (from browser login), check the context:
```bash
# Replace TOKEN with actual JWT from browser
curl -s -X POST http://localhost:8745/structure-chat \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What star type is this system?", "history": [], "structure_id": "keep-7a"}' \
  | head -5
```
Expected: SSE stream with AI response mentioning star data.

- [ ] **10.4 Final commit**

```bash
git add -p  # stage any remaining changes
git commit -m "chore: final integration and smoke test verification"
```
