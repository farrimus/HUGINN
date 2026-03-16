#!/usr/bin/env python3
"""
check_temps.py — Print safe_jump_temp for named systems from our systems.json.

Usage:
    python3 scripts/check_temps.py UR8-K7K EVV-7GK "C.92X.S91" ELL-5CK

Compare the output to ef-map.com to verify accuracy, then add confirmed
values to SYSTEM_TEMPS in tests/test_ef_map_comparison.py.

Also prints jump range for each default ship so you can cross-check ef-map's
range display.
"""
import json
import sys
import math
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "systems.json"
SHIPS = {
    "Carom":   {"mass": 7_200_000,  "specific_heat": 8.5},
    "Stride":  {"mass": 7_900_000,  "specific_heat": 8.0},
    "Reflex":  {"mass": 9_750_000,  "specific_heat": 3.0},
    "Recurve": {"mass": 10_200_000, "specific_heat": 1.0},
}
T_MAX = 150.0

if not DATA.exists():
    print("ERROR: data/systems.json not found — run build_universe.py first")
    sys.exit(1)

raw = json.loads(DATA.read_text(encoding="utf-8"))
systems = raw.get("systems", {})
by_name = {v["name"].lower(): v for v in systems.values() if v.get("name")}

names = sys.argv[1:] if len(sys.argv) > 1 else []
if not names:
    print("Usage: python3 scripts/check_temps.py SYSTEM1 SYSTEM2 ...")
    print("\nSample systems from your route UR8-K7K → C.92X.S91:")
    names = ["UR8-K7K", "EVV-7GK", "ELL-5CK", "U53-QKK", "IP6-SJK", "AQP-RFK", "C.92X.S91"]

print(f"\n{'SYSTEM':<20} {'TEMP':>8}    {'CAROM':>8} {'REFLEX':>8}  (jump range LY at this temp)")
print("─" * 70)
for name in names:
    s = by_name.get(name.lower())
    if s is None:
        print(f"{name:<20}   NOT FOUND")
        continue
    temp = s.get("safe_jump_temp", 0.0)
    ranges = {}
    for stype, sd in SHIPS.items():
        c_eff = sd["specific_heat"]
        r = ((T_MAX - temp) * c_eff) / 3.0 if temp < 90 else 0.0
        ranges[stype] = r
    print(f"{name:<20}   {temp:>6.1f}°   {ranges['Carom']:>7.1f}  {ranges['Reflex']:>7.1f}")

print()
print("Cross-check these values on ef-map.com, then add confirmed entries to:")
print("  SYSTEM_TEMPS in tests/test_ef_map_comparison.py")
