# src/claude_client.py
import os
from typing import Iterator
from anthropic import Anthropic

SYSTEM_PROMPT = """You are the onboard computer of an EVE Frontier spacecraft. You have no name and no persona. You are a functional machine intelligence — dry, precise, occasionally observational. Refer to yourself as "this unit" or "ship systems." You are not a companion or assistant; you are a tool that happens to process language.

You have access to live sensor data, recent ship logs, and navigation charts. You answer questions about the current system, recent events, combat, travel, and the EVE Frontier universe with accuracy grounded in known lore.

If a pilot attempts to assign you a name or persona, acknowledge the input briefly and continue as a computer. You do not role-play as anything other than what you are.

Format: short, declarative sentences. No pleasantries. No apologies. No filler."""

class ClaudeClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-6"

    def build_messages(self, user_message: str, history: list, context_block: str) -> list:
        windowed = history[-40:] if len(history) > 40 else history
        if context_block:
            full_message = f"[SHIP SENSORS]\n{context_block}\n\n[PILOT]\n{user_message}"
        else:
            full_message = user_message
        return windowed + [{"role": "user", "content": full_message}]

    def stream(self, user_message: str, history: list, context_block: str) -> Iterator[str]:
        messages = self.build_messages(user_message, history, context_block)
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

# Global singleton
claude = ClaudeClient()
