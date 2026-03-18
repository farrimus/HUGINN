# Radius Search — Spatial Discovery Tool

**Purpose:** Find systems within a spatial radius, apply filters (planets, killmails, heat, structures), and discover nearby points of interest.

**Status:** Deployed — server and client implementations complete. Server (all filters); client/log-agent (planets and heat only).

---

## Architecture

### Server-side (`src/radius_search.py`)

Spatial search engine that loads system data and structure locations, calculates 3D Euclidean distances, and returns filtered results.

- **Initialization:** Loads `data/systems.json` (24k+ systems) and `data/structure_locations.json` (persistent structure cache)
- **Distance metric:** Euclidean in 3D space; EVE coordinates in meters; converted to light-years (1 LY = 9.461e15 m)
- **Filters:** planets, killmails (async, World API), heat, structures (accessible to all authenticated clients)
- **Thresholding:** < 20 systems = return all results; >= 20 systems = limit to top N per filter (prevents context explosion)

### Client-side (`log-agent/radius_calculator.py`)

Lightweight client-side variant for Windows log-agent. No killmails, no structures (server-only features).

- **Initialization:** Loads `data/systems.json` from parent directory (shared)
- **Filters:** planets, heat only
- **Thresholding:** Same < 20 / >= 20 logic
- **Module-level singleton:** `init_radius_calculator()` + convenience `search()` function

---

## Server Endpoints

All endpoints require `X-Server-Token` header.

### `POST /search/radius`

Search for systems within a radius and apply filters.

**Request body:**
```json
{
  "center_system": "UR8-K7K",
  "radius_ly": 100,
  "filters": ["planets", "killmails", "heat", "structures"],
  "killmail_hours": 24,
  "top_n": 10,
  "skip_heat_traps": false
}
```

**Field details:**
- `center_system` (string, required): System name (case-insensitive) or ID
- `radius_ly` (float, required): Search radius in light-years; must be > 0
- `filters` (list, default `["planets"]`): Filter types to apply; valid: `"planets"`, `"killmails"`, `"heat"`, `"structures"`
- `killmail_hours` (int, default 24): Lookback window for killmail recency; must be >= 1
- `top_n` (int, default 10): Max results per filter; must be > 0
- `skip_heat_traps` (bool, default false): If true, exclude warm/hot systems (>= 70°)

**Response:**
```json
{
  "data": {
    "center": "UR8-K7K",
    "radius_ly": 100,
    "total_systems": 156,
    "scan_summary": "156 systems within 100 LY",
    "filters": {
      "planets": {
        "count": 10,
        "systems": [
          {
            "name": "K7G-P4W",
            "distance_ly": 15.2,
            "planets": 8,
            "safe_jump_temp": 45
          }
        ]
      },
      "killmails": {
        "count": 3,
        "systems": [
          {
            "name": "N5Y-4N7",
            "distance_ly": 32.5,
            "kills": 5,
            "most_recent_kill_hours_ago": 3.2
          }
        ]
      },
      "heat": {
        "count": 5,
        "systems": [
          {
            "name": "T8Z-1K2",
            "distance_ly": 48.3,
            "safe_jump_temp": 95,
            "heat_class": "hot"
          }
        ]
      },
      "structures": {
        "count": 2,
        "systems": [
          {
            "name": "V9K-3X1",
            "distance_ly": 22.7,
            "structures": [
              {
                "structure_id": "STR-001",
                "system_name": "V9K-3X1",
                "reported_by": "Pilot-Name",
                "tribe": "Tribal-Affiliation",
                "discovered_at": "2026-03-15T18:45:30Z"
              }
            ]
          }
        ]
      }
    }
  }
}
```

**Curl example:**
```bash
curl -X POST http://localhost:8745/search/radius \
  -H "Content-Type: application/json" \
  -H "X-Server-Token: YOUR-TOKEN" \
  -d '{
    "center_system": "UR8-K7K",
    "radius_ly": 100,
    "filters": ["planets", "heat"],
    "top_n": 10
  }'
```

---

### `POST /structures/record`

Record a structure location in the radius search index. Adds to `data/structure_locations.json`.

**Request body:**
```json
{
  "structure_id": "STR-001",
  "system_name": "V9K-3X1",
  "reported_by": "Pilot-Name",
  "tribe": "Tribal-Affiliation"
}
```

**Field details:**
- `structure_id` (string, required): Unique structure identifier; cannot be empty
- `system_name` (string, required): EVE Frontier system name; cannot be empty
- `reported_by` (string, required): Pilot name or reporter ID; cannot be empty
- `tribe` (string, optional): Tribal affiliation or null

**Response:**
```json
{
  "data": {
    "structure_id": "STR-001",
    "system_name": "V9K-3X1",
    "reported_by": "Pilot-Name",
    "tribe": "Tribal-Affiliation",
    "discovered_at": "2026-03-15T18:45:30Z"
  }
}
```

