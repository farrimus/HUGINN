# log-agent/session_tracker.py
#
# Sits between parsers and the server. Absorbs raw combat/mining events,
# accumulates them into sessions, and emits summary events when sessions end.
#
# Pass-through events (system_change, docking, autopilot, chat, etc.) are
# returned immediately so the server always has real-time state.
#
# Sessions close on:
#   - system_change  (pilot jumped or undocked into a new system)
#   - docking        (pilot entered a station)
#   - inactivity timeout (checked lazily on each incoming event)
#   - explicit flush() call (shutdown)
#
# See docs/log-pipeline.md for full design rationale.

import time
import threading
from typing import Optional

COMBAT_TIMEOUT_S = 60    # seconds of no combat before session closes
MINING_TIMEOUT_S = 120   # seconds of no mining before session closes


class CombatSession:
    def __init__(self, system: Optional[str]):
        self.system = system
        self.start = time.time()
        self._last = time.monotonic()

        self.damage_out = 0
        self.damage_in  = 0
        self.enemies: dict[str, int] = {}   # name → hit/appear count
        self.hits_out:  dict[str, int] = {} # hit quality → count
        self.hits_in:   dict[str, int] = {} # hit quality → count
        self.weapons_used: set[str] = set()
        self.misses_out = 0
        self.misses_in  = 0

    def add(self, event: dict):
        t = event["type"]
        self._last = time.monotonic()

        if t == "combat_out":
            self.damage_out += event["damage"]
            self._count(self.enemies, event["target"])
            self._count(self.hits_out, event["hit"])
            self.weapons_used.add(event["weapon"])

        elif t == "combat_in":
            self.damage_in += event["damage"]
            self._count(self.enemies, event["source"])
            self._count(self.hits_in, event["hit"])

        elif t == "combat_miss":
            if event["direction"] == "outgoing":
                self.misses_out += 1
                self.enemies.setdefault(event.get("target", "unknown"), 0)
            else:
                self.misses_in += 1
                self.enemies.setdefault(event.get("source", "unknown"), 0)

        elif t == "sightline_blocked":
            self.enemies.setdefault(event.get("source", "unknown"), 0)

    @staticmethod
    def _count(d: dict, key: str):
        d[key] = d.get(key, 0) + 1

    def timed_out(self) -> bool:
        return (time.monotonic() - self._last) > COMBAT_TIMEOUT_S

    def to_summary(self) -> dict:
        return {
            "type":         "combat_summary",
            "system":       self.system,
            "duration_s":   int(time.time() - self.start),
            "enemies":      dict(self.enemies),
            "damage_out":   self.damage_out,
            "damage_in":    self.damage_in,
            "hits_out":     dict(self.hits_out),
            "hits_in":      dict(self.hits_in),
            "weapons_used": list(self.weapons_used),
            "misses_out":   self.misses_out,
            "misses_in":    self.misses_in,
        }


class MiningSession:
    def __init__(self, system: Optional[str]):
        self.system = system
        self.start = time.time()
        self._last = time.monotonic()

        self.materials: dict[str, int] = {}  # material → total units
        self.cargo_fulls = 0

    def add(self, event: dict):
        self._last = time.monotonic()
        t = event["type"]

        if t == "mining":
            mat = event["material"]
            self.materials[mat] = self.materials.get(mat, 0) + event["quantity"]

        elif t == "cargo_full":
            self.cargo_fulls += 1

    def timed_out(self) -> bool:
        return (time.monotonic() - self._last) > MINING_TIMEOUT_S

    def to_summary(self) -> dict:
        return {
            "type":        "mining_summary",
            "system":      self.system,
            "duration_s":  int(time.time() - self.start),
            "materials":   dict(self.materials),
            "total_units": sum(self.materials.values()),
            "cargo_fulls": self.cargo_fulls,
        }


# Event types that feed combat session
_COMBAT_EVENTS = {"combat_out", "combat_in", "combat_miss", "sightline_blocked"}

# Event types that feed mining session
_MINING_EVENTS = {"mining"}

# Events that close all open sessions (location transition)
_CLOSE_ALL = {"system_change", "docking"}


class SessionTracker:
    """
    Thread-safe. Both gamelog and chatlog handlers share one instance.
    """

    def __init__(self):
        self._lock    = threading.Lock()
        self._system: Optional[str] = None
        self._combat: Optional[CombatSession] = None
        self._mining: Optional[MiningSession] = None

    def process(self, event: dict) -> list[dict]:
        with self._lock:
            return self._process(event)

    def _process(self, event: dict) -> list[dict]:
        out = []
        t = event.get("type")

        # Lazily expire stale sessions before handling the new event
        out.extend(self._flush_stale())

        # --- Location transitions: close everything first ---
        if t in _CLOSE_ALL:
            out.extend(self._close_all())
            if t == "system_change":
                self._system = event.get("system")
            out.append(event)
            return out

        if t == "undock":
            # Undocking doesn't necessarily mean a new system —
            # use it to update system only if we don't already know it
            if not self._system:
                self._system = event.get("system")
            out.append(event)
            return out

        # --- Combat events: absorbed into session ---
        if t in _COMBAT_EVENTS:
            if self._combat is None:
                self._combat = CombatSession(self._system)
            self._combat.add(event)
            return out  # absorbed, not forwarded individually

        # --- Mining events: absorbed into session ---
        if t in _MINING_EVENTS:
            if self._mining is None:
                self._mining = MiningSession(self._system)
            self._mining.add(event)
            return out  # absorbed

        # --- cargo_full: feeds mining session AND passes through ---
        if t == "cargo_full":
            if self._mining is not None:
                self._mining.add(event)
            out.append(event)
            return out

        # --- Everything else passes through as-is ---
        # (autopilot, ship_stopping, chat, gamelog_raw, etc.)
        out.append(event)
        return out

    def _flush_stale(self) -> list[dict]:
        out = []
        if self._combat is not None and self._combat.timed_out():
            out.append(self._combat.to_summary())
            self._combat = None
        if self._mining is not None and self._mining.timed_out():
            out.append(self._mining.to_summary())
            self._mining = None
        return out

    def _close_all(self) -> list[dict]:
        out = []
        if self._combat is not None:
            out.append(self._combat.to_summary())
            self._combat = None
        if self._mining is not None:
            out.append(self._mining.to_summary())
            self._mining = None
        return out

    @property
    def current_system(self) -> Optional[str]:
        with self._lock:
            return self._system

    def snapshot(self) -> list[dict]:
        """Return snapshots of open sessions without closing them."""
        with self._lock:
            out = []
            if self._combat is not None:
                s = self._combat.to_summary()
                s["in_progress"] = True
                out.append(s)
            if self._mining is not None:
                s = self._mining.to_summary()
                s["in_progress"] = True
                out.append(s)
            return out

    def flush_stale(self) -> list[dict]:
        """Close and return any sessions that have timed out. Call periodically."""
        with self._lock:
            return self._flush_stale()

    def flush(self) -> list[dict]:
        """Force-close all open sessions. Call on shutdown."""
        with self._lock:
            return self._close_all()
