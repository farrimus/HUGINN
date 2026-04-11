"""
src/entity_resolver.py

Resolver registry — thin wrapper over SuiAdapter.

EntityResolver is an alias for SuiAdapter. All data-access methods live in
src/sui_adapter.py (chain access) and src/datahub_types.py (type catalog).

This module only owns the per-tenant singleton registry and the two
dependency-injection helpers used by FastAPI endpoints.
"""

import logging
from typing import TYPE_CHECKING

from src.sui_adapter import SuiAdapter, TENANT_CONFIG

log = logging.getLogger(__name__)

# Public alias — all consumers import EntityResolver from here
EntityResolver = SuiAdapter

# ---------------------------------------------------------------------------
# Resolver registry (one instance per tenant, populated in main.py lifespan)
# ---------------------------------------------------------------------------

_resolvers: dict[str, EntityResolver] = {}
_default_tenant: str = "utopia"


def get_resolver_for_tenant(tenant: str) -> EntityResolver:
    """Return the EntityResolver for the given tenant.

    Falls back to the default tenant if the requested tenant is unknown.
    Raises RuntimeError if no resolvers have been registered yet (lifespan not run).
    """
    if not _resolvers:
        raise RuntimeError("EntityResolver not initialized — lifespan not run")
    if tenant in _resolvers:
        return _resolvers[tenant]
    log.warning("entity_resolver: unknown tenant %r, falling back to %s", tenant, _default_tenant)
    return _resolvers[_default_tenant]


def get_entity_resolver() -> EntityResolver:
    """Backward-compatible: returns the default-tenant resolver."""
    return get_resolver_for_tenant(_default_tenant)
