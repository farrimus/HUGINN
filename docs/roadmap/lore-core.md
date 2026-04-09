# Lore Core — Dynamic Archive System

HUGINN has no knowledge of EVE Frontier lore — factions, world history, ships, materials, structures, or game mechanics. This document defines the architecture and full implementation plan for a dynamic lore retrieval system.

---

## Design

**Delivery: thin orientation header + `search_lore` tool**

- A minimal always-present block (~150 tokens) appended to `prompts/companion.md` names factions, key terms, and instructs HUGINN to call `search_lore` before answering lore questions.
- `search_lore(query, category)` is a new AI tool. HUGINN calls it on demand, says "scanning archives" in-character, and presents the retrieved fragment as recalled records.
- Tool call results persist in message history — a fragment retrieved early in a conversation is available for the rest of that conversation without re-fetching.
- Token cost: ~150 tokens always-on. Retrieval fires only when needed (~300–500 tokens per fetch).

**Store: SQLite with FTS5 full-text search at `data/lore.db`**

Content seeded from `data/lore_seed.json` — a manually curated JSON file. Run `scripts/import_lore.py` after content is written.

**Environment: Stillness is canonical. Utopia is the test environment.**

All `game_id` values reference the Stillness type catalog (`data/type_knowledge_stillness.json`). IDs are identical between environments for all current content.

---

## Files

| File | Role | Change type |
|------|------|-------------|
| `src/lore_store.py` | SQLite wrapper — search, upsert, seed | New |
| `src/ai_tools.py` | Register `search_lore` tool + handler | Edit |
| `src/tier_capabilities.py` | Add `search_lore` to all tier tool lists | Edit |
| `prompts/companion.md` | Add thin orientation block (names/terms only) | Edit |
| `prompts/tools.yaml` | Add `search_lore` description, response_guidance, no_result | Edit |
| `data/lore_seed.json` | Content — all ~100 lore entries | New |
| `scripts/import_lore.py` | Seed `data/lore.db` from JSON | New |

No endpoint changes. No schema changes to existing stores. No changes to `context_builder.py`, `companion.py`, session system, or tier system.

---

## Step 1 — `src/lore_store.py`

New module. Follow the same pattern as `src/system_knowledge.py`.

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS lore_fragments (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    game_id     INTEGER,
    content     TEXT NOT NULL,
    tags        TEXT,
    aliases     TEXT,
    added_at    TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
    id, title, content, tags, aliases,
    content='lore_fragments',
    content_rowid='rowid'
);
```

**`category` values (enforced):**

```
setting | faction | pillar | ship | structure | npc | fuel | ore | material | mechanic | glossary | item
```

**Public interface:**

```python
search(query: str, category: str | None = None, limit: int = 3) -> list[dict]
get_by_id(id: str) -> dict | None
upsert(entry: dict) -> None
seed_from_json(path: str) -> int   # returns count imported; rejects entries with empty content
all_ids() -> list[str]
```

`search()` runs FTS5 MATCH on `lore_fts`. Apply `category` filter after FTS match. Return `[{id, title, category, content}]`.

`seed_from_json()` calls `upsert()` for each entry. Existing entries are overwritten — run it again after content updates. Raise on any entry with an empty `content` field.

Use a module-level singleton via `get_lore_store()`. DB path: `data/lore.db` relative to project root.

---

## Step 2 — `src/ai_tools.py` — register `search_lore`

Add alongside `query_system_knowledge`. Same tool registration pattern.

**Input schema:**

```python
{
    "query":    str,   # required — "Reflex corvette", "what is Still Knot", "Rogue Drone types"
    "category": str,   # optional — one of the category values above
}
```

**Handler:**

The handler must load `no_result` from `tools.yaml` explicitly — the default `no_result` mechanism only applies to `assess_threat` and `query_intel`. Return format follows the tool contract: `{"text": str, "structured": None}`.

```python
from src.prompt_loader import load_tool_prompts

results = lore_store.search(query, category=category, limit=3)
if not results:
    no_result = load_tool_prompts().get("search_lore", {}).get(
        "no_result", f"No archive records found on that subject."
    )
    return {"text": no_result, "structured": None}