**Curl example:**
```bash
curl -X POST http://localhost:8745/structures/record \
  -H "Content-Type: application/json" \
  -H "X-Server-Token: YOUR-TOKEN" \
  -d '{
    "structure_id": "STR-001",
    "system_name": "V9K-3X1",
    "reported_by": "MyPilot",
    "tribe": "Territorial Tribe"
  }'
```

---

### `GET /structures/locations`

Retrieve all recorded structure locations.

**Response:**
```json
{
  "data": {
    "structures": [
      {
        "structure_id": "STR-001",
        "system_name": "V9K-3X1",
        "reported_by": "Pilot-Name",
        "tribe": "Tribal-Affiliation",
        "discovered_at": "2026-03-15T18:45:30Z"
      }
    ]
  }
}
```

**Curl example:**
```bash
curl -X GET http://localhost:8745/structures/locations \
  -H "X-Server-Token: YOUR-TOKEN"
```

---

## Client-side Usage (Log-Agent)

The client-side radius calculator runs on the Windows gaming PC in the log-agent process. It is initialized at startup and available for `/search` commands.

### Initialization

Called in `log-agent/log_agent.py` at startup:

```python
from radius_calculator import init_radius_calculator

radius_calculator = init_radius_calculator()
```

### Command Syntax

In log-agent event processing or chat commands:

```python
from radius_calculator import search

result = search(
    center_system="UR8-K7K",
    radius_ly=100,
    filters=["planets", "heat"],
    top_n=10,
    skip_heat_traps=False
)
```

**Supported filters (client-only):**
- `"planets"` — systems with most planet count
- `"heat"` — warm/hot systems (>= 70°)

Note: Killmails and structures are server-only (not available on client).

### Response Format (Client)

Client response structure matches server (where applicable):

```json
{
  "center": "UR8-K7K",
  "radius_ly": 100,
  "total_systems": 156,
  "scan_summary": "156 systems within 100 LY",
  "filters": {
    "planets": {
      "count": 10,
      "systems": [
        {
          "name": "K7G-P4W",
          "distance_ly": 15.2,
          "planets": 8,
          "safe_jump_temp": 45
        }
      ]
    },
    "heat": {
      "count": 5,
      "systems": [
        {
          "name": "T8Z-1K2",
          "distance_ly": 48.3,
          "safe_jump_temp": 95,
          "heat_class": "hot"
        }
      ]
    }
  }
}
```

---

## Data Files

### `data/systems.json`

**Source:** EVE Frontier ResFiles (cached).

**Structure:**
```json
{
  "systems": {
    "30002001": {
      "id": 30002001,
      "name": "UR8-K7K",
      "x": 1.234e17,
      "y": 5.678e17,
      "z": 9.012e17,
      "safe_jump_temp": 45,
      "star_type": "K5V",
      "planet_ids": [60000001, 60000002],
      "gates": [30002002, 30002003]
    }
  }
}
```

**Key fields:**
- `id`: Solar system ID (integer)
- `name`: System name (e.g., "UR8-K7K")
- `x`, `y`, `z`: 3D coordinates in meters
- `safe_jump_temp`: System temperature; determines heat classification
- `planet_ids`: Array of planet IDs in the system
- `gates`: Array of adjacent system IDs (gate links)

### `data/structure_locations.json`

**Generated by:** Server endpoints (`/structures/record`); persisted to disk.

**Structure:**
```json
{
  "structure_locations": {
    "STR-001": {
      "system_name": "V9K-3X1",
      "reported_by": "Pilot-Name",
      "tribe": "Tribal-Affiliation",
      "discovered_at": "2026-03-15T18:45:30Z",
      "source": "manual"
    }
  },
  "built_at": 1710606330.123456
}
```

**Key fields:**
- `system_name`: System where structure is located
- `reported_by`: Pilot or reporter name
- `tribe`: Optional tribal affiliation
- `discovered_at`: ISO 8601 timestamp (UTC) when recorded
- `source`: Origin of data; typically `"manual"` (all authenticated clients can submit via /structures/record)

---

## Filter Types & Heat Classification

### Heat Classification

Systems are classified by safe jump temperature (`safe_jump_temp`):

- **cool:** < 70° — Safe, low risk of engine damage
- **warm:** 70–89° — Dangerous; ship cooling required
- **hot:** >= 90° — Very dangerous; high fuel/heat cost to jump

### Thresholding Logic

Radius searches can return many systems, causing context explosion. Thresholding prevents this:

- **< 20 systems:** Return all matching systems per filter (no truncation)
- **>= 20 systems:** Limit to `top_n` results per filter (default 10)

Example: A 200 LY radius search finds 250 systems. Per filter, return top 10 only (e.g., 10 most-profitable planets, 10 hottest systems, etc.).

