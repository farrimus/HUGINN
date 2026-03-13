# log-agent/parsers.py
#
# Parses EVE Frontier client log lines into structured events.
# See docs/log-pipeline.md for full format reference and event shapes.
#
# Both parse_gamelog_line and parse_chatlog_line accept a raw line string
# and return a dict or None. None means the line is intentionally discarded.

import re
from typing import Optional

# --- Shared utilities --------------------------------------------------------

_TAG_RE = re.compile(r'<[^>]+>')

def _strip_tags(text: str) -> str:
    return _TAG_RE.sub('', text).strip()


# --- Gamelog -----------------------------------------------------------------
#
# Format: [ YYYY.MM.DD HH:MM:SS ] (type) <tags...>message
# Some lines have no (type) — these are untagged system messages.

_GAMELOG_LINE_RE = re.compile(
    r'^\[\s*[\d.]+\s+[\d:]+\s*\]\s*(?:\((\w+)\))?\s*(.*)',
    re.DOTALL
)

# Untagged lines
_UNDOCK_RE = re.compile(
    r'^Undocking from (.+?) to (.+?) solar system'
)

# (combat)
_COMBAT_OUT_RE  = re.compile(r'^(\d+)\s+to\s+(.+?)\s+-\s+(.+?)\s+-\s+(.+)$')
_COMBAT_IN_RE   = re.compile(r'^(\d+)\s+from\s+(.+?)\s+-\s+(.+)$')
_MISS_YOURS_RE  = re.compile(r'^Your (.+?) misses (.+?)\s+completely')
_MISS_THEIRS_RE = re.compile(r'^(.+?)\s+misses you completely')
_SIGHTLINE_RE   = re.compile(r'^Sightline of (.+?)\s+to you is obscured')

# (mining)
_MINING_RE = re.compile(r'^You mined (\d+) units of (.+)$')

# (notify) — only signals with situational value
_AUTOPILOT_RE    = re.compile(r'^Autopilot (engaged|disabled)$')
_DOCK_REQ_RE     = re.compile(r'^Requested to dock at (.+?) station$')
_DOCK_ACC_RE     = re.compile(r'^Your docking request has been accepted')
_CARGO_FULL_RE   = re.compile(r'^(.+?) has completed operations\. Ship.s cargo hold is full')
_SHIP_STOP_RE    = re.compile(r'^Ship stopping')

# (notify) lines that are high-volume noise — discard silently
_NOTIFY_NOISE_RE = re.compile(
    r'^Speed changed to|too far away|automatic approach|already in progress'
)

# (info)/(question)/(warning)/(hint) — always discarded
_DISCARD_TYPES = {'info', 'question', 'warning', 'hint'}


def parse_gamelog_line(raw: str) -> Optional[dict]:
    raw = raw.lstrip('\ufeff')
    m = _GAMELOG_LINE_RE.match(raw)
    if not m:
        return None

    msg_type = m.group(1)       # None if no (type) prefix
    text = _strip_tags(m.group(2))
    if not text:
        return None

    # --- Untagged lines ---
    if msg_type is None:
        u = _UNDOCK_RE.search(text)
        if u:
            return {
                "type": "undock",
                "station": u.group(1).strip(),
                "system": u.group(2).strip(),
            }
        return None

    # --- Discarded types ---
    if msg_type in _DISCARD_TYPES:
        return None

    # --- (combat) ---
    if msg_type == 'combat':
        c = _COMBAT_OUT_RE.match(text)
        if c:
            return {
                "type": "combat_out",
                "damage": int(c.group(1)),
                "target": c.group(2).strip(),
                "weapon": c.group(3).strip(),
                "hit":    c.group(4).strip(),
            }
        c = _COMBAT_IN_RE.match(text)
        if c:
            return {
                "type": "combat_in",
                "damage": int(c.group(1)),
                "source": c.group(2).strip(),
                "hit":    c.group(3).strip(),
            }
        c = _MISS_YOURS_RE.match(text)
        if c:
            return {
                "type":      "combat_miss",
                "direction": "outgoing",
                "weapon":    c.group(1).strip(),
                "target":    c.group(2).strip(),
            }
        c = _MISS_THEIRS_RE.match(text)
        if c:
            return {
                "type":      "combat_miss",
                "direction": "incoming",
                "source":    c.group(1).strip(),
            }
        c = _SIGHTLINE_RE.match(text)
        if c:
            return {"type": "sightline_blocked", "source": c.group(1).strip()}
        # Unrecognised combat line — preserve it
        return {"type": "gamelog_raw", "msg_type": "combat", "text": text}

    # --- (mining) ---
    if msg_type == 'mining':
        c = _MINING_RE.match(text)
        if c:
            return {
                "type":     "mining",
                "quantity": int(c.group(1)),
                "material": c.group(2).strip(),
            }
        return {"type": "gamelog_raw", "msg_type": "mining", "text": text}

    # --- (notify) ---
    if msg_type == 'notify':
        if _NOTIFY_NOISE_RE.search(text):
            return None
        c = _AUTOPILOT_RE.match(text)
        if c:
            return {"type": "autopilot", "state": c.group(1)}
        c = _DOCK_REQ_RE.match(text)
        if c:
            return {"type": "docking", "state": "requested", "location": c.group(1).strip()}
        if _DOCK_ACC_RE.match(text):
            return {"type": "docking", "state": "accepted"}
        c = _CARGO_FULL_RE.match(text)
        if c:
            return {"type": "cargo_full", "module": c.group(1).strip()}
        if _SHIP_STOP_RE.match(text):
            return {"type": "ship_stopping"}
        # Unrecognised notify — preserve it
        return {"type": "gamelog_raw", "msg_type": "notify", "text": text}

    # Any other msg_type not handled above
    return {"type": "gamelog_raw", "msg_type": msg_type, "text": text}


# --- Chatlog -----------------------------------------------------------------
#
# Format: [ YYYY.MM.DD HH:MM:SS ] SENDER > message
# No (type) prefix. No color tags.

_CHATLOG_LINE_RE = re.compile(
    r'^\[\s*[\d.]+\s+[\d:]+\s*\]\s*(.+?)\s*>\s*(.+)'
)

# System change: "Channel changed to Local : SYSTEM_NAME"
_SYSTEM_CHANGE_RE = re.compile(r'^Channel changed to Local\s*:\s*(.+)$')


def parse_chatlog_line(raw: str) -> Optional[dict]:
    raw = raw.lstrip('\ufeff')
    m = _CHATLOG_LINE_RE.match(raw)
    if not m:
        return None

    sender  = m.group(1).strip()
    message = m.group(2).strip()
    if not message:
        return None

    c = _SYSTEM_CHANGE_RE.match(message)
    if c:
        return {
            "type":   "system_change",
            "system": c.group(1).strip(),
            "sender": sender,           # stored for future-proofing
        }

    return {"type": "chat", "sender": sender, "message": message}
