# log-agent/tests/test_parsers.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers import parse_gamelog_line, parse_chatlog_line

# ---------------------------------------------------------------------------
# Gamelog — combat
# ---------------------------------------------------------------------------

def test_combat_outgoing_damage():
    line = "[ 2025.08.28 21:08:29 ] (combat) <color=0xff00ffff><b>136</b> <color=0x77ffffff><font size=10>to</font> <b><color=0xffffffff>Bihepopths</b><font size=10><color=0x77ffffff> - Tier 3 Coilgun (S) - Grazes"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "combat_out"
    assert e["damage"] == 136
    assert e["target"] == "Bihepopths"
    assert e["weapon"] == "Tier 3 Coilgun (S)"
    assert e["hit"] == "Grazes"

def test_combat_incoming_damage():
    line = "[ 2025.08.28 21:08:29 ] (combat) <color=0xffcc0000><b>22</b> <color=0x77ffffff><font size=10>from</font> <b><color=0xffffffff>Bihepopths</b><font size=10><color=0x77ffffff> - Penetrates"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "combat_in"
    assert e["damage"] == 22
    assert e["source"] == "Bihepopths"
    assert e["hit"] == "Penetrates"

def test_combat_miss_incoming():
    line = "[ 2025.08.28 21:08:34 ] (combat) Bihepopths misses you completely"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "combat_miss"
    assert e["direction"] == "incoming"
    assert e["source"] == "Bihepopths"

def test_combat_miss_outgoing():
    line = "[ 2026.03.11 14:00:00 ] (combat) Your Base Autocannon (S) misses Faulty Scout Drone completely - Base Autocannon (S)"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "combat_miss"
    assert e["direction"] == "outgoing"
    assert e["weapon"] == "Base Autocannon (S)"
    assert "Faulty Scout Drone" in e["target"]

def test_sightline_blocked():
    line = "[ 2026.03.11 14:00:00 ] (combat) Sightline of Faulty Scout Drone  to you is obscured"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "sightline_blocked"
    assert "Faulty Scout Drone" in e["source"]

def test_combat_hit_qualities():
    for hit in ["Grazes", "Hits", "Glances Off", "Smashes", "Penetrates"]:
        line = f"[ 2026.03.11 14:00:00 ] (combat) 100 to Target - Base Autocannon (S) - {hit}"
        e = parse_gamelog_line(line)
        assert e is not None
        assert e["hit"] == hit

# ---------------------------------------------------------------------------
# Gamelog — mining
# ---------------------------------------------------------------------------

def test_mining_with_tags():
    line = "[ 2026.03.11 19:13:52 ] (mining) <color=0x77ffffff>You mined <font size=12><color=0xffaaaa00>3<color=0x77ffffff><font size=10> units of <color=0xffffffff><font size=12>Feldspar Crystals<color=0x77ffffff><font size=10>"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "mining"
    assert e["quantity"] == 3
    assert e["material"] == "Feldspar Crystals"

def test_mining_various_materials():
    for material in ["Carbonaceous Ore", "Hermetite", "Aestasium", "Iridosmine Nodules"]:
        line = f"[ 2026.03.11 14:00:00 ] (mining) You mined 50 units of {material}"
        e = parse_gamelog_line(line)
        assert e is not None
        assert e["material"] == material
        assert e["quantity"] == 50

# ---------------------------------------------------------------------------
# Gamelog — notify
# ---------------------------------------------------------------------------

def test_autopilot_engaged():
    line = "[ 2026.03.11 14:00:00 ] (notify) Autopilot engaged"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "autopilot"
    assert e["state"] == "engaged"

def test_autopilot_disabled():
    line = "[ 2026.03.11 14:00:00 ] (notify) Autopilot disabled"
    e = parse_gamelog_line(line)
    assert e["state"] == "disabled"

def test_docking_requested():
    line = "[ 2026.03.11 14:00:00 ] (notify) Requested to dock at Ersetu II - Keep #37 station"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "docking"
    assert e["state"] == "requested"
    assert e["location"] == "Ersetu II - Keep #37"

def test_docking_accepted():
    line = "[ 2026.03.11 14:00:00 ] (notify) Your docking request has been accepted. Your ship will be towed into station."
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "docking"
    assert e["state"] == "accepted"

def test_cargo_full():
    line = "[ 2026.03.11 19:13:52 ] (notify) Your Small Cutting Laser has completed operations. Ship's cargo hold is full."
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "cargo_full"
    assert e["module"] == "Your Small Cutting Laser"

def test_ship_stopping():
    line = "[ 2025.08.28 21:16:02 ] (notify) Ship stopping"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "ship_stopping"

