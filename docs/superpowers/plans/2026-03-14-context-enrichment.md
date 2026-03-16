# Context Enrichment Plan — Structure AI

**Goal:** Feed all actually-available data into the structure AI context. Remove phantom fields. Wire live game data into the structure profile.

**Date:** 2026-03-14
**Deadline:** March 31, 2026 (hackathon)

---

## Full Data Catalog

### Category A — Universe static data (ResFiles)
Built from `data/starmapcache.json` + `data/type_names_all.json` via `build_universe.py`.
Lives in `data/` on the server. Never changes unless the game patches.

| Dataset | Source file | Fields available | Built? |
|---------|------------|-----------------|--------|
| Systems | starmapcache.json | id, name, x/y/z, region_id, constellation_id, sun_type_id, spectral_class (K7/G2/etc), planet_ids[], gate_links[] | ✓ systems.json |
| Planet type counts per system | starmapcache.json | planetCountByType: {type_id: count} — e.g. {13:2, 2016:3} = 2 Gas + 3 Barren | ✓ in starmapcache, NOT in systems.json yet |
| Planet type names | type_names_all.json | type_id → name: 13=Gas, 11=Temperate, 12=Ice, 2014=Oceanic, 2015=Lava, 2016=Barren, 2017=Storm, 2063=Plasma | ✓ type_names_all.json |
| Gate pairs | starmapcache.json (neighbours + jumps) | system_a ↔ system_b pairs, 3,438 total | ✓ gates.json |
| Gate neighbors by name | gate_graph.json | system_name → [neighbor_name, ...] | ✓ gate_graph.json |
| Regions | starmapcache.json | id, center x/y/z, constellation_ids[], system_ids[] — **no names** | raw only |
| Constellations | starmapcache.json | id, center x/y/z, system_ids[], region_id — **no names** | raw only |
| Type names (all) | type_names_all.json | type_id → name, 32,112 entries — ships, modules, planet types, SKINs, etc. | ✓ type_names_all.json |
| Ship types | type_names_all.json | ~1,598 entries matching ship keywords — names only, no stats | names only |

**What's NOT in ResFiles:** security ratings, kill feeds, market prices, ship fitting stats, PI/resource extraction rates.

---

### Category B — Live game data (log agent → server)
Parsed from Gamelogs/ and Chatlogs/ on the gaming PC. POSTed to `/log/ingest` as events.

| Event type | Fields | Triggers |
|-----------|--------|---------|
| `system_change` | system, sender, channel | Jump gate / warp |
| `combat_summary` | system, duration_s, enemies{name:count}, damage_out, damage_in, weapons_used[] | End of combat session |
| `mining_summary` | system, duration_s, materials{name:qty}, total_units, cargo_fulls | End of mining session |
| `undock` | station, system | Undock from structure |
| `docking` | state (requested/accepted), location | Dock at structure |
| `autopilot` | state (engaged/disabled) | Autopilot toggle |
| `chat` | sender, message, channel | Any chat line |

**Not currently parsed (unknown if in logs):**
- Structure shield%, fuel%, services status
- Docked ship count
- Structure system location (could infer from `undock` event location)

---

### Category C — World API (live, external)
Base: `https://world-api-stillness.live.tech.evefrontier.com`

| Endpoint | Returns | Available? |
|---------|---------|-----------|
| `GET /v2/solarsystems` | id, name, constellationId, regionId, x/y/z — **no kills, no security** | ✓ (used for system index) |
| `GET /v2/solarsystems/{id}` | Same fields — no extra data | ✓ |
| `GET /v2/smartcharacters?address={addr}` | character id, name | ✓ (used in auth) |
| `GET /v2/smartassemblies` | 404 — does not exist | ✗ |

**Confirmed not available from World API:** security ratings, kill counts, pilot counts, structure state.

---

### Category D — Sui/Nova blockchain (live, external)
| Data | Source | Available? |
|------|--------|-----------|
| AccessRegistry: owner, tribe[], vetted[] | `sui_getObject` on AccessRegistry shared object | ✓ (used in auth) |
| Transaction history | Sui RPC | Possible but complex |

---

### Category E — Server-configured / manual
| Data | How set | Used? |
|------|---------|-------|
| Structure name | profile.structure_name | ✓ |
| Structure type | profile.structure_type | ✓ |
| System name | **NOT SET** — needs env var or log agent | ✗ |
| Shield%, fuel%, services | **STATIC at 100%/0** — needs log agent updates | partial |

---

## What Can Be Built (new scripts)

