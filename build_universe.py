#!/usr/bin/env python3
"""
build_universe.py — Build systems.json and gates.json from EVE Frontier static data.

Input files (must be present in data/):
  data/starmapcache.json     — from eve-frontier-tools data/json/
  data/type_names_all.json   — from eve-frontier-tools data/extracted/
  data/system_index.json     — already on server (name→id from world API)

Optional enrichment (if present):
  data/eve_universe.db       — SQLite DB: adds star_temperature, planet_count,
                               planet_types, lagrange_count per system

Output files:
  data/systems.json          — all systems: id, name, x/y/z, region, constellation,
                               star, gate_links, + enrichment if DB present
  data/gates.json            — deduplicated undirected gate pairs
"""

import json
import math
import re
import sqlite3
import time
from pathlib import Path

DATA = Path("data")

def load(name):
    p = DATA / name
    if not p.exists():
        raise FileNotFoundError(f"Missing: {p}")
    print(f"  Loading {name} ({p.stat().st_size // 1024:,} KB)...")
    return json.loads(p.read_text(encoding="utf-8"))

print("=== build_universe.py ===")
print("Loading input files...")

starmap    = load("starmapcache.json")
type_names = load("type_names_all.json")
index_data = load("system_index.json")

# Build id→name lookup from system_index (which is name→id)
name_to_id = index_data.get("index", {})
id_to_name = {str(v): k for k, v in name_to_id.items()}
print(f"  Name lookup: {len(id_to_name):,} systems")

solar_systems = starmap.get("solarSystems", {})
jumps_raw     = starmap.get("jumps", [])

print(f"  Solar systems in starmap: {len(solar_systems):,}")
print(f"  Jump entries in starmap:  {len(jumps_raw):,}")

# ---------------------------------------------------------------------------
# Parse star spectral class from type name
# "Sun K7 (Orange)" → "K7"   "Sun G2 (Yellow)" → "G2"
# ---------------------------------------------------------------------------
_SPECTRAL_RE = re.compile(r"Sun\s+([A-Z0-9]+)\s*\(", re.IGNORECASE)

def parse_spectral(type_name: str) -> str | None:
    m = _SPECTRAL_RE.search(type_name or "")
    return m.group(1) if m else None

# ---------------------------------------------------------------------------
# Build gate adjacency — union of neighbours field + jumps array
# Store as undirected pairs, keyed by frozenset to deduplicate
# ---------------------------------------------------------------------------
gate_pairs: set[tuple] = set()

# Source 1: neighbours field (already bidirectional per system)
for sys_id, sys in solar_systems.items():
    for nb in sys.get("neighbours") or []:
        pair = (min(int(sys_id), int(nb)), max(int(sys_id), int(nb)))
        gate_pairs.add(pair)

# Source 2: jumps array (union, deduplicate)
for j in jumps_raw:
    a = j.get("fromSystemID")
    b = j.get("toSystemID")
    if a and b:
        pair = (min(int(a), int(b)), max(int(a), int(b)))
        gate_pairs.add(pair)

print(f"  Unique gate pairs: {len(gate_pairs):,}")

# Build adjacency dict: sys_id (str) → [neighbor_id (int), ...]
adj: dict[str, list] = {}
for a, b in gate_pairs:
    adj.setdefault(str(a), []).append(b)
    adj.setdefault(str(b), []).append(a)

# ---------------------------------------------------------------------------
# Build systems.json
# ---------------------------------------------------------------------------
systems = {}
missing_names = 0

for sys_id, sys in solar_systems.items():
    center = sys.get("center") or [0, 0, 0]
    sun_type_id = sys.get("sunTypeID")
    sun_type_name = type_names.get(str(sun_type_id)) if sun_type_id else None
    spectral = parse_spectral(sun_type_name) if sun_type_name else None

    name = id_to_name.get(str(sys_id))
    if not name:
        missing_names += 1

    systems[sys_id] = {
        "id":               int(sys_id),
        "name":             name,
        "x":                center[0],
        "y":                center[1],
        "z":                center[2],
        "region_id":        sys.get("regionID"),
        "constellation_id": sys.get("constellationID"),
        "sun_type_id":      sun_type_id,
        "sun_type":         sun_type_name,
        "spectral_class":   spectral,
        "planet_ids":       sys.get("planetItemIDs") or [],
        "gate_links":       adj.get(str(sys_id), []),
    }

connected = sum(1 for s in systems.values() if s["gate_links"])
print(f"  Systems with gate links: {connected:,}")
print(f"  Systems missing names:   {missing_names:,}")

