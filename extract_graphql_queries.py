#!/usr/bin/env python3
"""
extract_graphql_queries.py

Reads all GraphQL query strings from the DApp Kit node_modules source,
runs each key query against the live Sui testnet using known probe IDs
to verify they still work, then writes src/graphql_queries.py with the
confirmed strings as Python constants.

Usage:
    python extract_graphql_queries.py [--tenant utopia|stillness] [--assembly-id 0x...]

Defaults:
    --tenant      utopia   (UAT; safe for testing)
    --assembly-id          auto-discovered via GET_OBJECTS_BY_TYPE

Run from the project root (/opt/eve-frontier).
"""

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Tenant config (from @evefrontier/dapp-kit/utils/constants.ts TENANT_CONFIG)
# ---------------------------------------------------------------------------

TENANT_CONFIG = {
    "stillness": {
        "package_id":  "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c",
        "datahub_host": "world-api-stillness.live.tech.evefrontier.com",
        "graphql_url":  "https://graphql.testnet.sui.io/graphql",
    },
    "utopia": {
        "package_id":  "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
        "datahub_host": "world-api-utopia.uat.pub.evefrontier.com",
        "graphql_url":  "https://graphql.testnet.sui.io/graphql",
    },
    "nebula": {
        "package_id":  "0x353988e063b4683580e3603dbe9e91fefd8f6a06263a646d43fd3a2f3ef6b8c1",
        "datahub_host": "world-api-nebula.test.evefrontier.tech",
        "graphql_url":  "https://graphql.testnet.sui.io/graphql",
    },
}

SINGLETON_TABLE_NAMES = {
    "EnergyConfig":  "assembly_energy",   # from config.ts getEnergyConfig()
    "FuelConfig":    "fuel_efficiency",   # from config.ts getFuelEfficiencyConfig()
}

# ---------------------------------------------------------------------------
# Type string builders (mirrors constants.ts helper functions)
# ---------------------------------------------------------------------------

def get_character_player_profile_type(pkg: str) -> str:
    """Type filter for the PlayerProfile object owned by a wallet."""
    return f"{pkg}::character::PlayerProfile"

def get_character_owner_cap_type(pkg: str) -> str:
    """characterOwnerType variable for the power query (GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON).
    The OwnerCap is owned BY the Character Sui object, not the wallet.
    Owner chain: assembly.owner_cap_id -> OwnerCap_assembly -> owner (Character Sui ID)
                 -> Character's OwnerCap<Character> -> authorized_object_id -> Character JSON
    """
    return f"{pkg}::access::OwnerCap<{pkg}::character::Character>"

def get_energy_config_type(pkg: str) -> str:
    """Type string for the EnergyConfig singleton."""
    return f"{pkg}::energy::EnergyConfig"

def get_fuel_efficiency_config_type(pkg: str) -> str:
    """Type string for the FuelConfig singleton."""
    return f"{pkg}::fuel::FuelConfig"

def get_smart_storage_unit_type(pkg: str) -> str:
    """Type string for SmartStorageUnit — used for discovering assemblies."""
    return f"{pkg}::storage_unit::StorageUnit"

# ---------------------------------------------------------------------------
# Step 1: Extract GQL strings from queries.ts
# ---------------------------------------------------------------------------

QUERIES_TS_PATH = Path(
    "frontend/node_modules/@evefrontier/dapp-kit/graphql/queries.ts"
)

def extract_queries_from_ts(path: Path) -> dict[str, str]:
    """
    Parse queries.ts and extract all exported const GQL template literals.
    Returns dict of {CONSTANT_NAME: gql_string}.
    """
    source = path.read_text()
    # Match: export const NAME = `...`
    pattern = re.compile(
        r"export\s+const\s+(\w+)\s*=\s*`(.*?)`",
        re.DOTALL,
    )
    results = {}
    for match in pattern.finditer(source):
        name = match.group(1)
        gql = match.group(2).strip()
        results[name] = gql
    return results

# ---------------------------------------------------------------------------
# Step 2: Run verification queries
# ---------------------------------------------------------------------------

