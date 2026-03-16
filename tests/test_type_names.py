from src.type_names import get_type_name


def test_known_type_id_returns_name():
    # 78502 and 88561 confirmed present in type_names_all.json
    assert get_type_name(78502) == "Velocity CD82"
    assert get_type_name(88561) == "Thermal Composites"


def test_string_type_id_also_works():
    assert get_type_name("78502") == "Velocity CD82"


def test_unknown_type_id_returns_unknown():
    assert get_type_name(999999999) == "Unknown"


def test_none_returns_unknown():
    assert get_type_name(None) == "Unknown"
