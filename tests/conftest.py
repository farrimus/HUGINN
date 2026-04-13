"""Shared pytest fixtures for the EVE Frontier test suite."""
import pytest
from src.structure_persistence import StructureProfile

# ---------------------------------------------------------------------------
# Common constants
# ---------------------------------------------------------------------------

# A valid 66-character Sui address used across tests.
VALID_SUI_ADDRESS = "0x" + "a" * 64

# A second valid address (for tests that need two distinct wallets).
VALID_SUI_ADDRESS_2 = "0x" + "b" * 64

# A slug-style assembly ID that passes _SAFE_ID_RE (alphanumeric + dash/underscore).
TEST_ASSEMBLY_SLUG = "test-ssu-01"


# ---------------------------------------------------------------------------
# Directory fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory mirroring the runtime layout.

    Creates:
      tmp_path/utopia/sessions/
      tmp_path/utopia/structures/
      tmp_path/utopia/memory/
      tmp_path/utopia/intel/
    """
    for subdir in ("sessions", "structures", "memory", "intel"):
        (tmp_path / "utopia" / subdir).mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Structure profile fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_structure_profile():
    """Factory fixture: returns a callable that builds a StructureProfile.

    Usage:
        def test_something(mock_structure_profile):
            p = mock_structure_profile()          # defaults
            p = mock_structure_profile(fuel_pct=50.0)  # override
    """
    def _factory(
        assembly_id=TEST_ASSEMBLY_SLUG,
        owner_address=VALID_SUI_ADDRESS,
        structure_name="Test Keep",
        fuel_pct=100.0,
        services_online=0,
        shield_pct=100.0,
        **kwargs,
    ):
        return StructureProfile(
            assembly_id=assembly_id,
            owner_address=owner_address,
            structure_name=structure_name,
            fuel_pct=fuel_pct,
            services_online=services_online,
            shield_pct=shield_pct,
            **kwargs,
        )
    return _factory
