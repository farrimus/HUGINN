# log-agent/parsers.py
import re
from typing import Optional

# NOTE: These regex patterns are based on the expected log format.
# Verify against real EVE Frontier log files and adjust before deploying.

COMBAT_RE = re.compile(r'\(combat\)\s+(\d+)\s+to\s+(.+)\s+-\s+\w')
MINING_RE = re.compile(r'\(mining\)')
SYSTEM_CHANGE_RE = re.compile(r'Channel changed to (.+)')

def parse_gamelog_line(line: str) -> Optional[dict]:
    m = COMBAT_RE.search(line)
    if m:
        return {"type": "combat", "damage": int(m.group(1)), "target": m.group(2).strip()}
    if MINING_RE.search(line):
        return {"type": "mining", "raw": line.strip()}
    return None

def parse_chatlog_line(line: str) -> Optional[dict]:
    m = SYSTEM_CHANGE_RE.search(line)
    if m:
        return {"type": "system_change", "system": m.group(1).strip()}
    return None