### Filter Details

#### Planets

Returns systems sorted by planet count (highest first).

```json
{
  "count": 10,
  "systems": [
    {
      "name": "K7G-P4W",
      "distance_ly": 15.2,
      "planets": 8,
      "safe_jump_temp": 45
    }
  ]
}
```

#### Killmails (Server-only)

Returns systems with recent kills, sorted by kill count (highest first). Queries World API `/v2/killmails/{system_id}`.

```json
{
  "count": 3,
  "systems": [
    {
      "name": "N5Y-4N7",
      "distance_ly": 32.5,
      "kills": 5,
      "most_recent_kill_hours_ago": 3.2
    }
  ]
}
```

**Note:** Timestamps may be in seconds or milliseconds; handler normalizes to seconds.

#### Heat

Returns systems with `safe_jump_temp >= 70`, sorted by temperature (hottest first).

```json
{
  "count": 5,
  "systems": [
    {
      "name": "T8Z-1K2",
      "distance_ly": 48.3,
      "safe_jump_temp": 95,
      "heat_class": "hot"
    }
  ]
}
```

#### Structures (Server-only)

Returns systems that have recorded structures, sorted by distance (closest first). All authenticated clients can access structure data via the radius search endpoints. Authentication uses the standard X-Server-Token header (same as all other server endpoints).

```json
{
  "count": 2,
  "systems": [
    {
      "name": "V9K-3X1",
      "distance_ly": 22.7,
      "structures": [
        {
          "structure_id": "STR-001",
          "system_name": "V9K-3X1",
          "reported_by": "Pilot-Name",
          "tribe": "Tribal-Affiliation",
          "discovered_at": "2026-03-15T18:45:30Z"
        }
      ]
    }
  ]
}
```

---

## Key Behaviors & Notes

### Distance Calculation

- **Formula:** 3D Euclidean distance in meters, divided by 9.461e15 to get light-years
- **Sorting:** Results sorted by distance ascending (closest first)
- **Missing coordinates:** Systems without x/y/z are skipped

### Heat Traps & Safety

The `skip_heat_traps` flag allows filtering out dangerous systems:

```json
{
  "skip_heat_traps": true
}
```

When true, all systems with `safe_jump_temp >= 70` are excluded from results.

### Killmail Recency

Killmails are filtered by a configurable lookback window (default 24 hours). The `most_recent_kill_hours_ago` field is computed as:

```
(current_time - killmail_timestamp) / 3600
```

Timestamps in milliseconds are normalized to seconds automatically.

### Structure Data Privacy

- **Server-side:** Structures are recorded and queryable via `/structures/locations`
- **Client-side (log-agent):** Structures are NOT fetched or displayed (server-only feature)
- **Access control:** All authenticated clients can access structure data. Authentication uses the standard X-Server-Token header (same as all other server endpoints).

### Performance Considerations

- **System count:** Loading 24k+ systems is CPU-bound; distance calculations are cached in results
- **Killmail queries:** Async, parallel API calls to World API; can be slow on large radius searches
- **Thresholding:** Essential to keep response size and Claude context under control

---

## Testing

### Server-side Tests

Located in `tests/test_radius_search*.py`:

- Initialization with default and custom paths
- System loading and lookup (by name, by ID, case-insensitive)
- Distance calculation (Euclidean, light-year conversion)
- Filter correctness (planets, killmails, heat, structures)
- Thresholding logic (< 20 vs >= 20 systems)
- Structure recording and persistence

### Client-side Tests

Located in `log-agent/tests/`:

- System loading from shared `systems.json`
- Client-side filtering (planets, heat only)
- No killmail/structure leakage to client

---

## Integration Example

### Server (in-lore companion)

```python
# Chat command: /search planets near UR8-K7K within 100 LY
result = await radius_search.search(
    center_system="UR8-K7K",
    radius_ly=100,
    filters=["planets", "heat"],
    top_n=10
)

# Response includes top 10 most-populated systems and top 10 hottest nearby systems
# Companion replies: "I've scanned 156 systems within 100 LY of UR8-K7K..."
```

### Client (Windows log-agent)

```python
# Player types: /search planets in 50 LY around current system
from radius_calculator import search

result = search(
    center_system="UR8-K7K",
    radius_ly=50,
    filters=["planets", "heat"],
    top_n=5
)

# Parse result and emit event to server
# Server picks it up for context, mentions: "...scanning nearby space..."
```

---

## References

- **Server module:** `/opt/eve-frontier/src/radius_search.py`
- **Client module:** `/opt/eve-frontier/log-agent/radius_calculator.py`
- **Endpoints:** `/opt/eve-frontier/main.py` (lines 529–590)
- **Tests:** `/opt/eve-frontier/tests/test_radius_search*.py`
- **Data:** `/opt/eve-frontier/data/{systems.json, structure_locations.json}`
