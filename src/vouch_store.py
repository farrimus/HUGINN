# src/vouch_store.py
import os
import re
import json
import fcntl
import logging

log = logging.getLogger(__name__)

_TIER_RANK = {"NONE": 0, "VETTED": 1, "TRIBE": 2, "OWNER": 3}
GRANTABLE_TIERS = {"VETTED", "TRIBE"}   # OWNER is on-chain only
_ENV_RE = re.compile(r"^[a-z0-9_-]{1,30}$")  # path traversal guard


def _overrides_path(env: str = None) -> str:
    if env:
        if not _ENV_RE.match(env):
            raise ValueError(f"Invalid env: {env!r}")
        data_base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
        path = os.path.join(data_base, env, "tier_overrides.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path
    from src.config import get_data_path
    return get_data_path("tier_overrides.json", env_specific=True)


def load_overrides(env: str = None) -> dict:
    path = _overrides_path(env)
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        # Sanitise: drop OWNER entries and non-string values (corruption guard)
        return {k.lower(): v for k, v in data.items()
                if isinstance(k, str) and isinstance(v, str)
                and v in _TIER_RANK and v != "OWNER"}
    except Exception as e:
        log.warning("vouch_store: load failed: %s", e)
        return {}


def _locked_mutate(fn, env: str = None):
    """Read-modify-write under exclusive lock. fn(dict) mutates the dict in-place."""
    path = _overrides_path(env)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+") as f:
            fd = None
            content = f.read()
            try:
                current = json.loads(content) if content.strip() else {}
                if not isinstance(current, dict):
                    current = {}
            except (json.JSONDecodeError, ValueError):
                log.warning("vouch_store: corrupt file on write, resetting")
                current = {}
            # Sanitise before mutating
            current = {k.lower(): v for k, v in current.items()
                       if isinstance(k, str) and isinstance(v, str)
                       and v in _TIER_RANK and v != "OWNER"}
            fn(current)
            f.seek(0)
            f.truncate()
            json.dump(current, f, indent=2)
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                pass


def set_override(wallet: str, tier: str, env: str = None) -> None:
    if tier not in GRANTABLE_TIERS:
        raise ValueError(f"Cannot grant tier {tier!r} via vouch")
    wallet = wallet.lower()
    _locked_mutate(lambda d: d.update({wallet: tier}), env=env)
    log.info("vouch_store: set %s -> %s (env=%s)", wallet[:12], tier, env or "current")


def remove_override(wallet: str, env: str = None) -> bool:
    wallet = wallet.lower()
    removed = [False]

    def _mutate(d):
        if wallet in d:
            del d[wallet]
            removed[0] = True

    _locked_mutate(_mutate, env=env)
    return removed[0]


def get_override(wallet: str, env: str = None) -> str | None:
    return load_overrides(env=env).get(wallet.lower())


def apply_override(on_chain_tier: str, wallet: str) -> str:
    """Elevation-only: return override tier if it outranks the on-chain tier.
    Always uses the current deployment env — never cross-env."""
    override = get_override(wallet)
    if override and _TIER_RANK.get(override, 0) > _TIER_RANK.get(on_chain_tier, 0):
        log.info("vouch_store: override elevates %s: %s -> %s",
                 wallet[:12], on_chain_tier, override)
        return override
    return on_chain_tier