text = "\n\n".join(f"[{r['title']}]\n{r['content']}" for r in results)
return {"text": text, "structured": None}
```

The fallback description in `register_tool()` can be minimal — the authoritative description lives in `tools.yaml` (Step 5).

---

## Step 3 — `src/tier_capabilities.py` — tier access

Add `"search_lore"` to the `tools` list for all four tiers: `NONE`, `VETTED`, `TRIBE`, `OWNER`.

Lore access is not gated content. A pilot asking what a Reflex is or what the Collapse was should get an answer regardless of tier. Add to every tier's list.

---

## Step 4 — `prompts/companion.md` — orientation block

Append to the end of the existing file. Target: ~60 tokens. This block is orientation only — faction names and key terms so HUGINN recognises lore-adjacent words. Trigger logic lives in `tools.yaml`.

```
**LORE ARCHIVES**
Known factions: Tribes, Syndicates, Exclave Ventures, Ophidia Operations.
Key terms: The Frontier, The Collapse, Crude Matter, Rifts, Still Knot, Feral Echo,
Fossilized Exotronics, Salt, $EVE, Askur, Ophidian Sensor Cloak.
```

Note: `companion.md` loads once at server startup. Changes require a restart.

---

## Step 5 — `prompts/tools.yaml` — `search_lore` entry

This is the primary behavior control. `description` governs when Claude calls the tool and the in-character pre-call announcement. `response_guidance` governs how it presents the result. Both reload per request — tune without a restart.

```yaml
search_lore:
  description: |
    Search the lore archives for information about EVE Frontier: factions, ships, structures,
    materials, ores, game mechanics, or world history. Use when a shell asks about:
    - what something is (ship class, item, material, structure, faction)
    - history or setting (The Collapse, The Frontier, Rogue Drones, Riders)
    - game mechanics (jump drive, heat system, clone death, network topology)
    - terminology (Still Knot, Feral Echo, Crude Matter, Rifts, $EVE, Salt)
    Do not use for live data — use get_system_intel or query_system_knowledge for that.
    Before calling: say "scanning archives" in-character.
  response_guidance: |
    Present retrieved content as a recalled archive record — not quoted text, not a recitation.
    Weave the title naturally into the response. One paragraph maximum per result.
    If multiple results are returned, lead with the most relevant.
    Do not say "according to the archives" or narrate the retrieval.
  no_result: "No archive records found on that subject. This unit has no filed data on that topic."
