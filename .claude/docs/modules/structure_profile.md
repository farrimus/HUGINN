# structure_profile

## When Should an Agent Use This Module?

Use **structure_profile** when you need to:
- Load and validate Structure AI state (fuel, shields, services, docked pilots)
- Enforce access control (owner vs. tribe vs. vetted vs. public)
- Serialize structure data for API responses
- Track structure metadata (name, type, system, Nova registry)

The `StructureProfile` dataclass models a smart storage unit or outpost with persistent state on disk.

## Public API

```python
@dataclass
class StructureProfile:
    structure_id: str
    owner_address: str
    structure_name: str = ""
    structure_type: str = "Smart Storage Unit"
    system_name: str = ""
    shield_pct: float = 100.0
    fuel_pct: float = 100.0
    services_online: int = 0
    services_total: int = 0
    docked_count: int = 0
    # ... additional fields (nova_registry_object_id, created_at, etc.)

    def save(self, base_dir: str = _DEFAULT_BASE_DIR) -> str:
        """Write to disk as {base_dir}/{structure_id}.json (flat file, not in subdirectory)."""

    @classmethod
    def load(cls, structure_id: str, base_dir: str = _DEFAULT_BASE_DIR):
        """Load from {base_dir}/{structure_id}.json (flat file, not in subdirectory)."""

    def to_dict(self) -> dict:
        """Return all fields as dict."""

    def as_dict_for_tier(self, access_tier: str) -> dict:
        """Return fields visible to access tier (OWNER|TRIBE|VETTED|NONE)."""
```

## Access Control

Field visibility by tier:

| Tier | Visible Fields | Hidden Fields |
|------|---|---|
| `OWNER` | Everything (all fields) | None |
| `TRIBE` | Shields, fuel, services, docked, inventory | None |
| `VETTED` | System, type, name, status | Shield %, fuel %, services, registry, pilots |
| `NONE` | System, type, name (only) | All operational state |

**Important:** Tier names must be UPPERCASE in requests and code.
- Correct: `profile.as_dict_for_tier("OWNER")`
- Wrong: `profile.as_dict_for_tier("owner")` (returns public-only data)

## Behavior

- **Persistence:** Atomic writes via temp file + rename
- **File locking:** fcntl on Unix for concurrent read/write safety
- **Immutable:** Once created, `structure_id` and `owner_address` are read-only
- **Timestamps:** Auto-generates ISO8601 `created_at` on first save if missing

## Constants

- `OWNER_FIELDS` — All fields visible to owner
- `TRIBE_FIELDS` — Same as owner (tribe sees everything)
- `VETTED_HIDDEN` — Fields hidden from vetted tier

## Integration Points

- **Input:** Created by Structure AI initialization
- **Input:** Loaded by `/structures/{id}` API endpoint
- **Input:** Updated by Structure AI state changes (fuel consumption, docking events)
- **Output:** Serialized to JSON for API responses
- **Output:** Filtered by access tier via `visible_to()`
