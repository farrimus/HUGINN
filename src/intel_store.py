# src/intel_store.py
"""
Field intelligence store — pilot-reported facts accumulated by HUGINN.

HUGINN's sensors are limited to the structure. Pilots bring external intelligence:
enemy behavior, resource locations, crafting knowledge, hazards. This store
persists those facts per-structure so every pilot benefits from what scouts report.

Storage: data/{env}/intel/{structure_id}.json
Cap: 100 entries per structure (oldest pruned on overflow).
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

MAX_ENTRIES = 100


class IntelStore:
    def __init__(self, structure_id: str):
        from src.config import get_data_path
        base = get_data_path("intel", env_specific=True)
        os.makedirs(base, exist_ok=True)
        self._path = os.path.join(base, f"{structure_id}.json")
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not os.path.exists(self._path):
            return []
        try:
            with open(self._path) as f:
                return json.load(f)
        except Exception as e:
            log.warning("intel_store: load failed (%s): %s", self._path, e)
            return []

    def _save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._entries, f, indent=2)
        except Exception as e:
            log.warning("intel_store: save failed (%s): %s", self._path, e)

    def log_intel(self, content: str, reported_by: str = "", tags: list[str] = None) -> dict:
        """Store a new intel entry. Prunes oldest if over cap. Returns the entry."""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "content": content[:500],
            "reported_by": (reported_by or "unknown")[:64],
            "reported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tags": [t.lower() for t in (tags or [])],
        }
        self._entries.append(entry)
        if len(self._entries) > MAX_ENTRIES:
            self._entries = self._entries[-MAX_ENTRIES:]
        self._save()
        log.info("intel_store: logged [%s] from %s: %s", entry["id"], reported_by, content[:80])
        return entry

    def query_intel(self, keyword: str, limit: int = 10) -> list[dict]:
        """Case-insensitive keyword search across content and tags. Returns newest first."""
        kw = keyword.lower()
        results = []
        for entry in reversed(self._entries):
            searchable = entry.get("content", "") + " " + " ".join(entry.get("tags", []))
            if kw in searchable.lower():
                results.append(entry)
            if len(results) >= limit:
                break
        return results

    def get_recent(self, n: int = 5) -> list[dict]:
        """Return the N most recent entries, newest first."""
        return list(reversed(self._entries[-n:]))

    def count(self) -> int:
        return len(self._entries)


def get_intel_store(structure_id: str) -> IntelStore:
    return IntelStore(structure_id)
