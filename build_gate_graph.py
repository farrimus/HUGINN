#!/usr/bin/env python3
import json
import time
from pathlib import Path
import concurrent.futures
import requests
import os
import sys

BASE_URL = os.getenv("WORLD_API_BASE_URL", "https://world-api-stillness.live.tech.evefrontier.com")
INDEX_PATH = Path("data/system_index.json")
GRAPH_PATH = Path("data/gate_graph.json")

if not INDEX_PATH.exists():
    print("❌ system_index.json missing — run rebuild-index first")
    sys.exit(1)

index_data = json.loads(INDEX_PATH.read_text())
name_to_id = index_data["index"]
id_to_name = {str(v): k for k, v in name_to_id.items()}

print(f"✅ Loaded {len(id_to_name):,} systems. Starting concurrent gateLink fetch...")

def fetch_system(sys_id: str):
    url = f"{BASE_URL}/v2/solarsystems/{sys_id}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        s = r.json()
        
        name = s.get("name", "").lower()
        security = s.get("security", 0.0)
        location = s.get("location")
        
        gate_links = s.get("gateLinks") or []
        neighbors = []
        for link in gate_links:
            if isinstance(link, (int, str)):
                neigh_id = str(link)
            elif isinstance(link, dict):
                neigh_id = str(link.get("solarSystemId") or link.get("id", ""))
            else:
                continue
            if neigh_id in id_to_name:
                neighbors.append(id_to_name[neigh_id])
        
        return {
            "name": name,
            "id": int(sys_id),
            "security": security,
            "location": location,
            "gateLinks": neighbors
        }
    except Exception:
        return None

# Concurrent fetch
adj = {}
meta = {}
completed = 0
total = len(id_to_name)

with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
    future_to_id = {executor.submit(fetch_system, sid): sid for sid in id_to_name}
    
    for future in concurrent.futures.as_completed(future_to_id):
        result = future.result()
        completed += 1
        if completed % 2000 == 0:
            print(f"   Progress: {completed:,}/{total:,} systems processed")
        if result:
            name = result["name"]
            adj[name] = result["gateLinks"]
            meta[name] = {
                "id": result["id"],
                "security": result["security"],
                "location": result["location"]
            }

gate_graph = {
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "adj": adj,
    "meta": meta
}

GRAPH_PATH.write_text(json.dumps(gate_graph, indent=2))
print(f"✅ SUCCESS: gate_graph.json written")
print(f"   Systems with adjacency: {len(adj):,}")
print(f"   File size: {GRAPH_PATH.stat().st_size / 1024:.1f} KB")
