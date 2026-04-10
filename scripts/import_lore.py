#!/usr/bin/env python3
"""Seed lore_store from data/lore_seed.json."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from src.lore_store import get_lore_store

seed_path = pathlib.Path(__file__).parent.parent / "data" / "lore_seed.json"
with open(seed_path) as f:
    entries = json.load(f)

store = get_lore_store()
count = store.seed_from_json(str(seed_path))
print(f"Imported {count} lore entries.")
