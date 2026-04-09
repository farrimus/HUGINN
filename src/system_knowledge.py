# src/system_knowledge.py
"""
Global, eternal knowledge graph mapping solar systems to known enemy types and ore types.

Aggregates field intelligence from all pilots across all time.
Built from log uploads and direct AI tool reports.

Storage: data/{env}/system_knowledge.db (SQLite, WAL mode)
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS systems (
    system_name    TEXT PRIMARY KEY,
    system_id      TEXT,
    region         TEXT,
    visit_count    INTEGER DEFAULT 0,
    first_recorded TEXT NOT NULL,
    last_updated   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sightings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name    TEXT NOT NULL REFERENCES systems(system_name),
    entry_type     TEXT NOT NULL,
    value          TEXT NOT NULL,
    value_key      TEXT NOT NULL,
    sighting_count INTEGER DEFAULT 1,
    first_seen     TEXT NOT NULL,
    last_seen      TEXT NOT NULL,
    sources        TEXT NOT NULL,
    UNIQUE(system_name, entry_type, value_key)
);

CREATE INDEX IF NOT EXISTS idx_sightings_system ON sightings(system_name);
CREATE INDEX IF NOT EXISTS idx_sightings_type   ON sightings(entry_type);
CREATE INDEX IF NOT EXISTS idx_sightings_value  ON sightings(value_key);
"""

_SKIP_NAMES = {"", "unknown"}


def _db_path(env: str | None = None) -> str:
    from src.config import get_data_path
    return get_data_path("system_knowledge.db", env_specific=True, env_override=env)


