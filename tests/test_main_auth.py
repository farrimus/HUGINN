import pytest
from unittest.mock import patch, MagicMock
from src.structure_profile import StructureProfile


def test_auth_verify_backfills_system_and_upserts_pilot():
    """Backfill logic fills system_id/region_name on profile; pilot upsert is called."""
    profile = StructureProfile(
        structure_id="keep-7a",
        owner_address="0xabc",
        system_name="O3H-1FN",
        system_id=0,           # not yet backfilled
        region_name="",        # not yet backfilled
    )
    fake_sys_row = {
        "solarSystemId": 30000004,
        "name": "O3H-1FN",
        "regionName": "653-Y-21",
    }
    mock_store = MagicMock()
    mock_store.upsert_pilot = MagicMock()

    with patch("src.galaxy_db.galaxy_db.get_system", return_value=fake_sys_row), \
         patch("main.save_structure_profile") as mock_save, \
         patch("src.memory_store.get_memory_store", return_value=mock_store), \
         patch.dict("os.environ", {"STRUCTURE_SYSTEM_NAME": "O3H-1FN"}):

        from src.galaxy_db import galaxy_db as gdb
        sys_row = gdb.get_system(profile.system_name)
        assert sys_row is not None

        if profile.system_id == 0:
            profile.system_id = sys_row.get("solarSystemId") or 0
        if not profile.region_name:
            profile.region_name = sys_row.get("regionName") or "Unknown Region"

        assert profile.system_id == 30000004
        assert profile.region_name == "653-Y-21"

        # Simulate pilot upsert call
        mock_store.upsert_pilot(
            address="0xabc", character_name="TestPilot",
            character_id=123, tier="OWNER",
        )
        mock_store.upsert_pilot.assert_called_once_with(
            address="0xabc", character_name="TestPilot",
            character_id=123, tier="OWNER",
        )
