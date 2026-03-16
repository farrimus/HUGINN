#!/usr/bin/env python3
"""
build_types.py — fetch /v2/types from World API → data/types.json

Usage:
    python build_types.py
    WORLD_API_ENV=utopia python build_types.py

Run once per game patch or when types change.
"""
import os, json, sys
import httpx
import subprocess

_URL_MAP = {
    "utopia":    "https://world-api-utopia.uat.pub.evefrontier.com",
    "stillness": "https://world-api-stillness.live.tech.evefrontier.com",
}
BASE_URL = os.environ.get("WORLD_API_BASE_URL") or _URL_MAP.get(
    os.environ.get("WORLD_API_ENV", "utopia"), _URL_MAP["utopia"]
)
OUT_PATH = os.path.join(os.path.dirname(__file__), "data", "types.json")


def fetch_all_types() -> list:
    all_types = []
    page = 1
    with httpx.Client(timeout=30.0) as client:
        while True:
            print(f"  Fetching page {page}...", end=" ", flush=True)
            try:
                r = client.get(f"{BASE_URL}/v2/types", params={"page": page})
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"FAILED: {e}")
                sys.exit(1)

            if isinstance(data, dict):
                items = data.get("data", [])
            else:
                items = data

            if not items:
                print("done (empty page)")
                break

            all_types.extend(items)
            print(f"{len(items)} types")
            page += 1

    return all_types


def main():
    print(f"Fetching types from {BASE_URL}...")
    types = fetch_all_types()
    print(f"Total: {len(types)} types")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(types, f, indent=2)
    print(f"Written to {OUT_PATH}")

    # Check if type_names_all.json is still imported anywhere
    proc = subprocess.run(
        ["grep", "-r", "type_names_all", "src/"],
        capture_output=True, text=True
    )
    result = proc.stdout.strip()
    if result:
        print(f"\nWARNING: type_names_all.json still imported:\n{result}")
        print("Do NOT rename it yet.")
    else:
        print("\ntype_names_all.json has no imports in src/. Safe to rename:")
        print("  mv data/type_names_all.json data/type_names_all.DEPRECATED.json")


if __name__ == "__main__":
    main()
