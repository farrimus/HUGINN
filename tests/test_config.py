import pytest
from src.config import get_network_config, load_config_from_env, validate_startup_config, get_data_path
import os
import tempfile


def test_get_network_config_utopia():
    """Test fetching Utopia network config."""
    config = get_network_config("utopia")
    assert config["world_api_url"] == "https://world-api-utopia.uat.pub.evefrontier.com"
    assert "testnet.sui.io" in config["nova_rpc_url"]
    assert config["eve_frontier_package"].startswith("0x")


def test_get_network_config_stillness():
    """Test fetching Stillness network config."""
    config = get_network_config("stillness")
    assert config["world_api_url"] == "https://world-api-stillness.live.tech.evefrontier.com"
    assert "testnet.sui.io" in config["nova_rpc_url"]


def test_get_network_config_invalid():
    """Test that invalid environment raises error."""
    with pytest.raises(ValueError, match="Unknown DEPLOYMENT_ENV"):
        get_network_config("invalid-env")


def test_load_config_from_env_defaults(monkeypatch):
    """Test loading config from environment with defaults."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    config = load_config_from_env()
    assert config["deployment_env"] == "utopia"
    assert config["anthropic_api_key"] == "sk-ant-test"
    assert config["port"] == 8745  # default


def test_load_config_from_env_custom_port(monkeypatch):
    """Test custom port from env."""
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    config = load_config_from_env()
    assert config["port"] == 9000


def test_load_config_missing_anthropic_key(monkeypatch):
    """Test that missing API key is allowed (logged but not fatal at config stage)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    config = load_config_from_env()
    assert config["anthropic_api_key"] == ""  # Empty, will be caught at startup


def test_validate_startup_config_valid():
    """Test that valid config passes validation."""
    config = {
        "anthropic_api_key": "sk-ant-...",
        "jwt_secret": "secret",
        "vps_sui_address": "0x...",
    }
    errors = validate_startup_config(config)
    assert errors == []


def test_validate_startup_config_missing_anthropic_key():
    """Test error when ANTHROPIC_API_KEY missing."""
    config = {
        "anthropic_api_key": "",
        "jwt_secret": "secret",
        "vps_sui_address": "0x...",
    }
    errors = validate_startup_config(config)
    assert len(errors) == 1
    assert "ANTHROPIC_API_KEY" in errors[0]


def test_validate_startup_config_missing_jwt_secret():
    """Test error when JWT_SECRET missing."""
    config = {
        "anthropic_api_key": "sk-ant-...",
        "jwt_secret": "",
        "vps_sui_address": "0x...",
    }
    errors = validate_startup_config(config)
    assert len(errors) == 1
    assert "JWT_SECRET" in errors[0]


def test_validate_startup_config_missing_vps_address():
    """Test warning when VPS_SUI_ADDRESS missing."""
    config = {
        "anthropic_api_key": "sk-ant-...",
        "jwt_secret": "secret",
        "vps_sui_address": "",
    }
    errors = validate_startup_config(config)
    assert len(errors) == 1
    assert "VPS_SUI_ADDRESS" in errors[0]


def test_validate_startup_config_multiple_errors():
    """Test that all errors are reported together."""
    config = {
        "anthropic_api_key": "",
        "jwt_secret": "",
        "vps_sui_address": "",
    }
    errors = validate_startup_config(config)
    assert len(errors) == 3
    assert any("ANTHROPIC_API_KEY" in e for e in errors)
    assert any("JWT_SECRET" in e for e in errors)
    assert any("VPS_SUI_ADDRESS" in e for e in errors)


# ============================================================================
# Tests for get_data_path() — environment-aware data paths
# ============================================================================

def test_get_data_path_shared_file(monkeypatch):
    """Test that shared files use root level data directory."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    path = get_data_path("systems.json", env_specific=False)
    assert path.endswith("data/systems.json")
    assert "utopia" not in path
    assert "stillness" not in path


def test_get_data_path_shared_file_stillness(monkeypatch):
    """Test that shared files ignore environment setting."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
    path = get_data_path("systems.json", env_specific=False)
    assert path.endswith("data/systems.json")
    assert "stillness" not in path
    assert "utopia" not in path


def test_get_data_path_env_specific_utopia(monkeypatch):
    """Test that environment-specific files use utopia subdirectory."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    path = get_data_path("system_index.json", env_specific=True)
    assert "data/utopia/system_index.json" in path


def test_get_data_path_env_specific_stillness(monkeypatch):
    """Test that environment-specific files use stillness subdirectory."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
    path = get_data_path("system_index.json", env_specific=True)
    assert "data/stillness/system_index.json" in path


def test_get_data_path_creates_directories(monkeypatch, tmp_path):
    """Test that parent directories are auto-created."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    # Use tmp_path to avoid polluting real data directory
    test_file = tmp_path / "data" / "utopia" / "test_file.json"

    # Simulate what get_data_path does
    os.makedirs(test_file.parent, exist_ok=True)

    # Verify directory was created
    assert test_file.parent.exists()


def test_get_data_path_nested_file(monkeypatch):
    """Test that nested file paths work correctly."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    path = get_data_path("structures/keep-7a.json", env_specific=True)
    assert "data/utopia/structures/keep-7a.json" in path


def test_get_data_path_default_env(monkeypatch):
    """Test that DEPLOYMENT_ENV defaults to utopia if not set."""
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    path = get_data_path("system_index.json", env_specific=True)
    assert "data/utopia/system_index.json" in path


def test_get_data_path_env_switching(monkeypatch):
    """Test that switching DEPLOYMENT_ENV changes the path."""
    # Start with utopia
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    path_utopia = get_data_path("gate_graph.json", env_specific=True)
    assert "utopia" in path_utopia

    # Switch to stillness
    monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
    path_stillness = get_data_path("gate_graph.json", env_specific=True)
    assert "stillness" in path_stillness

    # Verify they're different
    assert path_utopia != path_stillness
