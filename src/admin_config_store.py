# src/admin_config_store.py
import os
import json
import fcntl
import logging

log = logging.getLogger(__name__)


def _config_path() -> str:
    from src.config import get_data_path
    return get_data_path("admin_config.json", env_specific=True)


def load_admin_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log.warning("admin_config_store: load failed: %s", e)
        return {}


def save_admin_config(config: dict) -> None:
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(config, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    log.info("admin_config_store: saved")