def _get_conn(env: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(env=env), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.executescript(_SCHEMA)


def _normalize(name: str) -> str:
    name = name.strip().lower()
    for prefix in ("a ", "an ", "the "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_system(system_name: str) -> tuple[str | None, str | None]:
    """Attempt to resolve system_name to (system_id, region). Returns (None, None) if not found."""
    try:
        from src.galaxy_db import galaxy_db
        row = galaxy_db.get_system(system_name)
        if row:
            system_id = str(row.get("solarSystemId", "")) or None
            region = row.get("regionName") or None
            return system_id, region
    except Exception as e:
        log.debug("system_knowledge._resolve_system(%r) failed: %s", system_name, e)
    return None, None


# Initialize DB on import
try:
    _init_db()
except Exception as e:
    log.warning("system_knowledge: DB init failed: %s", e)


def record_sighting(
    system_name: str,
    entry_type: str,
    value: str,
    source: str,
    reported_by: str | None = None,
    env: str | None = None,
) -> None:
    """UPSERT a single enemy or ore sighting for a system."""
    if not system_name or system_name.strip().lower() in _SKIP_NAMES:
        return
    if not value or not value.strip():
        return

    now = _now()
    value_key = _normalize(value)
    system_id, region = _resolve_system(system_name)

    try:
        with _get_conn(env=env) as conn:
            conn.execute(
                """
                INSERT INTO systems (system_name, system_id, region, visit_count, first_recorded, last_updated)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(system_name) DO UPDATE SET
                    visit_count  = visit_count + 1,
                    last_updated = excluded.last_updated,
                    system_id    = COALESCE(systems.system_id, excluded.system_id),
                    region       = COALESCE(systems.region, excluded.region)
                """,
                (system_name, system_id, region, now, now),
            )

            row = conn.execute(
                "SELECT id, sighting_count, sources FROM sightings "
                "WHERE system_name=? AND entry_type=? AND value_key=?",
                (system_name, entry_type, value_key),
            ).fetchone()

            if row:
                sources = json.loads(row["sources"])
                if source not in sources:
                    sources.append(source)
                conn.execute(
                    """
                    UPDATE sightings
                    SET sighting_count = sighting_count + 1,
                        last_seen      = ?,
                        sources        = ?
                    WHERE system_name=? AND entry_type=? AND value_key=?
                    """,
                    (now, json.dumps(sources), system_name, entry_type, value_key),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO sightings
                        (system_name, entry_type, value, value_key, sighting_count, first_seen, last_seen, sources)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (system_name, entry_type, value, value_key, now, now, json.dumps([source])),
                )
    except Exception as e:
        log.warning("system_knowledge.record_sighting failed: %s", e)


def record_from_upload(systems_dict: dict, reported_by: str | None = None, env: str | None = None) -> None:
    """Batch-record from log upload format: {system_name: {ores: {name: ...}, hostiles: {name: ...}}}."""
    # Use wallet-prefixed source key so distinct pilots accumulate in sources[]
    # len(sources) on any sighting row gives distinct reporter count
    source_key = f"pilot:{reported_by[:10]}" if reported_by else "log_upload"
    for system_name, data in (systems_dict or {}).items():
        if not system_name or system_name.strip().lower() in _SKIP_NAMES:
            continue
        for ore_name in (data.get("ores") or {}).keys():
            record_sighting(system_name, "ore", ore_name, source_key, reported_by, env=env)
        # hostiles is {name: {count, ...}} after schema migration
        hostiles = data.get("hostiles") or {}
        hostile_names = hostiles.keys() if isinstance(hostiles, dict) else hostiles
        for hostile_name in hostile_names:
            record_sighting(system_name, "enemy", hostile_name, source_key, reported_by, env=env)


def record_system_visit(system_name: str) -> None:
    """Increment visit_count only — no sighting. Used for killmail system activity."""
    if not system_name or system_name.strip().lower() in _SKIP_NAMES:
        return
    now = _now()
    system_id, region = _resolve_system(system_name)
    try:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO systems (system_name, system_id, region, visit_count, first_recorded, last_updated)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(system_name) DO UPDATE SET
                    visit_count  = visit_count + 1,
                    last_updated = excluded.last_updated,
                    system_id    = COALESCE(systems.system_id, excluded.system_id),
                    region       = COALESCE(systems.region, excluded.region)
                """,
                (system_name, system_id, region, now, now),
            )
    except Exception as e:
        log.warning("system_knowledge.record_system_visit failed: %s", e)


def query_system(system_name: str) -> dict:
    """Return full profile for a system, or {found: False} if not in DB."""
    try:
        with _get_conn() as conn:
            sys_row = conn.execute(
                "SELECT * FROM systems WHERE system_name=?", (system_name,)
            ).fetchone()
            if not sys_row:
                return {"found": False}

            enemies = [
                {**dict(r), "reporter_count": len(json.loads(r["sources"] or "[]"))}
                for r in conn.execute(
                    "SELECT value, sighting_count, first_seen, last_seen, sources FROM sightings "
                    "WHERE system_name=? AND entry_type='enemy' ORDER BY sighting_count DESC",
                    (system_name,),
                ).fetchall()
            ]
            ores = [
                {**dict(r), "reporter_count": len(json.loads(r["sources"] or "[]"))}
                for r in conn.execute(
                    "SELECT value, sighting_count, first_seen, last_seen, sources FROM sightings "
                    "WHERE system_name=? AND entry_type='ore' ORDER BY sighting_count DESC",
                    (system_name,),
                ).fetchall()
            ]

            return {
                "found": True,
                "system_name": sys_row["system_name"],
                "system_id": sys_row["system_id"],
                "region": sys_row["region"],
                "visit_count": sys_row["visit_count"],
                "first_recorded": sys_row["first_recorded"],
                "last_updated": sys_row["last_updated"],
                "enemies": enemies,
                "ores": ores,
            }
    except Exception as e:
        log.warning("system_knowledge.query_system failed: %s", e)
        return {"found": False}


def search_entity(value: str, entry_type: str | None = None) -> list[dict]:
    """Cross-system search by normalized value_key (LIKE). Returns up to 50 results."""
    value_key = _normalize(value)
    try:
        with _get_conn() as conn:
            if entry_type:
                rows = conn.execute(
                    "SELECT system_name, entry_type, value, sighting_count FROM sightings "
                    "WHERE value_key LIKE ? AND entry_type=? ORDER BY sighting_count DESC LIMIT 50",
                    (f"%{value_key}%", entry_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT system_name, entry_type, value, sighting_count FROM sightings "
                    "WHERE value_key LIKE ? ORDER BY sighting_count DESC LIMIT 50",
                    (f"%{value_key}%",),
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.warning("system_knowledge.search_entity failed: %s", e)
        return []


def get_stats() -> dict:
    """Return global knowledge graph statistics."""
    try:
        with _get_conn() as conn:
            systems_mapped = conn.execute("SELECT COUNT(*) FROM systems").fetchone()[0]
            total_sightings = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]

            top_enemies = [
                dict(r) for r in conn.execute(
                    "SELECT value, COUNT(DISTINCT system_name) AS system_count "
                    "FROM sightings WHERE entry_type='enemy' GROUP BY value_key "
                    "ORDER BY system_count DESC LIMIT 10"
                ).fetchall()
            ]
            top_ores = [
                dict(r) for r in conn.execute(
                    "SELECT value, COUNT(DISTINCT system_name) AS system_count "
                    "FROM sightings WHERE entry_type='ore' GROUP BY value_key "
                    "ORDER BY system_count DESC LIMIT 10"
                ).fetchall()
            ]

            return {
                "systems_mapped": systems_mapped,
                "total_sightings": total_sightings,
                "top_enemies": top_enemies,
                "top_ores": top_ores,
            }
    except Exception as e:
        log.warning("system_knowledge.get_stats failed: %s", e)
        return {"systems_mapped": 0, "total_sightings": 0, "top_enemies": [], "top_ores": []}
