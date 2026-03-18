# galaxy_db

## When Should an Agent Use This Module?

Use **galaxy_db** when you need to:
- Query EVE Frontier universe data (systems, celestials, jumps)
- Look up spatial coordinates, names, security status
- Support routing via jump adjacency queries
- Support lore queries about locations and structures

The module queries an SQLite database (`eve_universe.db`) for fast, offline access to static universe data.

## Public API

### Initialization

**`__init__(db_path: str = "data/eve_universe.db")`**
- Initializes database connection
- Default path: `data/eve_universe.db` relative to project root
- Example: `db = GalaxyDB()` or `db = GalaxyDB("/path/to/eve_universe.db")`

### System Queries

**`get_system(name_or_id: int | str) -> dict | None`**
- Fetch system by ID (int) or exact name (str)
- Returns system record with joined region/constellation names
- Returns None if not found
- Example: `db.get_system(30000142)` or `db.get_system("Jita")`

**`search_systems(pattern: str) -> list[dict]`**
- Fuzzy search systems by name (case-insensitive substring match)
- Returns up to 50 matching system records
- Example: `db.search_systems("jita")` returns all variants

**`get_region(region_id: int) -> dict | None`**
- Fetch region by ID
- Returns None if not found

**`get_constellation(constellation_id: int) -> dict | None`**
- Fetch constellation by ID
- Returns None if not found

### Celestial & Station Queries

**`get_planet(planet_id: int) -> dict | None`**
- Fetch planet by ID
- Returns None if not found

**`get_moon(moon_id: int) -> dict | None`**
- Fetch moon by ID
- Returns None if not found

**`get_station(station_id: int) -> dict | None`**
- Fetch NPC station by ID
- Returns None if not found

**`get_celestials_in_system(system_id: int) -> dict`**
- Fetch all celestials in a system
- Returns dict: `{"planets": [...], "moons": [...], "stations": [...], "lagrange_points": [...]}`
- Returns empty lists if system has no celestials or query fails

### Routing & Advanced

**`get_jumps_from_system(system_id: int) -> list[dict]`**
- Fetch all jump gates originating from this system
- Used by route_engine for BFS pathfinding
- Returns list of jump records with fromSystemId, toSystemId
- Example: `neighbors = db.get_jumps_from_system(30000142)`

**`run_sql(sql: str, params: tuple = ()) -> list[dict]`**
- Execute arbitrary SELECT query for advanced use
- Read-only: only SELECT statements allowed
- Returns list of rows as dicts
- **Warning:** Dangerous if query contains unsanitized user input (SQL injection risk)
- Example: `db.run_sql("SELECT * FROM SolarSystems WHERE regionId = ?", (10000002,))`

## Behavior

All methods:
- Return None or empty list on query failure (exceptions are logged, not raised)
- Use SQLite row_factory to return dicts instead of tuples
- Connect on-demand; connections are not pooled

## Integration Points

- **Called by:** route_engine (get_jumps_from_system), context_builder (get_system, get_celestials_in_system), structure_ai (get_region, get_constellation)
- **Data source:** SQLite database at `data/eve_universe.db`
- **Singleton:** Module exports `galaxy_db` instance (ready to use without explicit init)
