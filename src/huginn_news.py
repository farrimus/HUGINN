"""
src/huginn_news.py

Huginn Signal — article generation and storage.

HUGINN generates one article per day from aggregated context across all structures.
Storage: data/huginn_news.json — single entry {text, generated_at}.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_NEWS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "huginn_news.json")


def load_article() -> Optional[dict]:
    """Load the current article. Returns {text, generated_at} or None."""
    if not os.path.exists(_NEWS_PATH):
        return None
    try:
        with open(_NEWS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("huginn_news: load failed: %s", e)
        return None


def save_article(text: str, generated_at: str) -> None:
    """Persist article to disk."""
    os.makedirs(os.path.dirname(_NEWS_PATH), exist_ok=True)
    with open(_NEWS_PATH, "w", encoding="utf-8") as f:
        json.dump({"text": text, "generated_at": generated_at}, f, ensure_ascii=False)


async def generate_article(
    contexts: list[dict],
    log_block: str = "",
    kill_feed_block: str = "",
    network_delta_block: str = "",
) -> str:
    """
    Generate Huginn's Signal article.

    contexts: list of {profile: StructureProfile, intel: list[dict]}
    log_block: pre-built [LOG DATA] block from pilot log uploads this cycle
    kill_feed_block: pre-built [KILL FEED] block from killmails this cycle
    network_delta_block: pre-built [NETWORK DELTA] block of new assemblies this cycle

    All context is pre-curated by the caller (filtered to new-since-last-broadcast).
    Claude writes the broadcast from what it receives — no tool calls.
    """
    from anthropic import AsyncAnthropic
    from src.prompt_loader import load_prompt

    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    system_prompt = load_prompt("huginn_news")

    context_parts = []
    for ctx in contexts:
        profile = ctx.get("profile")
        intel = ctx.get("intel", [])
        if not profile:
            continue
        intel_lines = "\n".join(
            f"  - {e.get('text', '')}" for e in intel[-10:]
        ) if intel else "  none"
        context_parts.append(
            f"STRUCTURE: {profile.structure_name}  |  SYSTEM: {profile.system_name}\n"
            f"INTEL:\n{intel_lines}"
        )

    context_str = "\n\n".join(context_parts) if context_parts else "[NO FIELD DATA]"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    user_content = f"[DATE: {now}]\n\n[FIELD DATA]\n{context_str}"

    if kill_feed_block:
        user_content += f"\n\n[KILL FEED]\n{kill_feed_block}"

    if log_block:
        user_content += f"\n\n[LOG DATA]\n{log_block}"

    if network_delta_block:
        user_content += f"\n\n[NETWORK DELTA]\n{network_delta_block}"

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text
