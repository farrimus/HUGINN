# src/log_analysis.py
#
# Cross-references gamelog events with chatlog system-change events to produce
# a location-annotated timeline, then compresses it into a Huginn-readable summary.

import bisect
import re
from collections import defaultdict
from typing import Optional

from src.log_parsers import parse_gamelog_line, parse_chatlog_line

# Minimum YYYYMMDD date string for files to be accepted.
LOG_DATE_CUTOFF = "20260311"

# Regex to extract YYYYMMDD from filenames like:
#   Local_20260315_123456_789.txt   → 20260315
#   20260315_123456.txt             → 20260315
_DATE_RE = re.compile(r'(?:^|[_/\\])(\d{8})(?:[_.]|$)')

# Timestamp in log lines: [ 2026.03.15 14:22:01 ]
# We compare these as plain strings (ISO-ish order preserved).
_TS_RE = re.compile(r'^\[\s*([\d.]+\s+[\d:]+)\s*\]')


def extract_date_tag(filename: str) -> Optional[str]:
    """Return the YYYYMMDD tag from a log filename, or None."""
    m = _DATE_RE.search(filename)
    if not m:
        return None
    return m.group(1)


# Keep private alias for internal use
_extract_date_tag = extract_date_tag


def filename_accepted(filename: str, last_processed_date: Optional[str] = None) -> bool:
    """
    Return True if the file should be processed.
    - date >= LOG_DATE_CUTOFF (global cutoff)
    - date > last_processed_date if provided (skip already-seen files)
    """
    tag = extract_date_tag(filename)
    if tag is None:
        return False
    if tag < LOG_DATE_CUTOFF:
        return False
    if last_processed_date and tag <= last_processed_date:
        return False
    return True


def channel_from_filename(filename: str) -> str:
    """
    Extract channel name from chatlog filename.
    Local_20260315_123_456.txt → "Local"
    Falls back to full stem if no underscore.
    """
    import os
    stem = os.path.splitext(os.path.basename(filename))[0]
    return stem.split("_")[0]


def detect_log_type(lines: list[str]) -> str:
    """
    Sniff whether this is a gamelog or chatlog from the first parseable line.
    Gamelogs: [ timestamp ] (word) message
    Chatlogs: [ timestamp ] SENDER > message
    Returns 'gamelog', 'chatlog', or 'unknown'.
    """
    _GAMELOG_TYPE_RE = re.compile(r'^\[\s*[\d.]+\s+[\d:]+\s*\]\s*\(\w+\)')
    _CHATLOG_SENDER_RE = re.compile(r'^\[\s*[\d.]+\s+[\d:]+\s*\]\s*.+?\s*>')
    for line in lines[:50]:
        line = line.strip().lstrip('\ufeff')
        if _GAMELOG_TYPE_RE.match(line):
            return 'gamelog'
        if _CHATLOG_SENDER_RE.match(line):
            return 'chatlog'
    return 'unknown'


def _ts_from_line(raw: str) -> Optional[str]:
    m = _TS_RE.match(raw.lstrip('\ufeff'))
    if not m:
        return None
    # Normalise "2026.03.15 14:22:01" → "2026-03-15 14:22:01" for clean sorting
    return m.group(1).replace(".", "-", 2)


def build_system_timeline(chatlog_events: list[dict]) -> tuple[list[str], list[str]]:
    """
    From parsed chatlog events, extract system_change entries and return two
    parallel lists (timestamps, system_names) sorted by timestamp.
    Only Local channel events are used (channel field == 'Local' or absent).
    """
    pairs: list[tuple[str, str]] = []
    for ev in chatlog_events:
        if ev.get("type") != "system_change":
            continue
        ts = ev.get("_ts")
        sys = ev.get("system")
        if ts and sys:
            pairs.append((ts, sys))
    pairs.sort(key=lambda x: x[0])
    if not pairs:
        return [], []
    timestamps, systems = zip(*pairs)
    return list(timestamps), list(systems)


def annotate_events(gamelog_events: list[dict], ts_list: list[str], sys_list: list[str]) -> list[dict]:
    """
    Attach a 'system' field to each gamelog event using the timeline.
    Uses bisect to find the most recent system_change before each event's timestamp.
    """
    if not ts_list:
        return gamelog_events
    for ev in gamelog_events:
        ts = ev.get("_ts")
        if ts is None:
            continue
        idx = bisect.bisect_right(ts_list, ts) - 1
        if idx >= 0:
            ev["system"] = sys_list[idx]
    return gamelog_events


def summarize_for_huginn(
    gamelog_events: list[dict],
    ts_list: list[str],
    sys_list: list[str],
    chat_events: list[dict],
) -> str:
    """
    Compress all events into a compact text block for Huginn's context window.
    """
    lines: list[str] = []

    # --- System visit sequence ---
    # Timestamps are used for gamelog annotation (already done); Claude only needs
    # the unique ordered list of systems the pilot passed through.
    if ts_list:
        unique_systems: list[str] = []
        prev = None
        for sys in sys_list:
            if sys != prev:
                unique_systems.append(sys)
                prev = sys
        lines.append(f"SYSTEMS VISITED: {', '.join(unique_systems)}")
    else:
        lines.append("SYSTEMS VISITED: (no Local chatlog data)")

    # --- Combat summary — hostiles per system ---
    combat_events = [e for e in gamelog_events if e.get("type") in ("combat_out", "combat_in", "sightline_blocked")]
    if combat_events:
        # Collect unique hostile names per system
        hostiles_by_sys: dict[str, set[str]] = defaultdict(set)
        for ev in combat_events:
            sys = ev.get("system", "unknown")
            name = ev.get("target") or ev.get("source")
            if name:
                hostiles_by_sys[sys].add(name)
        lines.append("\nHOSTILES ENCOUNTERED:")
        for sys, names in hostiles_by_sys.items():
            lines.append(f"  {sys}: {', '.join(sorted(names))}")

    # gamelog_raw, local chat, undocks, and docking events are intentionally excluded.
    # Both contain raw user-supplied or game-supplied text strings that could carry
    # prompt injection content. Only typed structured fields (damage numbers, material
    # names, system names from system_change events) reach Claude.

    return "\n".join(lines)


def decode_file(raw: bytes) -> tuple[str, str]:
    """
    BOM-sniff encoding and decode bytes to string.
    Returns (text, encoding_name).
    EVE chatlogs are UTF-16 LE; gamelogs are UTF-8.
    """
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="ignore"), "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="ignore"), "utf-16-be"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="ignore"), "utf-8-bom"
    return raw.decode("utf-8", errors="ignore"), "utf-8"


def parse_file(raw: bytes, filename: str) -> tuple[str, list[dict]]:
    """
    Decode, detect type, parse all lines. Returns (log_type, events).
    Events have a '_ts' field injected for timeline use.
    Capped at last 2000 lines.
    """
    text, _ = decode_file(raw)
    lines = text.splitlines()
    lines = lines[-2000:]  # cap

    log_type = detect_log_type(lines)
    parser = parse_gamelog_line if log_type == "gamelog" else parse_chatlog_line

    events = []
    for line in lines:
        ts = _ts_from_line(line)
        ev = parser(line)
        if ev is not None:
            if ts:
                ev["_ts"] = ts
            events.append(ev)

    return log_type, events
