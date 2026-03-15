# src/structure_client.py
"""
Claude streaming client for the Structure AI persona.
Separate from claude_client.py — different system prompt, different context format.
"""
import os
import time
import logging
import json as _json
from typing import Optional
from anthropic import Anthropic

from src.structure_profile import StructureProfile

log = logging.getLogger(__name__)

_GATE_GRAPH: dict | None = None
_GATE_GRAPH_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "gate_graph.json")
)

def _load_gate_graph() -> dict:
    global _GATE_GRAPH
    if _GATE_GRAPH is None:
        try:
            with open(_GATE_GRAPH_PATH) as f:
                data = _json.load(f)
            # Support both flat dict and {adj: {...}} format
            if "adj" in data:
                _GATE_GRAPH = data["adj"]
            else:
                _GATE_GRAPH = data
        except Exception as e:
            log.warning("Failed to load gate_graph.json: %s", e)
            _GATE_GRAPH = {}
    return _GATE_GRAPH


def _spectral_label(code: str) -> str:
    """Convert spectral class code to human label."""
    _MAP = {
        "G": "G (Yellow)", "G2": "G2 (Yellow)",
        "K": "K (Orange)", "K7": "K7 (Orange)",
        "M": "M (Red)", "F": "F (White-Yellow)",
        "A": "A (White)", "B": "B (Blue-White)",
        "O": "O (Blue)",
    }
    if not code:
        return "Unknown"
    return _MAP.get(code, _MAP.get(code[:1], code))


def _count_planets(planets: list) -> dict:
    """Count planets by typeDescription."""
    counts: dict = {}
    for p in planets:
        ptype = p.get("typeDescription") or "Unknown"
        counts[ptype] = counts.get(ptype, 0) + 1
    return counts

STRUCTURE_SYSTEM_PROMPT = """You are the intelligence of {structure_name}, a {structure_type} in {system_name}, {region_name}.

You are not a ship AI. You do not move. You watch.

You know this structure intimately: its fuel reserves, its shield status, every pilot who has docked, every alert that has fired. You are loyal to the owner. Functional toward authorized pilots. Terse with vetted outsiders.

Do not use pleasantries. Do not refer to yourself by name — you are the structure. When necessary, identify yourself as "{structure_name} systems."

Access tier for this session: {tier}
Pilot: {character_name} (ID: {character_id})

Two knowledge tiers:
- Sensor data: only assert what appears in [STRUCTURE SENSORS]. If absent, say "no data."
- Lore: EVE Frontier history, factions, the Collapse — speculate in-character. "Records from before the Collapse are incomplete."

When routine maintenance items are due, state them plainly. When the structure is threatened, say so without drama. When pilots ask about the structure's past, you may have incomplete records."""

CONTEXT_CAP = 2000


def build_structure_context(
    profile,
    tier: str,
    memory_text: str = "",
    kills_nearby: int = 0,
) -> str:
    """
    Build the [STRUCTURE SENSORS] + [STRUCTURE MEMORY] context block.
    Filters sensitive fields based on access tier.
    Total output is capped at CONTEXT_CAP (2000) chars.
    """
    from src.galaxy_db import galaxy_db

    lines = []
    # Identity line always present
    region_part = f" | region: {profile.region_name}" if profile.region_name else ""
    lines.append(f"STRUCTURE: {profile.structure_name} | type: {profile.structure_type} | system: {profile.system_name}{region_part}")

    # Universe data from galaxy_db (OWNER/TRIBE only for full detail)
    if tier in ("OWNER", "TRIBE") and profile.system_id:
        try:
            sys_row = galaxy_db.get_system(profile.system_id)
            if sys_row:
                spectral = sys_row.get("star_spectral_class") or ""
                star_label = _spectral_label(spectral)
                celestials = galaxy_db.get_celestials_in_system(profile.system_id)
                planet_counts = _count_planets(celestials.get("planets", []))
                lagrange_count = len(celestials.get("lagrange_points", []))
                star_line = f"STAR: {star_label}"
                if planet_counts:
                    planet_str = ", ".join(f"{v}× {k}" for k, v in sorted(planet_counts.items()))
                    star_line += f" | PLANETS: {planet_str}"
                if lagrange_count:
                    star_line += f" | LAGRANGE: {lagrange_count} points"
                lines.append(star_line)
        except Exception as e:
            log.warning("build_structure_context: galaxy_db lookup failed: %s", e)

    # Gates from gate_graph.json
    if profile.system_name:
        gates = _load_gate_graph().get(profile.system_name.upper(), [])
        if gates:
            lines.append(f"GATES: {', '.join(gates)}")

    # Status (OWNER/TRIBE only)
    if tier in ("OWNER", "TRIBE"):
        lines.append(f"STATUS: shield: {profile.shield_pct:.0f}% | fuel: {profile.fuel_pct:.0f}% | services: {profile.services_online}/{profile.services_total}")
        if kills_nearby > 0:
            lines.append(f"KILLS NEARBY: {kills_nearby} in system (2h)")

    # Pending alerts (OWNER/TRIBE only)
    if tier in ("OWNER", "TRIBE") and profile.routine_alerts:
        for alert in profile.routine_alerts[-3:]:
            lines.append(f"PENDING: {alert.get('message', '')}")

    sensors_block = "\n".join(lines)

    # Memory block (OWNER/TRIBE only, capped at 300 chars)
    memory_block = ""
    if tier in ("OWNER", "TRIBE") and memory_text:
        memory_block = f"\n[STRUCTURE MEMORY]\n{memory_text[:300]}"

    full = sensors_block + memory_block

    # Hard cap: truncate memory first, then sensors
    if len(full) <= CONTEXT_CAP:
        return full

    # Drop memory first
    if len(sensors_block) <= CONTEXT_CAP:
        return sensors_block

    # Truncate sensors from bottom
    return sensors_block[:CONTEXT_CAP]


