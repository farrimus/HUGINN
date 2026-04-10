# src/lore_store.py
"""
Static lore archive for EVE Frontier.

Authored knowledge: factions, ships, structures, materials, ores, mechanics, world history.
Searched by HUGINN via the search_lore AI tool.

Storage: data/lore.db (SQLite with FTS5, env-agnostic — lore is shared across environments)
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

log = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset({
    "setting", "faction", "pillar", "ship", "structure",
    "npc", "fuel", "ore", "material", "mechanic", "glossary", "item",
})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lore_fragments (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    game_id     INTEGER,
    content     TEXT NOT NULL,
    tags        TEXT,
    aliases     TEXT,
    added_at    TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
    id, title, content, tags, aliases,
    content='lore_fragments',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS lore_fts_insert AFTER INSERT ON lore_fragments BEGIN
    INSERT INTO lore_fts(rowid, id, title, content, tags, aliases)
    VALUES (new.rowid, new.id, new.title, new.content, new.tags, new.aliases);
END;

CREATE TRIGGER IF NOT EXISTS lore_fts_update AFTER UPDATE ON lore_fragments BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, id, title, content, tags, aliases)
    VALUES ('delete', old.rowid, old.id, old.title, old.content, old.tags, old.aliases);
    INSERT INTO lore_fts(rowid, id, title, content, tags, aliases)
    VALUES (new.rowid, new.id, new.title, new.content, new.tags, new.aliases);
END;

CREATE TRIGGER IF NOT EXISTS lore_fts_delete AFTER DELETE ON lore_fragments BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, id, title, content, tags, aliases)
    VALUES ('delete', old.rowid, old.id, old.title, old.content, old.tags, old.aliases);
END;
"""


def _db_path() -> str:
    from src.config import get_data_path
    return get_data_path("lore.db", env_specific=False)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Initialize DB on import
try:
    _init_db()
except Exception as e:
    log.warning("lore_store: DB init failed: %s", e)


class LoreStore:
    """SQLite-backed lore archive with FTS5 full-text search."""

    def search(self, query: str, category: str | None = None, limit: int = 3) -> list[dict]:
        """Full-text search lore_fts. Optional category filter applied post-match."""
        if not query or not query.strip():
            return []
        try:
            with _get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT lf.id, lf.title, lf.category, lf.content
                    FROM lore_fts
                    JOIN lore_fragments lf ON lore_fts.rowid = lf.rowid
                    WHERE lore_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit * 4 if category else limit),
                ).fetchall()

                results = [dict(r) for r in rows]
                if category:
                    results = [r for r in results if r["category"] == category]
                return results[:limit]
        except Exception as e:
            log.warning("lore_store.search failed: %s", e)
            return []

    def get_by_id(self, id: str) -> dict | None:
        try:
            with _get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM lore_fragments WHERE id = ?", (id,)
                ).fetchone()
                return dict(row) if row else None
        except Exception as e:
            log.warning("lore_store.get_by_id failed: %s", e)
            return None

    def upsert(self, entry: dict) -> None:
        """Insert or overwrite a lore fragment."""
        if not entry.get("content", "").strip():
            raise ValueError(f"lore_store.upsert: entry '{entry.get('id')}' has empty content")

        now = _now()
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT rowid FROM lore_fragments WHERE id = ?", (entry["id"],)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE lore_fragments
                    SET category=?, title=?, game_id=?, content=?, tags=?, aliases=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        entry["category"],
                        entry["title"],
                        entry.get("game_id"),
                        entry["content"],
                        entry.get("tags", ""),
                        entry.get("aliases", ""),
                        now,
                        entry["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO lore_fragments (id, category, title, game_id, content, tags, aliases, added_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry["id"],
                        entry["category"],
                        entry["title"],
                        entry.get("game_id"),
                        entry["content"],
                        entry.get("tags", ""),
                        entry.get("aliases", ""),
                        now,
                        now,
                    ),
                )

    def seed_from_json(self, path: str) -> int:
        """Import all entries from a JSON file. Returns count imported. Raises on empty content."""
        with open(path) as f:
            entries = json.load(f)

        count = 0
        for entry in entries:
            if not entry.get("content", "").strip():
                raise ValueError(
                    f"lore_store.seed_from_json: entry '{entry.get('id')}' has empty content — "
                    "fill all content fields before importing"
                )
            self.upsert(entry)
            count += 1
        return count

    def all_ids(self) -> list[str]:
        try:
            with _get_conn() as conn:
                rows = conn.execute("SELECT id FROM lore_fragments ORDER BY id").fetchall()
                return [r["id"] for r in rows]
        except Exception as e:
            log.warning("lore_store.all_ids failed: %s", e)
            return []


_store: LoreStore | None = None


def get_lore_store() -> LoreStore:
    global _store
    if _store is None:
        _store = LoreStore()
    return _store
