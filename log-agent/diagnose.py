"""
diagnose.py — one-shot diagnostic for chatlog encoding and parsing issues.

Run from the log-agent directory:
    python diagnose.py

Reads LOG_BASE_PATH from .env, finds the most recent Local_* chatlog,
and prints everything needed to understand why bootstrap is failing.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from parsers import parse_chatlog_line

CHATLOG_DIR = os.path.join(os.getenv("LOG_BASE_PATH", ""), "Chatlogs")

# --- Find Local_* files ---
print(f"\nChatlog directory: {CHATLOG_DIR}")
if not os.path.isdir(CHATLOG_DIR):
    print("ERROR: directory not found")
    sys.exit(1)

files = [
    os.path.join(CHATLOG_DIR, f)
    for f in os.listdir(CHATLOG_DIR)
    if f.startswith("Local_") and os.path.isfile(os.path.join(CHATLOG_DIR, f))
]
if not files:
    print("ERROR: no Local_* files found")
    sys.exit(1)

latest = max(files, key=os.path.getmtime)
print(f"Most recent Local_* file: {os.path.basename(latest)}")

# --- Raw bytes ---
with open(latest, "rb") as f:
    raw = f.read()

print(f"\nFile size: {len(raw)} bytes")
print(f"First 20 bytes (hex): {raw[:20].hex(' ')}")

# --- BOM detection ---
if raw.startswith(b"\xff\xfe"):
    print("Detected: UTF-16 LE (BOM ff fe)")
    text = raw[2:].decode("utf-16-le", errors="ignore")
elif raw.startswith(b"\xfe\xff"):
    print("Detected: UTF-16 BE (BOM fe ff)")
    text = raw[2:].decode("utf-16-be", errors="ignore")
elif raw.startswith(b"\xef\xbb\xbf"):
    print("Detected: UTF-8 with BOM (ef bb bf)")
    text = raw[3:].decode("utf-8", errors="ignore")
else:
    print("Detected: UTF-8 (no BOM)")
    text = raw.decode("utf-8", errors="ignore")

lines = text.splitlines()
print(f"Total lines decoded: {len(lines)}")

# --- First 10 lines ---
print("\n--- First 10 decoded lines ---")
for i, line in enumerate(lines[:10]):
    print(f"  [{i}] repr: {repr(line)}")

# --- Parse each line ---
print("\n--- parse_chatlog_line results (all lines) ---")
found = 0
for i, line in enumerate(lines):
    result = parse_chatlog_line(line)
    if result:
        print(f"  [{i}] {result}")
        if result.get("type") == "system_change":
            found += 1

if found == 0:
    print("  (no events parsed — parser returned None for every line)")

print(f"\nSummary: {found} system_change event(s) found")
