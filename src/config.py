"""Network and deployment configuration.

Maps DEPLOYMENT_ENV to network-specific settings (RPC URL, World API URL, package IDs).
Loads secrets from environment variables.
"""

import os
import logging

log = logging.getLogger(__name__)


NETWORK_CONFIG = {
    "utopia": {
        "description": "EVE Frontier Utopia (test environment)",
        "world_api_url": "https://world-api-utopia.uat.pub.evefrontier.com",
        "nova_rpc_url": "https://fullnode.testnet.sui.io",
        "eve_frontier_package": "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
        "nova_registry_package": "0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9",
    },
    "stillness": {
        "description": "EVE Frontier Stillness (staging environment)",
        "world_api_url": "https://world-api-stillness.live.tech.evefrontier.com",
        "nova_rpc_url": "https://fullnode.testnet.sui.io",
        "eve_frontier_package": "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c",
        "nova_registry_package": "0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9",
    },
}


def get_network_config(env: str) -> dict:
    """Get configuration for deployment environment.

    Args:
        env: 'utopia', 'stillness', or 'mainnet'

    Returns:
        Dict with keys: world_api_url, nova_rpc_url, eve_frontier_package, nova_registry_package

    Raises:
        ValueError if env not in NETWORK_CONFIG
    """
    if env not in NETWORK_CONFIG:
        available = ", ".join(NETWORK_CONFIG.keys())
        raise ValueError(f"Unknown DEPLOYMENT_ENV: {env}. Choose: {available}")
    return NETWORK_CONFIG[env].copy()


def load_config_from_env() -> dict:
    """Load all configuration from environment variables.

    Returns:
        Dict with keys:
        - deployment_env: 'utopia'|'stillness'
        - anthropic_api_key: str
        - port: int
        - jwt_secret: str
        - token_key_password: str
        - server_token: str (legacy)
        - vps_sui_address: str
        - world_api_url, nova_rpc_url, eve_frontier_package, nova_registry_package (from network map)
    """
    deployment_env = os.getenv("DEPLOYMENT_ENV", "utopia")
    network = get_network_config(deployment_env)

    return {
        "deployment_env": deployment_env,
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "port": int(os.getenv("PORT", "8745")),
        "jwt_secret": os.getenv("JWT_SECRET", "change-me-in-production"),
        "token_key_password": os.getenv("TOKEN_KEY_PASSWORD", ""),
        "server_token": os.getenv("SERVER_TOKEN", ""),
        "vps_sui_address": os.getenv("VPS_SUI_ADDRESS", ""),
        # Network-derived:
        "world_api_url": network["world_api_url"],
        "nova_rpc_url": network["nova_rpc_url"],
        "eve_frontier_package": network["eve_frontier_package"],
        "nova_registry_package": network["nova_registry_package"],
    }


def validate_startup_config(config: dict) -> list[str]:
    """Validate required configuration at startup.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not config.get("anthropic_api_key"):
        errors.append("ANTHROPIC_API_KEY not set")
    if not config.get("jwt_secret"):
        errors.append("JWT_SECRET not set")
    if not config.get("vps_sui_address"):
        errors.append("VPS_SUI_ADDRESS not set (optional for dev, required for production)")

    return errors


def get_data_path(filename: str, env_specific: bool = False, env_override: str | None = None) -> str:
    """Get path to data file, respecting environment separation.

    Args:
        filename: Relative path within data directory (e.g., "systems.json" or "structures/keep-7a.json")
        env_specific: If True, path includes environment subdirectory (data/{env}/filename)
                      If False, path is at root level (data/filename)
        env_override: If set and env_specific=True, use this env instead of DEPLOYMENT_ENV.
                      Must be a validated value — callers are responsible for whitelisting.

    Returns:
        Absolute path to file. Parent directories are auto-created.
    """
    data_base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))

    if env_specific:
        env = env_override or os.getenv("DEPLOYMENT_ENV", "utopia")
        path = os.path.join(data_base, env, filename)
    else:
        path = os.path.join(data_base, filename)

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    return os.path.normpath(path)
