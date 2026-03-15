# src/galaxy_db.py
import os
import sqlite3
import logging
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "eve_universe.db")
)


class GalaxyDB:
    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict(self, row) -> dict:
        return dict(row) if row else None

    def get_system(self, name_or_id) -> dict | None:
        """Return SolarSystems row joined with region/constellation names."""
        sql = """
            SELECT s.*,
                   r.name AS regionName,
                   c.name AS constellationName
            FROM SolarSystems s
            LEFT JOIN Regions r ON s.regionId = r.regionId
            LEFT JOIN Constellations c ON s.constellationId = c.constellationId
            WHERE {}
        """
        try:
            with self._connect() as conn:
                if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
                    row = conn.execute(
                        sql.format("s.solarSystemId = ?"), (int(name_or_id),)
                    ).fetchone()
                else:
                    row = conn.execute(
                        sql.format("LOWER(s.name) = LOWER(?)"), (str(name_or_id),)
                    ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_system(%r) failed: %s", name_or_id, e)
            return None

    def get_region(self, region_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Regions WHERE regionId = ?", (region_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_region(%r) failed: %s", region_id, e)
            return None

    def get_constellation(self, constellation_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Constellations WHERE constellationId = ?", (constellation_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_constellation(%r) failed: %s", constellation_id, e)
            return None

    def get_planet(self, planet_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Planets WHERE planetId = ?", (planet_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_planet(%r) failed: %s", planet_id, e)
            return None

    def get_moon(self, moon_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM Moons WHERE moonId = ?", (moon_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_moon(%r) failed: %s", moon_id, e)
            return None

    def get_station(self, station_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM NpcStations WHERE stationId = ?", (station_id,)
                ).fetchone()
                return self._row_to_dict(row)
        except Exception as e:
            log.warning("galaxy_db.get_station(%r) failed: %s", station_id, e)
            return None

    def get_celestials_in_system(self, system_id: int) -> dict:
        """Return {planets, moons, stations, lagrange_points} dicts."""
        try:
            with self._connect() as conn:
                planets = [dict(r) for r in conn.execute(
                    "SELECT * FROM Planets WHERE solarSystemId = ? ORDER BY celestialIndex",
                    (system_id,)
                ).fetchall()]
                moons = [dict(r) for r in conn.execute(
                    "SELECT * FROM Moons WHERE solarSystemId = ?", (system_id,)
                ).fetchall()]
                stations = [dict(r) for r in conn.execute(
                    "SELECT * FROM NpcStations WHERE solarSystemId = ?", (system_id,)
                ).fetchall()]
                lagrange = [dict(r) for r in conn.execute(
                    "SELECT * FROM LagrangePoints WHERE solarSystemId = ?", (system_id,)
                ).fetchall()]
                return {"planets": planets, "moons": moons, "stations": stations, "lagrange_points": lagrange}
        except Exception as e:
            log.warning("galaxy_db.get_celestials_in_system(%r) failed: %s", system_id, e)
            return {"planets": [], "moons": [], "stations": [], "lagrange_points": []}

    def search_systems(self, pattern: str) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM SolarSystems WHERE LOWER(name) LIKE LOWER(?) LIMIT 50",
                    (f"%{pattern}%",)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            log.warning("galaxy_db.search_systems(%r) failed: %s", pattern, e)
            return []

    def get_jumps_from_system(self, system_id: int) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM Jumps WHERE fromSystemId = ?", (system_id,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            log.warning("galaxy_db.get_jumps_from_system(%r) failed: %s", system_id, e)
            return []

    def run_sql(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            log.warning("galaxy_db.run_sql failed: %s", e)
            return []


# Module-level singleton
galaxy_db = GalaxyDB()
