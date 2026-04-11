# Structural Bug Backlog

Low-urgency issues identified during a post-hackathon audit. None are causing visible
failures today, but each will bite eventually under the right conditions. Fix before any
serious multi-player load or feature work that touches these paths.

---

## 1. `companion.py:770` — `character_id` hardcoded as `0` in pilot record

**Category:** Dead write / latent data corruption  
**Severity:** Invisible today, breaks on first use

The call to `upsert_pilot` always passes `0` as `character_id`:

```python
# companion.py line 770
store.upsert_pilot(req.owner_address, req.character_name or "", 0, tier)
```

The real value was loaded three lines earlier:

```python
character_id = _session.character_id  # line 764
```

The variable is just never passed down. Every chat message overwrites the pilot
record's `character_id` field with `0`. Currently harmless because nothing reads
`character_id` from the pilot record — the AI context reads it from the session
directly (`companion.py:173`). The moment any feature reads from the pilot record
instead of the session, it will always see `0`.

**Fix:** Pass `character_id` instead of `0`:
```python
store.upsert_pilot(req.owner_address, req.character_name or "", character_id or 0, tier)
```

---

## 2. `watcher.py:110` — Watch rules appended without dedup check

**Category:** Non-idempotent write  
**Severity:** Active bug under realistic conditions (network retry, double-click)

`add_watch_rule` unconditionally appends to `session.watch_list`:

```python
session.watch_list.append(rule)
save_session(session)
```

No check for an existing rule with the same `ssu_id` + `scope`. A frontend network
retry or a user clicking twice creates duplicate rules. The watcher then fires two
alerts for every event on that SSU, and the list grows unboundedly.

**Fix:** Check for an existing rule before appending:
```python
existing = next(
    (r for r in session.watch_list
     if r.get("ssu_id") == req.ssu_id and r.get("scope") == req.scope),
    None
)
if existing:
    return {"rule": existing}
session.watch_list.append(rule)
save_session(session)
```

---

## 3. `memory_store.py:187–206` — `upsert_pilot` has no file lock

**Category:** Race condition on concurrent writes  
**Severity:** Low risk in single-player, real risk under load

The read-modify-write cycle in `upsert_pilot` holds no lock:

```python
if os.path.exists(path):
    with open(path) as f:          # read
        profile = json.load(f)
    profile["visit_count"] += 1    # modify
with open(path, "w") as f:         # write (no lock held across the above)
    json.dump(profile, f)
```

Two concurrent chat messages for the same pilot can both read `visit_count: 5`,
both write `6`, and one increment is silently lost. The same race could corrupt
the `tier` field if two requests resolve different tiers simultaneously. The rest
of the codebase (e.g. `courier_store.py`) uses `fcntl.LOCK_EX` for exactly this
pattern.

**Fix:** Wrap the entire read-modify-write in an exclusive `fcntl` lock, matching
the pattern used in `courier_store.py`.

---

## 4. `companion.py:750 + 770` — Pilot tier lags one message in AI context

**Category:** Ordering / stale context  
**Severity:** Cosmetic — auth is unaffected

The AI context is built at line 750 (`_preload_context`), which reads the pilot
record from disk. The pilot record is then updated at line 770 (`upsert_pilot`).
Because the update happens after the context is already assembled, the AI's first
response to a newly-vouched pilot will reference their old tier. The second message
sees the correct tier.

Authorization is not affected — tool access is derived from the session tier read
at line 762, which is always current.

**Fix:** Call `upsert_pilot` before `_preload_context`, or pass the resolved `tier`
into `_preload_context` so it can inject it directly without re-reading the file.

---

## 5. `ssu_poller.py:374` — Profile reloaded after poll instead of using return value

**Category:** Unnecessary I/O / minor race window  
**Severity:** Very unlikely to trigger, structural smell

After `poll_ssu_state` saves the updated profile, `_ssu_loop` reloads it from disk
to retrieve `connected_assembly_ids`:

```python
await poll_ssu_state(structure_id, ssu_object_id)   # saves profile
await poll_sui_events(...)                           # yields to event loop here
profile = load_profile(structure_id)                 # re-reads from disk
if profile and profile.connected_assembly_ids:
    await poll_connected_assemblies(structure_id, other_ids)
```

The `await` in `poll_sui_events` yields execution. The inventory loop (5-minute
interval) could load the profile at that moment, update `ssu_inventory`, and save
— writing a snapshot that predates `poll_ssu_state`'s changes. The subsequent
`load_profile` in `_ssu_loop` would then see the inventory loop's write, not the
poller's. In practice this race window is milliseconds and the intervals
(60s vs 300s) make it rare, but it is unnecessary.

**Fix:** Have `poll_ssu_state` return `connected_ids` and use that directly:
```python
connected_ids = await poll_ssu_state(structure_id, ssu_object_id)
await poll_sui_events(...)
if connected_ids:
    other_ids = [i for i in connected_ids if i != ssu_object_id]
    await poll_connected_assemblies(structure_id, other_ids)
```
