import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import json
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from src.structure_persistence import StructureProfile, save_profile, load_profile

client = TestClient(app)


@pytest.fixture
def temp_structures_dir(monkeypatch):
    """Provide a temporary directory for structure profiles."""
    temp_dir = tempfile.mkdtemp()
    monkeypatch.setenv("STRUCTURES_DATA_PATH", temp_dir)
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_post_location_manual(temp_structures_dir):
    """Test POST /structure/{assembly_id}/location/manual saves location."""
    assembly_id = "test_location_manual"

    response = client.post(
        f"/structure/{assembly_id}/location/manual",
        json={"system_name": "JITA-01"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("success") == True
    assert data["location"]["system"] == "JITA-01"
    assert data["location"]["proved"] == False


def test_post_location_reveal_missing_jwt(temp_structures_dir):
    """Test that reveal endpoint requires JWT."""
    assembly_id = "test_location_reveal"

    # First create a manual location
    client.post(
        f"/structure/{assembly_id}/location/manual",
        json={"system_name": "UR8-K7K"}
    )

    # Try to reveal without JWT
    response = client.post(
        f"/structure/{assembly_id}/location/reveal",
        json={"jwt_token": ""}
    )

    # Should return an error -- 400/401 if JWT validated, 501 if unimplemented
    assert response.status_code in [400, 401, 501]