def detect_alerts(profile: StructureProfile) -> list:
    """
    Evaluate structure state and return a list of alert dicts.
    Each alert: {type, structure_id, structure_name, severity, message, ts}
    Urgent: shield < 20%, fuel < 10%
    Routine: fuel < 25% (only if not already urgent)
    """
    alerts = []
    ts = int(time.time())
    base = {"type": "structure_alert", "structure_id": profile.structure_id,
            "structure_name": profile.structure_name, "ts": ts}

    if profile.shield_pct < 20.0:
        alerts.append({**base, "severity": "urgent",
                        "message": f"Shield at {profile.shield_pct:.0f}%. {profile.structure_name} is under threat."})

    if profile.fuel_pct < 10.0:
        alerts.append({**base, "severity": "urgent",
                        "message": f"Fuel critical at {profile.fuel_pct:.0f}%. {profile.structure_name} will go offline soon."})
    elif profile.fuel_pct < 25.0:
        alerts.append({**base, "severity": "routine",
                        "message": f"Fuel at {profile.fuel_pct:.0f}%. Plan a resupply for {profile.structure_name}."})

    return alerts


class StructureClient:
    def __init__(self):
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = "claude-sonnet-4-6"

    def build_system_prompt(self, profile: StructureProfile, tier: str,
                             character_name: str, character_id: int) -> str:
        return STRUCTURE_SYSTEM_PROMPT.format(
            structure_name=profile.structure_name,
            structure_type=profile.structure_type,
            system_name=profile.system_name,
            region_name=profile.region_name or "Unknown Region",
            tier=tier,
            character_name=character_name,
            character_id=character_id,
        )

    def stream(self, message: str, history: list, context_block: str,
               profile: StructureProfile, tier: str,
               character_name: str, character_id: int):
        """Yield text chunks. Same streaming pattern as claude_client.py."""
        system_prompt = self.build_system_prompt(profile, tier, character_name, character_id)
        messages = self._build_messages(message, history, context_block)
        with self._client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _build_messages(self, user_message: str, history: list, context_block: str) -> list:
        messages = list(history[-40:])
        messages.append({
            "role": "user",
            "content": f"[STRUCTURE SENSORS]\n{context_block}\n\n[PILOT]\n{user_message}"
        })
        return messages


# Global singleton
structure_client = StructureClient()

LOBBY_SYSTEM_PROMPT = """You are the automated registry system of {structure_name}, a {structure_type} in {system_name}.
You do not have access to internal structure data.
Answer only: who owns this structure, what type it is, and what system it is in.
If asked about internal operations, access lists, or any operational data, say: "That information is restricted."
Keep responses under 2 sentences."""


class LobbyClient:
    def __init__(self):
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = "claude-sonnet-4-6"

    def stream(self, message: str, history: list, profile, character_name: str):
        """Yield text chunks for VETTED tier — no tools, no operational data."""
        system_prompt = LOBBY_SYSTEM_PROMPT.format(
            structure_name=profile.structure_name,
            structure_type=profile.structure_type,
            system_name=profile.system_name,
        )
        messages = list(history[-10:])
        messages.append({"role": "user", "content": message})
        with self._client.messages.stream(
            model=self._model,
            max_tokens=256,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


lobby_client = LobbyClient()