| Asset | Input | Output | Value |
|-------|-------|--------|-------|
| Planet count per system | starmapcache.json | Add to systems.json: `planets: {"Gas":2,"Barren":3}` | AI can describe local planets |
| Region/constellation name lookup | type_names_all.json + starmapcache | Map region_id/constellation_id → name | AI can say which region the structure is in |
| Ship type catalog | type_names_all.json (filtered) | ship_types.json: id → name, category | AI can identify ship types from combat logs |
| Enriched system lookup | systems.json + gate_graph | Fast name → {neighbors, spectral, planets} | Feed gate + star + planet data to context |

---

## What Is Simply Not Available

- Security ratings (not in ResFiles, not in World API)
- Kill feeds (no API in EVE Frontier — EVE Online ESI won't work)
- Local pilot count (no API)
- Ship fitting stats / HP / speed (ResFiles have type IDs but not attributes — would need a separate dogma extractor)
- Structure live state from World API (endpoint does not exist)

---

## How Data Reaches the Server

```
ResFiles (on gaming PC)
  └── build_universe.py (run once, or on patch)
        → data/systems.json       (static, server)
        → data/gates.json         (static, server)
        → data/gate_graph.json    (static, server)
  └── [NEW] build_enriched.py
        → data/systems_rich.json  (adds planets, region name)

Gamelogs/ + Chatlogs/ (gaming PC, live)
  └── log-agent/log_agent.py
        → POST /log/ingest        (live events to server)
        → [NEW] PATCH /structure/{id}  (structure state updates if log lines exist)

World API (external, live)
  └── world_api.py
        → system index (name → id)
        → character lookup (address → name/id)

Sui testnet (external, live)
  └── nova_client.py
        → AccessRegistry (tier resolution)

Manual / .env
  └── STRUCTURE_SYSTEM_NAME, STRUCTURE_NAME
        → set on first profile creation
```

---

## Implementation Steps

### Step 1 — Enrich systems.json with planet type counts (build script, server)

- [ ] **1.1** Update `build_universe.py`: read `planetCountByType` from starmapcache, map type_ids to names, add `planets` dict to each system entry
  ```python
  # e.g. {"Gas": 2, "Barren": 3, "Plasma": 1}
  PLANET_TYPE_NAMES = {13:"Gas", 11:"Temperate", 12:"Ice", 2014:"Oceanic",
                       2015:"Lava", 2016:"Barren", 2017:"Storm", 2063:"Plasma"}
  ```
- [ ] **1.2** Run `build_universe.py` to regenerate `systems.json`
- [ ] **1.3** Update `route_engine.py` to expose a `get_system_info(name)` helper (returns neighbors, spectral, planets)

### Step 2 — Set system_name from .env (immediate fix)

- [ ] **2.1** Add `STRUCTURE_SYSTEM_NAME=<system>` to `.env` and `.env.example`
- [ ] **2.2** In `main.py` `auth_verify`: on first profile creation, read env var, set `profile.system_name`
- [ ] **2.3** Reload page, confirm system name appears in structure AI context

### Step 3 — Remove phantom context fields, add real ones

- [ ] **3.1** Remove `local_kills` and `local_pilots` from `build_structure_context` — these are always 0
- [ ] **3.2** Remove World API call in `/structure-chat` (no longer needed — kills always 0 anyway)
- [ ] **3.3** Add gate neighbors from `gate_graph.json`:
  ```
  GATES: PERIMETER, NEW CALDARI, URLEN (3 connections)
  ```
- [ ] **3.4** Add star type from `systems.json`:
  ```
  STAR: K7 (Orange)
  ```
- [ ] **3.5** Add planet summary from enriched `systems.json`:
  ```
  PLANETS: 2× Gas, 3× Barren, 1× Plasma
  ```
- [ ] **3.6** Run tests

### Step 4 — PATCH /structure/{id} endpoint

- [ ] **4.1** Add `PATCH /structure/{id}` to `main.py` (OWNER JWT required):
  - Partial update: `system_name`, `shield_pct`, `fuel_pct`, `services_online`, `services_total`, `docked_count`, `structure_name`
- [ ] **4.2** Test with curl

### Step 5 — Investigate log lines for structure state (gaming PC)

- [ ] **5.1** Dock at the structure, watch Gamelogs/ for any lines about shield%, fuel%, services
- [ ] **5.2** If present: add parser + log_agent handler to POST PATCH /structure/{id}
- [ ] **5.3** Test end-to-end

### Step 6 — Validate and commit

- [ ] **6.1** Send a chat message, verify context block looks like target below
- [ ] **6.2** Commit

---

## Target Context Block

```
STRUCTURE: KEEP-7A | type: Smart Storage Unit | system: JITA
STATUS: shield: 87% | fuel: 64% | services: 2/4
DOCKED: 3 ship(s)
STAR: G2 (Yellow) | PLANETS: 2× Temperate, 3× Barren, 1× Gas
GATES: PERIMETER, NEW CALDARI, URLEN (3 connections)
PENDING: Fuel at 64%. Plan a resupply for KEEP-7A.
```
