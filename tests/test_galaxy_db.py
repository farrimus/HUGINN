# tests/test_galaxy_db.py
import pytest
from src.galaxy_db import GalaxyDB

DB_PATH = "data/eve_universe.db"

# Known real IDs from eve_universe.db
REAL_SYSTEM_ID = 30000004
REAL_SYSTEM_NAME = "O3H-1FN"
REAL_REGION_NAME = "653-Y-21"
REAL_PLANET_ID = 40000005

@pytest.fixture
def db():
    return GalaxyDB(DB_PATH)

def test_get_system_by_name_returns_dict(db):
    result = db.get_system(REAL_SYSTEM_NAME)
    assert result is not None
    assert result["solarSystemId"] == REAL_SYSTEM_ID

def test_get_system_includes_region_name(db):
    result = db.get_system(REAL_SYSTEM_ID)
    assert result is not None
    assert result["regionName"] == REAL_REGION_NAME  # exact camelCase key from SQL alias

def test_get_system_not_found_returns_none(db):
    result = db.get_system("ZZZDOESNOTEXIST_XYZ_999")
    assert result is None

def test_get_system_case_insensitive(db):
    result = db.get_system(REAL_SYSTEM_NAME.lower())
    assert result is not None
    assert result["solarSystemId"] == REAL_SYSTEM_ID

def test_search_systems_returns_list(db):
    results = db.search_systems("O3H")
    assert isinstance(results, list)
    assert len(results) > 0
    # search_systems returns raw SolarSystems rows (no join)
    assert "solarSystemId" in results[0]

def test_search_systems_no_match_returns_empty(db):
    results = db.search_systems("XXXXXXNOEXIST")
    assert results == []

def test_get_celestials_in_system_structure(db):
    celestials = db.get_celestials_in_system(REAL_SYSTEM_ID)
    assert isinstance(celestials, dict)
    for key in ("planets", "moons", "stations", "lagrange_points"):
        assert key in celestials
        assert isinstance(celestials[key], list)

def test_get_celestials_planets_have_expected_columns(db):
    celestials = db.get_celestials_in_system(REAL_SYSTEM_ID)
    planets = celestials["planets"]
    assert len(planets) > 0
    # Verify key columns exist (from PROGRAMMER_GUIDE.md schema)
    p = planets[0]
    assert "planetId" in p
    assert "solarSystemId" in p

def test_get_jumps_from_system_returns_list(db):
    jumps = db.get_jumps_from_system(REAL_SYSTEM_ID)
    assert isinstance(jumps, list)
    # Real system should have at least one jump (or none — both are valid)

def test_run_sql_count(db):
    rows = db.run_sql("SELECT COUNT(*) as cnt FROM Regions")
    assert len(rows) == 1
    assert rows[0]["cnt"] > 0

def test_get_region_returns_dict(db):
    # Get region via system first
    result = db.get_system(REAL_SYSTEM_ID)
    region_id = result["regionId"]
    region = db.get_region(region_id)
    assert region is not None
    assert region["name"] == REAL_REGION_NAME

def test_get_region_not_found_returns_none(db):
    assert db.get_region(99999999) is None

def test_get_planet_returns_dict(db):
    planet = db.get_planet(REAL_PLANET_ID)
    assert planet is not None
    assert planet["planetId"] == REAL_PLANET_ID
    assert planet["solarSystemId"] == REAL_SYSTEM_ID

def test_get_planet_not_found_returns_none(db):
    assert db.get_planet(99999999) is None