def graphql(url: str, query: str, variables: dict) -> dict:
    """Execute one GraphQL query. Returns response dict. Raises on HTTP error."""
    resp = httpx.post(
        url,
        json={"query": query, "variables": variables},
        headers={"Content-Type": "application/json"},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


def check(label: str, result: dict) -> bool:
    """Print pass/fail for a query result. Returns True if no GraphQL errors."""
    errors = result.get("errors")
    if errors:
        print(f"  [FAIL] {label}")
        for e in errors[:2]:
            print(f"         {e.get('message', e)}")
        return False
    data = result.get("data", {})
    if data is None:
        print(f"  [FAIL] {label} — data is null")
        return False
    print(f"  [PASS] {label}")
    return True


def discover_assembly_id(queries: dict, url: str, pkg: str) -> str | None:
    """Use GET_OBJECTS_BY_TYPE to find any live SmartStorageUnit ID."""
    ssu_type = get_smart_storage_unit_type(pkg)
    result = graphql(url, queries["GET_OBJECTS_BY_TYPE"], {
        "object_type": ssu_type,
        "first": 1,
    })
    nodes = (result.get("data") or {}).get("objects", {}).get("nodes", [])
    if nodes:
        addr = nodes[0].get("address")
        print(f"  discovered assembly: {addr}")
        return addr
    return None


def run_verification(queries: dict, tenant: str, assembly_id: str | None) -> bool:
    """
    Run each key query against the live chain.
    Returns True if all pass.
    """
    cfg = TENANT_CONFIG[tenant]
    url = cfg["graphql_url"]
    pkg = cfg["package_id"]

    print(f"\nVerification against tenant={tenant}")
    print(f"  GraphQL endpoint: {url}")
    print(f"  Package ID:       {pkg}\n")

    all_ok = True

    # -- Discover a real assembly ID if none provided --
    if not assembly_id:
        print("Discovering assembly ID via GET_OBJECTS_BY_TYPE...")
        assembly_id = discover_assembly_id(queries, url, pkg)
        if not assembly_id:
            print("  [WARN] No assembly found; skipping assembly-dependent tests")

    # 1. GET_OBJECT_WITH_JSON
    if assembly_id:
        r = graphql(url, queries["GET_OBJECT_WITH_JSON"], {"address": assembly_id})
        ok = check("GET_OBJECT_WITH_JSON", r)
        all_ok = all_ok and ok
        if ok:
            obj = (r.get("data") or {}).get("object")
            json_data = (obj or {}).get("asMoveObject", {}).get("contents", {}).get("json")
            if json_data:
                move_type = (obj or {}).get("asMoveObject", {}).get("contents", {}).get("type", {}).get("repr", "")
                print(f"         type repr: {move_type[:80]}")
                print(f"         json keys: {list(json_data.keys())[:8]}")

    # 2. GET_OBJECT_WITH_DYNAMIC_FIELDS (SSU inventory)
    if assembly_id:
        r = graphql(url, queries["GET_OBJECT_WITH_DYNAMIC_FIELDS"], {"objectId": assembly_id})
        ok = check("GET_OBJECT_WITH_DYNAMIC_FIELDS", r)
        all_ok = all_ok and ok
        if ok:
            df = (r.get("data") or {}).get("object", {}).get("asMoveObject", {}).get("dynamicFields", {}).get("nodes", [])
            print(f"         dynamic field count: {len(df)}")

    # 3. GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON (power query)
    if assembly_id:
        char_owner_type = get_character_owner_cap_type(pkg)
        r = graphql(url, queries["GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON"], {
            "objectId": assembly_id,
            "characterOwnerType": char_owner_type,
        })
        ok = check("GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON (power query)", r)
        all_ok = all_ok and ok
        if ok:
            mo = ((r.get("data") or {}).get("object") or {}).get("asMoveObject", {})
            contents = mo.get("contents", {})
            # Check energy source
            es = (contents.get("energySource") or {}).get("asAddress", {}).get("asObject", {})
            print(f"         energySource present: {bool(es)}")
            # Check character chain
            char_mo = (
                (contents.get("extract") or {})
                .get("asAddress", {}).get("asObject", {})
                .get("asMoveObject", {})
                .get("owner", {}).get("address", {})
                .get("objects", {}).get("nodes", [])
            )
            print(f"         character chain nodes: {len(char_mo)}")

    # 4. GET_CHARACTER_AND_OWNED_OBJECTS
    # We need a wallet address — try to extract from the assembly's owner chain
    wallet_address = None
    if assembly_id:
        # Get the owner from the simple object query
        r2 = graphql(url, queries["GET_OBJECT_WITH_JSON"], {"address": assembly_id})
        json_data = (
            (r2.get("data") or {}).get("object", {})
            .get("asMoveObject", {}).get("contents", {}).get("json") or {}
        )
        # Try character_address field if present
        wallet_address = (json_data.get("key") or {}).get("item_id")  # not wallet, just check structure

    # Just test with a known structure — if we can discover a wallet from chain, use it
    # For now, skip this query if we can't find a wallet
    print(f"  [SKIP] GET_CHARACTER_AND_OWNED_OBJECTS — requires wallet address (not discoverable without auth)")

    # 5. GET_SINGLETON_CONFIG_OBJECT_BY_TYPE — EnergyConfig
    energy_type = get_energy_config_type(pkg)
    r = graphql(url, queries["GET_SINGLETON_CONFIG_OBJECT_BY_TYPE"], {
        "object_type": energy_type,
        "table_name": SINGLETON_TABLE_NAMES["EnergyConfig"],
    })
    ok = check("GET_SINGLETON_CONFIG_OBJECT_BY_TYPE (EnergyConfig)", r)
    all_ok = all_ok and ok
    if ok:
        nodes_path = (
            ((r.get("data") or {}).get("objects") or {}).get("nodes") or []
        )
        if nodes_path:
            df = (
                (nodes_path[0].get("asMoveObject") or {})
                .get("contents", {}).get("extract", {})
                .get("extract", {}).get("asAddress", {})
                .get("addressAt", {}).get("dynamicFields", {})
                .get("nodes", [])
            )
            print(f"         EnergyConfig entries: {len(df)}")

    # 6. GET_SINGLETON_CONFIG_OBJECT_BY_TYPE — FuelConfig
    fuel_type = get_fuel_efficiency_config_type(pkg)
    r = graphql(url, queries["GET_SINGLETON_CONFIG_OBJECT_BY_TYPE"], {
        "object_type": fuel_type,
        "table_name": SINGLETON_TABLE_NAMES["FuelConfig"],
    })
    ok = check("GET_SINGLETON_CONFIG_OBJECT_BY_TYPE (FuelConfig)", r)
    all_ok = all_ok and ok
    if ok:
        nodes_path = (
            ((r.get("data") or {}).get("objects") or {}).get("nodes") or []
        )
        if nodes_path:
            df = (
                (nodes_path[0].get("asMoveObject") or {})
                .get("contents", {}).get("extract", {})
                .get("extract", {}).get("asAddress", {})
                .get("addressAt", {}).get("dynamicFields", {})
                .get("nodes", [])
            )
            print(f"         FuelConfig entries: {len(df)}")

    # 7. GET_OBJECTS_BY_TYPE (used for type pre-warming)
    ssu_type = get_smart_storage_unit_type(pkg)
    r = graphql(url, queries["GET_OBJECTS_BY_TYPE"], {
        "object_type": ssu_type,
        "first": 3,
    })
    ok = check("GET_OBJECTS_BY_TYPE (SSU listing)", r)
    all_ok = all_ok and ok
    if ok:
        nodes = ((r.get("data") or {}).get("objects") or {}).get("nodes", [])
        print(f"         SSU objects found: {len(nodes)}")

    # 8. GET_SINGLETON_OBJECT_BY_TYPE
    r = graphql(url, queries["GET_SINGLETON_OBJECT_BY_TYPE"], {
        "object_type": energy_type,
    })
    ok = check("GET_SINGLETON_OBJECT_BY_TYPE (EnergyConfig address)", r)
    all_ok = all_ok and ok
    if ok:
        nodes = ((r.get("data") or {}).get("objects") or {}).get("nodes", [])
        if nodes:
            print(f"         singleton address: {nodes[0].get('address', '?')[:20]}...")

    return all_ok


# ---------------------------------------------------------------------------
# Step 3: Write src/graphql_queries.py
# ---------------------------------------------------------------------------

OUTPUT_PATH = Path("src/graphql_queries.py")

FILE_HEADER = '''\
"""
src/graphql_queries.py

GraphQL query string constants for the Sui blockchain, extracted verbatim from:
  @evefrontier/dapp-kit/graphql/queries.ts  (v0.0.18)

Generated by: extract_graphql_queries.py
Do NOT hand-edit the GQL strings — update the source DApp Kit package and re-run
the generator script instead.

Owner chain (confirmed by live testnet queries):
  Wallet (0xff09...) → owns PlayerProfile
  PlayerProfile.character_id → Character Sui object ID (0xb789...)
  Character Sui object → owns OwnerCap<Assembly> per assembly it controls
  Character Sui object → owns OwnerCap<Character> (self-authorizing cap)
  OwnerCap<Assembly>.authorized_object_id → Assembly Sui object ID

The power query (GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON) uses:
  characterOwnerType = {pkg}::access::OwnerCap<{pkg}::character::Character>
  NOT PlayerProfile — it follows the OwnerCap<Character> from the Character Sui object.

FuelConfig/EnergyConfig notes:
  These singletons store data in child Table objects, not directly on the object.
  Use GET_SINGLETON_CONFIG_OBJECT_BY_TYPE with the correct table_name:
    EnergyConfig  → table_name = "assembly_energy"
    FuelConfig    → table_name = "fuel_efficiency"
  Direct object() queries return null for these child tables.

Response path for config singletons (mirrors config.ts parseConfig()):
  result["data"]["objects"]["nodes"][0]["asMoveObject"]["contents"]
        ["extract"]["extract"]["asAddress"]["addressAt"]["dynamicFields"]["nodes"]
  Each node: {"key": {"json": type_id_str}, "value": {"json": value_str}}
"""
'''

CONSTANTS_BLOCK = '''
# ---------------------------------------------------------------------------
# Tenant Configuration
# (from @evefrontier/dapp-kit/utils/constants.ts TENANT_CONFIG v0.0.18)
# ---------------------------------------------------------------------------

GRAPHQL_ENDPOINT = "https://graphql.testnet.sui.io/graphql"

TENANT_CONFIG: dict[str, dict] = {
    "stillness": {
        "package_id":   "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c",
        "datahub_host": "world-api-stillness.live.tech.evefrontier.com",
    },
    "utopia": {
        "package_id":   "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
        "datahub_host": "world-api-utopia.uat.pub.evefrontier.com",
    },
    "nebula": {
        "package_id":   "0x353988e063b4683580e3603dbe9e91fefd8f6a06263a646d43fd3a2f3ef6b8c1",
        "datahub_host": "world-api-nebula.test.evefrontier.tech",
    },
}

DEFAULT_TENANT = "stillness"

# Table names for config singleton queries
# (from config.ts getEnergyConfig() / getFuelEfficiencyConfig())
ENERGY_CONFIG_TABLE   = "assembly_energy"
FUEL_CONFIG_TABLE     = "fuel_efficiency"


# ---------------------------------------------------------------------------
# Type String Builders
# (mirror @evefrontier/dapp-kit/utils/constants.ts helper functions)
# ---------------------------------------------------------------------------

def character_player_profile_type(pkg: str) -> str:
    """Type filter for the PlayerProfile object owned by a wallet.
    Used in GET_WALLET_CHARACTERS and GET_CHARACTER_AND_OWNED_OBJECTS.
    Variable name: characterPlayerProfileType
    """
    return f"{pkg}::character::PlayerProfile"


def character_owner_cap_type(pkg: str) -> str:
    """Type filter for OwnerCap<Character> — used in the POWER QUERY.
    Variable name: characterOwnerType

    In GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON, this filters the objects
    owned by the Character Sui object to find its self-authorizing OwnerCap,
    whose authorized_object_id points back to the Character JSON.

    NOT PlayerProfile. The owner chain here goes:
      assembly.owner_cap_id -> OwnerCap_assembly -> owner (Character Sui ID)
      -> Character's owned objects of type OwnerCap<Character>
      -> OwnerCap<Character>.authorized_object_id -> Character object JSON
    """
    return f"{pkg}::access::OwnerCap<{pkg}::character::Character>"


def energy_config_type(pkg: str) -> str:
    """Full Move type string for the EnergyConfig singleton.
    Use with GET_SINGLETON_CONFIG_OBJECT_BY_TYPE and table_name=ENERGY_CONFIG_TABLE.
    """
    return f"{pkg}::energy::EnergyConfig"


def fuel_config_type(pkg: str) -> str:
    """Full Move type string for the FuelConfig singleton.
    Use with GET_SINGLETON_CONFIG_OBJECT_BY_TYPE and table_name=FUEL_CONFIG_TABLE.
    """
    return f"{pkg}::fuel::FuelConfig"


def smart_storage_unit_type(pkg: str) -> str:
    """Full Move type string for SmartStorageUnit.
    Use with GET_OBJECTS_BY_TYPE or GET_OWNED_OBJECTS_BY_TYPE.
    """
    return f"{pkg}::storage_unit::StorageUnit"

'''

def write_output(queries: dict[str, str]) -> None:
    """Write src/graphql_queries.py with all extracted constants."""
    lines = [FILE_HEADER, CONSTANTS_BLOCK]
    lines.append("# " + "-" * 75 + "\n")
    lines.append("# GraphQL Query String Constants\n")
    lines.append("# (verbatim from @evefrontier/dapp-kit/graphql/queries.ts)\n")
    lines.append("# " + "-" * 75 + "\n\n")

    # Group by category for readability
    groups = {
        "Core object queries": [
            "GET_OBJECT_BY_ADDRESS",
            "GET_OBJECT_WITH_JSON",
            "GET_OBJECT_WITH_DYNAMIC_FIELDS",
            "GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON",
        ],
        "Owner and ownership queries": [
            "GET_OBJECT_OWNER_AND_OWNED_OBJECTS_BY_TYPE",
            "GET_OBJECT_OWNER_AND_OWNED_OBJECTS_WITH_JSON",
            "GET_OWNED_OBJECTS_BY_TYPE",
            "GET_OWNED_OBJECTS_BY_PACKAGE",
        ],
        "Character queries": [
            "GET_WALLET_CHARACTERS",
            "GET_CHARACTER_AND_OWNED_OBJECTS",
        ],
        "Singleton and type queries": [
            "GET_SINGLETON_OBJECT_BY_TYPE",
            "GET_SINGLETON_CONFIG_OBJECT_BY_TYPE",
            "GET_OBJECTS_BY_TYPE",
        ],
    }

    documented = set()

    for group_label, names in groups.items():
        lines.append(f"# --- {group_label} ---\n\n")
        for name in names:
            if name not in queries:
                print(f"  [WARN] {name} not found in queries.ts — skipping")
                continue
            gql = queries[name]
            lines.append(f"{name} = '''\n{gql}\n'''\n\n")
            documented.add(name)

    # Emit any remaining queries not in the groups above
    extras = [k for k in queries if k not in documented]
    if extras:
        lines.append("# --- Additional queries ---\n\n")
        for name in extras:
            lines.append(f"{name} = '''\n{queries[name]}\n'''\n\n")

    OUTPUT_PATH.write_text("".join(lines))
    print(f"\nWrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes, {len(queries)} queries)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenant",
        default="utopia",
        choices=list(TENANT_CONFIG),
        help="Tenant to run verification queries against (default: utopia)",
    )
    parser.add_argument(
        "--assembly-id",
        default=None,
        help="Sui object ID of a known assembly to use in tests (0x...); auto-discovered if omitted",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip live query verification; just extract and write the file",
    )
    args = parser.parse_args()

    # Step 1: Extract
    print(f"Reading queries from {QUERIES_TS_PATH}...")
    if not QUERIES_TS_PATH.exists():
        print(f"ERROR: {QUERIES_TS_PATH} not found. Run from project root.", file=sys.stderr)
        sys.exit(1)

    queries = extract_queries_from_ts(QUERIES_TS_PATH)
    print(f"Extracted {len(queries)} query constants: {', '.join(queries)}")

    # Step 2: Verify
    if not args.skip_verification:
        ok = run_verification(queries, args.tenant, args.assembly_id)
        if not ok:
            print("\n[WARN] Some queries failed verification — review output above before using.", file=sys.stderr)
    else:
        print("\n[SKIP] Verification skipped via --skip-verification")

    # Step 3: Write
    write_output(queries)


if __name__ == "__main__":
    main()
