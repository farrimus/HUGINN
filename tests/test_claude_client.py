# tests/test_claude_client.py
from src.claude_client import ClaudeClient, SYSTEM_PROMPT

def test_system_prompt_contains_ship_computer_identity():
    assert "ship" in SYSTEM_PROMPT.lower() or "vessel" in SYSTEM_PROMPT.lower()
    assert "computer" in SYSTEM_PROMPT.lower() or "unit" in SYSTEM_PROMPT.lower()

def test_system_prompt_has_no_name():
    assert "my name is" not in SYSTEM_PROMPT.lower()
    assert "i am called" not in SYSTEM_PROMPT.lower()
    assert "i am known as" not in SYSTEM_PROMPT.lower()

def test_build_messages_includes_history():
    client = ClaudeClient(api_key="fake")
    history = [
        {"role": "user", "content": "where am i"},
        {"role": "assistant", "content": "Jita system."},
    ]
    messages = client.build_messages("hello", history, context_block="CURRENT SYSTEM: Jita")
    assert messages[0]["role"] == "user"
    assert len(messages) == 3  # 2 history + 1 new

def test_build_messages_sliding_window_cap():
    client = ClaudeClient(api_key="fake")
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
        for i in range(50)
    ]
    messages = client.build_messages("new", history, context_block="")
    assert len(messages) <= 41  # max 40 history + 1 new

def test_build_messages_context_prepended_to_user_message():
    client = ClaudeClient(api_key="fake")
    messages = client.build_messages("hello", [], context_block="CURRENT SYSTEM: Jita")
    assert "CURRENT SYSTEM: Jita" in messages[0]["content"]
    assert "hello" in messages[0]["content"]

def test_build_messages_no_context_uses_plain_message():
    client = ClaudeClient(api_key="fake")
    messages = client.build_messages("hello", [], context_block="")
    assert messages[0]["content"] == "hello"
