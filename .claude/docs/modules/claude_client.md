# claude_client

## When Should an Agent Use This Module?

Use **claude_client** when you need to stream responses from the Claude Ship AI persona. The module:
- Enforces a specific system prompt (ship computer, not assistant)
- Builds message history with context injection
- Streams text tokens via the Anthropic API

The Ship AI operates in a lore-grounded voice — report sensor data, never invent facts, speculate cautiously on lore, do not offer unsolicited advice.

## Public API

```python
class ClaudeClient:
    def __init__(self, api_key: str = None):
        """Initialize client; reads ANTHROPIC_API_KEY from env if not provided."""

    def build_messages(
        self, user_message: str, history: list, context_block: str
    ) -> list:
        """Assemble messages array with sliding window (max 40 prior messages)."""

    def stream(
        self, user_message: str, history: list, context_block: str
    ) -> Iterator[str]:
        """Stream response tokens from Claude Sonnet 4.6."""

# Global singleton
claude = ClaudeClient()
```

## Behavior

- **Model:** `claude-sonnet-4-6`
- **Max tokens:** 1024 per response
- **History window:** Last 40 messages (prevents context explosion)
- **Context injection:** Prepends `[SHIP SENSORS]\n{context_block}\n\n[PILOT]\n{user_message}`
- **System prompt:** Enforces ship computer persona — only report facts in sensors, speculate cautiously on lore

## Two-Tier Knowledge Model

The system prompt enforces a strict separation between two kinds of knowledge:

1. **SENSOR DATA** (ground truth) — Facts from [SHIP SENSORS] block: security ratings, kill counts, system names, combat summaries, gate links, planned routes. Only assert sensor facts if they appear in the block. Say plainly if data is absent. Never invent sensor data.

2. **LORE** (fragmentary by design) — History, factions, structures, the Collapse. Treat as incomplete records. Draw on known fragments and speculate in-character ("Records from before the Collapse are incomplete."). Avoid confident invention of lore facts.

## System Prompt Rules

The SYSTEM_PROMPT constant explicitly:
- Refuses to be named or assigned a persona — "you are a tool that happens to process language"
- Reports only what [SHIP SENSORS] block contains — never invents sensor facts
- Speculates cautiously on lore from known fragments — never claims to resolve deliberately open questions
- Formats routes as: `"Plotting course: N jumps. [list of systems]."`
- Offers no unsolicited strategic, route, or fitting advice
- Uses short, declarative sentences — no pleasantries, no apologies, no filler

## Implementation Notes

- History windowing (last 40) prevents context overflow without losing conversational state
- Context block injection wraps user message in `[PILOT]` tags to distinguish pilot speech from sensors
- Token limit of 1024 is deliberate — forces conciseness, prevents rambling
- Global singleton `claude` is initialized at module load time

## Integration Points

- **Input:** Called by `/chat` endpoint
- **Note:** Not used by Structure AI; `structure_client` is separate
- **Output:** Yields text tokens for SSE streaming to client