# ---------------------------------------------------------------------------
# Optional enrichment from eve_universe.db
# Adds: star_temperature, planet_count, planet_types dict, lagrange_count
# Hot system flag: star_temperature > 10000 K (spectral class B or O)
# ---------------------------------------------------------------------------
db_path = DATA / "eve_universe.db"
if db_path.exists():
    print(f"\nEnriching from {db_path.name}...")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Star temperatures + authoritative spectral class + luminosity + radius from DB (bulk — one query)
    # DB star_spectral_class is more accurate than the ResFiles type_name parse.
    star_data: dict[str, dict] = {}
    for row in conn.execute(
        "SELECT solarSystemId, star_temperature, star_spectral_class, "
        "star_luminosity, star_radius FROM SolarSystems"
    ):
        sid = str(row["solarSystemId"])
        star_data[sid] = {
            "temp":       row["star_temperature"],
            "spectral":   row["star_spectral_class"],
            "luminosity": row["star_luminosity"] or 0.0,
            "radius":     row["star_radius"] or 0.0,
        }

    # Planet type counts per system (bulk — one query)
    planet_types: dict[str, dict] = {}
    planet_counts: dict[str, int] = {}
    for row in conn.execute(
        "SELECT solarSystemId, typeDescription, COUNT(*) as cnt "
        "FROM Planets WHERE typeDescription IS NOT NULL "
        "GROUP BY solarSystemId, typeDescription"
    ):
        sid = str(row["solarSystemId"])
        planet_types.setdefault(sid, {})[row["typeDescription"]] = row["cnt"]
        planet_counts[sid] = planet_counts.get(sid, 0) + row["cnt"]

    # Lagrange point counts per system (bulk — one query)
    lagrange_counts: dict[str, int] = {}
    for row in conn.execute(
        "SELECT solarSystemId, COUNT(*) as cnt FROM LagrangePoints GROUP BY solarSystemId"
    ):
        lagrange_counts[str(row["solarSystemId"])] = row["cnt"]

    # Max planet orbit radius per system
    max_planet_orbit: dict[str, float] = {}
    for row in conn.execute(
        "SELECT solarSystemId, MAX(orbitRadius) as max_orbit FROM Planets GROUP BY solarSystemId"
    ):
        max_planet_orbit[str(row["solarSystemId"])] = row["max_orbit"] or 0.0

    # Max Lagrange point distance from star (star at origin in system local coords)
    max_lagrange_dist: dict[str, float] = {}
    for row in conn.execute(
        "SELECT solarSystemId, centerX, centerY, centerZ FROM LagrangePoints"
    ):
        sid = str(row["solarSystemId"])
        dist = math.sqrt(row["centerX"]**2 + row["centerY"]**2 + row["centerZ"]**2)
        if dist > max_lagrange_dist.get(sid, 0.0):
            max_lagrange_dist[sid] = dist

    conn.close()

    # Constants for safe_jump_temp formula
    _L_SUN = 3.828e26
    _K     = 100

    enriched = 0
    for sys_id, s in systems.items():
        sd   = star_data.get(sys_id, {})
        temp = sd.get("temp")
        s["star_temperature"] = temp
        s["hot_system"]       = temp is not None and temp > 10000
        # Prefer DB spectral class (physically derived) over ResFiles type_name parse
        if sd.get("spectral"):
            s["spectral_class"] = sd["spectral"]
        s["planet_count"]     = planet_counts.get(sys_id, 0)
        s["planet_types"]     = planet_types.get(sys_id, {})
        s["lagrange_count"]   = lagrange_counts.get(sys_id, 0)

        # Compute safe_jump_temp
        star_lum   = sd.get("luminosity", 0.0)
        star_rad   = sd.get("radius", 0.0)
        planet_orb = max_planet_orbit.get(sys_id, 0.0)
        lagrange_d = max_lagrange_dist.get(sys_id, 0.0)
        max_orbit_m = max(planet_orb, lagrange_d)
        if max_orbit_m == 0.0:
            max_orbit_m = star_rad  # star-only system → hot

        s["star_luminosity"] = star_lum
        s["max_orbit_m"]     = max_orbit_m

        if star_lum > 0.0 and max_orbit_m > 0.0:
            _D = max_orbit_m / 299_792_458.0
            s["safe_jump_temp"] = 100.0 * (2.0 / math.pi) * math.atan(
                _K * 2.0 * math.pi * math.sqrt(star_lum / _L_SUN) / _D
            )
        else:
            s["safe_jump_temp"] = 0.0

        enriched += 1

    hot         = sum(1 for s in systems.values() if s.get("hot_system"))
    red_zone    = sum(1 for s in systems.values() if s.get("safe_jump_temp", 0) >= 90)
    yellow_zone = sum(1 for s in systems.values() if 70 <= s.get("safe_jump_temp", 0) < 90)
    print(f"  Enriched:       {enriched:,} systems")
    print(f"  Hot systems:    {hot:,}  (star_temperature > 10,000 K)")
    print(f"  With planets:   {sum(1 for s in systems.values() if s.get('planet_count', 0) > 0):,}")
    print(f"  With lagrange:  {sum(1 for s in systems.values() if s.get('lagrange_count', 0) > 0):,}")
    print(f"  Red zone (>=90):    {red_zone:,}  systems")
    print(f"  Yellow/Orange zone (70-89): {yellow_zone:,}  systems")
else:
    print(f"\nNote: {db_path.name} not found — skipping enrichment (star_temperature, planet_types, lagrange_count)")

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
out_systems = {
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "count": len(systems),
    "systems": systems,
}
(DATA / "systems.json").write_text(json.dumps(out_systems, separators=(",", ":")), encoding="utf-8")
print(f"\n✓ systems.json written ({(DATA / 'systems.json').stat().st_size // 1024:,} KB, {len(systems):,} systems)")

gates_list = [{"a": a, "b": b} for a, b in sorted(gate_pairs)]
out_gates = {
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "count": len(gates_list),
    "gates": gates_list,
}
(DATA / "gates.json").write_text(json.dumps(out_gates, separators=(",", ":")), encoding="utf-8")
print(f"✓ gates.json written ({(DATA / 'gates.json').stat().st_size // 1024:,} KB, {len(gates_list):,} gate pairs)")

print("\nDone.")