```

---

## Step 6 — `data/lore_seed.json` — content brief

JSON array of entry objects. Content agents fill the `content` field for every entry. All other fields are pre-populated by engineering.

**Entry structure:**

```json
{
    "id": "ship_reflex",
    "category": "ship",
    "title": "Reflex",
    "game_id": 87847,
    "content": "",
    "tags": "corvette,long-range,fuel-efficient,jump",
    "aliases": "reflex corvette"
}
```

**Writing rules for content agents:**

- Write in-universe. No meta-language: never "in the game", "players", "CCP", "devs".
- Register: intelligence-file tone. Terse, factual, operational. HUGINN recalls these as archived records.
- Length: 1–2 sentences for fuel/glossary; 2–4 sentences for ores/materials/structures; 1 paragraph for ships/npcs; 2 paragraphs for factions/setting/mechanics.
- Source authority in priority order: in-game item descriptions from `data/type_knowledge_stillness.json`, Whitepaper v0.7.5, player-confirmed behavior.
- `tags` and `aliases` are comma-separated strings. Include all plausible search terms a pilot might use.
- Do not leave `content` empty. The import script rejects empty entries.

---

## Full Entry List (~100 entries)

All IDs and `game_id` values reference the Stillness environment.

### Setting (5)

| id | title |
|----|-------|
| `setting_the_frontier` | The Frontier |
| `setting_the_collapse` | The Collapse |
| `setting_rogue_drones` | Rogue Drones (Setting) |
| `setting_riders` | The Riders |
| `setting_digital_physics` | Digital Physics & Energy |

### Factions (4)

| id | title | notes |
|----|-------|-------|
| `faction_tribes` | Tribes | player-formed |
| `faction_syndicates` | Syndicates | player-formed |
| `faction_exclave_ventures` | Exclave Ventures | NPC — Orphan Geist |
| `faction_ophidia_operations` | Ophidia Operations | NPC — Askur, Ophidian Sensor Cloak |

### Game Pillars (5)

| id | title |
|----|-------|
| `pillar_realism` | Realism |
| `pillar_cruel_survival` | Cruel Survival |
| `pillar_broken_world` | Broken World |
| `pillar_forever_game` | Forever Game |
| `pillar_co_created_universe` | Co-Created Universe |

### Ships (14)

| id | game_id | title | class |
|----|---------|-------|-------|
| `ship_wend` | 87698 | Wend | Shuttle |
| `ship_recurve` | 87846 | Recurve | Corvette |
| `ship_reflex` | 87847 | Reflex | Corvette |
| `ship_reiver` | 87848 | Reiver | Corvette |
| `ship_stride` | 91106 | Stride | Corvette |
| `ship_carom` | 91107 | Carom | Corvette |
| `ship_usv` | 81609 | USV | Frigate |
| `ship_mcf` | 81904 | MCF | Frigate |
| `ship_haf` | 82424 | HAF | Frigate |
| `ship_lai` | 82425 | LAI | Frigate |
| `ship_lorha` | 82426 | LORHA | Frigate |
| `ship_tades` | 81808 | TADES | Destroyer |
| `ship_maul` | 82430 | MAUL | Cruiser |
| `ship_chumaq` | 81611 | Chumaq | Combat Battlecruiser |

### Fuel (7)

| id | game_id | title |
|----|---------|-------|
| `fuel_d1` | 88335 | D1 Fuel |
| `fuel_d2` | 88319 | D2 Fuel |
| `fuel_sof40` | 84868 | SOF-40 Fuel |
| `fuel_sof80` | 78515 | SOF-80 Fuel |
| `fuel_eu40` | 78516 | EU-40 Fuel |
| `fuel_eu90` | 78437 | EU-90 Fuel |
| `fuel_unstable` | 77818 | Unstable Fuel |

### Structures (17)

Mini/Heavy size variants share the same lore entry.

| id | game_id | title | group |
|----|---------|-------|-------|
| `structure_ssu` | — | Smart Storage Unit | Core |
| `structure_smartgate` | 88086 | SmartGate | Gates |
| `structure_smart_turret` | 84556 | Smart Turret | Defense |
| `structure_network_node` | 88092 | Network Node | Core |
| `structure_refuge` | 87160 | Refuge | Core |
| `structure_nursery` | 91978 | Nursery | Industry |
| `structure_nest` | 91871 | Nest | Hangars |
| `structure_printer` | 87119 | Printer | Industry |
| `structure_refinery` | 88063 | Refinery | Industry |
| `structure_berth` | 88069 | Berth | Industry |
| `structure_assembler` | 88068 | Assembler | Industry |
| `structure_relay` | 90184 | Relay | Industry |
| `structure_field_cairn` | 93141 | Field Cairn | Core |
| `structure_seer` | 89775 | SEER | Misc |
| `structure_harbinger` | 89777 | HARBINGER | Misc |
| `structure_rainmaker` | 89779 | RAINMAKER | Misc |
| `structure_monolith` | 88098 | Monolith | Misc |

### NPCs (11)

| id | game_id | title |
|----|---------|-------|
| `npc_rogue_drones` | — | Rogue Drones (faction) |
| `npc_caird` | 92096 | Caird |
| `npc_luthier` | 92097 | Luthier |
| `npc_ostler` | 92098 | Ostler |
| `npc_wright` | 92099 | Wright |
| `npc_shambler` | 92100 | Shambler |
| `npc_dowser` | 92101 | Dowser |
| `npc_scrivener` | 92102 | Scrivener |
| `npc_grave_variants` | 92271 | Grave Variants (elite tier) |
| `npc_watcher` | 92503 | Watcher |
| `npc_riders` | — | The Riders |

### Ores (11)

| id | title | notes |
|----|-------|-------|
| `ore_crude_matter` | Crude Matter | covers Rough/Fine/Defiled Old/Young — all Rift variants |
| `ore_char` | Char belt ores | Feldspar Crystals family |
| `ore_slag` | Slag belt ores | Platinum-Palladium Matrix family |
| `ore_ingot` | Ingot belt ores | Iridosmine Nodules family |
| `ore_comet` | Comet belt ores | Hydrated Sulfide Matrix family |
| `ore_dewdrop` | Dewdrop belt ores | Methane Ice Shards family |
| `ore_ember` | Ember belt ores | Primitive Kerogen Matrix family |
| `ore_glint` | Glint belt ores | Aromatic Carbon Veins family |
| `ore_soot` | Soot belt ores | Tholin Nodules family |
| `ore_hermetite` | Hermetite | Fluid/Crystallizing/Stale/Sediment variants |
| `ore_deep_core_carbon` | Deep-Core Carbon | 78429 |

### Rogue Drone Materials (5)

| id | game_id | title |
|----|---------|-------|
| `material_gravionite` | 83891 | Gravionite |
| `material_luminalis` | 83892 | Luminalis |
| `material_eclipsite` | 83893 | Eclipsite |
| `material_radiantium` | 83894 | Radiantium |
| `material_catalytic_dust` | 83899 | Catalytic Dust |

### Key Materials (7)

| id | game_id | title |
|----|---------|-------|
| `material_feral_echo` | 88564 | Feral Echo |
| `material_still_knot` | 88565 | Still Knot |
| `material_echo_chamber` | 88780 | Echo Chamber |
| `material_sophrogon` | 77728 | Sophrogon |
| `material_palladium` | 99001 | Palladium |
| `material_salt` | 83839 | Salt |
| `material_feral_data` | 72244 | Feral Data |

### Key Items (8)

| id | game_id | title |
|----|---------|-------|
| `item_ophidian_sensor_cloak` | 73192 | Ophidian Sensor Cloak |
| `item_askur_access_code` | 73210 | Askur Access Code Cypher |
| `item_fossilized_exotronics` | 83818 | Fossilized Exotronics |
| `item_network_pollinator` | 83982 | Network Pollinator |
| `item_void_residue` | 91206 | Void Residue |
| `item_calamitous_marrow` | 91937 | Calamitous Marrow |
| `item_mummified_clone` | 88765 | Mummified Clone |
| `item_reaping_shell` | 91749 | Reaping Shell |

### Mechanics (6)

| id | title | covers |
|----|-------|--------|
| `mechanic_energy_heat` | Energy & Heat System | temperature, specific heat, adaptive level, heat ejectors |
| `mechanic_jump_drive` | Jump Drive | LY calculation, fuel cost, jump range at temp |
| `mechanic_warp` | Intra-System Warp | warp accelerators, intra-system movement |
| `mechanic_networks` | Network Topology | network nodes, relay, connected assemblies |
| `mechanic_clones` | Shell / Clone System | Nursery, Nest, clone death, shell types |
| `mechanic_access_control` | SSU Access Control | tiers: OWNER / TRIBE / VETTED / NONE, access registry |

---

## Step 7 — `scripts/import_lore.py`

```python
#!/usr/bin/env python3
"""Seed lore_store from data/lore_seed.json."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from src.lore_store import get_lore_store

seed_path = pathlib.Path(__file__).parent.parent / "data" / "lore_seed.json"
with open(seed_path) as f:
    entries = json.load(f)

store = get_lore_store()
count = store.seed_from_json(str(seed_path))
print(f"Imported {count} lore entries.")
```

Run from project root: `python scripts/import_lore.py`

Re-run at any time to update entries after content edits. Existing entries are overwritten.

---

## Hard Rules

1. **Never skip `search_lore` for lore questions.** The `tools.yaml` description is the trigger mechanism — tune it there, not in `companion.md`. HUGINN speculates on nothing it has not retrieved.
2. **Content agents write in-universe only.** No meta-language. No "in the game", "players", "devs".
3. **`content` must never be empty at import time.** `seed_from_json()` raises on empty entries.
4. **Do not add lore to `system_knowledge.db`.** Lore is authored, not observed. Keep the stores separate.
5. **Stillness is canonical.** All `game_id` values reference Stillness. Cross-check against `data/type_knowledge_stillness.json`.

---

## What Stays Untouched

`context_builder.py`, `src/endpoints/companion.py`, all existing endpoints, session system, `system_knowledge.db`, `intel_store.py`, `log_intel_store.py`.

---

## Verification

1. `python scripts/import_lore.py` exits with count = 100 and no errors.
2. Ask HUGINN "what is a Reflex?" — it calls `search_lore`, returns content from the archive.
3. Ask HUGINN "what happened during the Collapse?" — it says "scanning archives", calls `search_lore(query="The Collapse", category="setting")`, returns the entry.
4. Ask HUGINN a non-lore question (fuel status, route) — `search_lore` is not called.
