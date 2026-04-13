# src/endpoints/ -- FastAPI Route Handlers

One file per feature area. All routers registered in `main.py` at startup.

## Routers

| File | Prefix | Purpose |
|------|--------|---------|
| companion.py | /companion | AI chat -- SSE streaming + tool use (core product) |
| session.py | /session | Registration, tier resolution, pilot state |
| structures.py | /structure | Structure profiles, location management |
| navigation.py | /route, /systems | Pathfinding, system name search |
| search.py | /structures, /search | Structure list, radius search |
| logs.py | /logs | Game log upload and analysis |
| watcher.py | /watcher | SSU state change alerts (SSE) |
| courier.py | /courier | Hauling contract board CRUD |
| tribe.py | /tribe | Tribe presence heartbeat and snapshot |
| tribe_posts.py | /tribe-posts | Tribe posts CRUD + SSE stream |
| news.py | /news | Huginn Signal (latest broadcast) |
| transactions.py | /tx | Unsigned Sui PTB builder |
| admin.py | /admin | Health, config, log stream, tool registry (OWNER-gated) |
| entity.py | /entity | Assembly/network/inventory resolution |
| game_data.py | /game-data | Game type and region passthrough |
| system_knowledge.py | /knowledge | System knowledge graph queries |
| ui.py | /ui | Frontend UI config |

## Conventions

- Each file exports a single `APIRouter` with a prefix and tags.
- main.py imports and `app.include_router()` for every router.
- Tier gating uses `tier_capabilities.py` -- do not inline blockchain calls in endpoints.
- All endpoint functions are async.

## Adding a New Endpoint

1. Create `src/endpoints/<feature>.py` with a new `APIRouter`.
2. Import and `app.include_router()` in `main.py`.
3. Add tier gating in `tier_capabilities.py` if the feature is tier-restricted.
4. Add tests in `tests/test_main.py` or a new test file.
