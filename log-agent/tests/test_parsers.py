# log-agent/tests/test_parsers.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from parsers import parse_gamelog_line, parse_chatlog_line

def test_parse_combat_line():
    line = "[ 2026.03.11 14:23:01 ] (combat) 450 to Rogue Drone - Railgun II"
    event = parse_gamelog_line(line)
    assert event is not None
    assert event["type"] == "combat"
    assert event["damage"] == 450
    assert event["target"] == "Rogue Drone"

def test_parse_mining_line():
    line = "[ 2026.03.11 14:25:00 ] (mining) 150 units of Veldspar mined"
    event = parse_gamelog_line(line)
    assert event is not None
    assert event["type"] == "mining"

def test_unrecognised_line_returns_none():
    line = "[ 2026.03.11 14:00:00 ] (notify) Some irrelevant notification"
    event = parse_gamelog_line(line)
    assert event is None

def test_parse_system_change_from_local_chat():
    line = "[ 2026.03.11 14:30:00 ] Channel changed to Jita"
    event = parse_chatlog_line(line)
    assert event is not None
    assert event["type"] == "system_change"
    assert event["system"] == "Jita"

def test_parse_regular_chat_returns_none():
    line = "[ 2026.03.11 14:31:00 ] Pilot_Name > hello"
    event = parse_chatlog_line(line)
    assert event is None