def test_notify_noise_discarded():
    for text in [
        "Speed changed to 924 m/s",
        "Common Ore is too far away to use your Asteroid Mining Laser II on, it needs to be closer than 15,000 meters.",
        "Cargo is too far away. Ship is on automatic approach to cargo.",
        "Docking operation already in progress.Estimated time left: 10 seconds.",
    ]:
        line = f"[ 2026.03.11 14:00:00 ] (notify) {text}"
        assert parse_gamelog_line(line) is None

# ---------------------------------------------------------------------------
# Gamelog — discarded types
# ---------------------------------------------------------------------------

def test_info_discarded():
    line = "[ 2026.03.11 14:00:00 ] (info) The cluster is not currently accepting connections"
    assert parse_gamelog_line(line) is None

def test_hint_discarded():
    line = "[ 2026.03.11 14:00:00 ] (hint) Base Coilgun (S) is already active"
    assert parse_gamelog_line(line) is None

def test_question_discarded():
    line = "[ 2026.03.11 14:00:00 ] (question) Are you sure you want to quit the game?"
    assert parse_gamelog_line(line) is None

def test_warning_discarded():
    line = "[ 2026.03.11 14:00:00 ] (warning) You are about to throw away 1 x Crawler. Are you absolutely sure you want to do this?"
    assert parse_gamelog_line(line) is None

# ---------------------------------------------------------------------------
# Gamelog — untagged undock lines
# ---------------------------------------------------------------------------

def test_undock_extracts_system():
    line = "[ 2026.03.11 14:00:00 ] Undocking from Ersetu II - Keep #37 to Ersetu solar system."
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "undock"
    assert e["system"] == "Ersetu"
    assert e["station"] == "Ersetu II - Keep #37"

def test_undock_alphanumeric_system():
    line = "[ 2026.03.11 14:00:00 ] Undocking from I.59R.8J2 II - Keep to I.59R.8J2 solar system."
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["system"] == "I.59R.8J2"

# ---------------------------------------------------------------------------
# Gamelog — unrecognised lines preserved as gamelog_raw
# ---------------------------------------------------------------------------

def test_unrecognised_notify_preserved():
    line = "[ 2026.03.11 14:00:00 ] (notify) You're halfway onboard already. Please wait."
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "gamelog_raw"
    assert e["msg_type"] == "notify"
    assert "halfway" in e["text"]

def test_blank_line_returns_none():
    assert parse_gamelog_line("") is None
    assert parse_gamelog_line("   ") is None

# ---------------------------------------------------------------------------
# Chatlog
# ---------------------------------------------------------------------------

def test_system_change_from_local():
    line = "[ 2026.02.16 22:23:37 ] Keeper > Channel changed to Local : UTR-SN4"
    e = parse_chatlog_line(line)
    assert e is not None
    assert e["type"] == "system_change"
    assert e["system"] == "UTR-SN4"
    assert e["sender"] == "Keeper"

def test_system_change_alphanumeric():
    line = "[ 2026.03.11 14:00:00 ] Keeper > Channel changed to Local : I.59R.8J2"
    e = parse_chatlog_line(line)
    assert e["system"] == "I.59R.8J2"

def test_chat_message_captured():
    line = "[ 2026.03.11 14:00:00 ] zaroot > o7"
    e = parse_chatlog_line(line)
    assert e is not None
    assert e["type"] == "chat"
    assert e["sender"] == "zaroot"
    assert e["message"] == "o7"

def test_chat_non_matching_line_returns_none():
    assert parse_chatlog_line("") is None
    assert parse_chatlog_line("[ 2026.03.11 14:00:00 ] no arrow here") is None

# ---------------------------------------------------------------------------
# Gamelog — fallthrough / gamelog_raw edge cases
# ---------------------------------------------------------------------------

def test_untagged_non_undock_returns_none():
    # Untagged lines that aren't undock notifications are silently dropped
    line = "[ 2026.03.11 14:00:00 ] Some untagged system message"
    assert parse_gamelog_line(line) is None

def test_unrecognised_combat_preserved():
    line = "[ 2026.03.11 14:00:00 ] (combat) Some new combat message we don't recognise yet"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "gamelog_raw"
    assert e["msg_type"] == "combat"
    assert "new combat message" in e["text"]

def test_unrecognised_mining_preserved():
    line = "[ 2026.03.11 14:00:00 ] (mining) Some new mining message we don't recognise yet"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "gamelog_raw"
    assert e["msg_type"] == "mining"
    assert "new mining message" in e["text"]

def test_unknown_msg_type_preserved():
    # A future or unknown type should come through as gamelog_raw with its msg_type
    line = "[ 2026.03.11 14:00:00 ] (loot) You looted 1x Tritanium"
    e = parse_gamelog_line(line)
    assert e is not None
    assert e["type"] == "gamelog_raw"
    assert e["msg_type"] == "loot"
    assert "Tritanium" in e["text"]
