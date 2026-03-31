# src/session_store.py
import json
import os
import re
import logging
import fcntl
import datetime
from dataclasses import dataclass, field, asdict, fields
from typing import Optional

log = logging.getLogger(__name__)

_WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{1,64}$")


def _sessions_dir() -> str:
    from src.config import get_data_path
    return get_data_path("sessions", env_specific=True)


@dataclass
class CharacterSession:
    wallet_address: str
    character_name: str
    character_id: Optional[int] = None
    tribe_id: Optional[int] = None
    ship_profile: Optional[dict] = None
    interaction_memory: list = field(default_factory=list)
    watch_list: list = field(default_factory=list)
    created_at: str = ""
    last_seen: str = ""


def _wallet_filename(wallet_address: str) -> str:
    """Strip 0x prefix for safe filename."""
    if not _WALLET_RE.match(wallet_address):
        raise ValueError(f"Invalid wallet address: {wallet_address!r}")
    return wallet_address[2:] + ".json"  # strip "0x"


def session_path(wallet_address: str, base_dir: str = None) -> str:
    if base_dir is None:
        base_dir = _sessions_dir()
    return os.path.join(base_dir, _wallet_filename(wallet_address))


def load_session(wallet_address: str, base_dir: str = None) -> Optional[CharacterSession]:
    if base_dir is None:
        base_dir = _sessions_dir()
    try:
        path = session_path(wallet_address, base_dir)
    except ValueError as e:
        log.warning("Invalid wallet in load_session: %s", e)
        return None
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path).read())
        known = {f.name for f in fields(CharacterSession)}
        filtered = {k: v for k, v in data.items() if k in known}
        return CharacterSession(**filtered)
    except Exception as e:
        log.warning("Failed to load session %s: %s", wallet_address[:12], e)
        return None


def save_session(session: CharacterSession, base_dir: str = None):
    if base_dir is None:
        base_dir = _sessions_dir()
    path = session_path(session.wallet_address, base_dir)  # raises ValueError for invalid wallet
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        if not session.created_at:
            session.created_at = now
        session.last_seen = now
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(asdict(session), f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except ValueError:
        raise
    except Exception as e:
        log.warning("Failed to save session %s: %s", session.wallet_address[:12], e)
