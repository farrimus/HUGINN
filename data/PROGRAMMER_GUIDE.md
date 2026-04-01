# EVE Universe Database — Programmer Guide

**Purpose**: Read data from `eve_universe.db` (SQLite 3). Single file: regions, constellations, solar systems, jumps, planets, moons, NPC stations, Lagrange points, types. Produced by `generate.py`.  
**Build/sources**: [DATABASE_GENERATION.md](DATABASE_GENERATION.md).

**Open**: `sqlite3.connect("eve_universe.db")`; use `?` placeholders. Optional: `row_factory = sqlite3.Row`.

---

## Hierarchy and IDs

| Level | ID range | PK column |
|-------|----------|-----------|
| Region | 10xxxxxx | regionId |
| Constellation | 20xxxxxx | constellationId |
| Solar System | 30xxxxxx | solarSystemId |
| Planet / Moon / Station | 40xxxxxx | planetId / moonId / stationId |

**Tree**: Region → Constellation → Solar System → Planets, Moons, NpcStations, LagrangePoints; Jumps link system↔system; Types referenced by typeId. Celestial ID = look up in Planets, then Moons, then NpcStations by primary key.

---

## Tables and links

| Table | Key columns | Links to |
|-------|-------------|----------|
| Regions | regionId, name, centerX/Y/Z | — |
| Constellations | constellationId, name, regionId, centerX/Y/Z | Regions |
| SolarSystems | solarSystemId, name, constellationId, regionId, centerX/Y/Z, star_* (age, mass, temperature, spectral_class, etc.) | Constellations, Regions |
| Planets | planetId, name, solarSystemId, celestialIndex, typeId, centerX/Y/Z, radius, density, temperature, orbitRadius, typeDescription, … | SolarSystems; Types |
| Moons | moonId, name, planetId, solarSystemId, typeId, centerX/Y/Z, radius, same physical cols as Planets | Planets, SolarSystems; Types |
| NpcStations | stationId, name, solarSystemId, planetId, typeId, centerX/Y/Z, operationId, … | SolarSystems, Planets; Types |
| LagrangePoints | id (AUTOINCREMENT), solarSystemId, planetId, pointType (L1–L5), centerX/Y/Z | SolarSystems, Planets |
| Jumps | fromSystemId, toSystemId (PK), jumpType, optional position cols | SolarSystems (both) |
| Types | typeId, typeName, groupId, mass, volume, … | Referenced by typeId elsewhere |

---

## Lookups by entity

| Want | Query |
|------|--------|
| Region | `SELECT * FROM Regions WHERE regionId = ?` |
| Constellations in region | `SELECT * FROM Constellations WHERE regionId = ?` |
| Systems in region | `SELECT * FROM SolarSystems WHERE regionId = ?` |
| Constellation | `SELECT * FROM Constellations WHERE constellationId = ?` |
| Systems in constellation | `SELECT * FROM SolarSystems WHERE constellationId = ?` |
| System by ID/name | `SolarSystems WHERE solarSystemId = ?` or `name = ?` |
| Planets in system | `Planets WHERE solarSystemId = ? ORDER BY celestialIndex` |
| Moons in system | `Moons WHERE solarSystemId = ?` |
| Stations in system | `NpcStations WHERE solarSystemId = ?` |
| Lagrange in system | `LagrangePoints WHERE solarSystemId = ?` |
| Jumps from/to system | `Jumps WHERE fromSystemId = ?` or `toSystemId = ?` |
| Planet | `Planets WHERE planetId = ?` |
| Moons of planet | `Moons WHERE planetId = ?` |
| Stations at planet | `NpcStations WHERE planetId = ?` |
| Lagrange at planet | `LagrangePoints WHERE planetId = ?` |
| Type | `Types WHERE typeId = ?`; by name: `Types WHERE typeName LIKE ?` |
| Celestial by ID | Try Planets.planetId, then Moons.moonId, then NpcStations.stationId |

---

## Columns (summary)

- **Regions**: regionId, name, centerX, centerY, centerZ (REAL nullable).
- **Constellations**: constellationId, name, regionId, centerX/Y/Z.
- **SolarSystems**: solarSystemId, name, constellationId, regionId, centerX/Y/Z, frost_line, habitable_zone_*, star_age, star_luminosity, star_mass, star_metallicity, star_radius, star_spectral_class, star_temperature.
- **Planets**: planetId, name, solarSystemId, celestialIndex, typeId, centerX/Y/Z, radius, density, eccentricity, escapeVelocity, surfaceGravity, temperature, pressure, orbitRadius, orbitPeriod, rotationRate, mass, typeDescription (REAL/TEXT; many nullable).
- **Moons**: moonId, name, planetId, solarSystemId, typeId, centerX/Y/Z, radius, same physical/orbital cols as Planets.
- **NpcStations**: stationId, name, solarSystemId, planetId, typeId, centerX/Y/Z, operationId, isConquerable, reprocessingEfficiency, reprocessingStationsTake.
- **LagrangePoints**: id, solarSystemId, planetId, pointType, centerX/Y/Z.
- **Jumps**: fromSystemId, toSystemId, fromCenterX/Y/Z, toCenterX/Y/Z, jumpType.
- **Types**: typeId, typeName, groupId, description, published, mass, volume, capacity, portionSize, basePrice, marketGroupId, iconId, soundId, graphicId.

IDs = INTEGER. Coords/physical = REAL (often NULL). Booleans = 0/1. Use `IS NULL` for missing FKs, not 0.

---

## Query patterns (SQL)

**System + region/constellation names:**
```sql
SELECT s.solarSystemId, s.name, c.name AS constellationName, r.name AS regionName
FROM SolarSystems s
LEFT JOIN Constellations c ON s.constellationId = c.constellationId
LEFT JOIN Regions r ON s.regionId = r.regionId WHERE s.solarSystemId = ?;
```

**All celestials in system (union):**
```sql
SELECT planetId AS id, name, 'planet' AS kind, solarSystemId, typeId, centerX, centerY, centerZ, radius FROM Planets WHERE solarSystemId = ?
UNION ALL SELECT moonId, name, 'moon', solarSystemId, typeId, centerX, centerY, centerZ, radius FROM Moons WHERE solarSystemId = ?
UNION ALL SELECT stationId, name, 'station', solarSystemId, typeId, centerX, centerY, centerZ, NULL FROM NpcStations WHERE solarSystemId = ?;
```

**Neighbors (one jump):** `SELECT toSystemId FROM Jumps WHERE fromSystemId = ? UNION SELECT fromSystemId FROM Jumps WHERE toSystemId = ?`

**Planet + type name:** `SELECT p.planetId, p.name, p.typeDescription, t.typeName FROM Planets p LEFT JOIN Types t ON p.typeId = t.typeId WHERE p.solarSystemId = ?`

---

## Python helper (query_galaxy.py)

`GalaxyDB("eve_universe.db")`: `get_system(name_or_id)`, `get_region(id)`, `get_constellation(id)`, `get_planet(id)`, `get_moon(id)`, `get_station(id)`, `get_celestials_in_system(systemId)` → {planets, moons, stations, lagrange_points}, `search_systems(pattern)`, `get_jumps_from_system(systemId)`, `run_sql(sql, params)` → list of dicts.
