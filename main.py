from dotenv import load_dotenv
import os

# Load .env FIRST, before any imports that depend on environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

# Now import everything else
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import logging

from src.world_api import world_api
from src.endpoints.transactions import tx_router
from src.endpoints.ui import ui_router
from src.endpoints.game_data import game_data_router
from src.endpoints.admin import admin_router, init_logging
from src.endpoints.search import search_router
from src.endpoints.structures import structures_router
from src.endpoints.navigation import navigation_router
from src.endpoints.companion import companion_router
from src.endpoints.entity import entity_router
from src.endpoints.session import session_router
from src.endpoints.watcher import watcher_router
from src.endpoints.courier import courier_router
from src.endpoints.tribe import tribe_router
from src.endpoints.tribe_posts import tribe_posts_router
from src.endpoints.news import news_router
from src.endpoints.logs import logs_router
from src.entity_resolver import EntityResolver
import src.entity_resolver as _entity_resolver_module
import src.ssu_watcher_task as _watcher_task
import src.huginn_news_task as _huginn_news_task

log = logging.getLogger(__name__)

# Global cache for loaded structures
_STRUCTURES_CACHE: list[dict] = []

# Server-side SSU to structure slug reverse map: ssu_object_id (hex) -> assembly_id (slug).
# Built at startup from loaded structures. Allows /auth/challenge to resolve blockchain IDs.
_SSU_TO_SLUG: dict[str, str] = {}


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Step 0: Initialize logging
    init_logging()

    # Step 1: Load configuration
    from src.config import load_config_from_env, validate_startup_config
    config = load_config_from_env()
    log.info(f"Deployment: {config['deployment_env']}")
    log.info(f"World API: {config['world_api_url']}")

    # Validate critical secrets
    errors = validate_startup_config(config)
    if errors:
        for error in errors:
            log.error(error)
        raise RuntimeError("Missing required configuration")

    # Step 2: Load all structures
    from src.structure_loader import load_structures_from_directory
    structures = load_structures_from_directory("data/structures")
    log.info(f"Structures loaded: {len(structures)}")
    for struct in structures:
        log.info(f"  • {struct['id']} ({struct['system_name']}, owner {struct['owner_address'][:6]}...)")

    # Cache structures for /structures endpoint
    global _STRUCTURES_CACHE, _SSU_TO_SLUG
    _STRUCTURES_CACHE = structures
    search_router._structures_cache = structures  # Pass to search router
    log.info(f"Cached {len(structures)} structures for /structures endpoint")

    # Build ssu_object_id → assembly_id (slug) reverse map for ID resolution
    for s in structures:
        ssu_id = s.get("ssu_object_id", "")
        slug = s.get("id", "")
        if ssu_id and slug:
            _SSU_TO_SLUG[ssu_id.lower()] = slug
    log.info(f"Built reverse map: {len(_SSU_TO_SLUG)} ssu_object_id → slug mappings")

    # Step 3: Initialize per-structure components
    from src.memory_store import get_memory_store
    from src.structure_persistence import load_profile as load_structure_profile_fn
    from src.ssu_poller import start_background_tasks

    for struct in structures:
        assembly_id = struct["id"]

        # Create memory store
        mem_store = get_memory_store(assembly_id)
        log.debug(f"Memory store initialized for {assembly_id}")

        # Start background tasks if enabled
        if struct.get("polling_enabled", True):
            ssu_object_id = struct.get("ssu_object_id", "")
            # Load system_id from existing profile if available
            profile = load_structure_profile_fn(assembly_id)
            system_id = profile.system_id if profile else 0

            start_background_tasks(assembly_id, ssu_object_id, system_id)
            log.info(f"  → Polling enabled for {assembly_id}")
        else:
            log.info(f"  → Polling disabled for {assembly_id}")

    # Step 4: Warm up World API index
    asyncio.create_task(world_api.load_or_build_index())
    log.info("World API index loaded")

    # Step 5: Initialize EntityResolvers (one per supported tenant)
    from src.graphql_queries import TENANT_CONFIG as _TENANT_CONFIG
    deployment_env = config["deployment_env"]
    _entity_resolver_module._default_tenant = deployment_env
    for _tenant_name in ("utopia", "stillness"):
        if _tenant_name not in _TENANT_CONFIG:
            log.warning("EntityResolver: skipping unknown tenant %s", _tenant_name)
            continue
        _r = EntityResolver(tenant=_tenant_name)
        _entity_resolver_module._resolvers[_tenant_name] = _r
        asyncio.create_task(_r.prewarm_types())
        log.info("EntityResolver initialized (tenant=%s)", _tenant_name)

    # Step 6: Start SSU watcher background task
    asyncio.create_task(_watcher_task.run_forever())
    log.info("SSU watcher task started")

    # Step 7: Start Huginn Signal generation task
    asyncio.create_task(_huginn_news_task.run_forever())
    log.info("Huginn news task started")

    # Step 8: Start killmail refresh task (hourly incremental sync from blockchain)
    from src.blockchain_killmails import killmail_refresh_loop
    asyncio.create_task(killmail_refresh_loop())
    log.info("Killmail refresh task started (interval=1h)")

    yield

    for _r in _entity_resolver_module._resolvers.values():
        await _r.close()

app = FastAPI(title="Ship AI Companion", lifespan=lifespan)

# Middleware: CORS (for discovery and auth endpoints)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/static/companion/index.html", include_in_schema=False)
async def companion_index():
    return FileResponse(
        "static/companion/index.html",
        headers={"Cache-Control": "no-store"},
    )

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/app", StaticFiles(directory="frontend/dist"), name="app")

# Route registration (auth now handled by @evefrontier/dapp-kit)
app.include_router(tx_router)
app.include_router(ui_router)
app.include_router(game_data_router)
app.include_router(admin_router)
app.include_router(search_router)
app.include_router(structures_router)
app.include_router(navigation_router)
app.include_router(companion_router)
app.include_router(entity_router)
app.include_router(session_router)
app.include_router(watcher_router)
app.include_router(courier_router)
app.include_router(tribe_router)
app.include_router(tribe_posts_router)
app.include_router(news_router)
app.include_router(logs_router)



