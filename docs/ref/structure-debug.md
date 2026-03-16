# Structure AI — Dev Console (`structure-debug.html`)

**Last updated:** 2026-03-16

Developer console for inspecting and editing structure profiles, chatting with the Structure AI without wallet auth, and watching live logs and pending alerts — all via `X-Server-Token` from a VPS browser.

Amber/gold color scheme (distinct from the green `debug.html` Ship AI console).

---

## Access

```
http://localhost:18789/static/structure-debug.html
```

Auth: `X-Server-Token` header (same token as all other dev endpoints). No JWT / Sui wallet required.

---

## Layout

Three columns, same structural pattern as `debug.html`.

### Col 1 — Live Log Stream

SSE from `GET /logs/stream`. Identical to `debug.html`:
- Level coloring (ERROR red, WARNING amber, DEBUG dim, INFO default)
- Autoscroll checkbox
- Hide debug checkbox
- Clear button + line count

### Col 2 — Structure Profile + Chat

**Structure selector (top)**
- Text input for `structure_id`, LOAD button.
- On load: `GET /structure-debug/{id}` → populates all sections below.

**Identity (read-only)**
- `structure_name`, `structure_type`, `system_name`, `region_name`, `owner_address`, `created_at`

**Live status (editable)**
- `shield_pct`, `fuel_pct`, `services_online`, `services_total`, `docked_count`
- SAVE PROFILE → `POST /structure-debug/{id}` with edited values
- RELOAD → re-fetches from server

**Connected assemblies** — read-only list from `connected_assemblies`

**SSU inventory** — read-only list from `ssu_inventory` (`type_name × quantity`)

**Routine alerts queue** — read-only list from `routine_alerts`, CLEAR button POSTs `{ routine_alerts: [] }`

**Structure AI chat (bottom)**
- Sends to `POST /structure-debug/chat`
- Streams SSE same as `/chat`
- AI messages prefixed with `> STRUCTURE AI //`
- Chat history kept per page load, cleared on LOAD

### Col 3 — Pipeline State + Alerts

**Pipeline state (top, scrollable)**
- Polls `GET /debug` every 5s
- Renders JSON (same as `debug.html`), with `pending_structure_alerts` split out

**Pending structure alerts (bottom panel)**
- Reads `pending_structure_alerts` from the `/debug` response
- Displayed separately; alerts are NOT popped (non-destructive read)

---

## Server Endpoints

All three endpoints use `Depends(require_token)` — no JWT required.

### `GET /structure-debug/{structure_id}`

Returns `asdict(profile)` — full profile, no tier filtering.

- 404 if profile file does not exist.

### `POST /structure-debug/{structure_id}`

Body: any subset of `StructureProfile` fields as JSON. `structure_id` in the body is ignored (path param takes precedence).

- If profile exists: updates matching fields, saves, returns full updated dict.
- If profile does not exist: creates a new `StructureProfile` if `owner_address` is in the body; 404 otherwise.
- 400 if `structure_id` fails path validation (`_SAFE_ID_RE`).

### `POST /structure-debug/chat`

Body: `{ structure_id, message, history }`.

- Loads profile (404 if missing).
- Runs `detect_alerts()` — routes urgent alerts to `log_buffer`, appends routine alerts to `profile.routine_alerts`.
- Loads memory summary via `get_memory_store(structure_id).get_summary()`.
- Calls `build_structure_context(profile, "OWNER", memory_text=...)`.
- Streams via `structure_client.stream(... tier="OWNER", character_name="[DEV CONSOLE]", character_id=0)`.
- After stream ends: calls `mem_store.rebuild_summary()`.
- Returns `StreamingResponse` (SSE, same format as `/chat` and `/structure-chat`).

**Route ordering note:** `/structure-debug/chat` is registered *before* `/structure-debug/{structure_id}` in `main.py` so FastAPI does not match `chat` as a path parameter.

---

## `/debug` response — added field

`GET /debug` now includes:

```json
{
  "pending_structure_alerts": [ ... ]
}
```

The field is a non-destructive read of `log_buffer.pending_structure_alerts` (alerts are not popped). Used by `structure-debug.html` Col 3 to display pending alerts without consuming them.

---

## Files

| File | Role |
|------|------|
| `static/structure-debug.html` | Dev console UI |
| `main.py` — `GET /structure-debug/{structure_id}` | Profile read (token-gated) |
| `main.py` — `POST /structure-debug/{structure_id}` | Profile write/create (token-gated) |
| `main.py` — `POST /structure-debug/chat` | Structure AI chat stream (token-gated, OWNER tier) |

## Dependencies (reused, not new)

| Symbol | Source |
|--------|--------|
| `require_token` | `src/auth.py` |
| `load_structure_profile`, `save_structure_profile`, `StructureProfile` | `src/structure_profile.py` |
| `structure_client`, `build_structure_context`, `detect_alerts` | `src/structure_client.py` |
| `get_memory_store` | `src/memory_store.py` |
| `log_buffer` | `src/log_buffer.py` |
