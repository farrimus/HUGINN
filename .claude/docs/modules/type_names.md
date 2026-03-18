# type_names

## When Should an Agent Use This Module?

Use **type_names** when you need to:
- Convert numeric type IDs to human-readable names
- Look up ship, module, structure, item types by ID
- Display type information in UI or logs

The module maintains a cache of type name lookups from EVE Frontier data.

## Public API

### Single Function

**`get_type_name(type_id: int) -> str`**
- Returns human-readable type name for EVE item/structure type
- Example: `name = get_type_name(587)  # returns "Rifter" (frigate)`
- Behavior:
  - First call: Loads entire type names database into memory (≈50KB)
  - Subsequent calls: Returns cached value (O(1) dict lookup)
  - Returns: `"Unknown"` if type_id not found (never raises)
- Cache: Loaded once at module import from `data/type_names_all.json`
- Thread-safe: Dict is read-only after initialization; no race conditions

### Design Notes

The module intentionally exposes only one function to keep the interface simple. All type name lookups go through this single point. No fallback mechanism—if a type isn't found, it returns "Unknown" so callers get consistent behavior without special handling.

## Integration Points

- **Input:** Called by context_builder to name ships in combat summaries
- **Input:** Called by Structure AI to name structures and services
- **Input:** Called by UI to display item names
- **Output:** Human-readable type names flow to all context builders
