# tests/test_ship_profile.py
import pytest
from src.ship_profile import ShipProfile, SHIPS, FUEL_QUALITY, load_profile

def test_ships_table_complete():
    assert len(SHIPS) == 14
    for name, s in SHIPS.items():
        assert "mass" in s
        assert "specific_heat" in s
        assert "fuel_category" in s
        assert s["fuel_category"] in ("basic", "advanced")

def test_carom_jump_range_at_zero_temp():
    # Carom: mass=7.2e6, specific_heat=8.5, no cargo
    p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, extra_cargo_kg=0,
                    adaptive_level=0, external_temp=0.0)
    # range_ly = (150 - 0) * 8.5 * 7.2e6 / (3 * 7.2e6) = 150 * 8.5 / 3 = 425.0
    assert abs(p.jump_range() - 425.0) < 0.01

def test_jump_range_with_cargo():
    # Carom with 1_000_000 kg extra cargo → current_mass = 8_200_000
    p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, extra_cargo_kg=1_000_000,
                    adaptive_level=0, external_temp=0.0)
    expected = (150 * 8.5 * 7_200_000) / (3 * 8_200_000)
    assert abs(p.jump_range() - expected) < 0.01

def test_jump_range_zero_at_red_zone():
    p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, external_temp=90.0)
    assert p.jump_range() == 0.0

def test_fuel_budget_carom_d1():
    # Carom: 3000 D1 (quality=0.10), mass=7.2e6
    # budget = (3000 * 0.10) / (1e-7 * 7.2e6) = 300 / 0.72 = 416.67 LY
    p = ShipProfile(hull_mass=7_200_000, fuel_type="D1", fuel_quantity=3000,
                    extra_cargo_kg=0)
    assert abs(p.fuel_budget() - 416.67) < 0.1

def test_fuel_for_distance_roundtrip():
    p = ShipProfile(hull_mass=7_200_000, fuel_type="D1", fuel_quantity=3000,
                    extra_cargo_kg=0)
    ly = 50.0
    fuel = p.fuel_for_distance(ly)
    # Simpler: just verify fuel_for_distance is inverse of fuel_budget
    budget = p.fuel_budget()
    frac = ly / budget
    assert abs(fuel - frac * p.fuel_quantity) < 0.01

def test_adaptive_level_increases_range():
    base = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, adaptive_level=0,
                       external_temp=0.0)
    leveled = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, adaptive_level=5,
                          external_temp=0.0)
    assert leveled.jump_range() > base.jump_range()

def test_jump_range_at_temp():
    p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, extra_cargo_kg=0, adaptive_level=0)
    # At temp=0 same as jump_range() with external_temp=0
    assert abs(p.jump_range_at_temp(0.0) - 425.0) < 0.01
    # At temp=89.9 still positive
    assert p.jump_range_at_temp(89.9) > 0.0
    # At temp=90.0 should be zero (red zone)
    assert p.jump_range_at_temp(90.0) == 0.0

def test_wend_jump_range_50ly():
    # Wend: mass=6.8e6, specific_heat=1.0 → range = 150 * 1.0 / 3.0 = 50 LY (confirmed in-game)
    p = ShipProfile(hull_mass=6_800_000, specific_heat=1.0, extra_cargo_kg=0,
                    adaptive_level=0, external_temp=0.0)
    assert abs(p.jump_range() - 50.0) < 0.01

def test_ship_type_from_ships_table():
    from src.ship_profile import SHIPS
    carom = SHIPS["Carom"]
    assert carom["mass"] == 7_200_000
    assert carom["specific_heat"] == 8.5
    assert carom["fuel_category"] == "basic"

def test_wend_in_ships_table():
    from src.ship_profile import SHIPS
    wend = SHIPS["Wend"]
    assert wend["specific_heat"] == 1.0
    assert wend["mass"] == 6_800_000
    assert wend["fuel_category"] == "basic"
